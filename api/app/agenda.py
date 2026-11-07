"""Agenda of a condominium (D71): what is due, expected or ending, by date.

A follow-up view over data the system already has — it creates nothing and decides nothing:
- ``vencimento``: due date of each expense (from the boleto or bill), with ``pago`` (a debit
  matched in the bank statement), ``vencido`` (past due, unpaid) or ``a_vencer``;
- ``nf_prevista``: when a contract's invoice is expected (billing frequency, D70), on the
  usual issue day seen in its past invoices — always marked as predicted;
- ``reajuste``: the adjustment month of indexed contracts;
- ``fim_contrato``: end of the term (contracts with an indeterminate term never appear).

It never suggests or schedules a payment: the system does not move money.
"""

import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.enums import AdjustmentIndex
from app.db.models import (
    BankTransaction,
    Contract,
    ContractAmendment,
    Expense,
    ExpenseDocument,
    Supplier,
)
from app.enrichment.indices import load_index_table
from app.pending import GRACE_DAYS, billing_expected, month_end
from app.rules.contracts import anniversaries, contract_value_at, terms_at

KINDS = ("vencimento", "nf_prevista", "reajuste", "fim_contrato")
ADJUSTING = {
    AdjustmentIndex.IPCA.value,
    AdjustmentIndex.IGPM.value,
    AdjustmentIndex.INPC.value,
    AdjustmentIndex.OUTRO.value,
}
INDEX_NAME = {"IPCA": "IPCA", "IGPM": "IGP-M", "INPC": "INPC"}


@dataclass
class Event:
    date: date
    kind: str
    title: str
    detail: str
    status: str
    predicted: bool = False
    amount: Decimal | None = None
    contract_id: uuid.UUID | None = None
    expense_id: uuid.UUID | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["amount"] = None if self.amount is None else f"{self.amount:.2f}"
        d["contract_id"] = str(self.contract_id) if self.contract_id else None
        d["expense_id"] = str(self.expense_id) if self.expense_id else None
        return d


def _months(start: date, end: date) -> list[date]:
    out, m = [], start.replace(day=1)
    while m <= end:
        out.append(m)
        m = add_months(m, 1)
    return out


def _on_day(month: date, day: int) -> date:
    return month.replace(day=min(day, month_end(month).day))


async def condominium_agenda(
    session: AsyncSession, condominium_id: uuid.UUID, start: date, end: date, today: date
) -> list[Event]:
    contracts = list(
        await session.scalars(select(Contract).where(Contract.condominium_id == condominium_id))
    )
    supplier_ids = {c.supplier_id for c in contracts}
    expenses = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condominium_id,
                # the window plus a year of history for the usual issue day of contracts
                Expense.competence >= add_months(start.replace(day=1), -12),
                Expense.competence <= end,
            )
        )
    )
    supplier_ids |= {e.supplier_id for e in expenses if e.supplier_id}
    names = {
        s.id: s.trade_name or s.legal_name
        for s in await session.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))
    }
    paid = {
        r[0]: r[1]
        for r in await session.execute(
            select(BankTransaction.expense_id, BankTransaction.posted_at).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
            )
        )
    }
    fiscal = set(
        await session.scalars(
            select(ExpenseDocument.expense_id).where(
                ExpenseDocument.condominium_id == condominium_id,
                ExpenseDocument.role == "fiscal",
            )
        )
    )
    amendments: dict[uuid.UUID, list[ContractAmendment]] = {}
    for amendment in await session.scalars(
        select(ContractAmendment).where(ContractAmendment.condominium_id == condominium_id)
    ):
        amendments.setdefault(amendment.contract_id, []).append(amendment)

    table = await load_index_table(session)

    def expected(c: Contract, month: date) -> Decimal:
        """Value due in the month: amendments and index adjustments applied (D66, D68)."""
        mine = amendments.get(c.id, [])
        return contract_value_at(c, mine, month, table) or terms_at(c, mine, month)[0]

    events: list[Event] = []

    # Due dates of expenses.
    for e in expenses:
        if e.due_date is None or not (start <= e.due_date <= end):
            continue
        if e.id in paid:
            status = "pago"
        elif e.due_date < today:
            status = "vencido"
        else:
            status = "a_vencer"
        who = (
            names.get(e.supplier_id, "Fornecedor não identificado")
            if e.supplier_id
            else ("Fornecedor não identificado")
        )
        events.append(
            Event(
                date=e.due_date,
                kind="vencimento",
                title=f"Vencimento · {who}",
                detail=e.description,
                status=status,
                amount=e.amount,
                contract_id=e.contract_id,
                expense_id=e.id,
            )
        )

    for c in contracts:
        name = names.get(c.supplier_id, "")
        history = sorted((e for e in expenses if e.contract_id == c.id), key=lambda e: e.competence)
        usual_day = int(statistics.median(e.issue_date.day for e in history[-6:])) if history else 1
        # Expected invoices.
        for month in _months(start, end):
            if not billing_expected(c, month):
                continue
            when = _on_day(month, usual_day)
            if not (start <= when <= end):
                continue
            mine = [e for e in history if e.competence == month]
            invoiced = next((e for e in mine if e.invoice_number or e.id in fiscal), None)
            if invoiced is not None:
                status = "recebida"
            elif today > month_end(month) + timedelta(days=GRACE_DAYS):
                status = "nao_chegou"
            else:
                status = "prevista"
            events.append(
                Event(
                    date=invoiced.issue_date if invoiced else when,
                    kind="nf_prevista",
                    title=f"NF do contrato · {name}",
                    detail=c.object
                    + (
                        f" · NF {invoiced.invoice_number}"
                        if invoiced and invoiced.invoice_number
                        else ""
                    ),
                    status=status,
                    predicted=invoiced is None,
                    amount=invoiced.amount if invoiced else expected(c, month),
                    contract_id=c.id,
                    expense_id=invoiced.id if invoiced else None,
                )
            )
        # Adjustments.
        if c.adjustment_index in ADJUSTING:
            index = INDEX_NAME.get(c.adjustment_index) or c.adjustment_index_other or "outro índice"
            for anniversary in anniversaries(c.start_date, c.adjustment_base_month, end):
                if start <= anniversary <= end or (anniversary < start <= month_end(anniversary)):
                    events.append(
                        Event(
                            date=max(anniversary, start),
                            kind="reajuste",
                            title=f"Reajuste · {name}",
                            detail=f"{c.object} · {index}",
                            status="previsto" if anniversary > today else "conferir",
                            predicted=anniversary > today,
                            contract_id=c.id,
                        )
                    )
        # End of the term.
        if c.end_date is not None and start <= c.end_date <= end:
            events.append(
                Event(
                    date=c.end_date,
                    kind="fim_contrato",
                    title=f"Fim do contrato · {name}",
                    detail=c.object,
                    status="vence" if c.end_date >= today else "vencido",
                    contract_id=c.id,
                )
            )

    order = {k: i for i, k in enumerate(KINDS)}
    events.sort(key=lambda ev: (ev.date, order[ev.kind], ev.title))
    return events
