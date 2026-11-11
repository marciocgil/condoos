"""Payment allocation N:N (A3/A4, D123): one bank debit can pay several expenses (grouped
payment, a DARF covering several withholdings) and one expense can be paid by several debits.

Verified only by an objective rule: exactly one combination of open expenses of the same
payee (CNPJ of the line = supplier's CNPJ), or of the tax slips for a tax debit, sums to the
debit to the cent. Several combinations: every candidate becomes a suggestion, nothing is
chosen. The sums never exceed the line nor the expense (no double counting).
"""

import itertools
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.enums import EdgeKind
from app.db.models import BankTransaction, Condominium, Expense, PaymentAllocation, Supplier

ZERO = Decimal("0")
MAX_CANDIDATES = 14  # 2^14 combinations at most per debit
TAX_DEBIT = re.compile(
    r"darf|receita federal|\bgps\b|fgts|dctf|\biss\b|simples nacional|pagamento de tributo", re.I
)
METHOD_1_1 = "casamento:1:1"
METHOD_GROUP = "agrupado:mesmo_favorecido"
METHOD_TAX = "agrupado:guias"


def _subsets(expenses: list[Expense], target: Decimal) -> list[tuple[Expense, ...]]:
    found: list[tuple[Expense, ...]] = []
    for size in range(1, len(expenses) + 1):
        for combo in itertools.combinations(expenses, size):
            if sum((e.amount for e in combo), ZERO) == target:
                found.append(combo)
                if len(found) > 1:
                    return found
    return found


async def _existing(
    session: AsyncSession, condo_id: uuid.UUID
) -> tuple[dict[uuid.UUID, Decimal], dict[uuid.UUID, Decimal]]:
    per_line: dict[uuid.UUID, Decimal] = {}
    per_expense: dict[uuid.UUID, Decimal] = {}
    for a in await session.scalars(
        select(PaymentAllocation).where(
            PaymentAllocation.condominium_id == condo_id,
            PaymentAllocation.kind == EdgeKind.VERIFICADO.value,
        )
    ):
        per_line[a.bank_transaction_id] = per_line.get(a.bank_transaction_id, ZERO) + a.amount
        per_expense[a.expense_id] = per_expense.get(a.expense_id, ZERO) + a.amount
    return per_line, per_expense


async def _add(
    session: AsyncSession,
    condo_id: uuid.UUID,
    trn: BankTransaction,
    expense: Expense,
    amount: Decimal,
    kind: EdgeKind,
    method: str,
    reason: str,
) -> bool:
    exists = await session.scalar(
        select(PaymentAllocation).where(
            PaymentAllocation.bank_transaction_id == trn.id,
            PaymentAllocation.expense_id == expense.id,
        )
    )
    if exists is not None:
        if exists.kind == EdgeKind.SUGERIDO.value and kind == EdgeKind.VERIFICADO:
            exists.kind, exists.method, exists.reason = kind.value, method, reason
            return True
        return False
    session.add(
        PaymentAllocation(
            condominium_id=condo_id,
            bank_transaction_id=trn.id,
            expense_id=expense.id,
            amount=amount,
            kind=kind.value,
            method=method,
            reason=reason[:300],
        )
    )
    return True


async def allocate(session: AsyncSession, condo: Condominium, competence: date) -> dict[str, int]:
    first, last = competence, add_months(competence, 1) - timedelta(days=1)
    per_line, per_expense = await _existing(session, condo.id)
    lines = list(
        await session.scalars(
            select(BankTransaction).where(
                BankTransaction.condominium_id == condo.id,
                BankTransaction.posted_at.between(first, last),
                BankTransaction.amount < 0,
                BankTransaction.origin != "cnab",
            )
        )
    )
    window = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condo.id,
                Expense.competence.between(add_months(first, -2), first),
            )
        )
    )
    suppliers = {
        s.id: s.cnpj
        for s in await session.scalars(
            select(Supplier).where(
                Supplier.id.in_([e.supplier_id for e in window if e.supplier_id] or [uuid.uuid4()])
            )
        )
    }
    out = {"verificadas": 0, "sugeridas": 0}
    # 1. The existing 1:1 matches become verified allocations.
    by_id = {e.id: e for e in window}
    for trn in lines:
        if trn.expense_id is not None and trn.id not in per_line:
            exp = by_id.get(trn.expense_id) or await session.get(Expense, trn.expense_id)
            if exp is None:
                continue
            amount = min(-trn.amount, exp.amount - per_expense.get(exp.id, ZERO))
            if amount > 0 and await _add(
                session,
                condo.id,
                trn,
                exp,
                amount,
                EdgeKind.VERIFICADO,
                METHOD_1_1,
                "Débito casado com a despesa (valor, data e favorecido).",
            ):
                per_line[trn.id] = per_line.get(trn.id, ZERO) + amount
                per_expense[exp.id] = per_expense.get(exp.id, ZERO) + amount
                out["verificadas"] += 1
    # 2. Grouped payments for debits nobody matched.
    for trn in lines:
        if trn.expense_id is not None or per_line.get(trn.id, ZERO) >= -trn.amount:
            continue
        target = -trn.amount - per_line.get(trn.id, ZERO)
        open_ = [
            e
            for e in window
            if per_expense.get(e.id, ZERO) == ZERO and e.issue_date <= trn.posted_at
        ]
        if trn.payee_document:
            pool = [
                e
                for e in open_
                if e.supplier_id and suppliers.get(e.supplier_id) == trn.payee_document
            ]
            method, why = (
                METHOD_GROUP,
                "Pagamento agrupado: a soma exata das despesas do mesmo favorecido (CNPJ).",
            )
        elif TAX_DEBIT.search(f"{trn.description} {trn.payee_name or ''}"):
            pool = [e for e in open_ if e.category == "tributos"]
            method, why = (
                METHOD_TAX,
                "Tributo pago em uma guia que soma exatamente as guias abertas.",
            )
        else:
            continue
        pool = sorted(pool, key=lambda e: (e.issue_date, str(e.id)))[:MAX_CANDIDATES]
        combos = _subsets(pool, target)
        if len(combos) == 1:
            for exp in combos[0]:
                if await _add(
                    session, condo.id, trn, exp, exp.amount, EdgeKind.VERIFICADO, method, why
                ):
                    per_expense[exp.id] = exp.amount
                    out["verificadas"] += 1
            per_line[trn.id] = per_line.get(trn.id, ZERO) + target
        elif combos:
            for exp in {e for c in combos for e in c}:
                if await _add(
                    session,
                    condo.id,
                    trn,
                    exp,
                    exp.amount,
                    EdgeKind.SUGERIDO,
                    method,
                    "Mais de uma combinação soma o débito: escolha uma pessoa.",
                ):
                    out["sugeridas"] += 1
    await session.flush()
    return out
