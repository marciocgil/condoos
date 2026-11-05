"""Expense ↔ bank transaction (spec §5.5).

A debit matches an expense when: same value (±R$ 0,01), compatible payee (same CNPJ, or a
name sharing words with the supplier, or no payee in the statement) and a debit date between
5 days before and 10 days after the due date (or the issue date when there is no due date).
Only one-to-one matches are linked. Anything ambiguous goes to the exception queue.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BankTransaction, Expense, Supplier
from app.matching.documents import open_issue
from app.matching.text import overlap

TOLERANCE = Decimal("0.01")
BEFORE = timedelta(days=5)
AFTER = timedelta(days=10)


def payee_compatible(trn: BankTransaction, supplier: Supplier | None) -> bool:
    if supplier is None:
        return trn.payee_document is None
    if trn.payee_document:
        return trn.payee_document == supplier.cnpj
    if trn.payee_name:
        return overlap(trn.payee_name, supplier.legal_name) > 0 or (
            supplier.trade_name is not None and overlap(trn.payee_name, supplier.trade_name) > 0
        )
    return True  # statement without payee data: value and date decide


def date_compatible(trn: BankTransaction, expense: Expense) -> bool:
    anchor: date = expense.due_date or expense.issue_date
    return anchor - BEFORE <= trn.posted_at <= anchor + AFTER


async def match_bank(session: AsyncSession, condominium_id: uuid.UUID) -> list[Expense]:
    """Link one-to-one matches; returns the expenses that got a debit."""
    debits = list(
        await session.scalars(
            select(BankTransaction).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.expense_id.is_(None),
                BankTransaction.amount < 0,
            )
        )
    )
    if not debits:
        return []
    matched_ids = set(
        await session.scalars(
            select(BankTransaction.expense_id).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.expense_id.is_not(None),
            )
        )
    )
    expenses = [
        e
        for e in await session.scalars(
            select(Expense).where(Expense.condominium_id == condominium_id)
        )
        if e.id not in matched_ids
    ]
    suppliers = {
        s.id: s
        for s in await session.scalars(
            select(Supplier).where(
                Supplier.id.in_({e.supplier_id for e in expenses if e.supplier_id})
            )
        )
    }
    by_trn: dict[uuid.UUID, list[Expense]] = defaultdict(list)
    by_exp: dict[uuid.UUID, list[BankTransaction]] = defaultdict(list)
    for trn in debits:
        value = -trn.amount
        for e in expenses:
            if (
                abs(e.amount - value) <= TOLERANCE
                and date_compatible(trn, e)
                and payee_compatible(trn, suppliers.get(e.supplier_id) if e.supplier_id else None)
            ):
                by_trn[trn.id].append(e)
                by_exp[e.id].append(trn)
    linked: list[Expense] = []
    for trn in debits:
        cands = by_trn.get(trn.id, [])
        if len(cands) == 1 and len(by_exp[cands[0].id]) == 1:
            trn.expense_id = cands[0].id
            linked.append(cands[0])
        elif len(cands) > 1:
            await open_issue(
                session,
                condominium_id,
                "pagamento_ambiguo",
                "bank_transaction",
                trn.id,
                [
                    {
                        "type": "expense",
                        "id": str(e.id),
                        "label": f"{e.description[:80]} · R$ {e.amount} · {e.issue_date:%d/%m/%Y}",
                    }
                    for e in cands
                ],
                f"Débito de R$ {-trn.amount} em {trn.posted_at:%d/%m/%Y} compatível com mais de uma despesa",
            )
    # One expense compatible with several debits: ask once, about the expense.
    for expense_id, trns in by_exp.items():
        if len(trns) > 1 and all(len(by_trn[t.id]) == 1 for t in trns):
            await open_issue(
                session,
                condominium_id,
                "pagamento_ambiguo",
                "expense",
                expense_id,
                [
                    {
                        "type": "bank_transaction",
                        "id": str(t.id),
                        "label": f"{t.description[:80]} · R$ {-t.amount} · {t.posted_at:%d/%m/%Y}",
                    }
                    for t in trns
                ],
                "Despesa compatível com mais de um débito no extrato",
            )
    return linked


async def match_bank_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    from app.matching.documents import enqueue_rules

    condominium_id = uuid.UUID(payload["condominium_id"])
    linked = await match_bank(session, condominium_id)
    for month in {e.competence for e in linked}:
        await enqueue_rules(session, condominium_id, month)
