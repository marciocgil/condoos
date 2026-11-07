"""Pending items of a condominium in a month — the management company's cockpit (D70).

1. **Contract billing.** Every contract in force must be billed (a fiscal invoice, NF) in the
   months its billing frequency expects: monthly by default, every N months from the start,
   never for "on demand" contracts. Status per contract:
   - ``faturado``: an expense of the contract in the month with an invoice (number or NF);
   - ``sem_nf``: charged (boleto, debit) but no invoice;
   - ``sem_faturamento``: nothing for the contract in the month;
   - ``aguardando``: still within the usual issue time (``grace_days`` after the month end).
2. **One-off services.** An expense without a contract (utility bills aside) must be backed
   by an approval — the signed proposal, the minutes, the approved quote. Without one it is
   pending.

These are follow-up items for the management company, not audit findings: nothing here
accuses anyone; R09, R10 and R12 keep doing the auditing.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.models import (
    Approval,
    Condominium,
    Contract,
    ContractAmendment,
    Document,
    Expense,
    ExpenseDocument,
    Supplier,
)
from app.enrichment.indices import load_index_table
from app.rules.contracts import contract_value_at, terms_at

GRACE_DAYS = 10
UTILITIES = ["energia", "agua", "gas"]


@dataclass
class ContractBilling:
    contract_id: uuid.UUID
    supplier: str
    object: str
    expected_value: Decimal
    status: str  # faturado | sem_nf | sem_faturamento | aguardando
    expense_id: uuid.UUID | None = None
    billed_value: Decimal | None = None
    invoice_number: str | None = None


@dataclass
class OneOffService:
    expense_id: uuid.UUID
    supplier: str | None
    description: str
    amount: Decimal
    issue_date: date
    invoice_number: str | None
    approvals: list[dict[str, Any]] = field(default_factory=list)

    @property
    def pending(self) -> bool:
        return not self.approvals


@dataclass
class MonthPending:
    month: date
    contracts: list[ContractBilling]
    one_off: list[OneOffService]

    @property
    def open_count(self) -> int:
        return sum(c.status in ("sem_nf", "sem_faturamento") for c in self.contracts) + sum(
            o.pending for o in self.one_off
        )


def billing_expected(contract: Contract, month: date) -> bool:
    """Does the contract expect an invoice for this month (competence)?"""
    start = contract.start_date.replace(day=1)
    if month < start or (contract.end_date is not None and month > contract.end_date):
        return False
    every = contract.billing_frequency_months
    if every == 0:
        return False
    elapsed = (month.year - start.year) * 12 + month.month - start.month
    return elapsed % every == 0


def month_end(month: date) -> date:
    return add_months(month, 1) - timedelta(days=1)


async def month_pending(
    session: AsyncSession, condominium_id: uuid.UUID, month: date, today: date
) -> MonthPending:
    condo = await session.get(Condominium, condominium_id)
    assert condo is not None
    contracts = list(
        await session.scalars(select(Contract).where(Contract.condominium_id == condominium_id))
    )
    suppliers = {
        s.id: s.legal_name
        for s in await session.scalars(
            select(Supplier).where(
                Supplier.id.in_(
                    select(Expense.supplier_id).where(
                        Expense.condominium_id == condominium_id, Expense.competence == month
                    )
                )
                | Supplier.id.in_([c.supplier_id for c in contracts])
            )
        )
    }
    amendments: dict[uuid.UUID, list[ContractAmendment]] = {}
    for amendment in await session.scalars(
        select(ContractAmendment).where(ContractAmendment.condominium_id == condominium_id)
    ):
        amendments.setdefault(amendment.contract_id, []).append(amendment)
    expenses = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condominium_id, Expense.competence == month
            )
        )
    )
    fiscal = set(
        await session.scalars(
            select(ExpenseDocument.expense_id).where(
                ExpenseDocument.condominium_id == condominium_id,
                ExpenseDocument.role == "fiscal",
                ExpenseDocument.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
            )
        )
    )

    def has_invoice(e: Expense) -> bool:
        return bool(e.invoice_number) or e.id in fiscal

    table = await load_index_table(session)  # expected value with index adjustments
    waiting = today <= month_end(month) + timedelta(days=GRACE_DAYS)
    billing: list[ContractBilling] = []
    for c in sorted(contracts, key=lambda c: suppliers.get(c.supplier_id, "")):
        if not billing_expected(c, month):
            continue
        mine = [e for e in expenses if e.contract_id == c.id]
        invoiced = next((e for e in mine if has_invoice(e)), None)
        charged = invoiced or (mine[0] if mine else None)
        if invoiced is not None:
            status = "faturado"
        elif waiting:
            status = "aguardando"
        elif charged is not None:
            status = "sem_nf"
        else:
            status = "sem_faturamento"
        billing.append(
            ContractBilling(
                contract_id=c.id,
                supplier=suppliers.get(c.supplier_id, ""),
                object=c.object,
                expected_value=(
                    contract_value_at(c, amendments.get(c.id, []), month, table)
                    or terms_at(c, amendments.get(c.id, []), month)[0]
                ),
                status=status,
                expense_id=charged.id if charged else None,
                billed_value=charged.amount if charged else None,
                invoice_number=invoiced.invoice_number if invoiced else None,
            )
        )

    exempt = set(
        ((condo.rule_params or {}).get("R12", {}) or {}).get("exempt_categories", UTILITIES)
    )
    loose = [e for e in expenses if e.contract_id is None and e.category not in exempt]
    approvals: dict[uuid.UUID, list[dict[str, Any]]] = {}
    if loose:
        rows = await session.execute(
            select(Approval, Document.original_filename)
            .outerjoin(Document, Document.id == Approval.source_document_id)
            .where(
                Approval.condominium_id == condominium_id,
                Approval.expense_id.in_([e.id for e in loose]),
            )
        )
        for ap, filename in rows:
            approvals.setdefault(ap.expense_id, []).append(
                {
                    "id": str(ap.id),
                    "approved_by": ap.approved_by,
                    "approved_at": ap.approved_at.isoformat(),
                    "document": filename,
                    "document_id": str(ap.source_document_id) if ap.source_document_id else None,
                }
            )
    one_off = [
        OneOffService(
            expense_id=e.id,
            supplier=suppliers.get(e.supplier_id) if e.supplier_id else None,
            description=e.description,
            amount=e.amount,
            issue_date=e.issue_date,
            invoice_number=e.invoice_number,
            approvals=approvals.get(e.id, []),
        )
        for e in sorted(loose, key=lambda e: (-e.amount, e.issue_date))
    ]
    return MonthPending(month=month, contracts=billing, one_off=one_off)
