"""Pending items of a condominium in a month — the management company's cockpit (D70).

1. **Contract billing.** Every contract in force must be billed (a fiscal invoice, NF) in the
   months its billing frequency expects: monthly by default, every N months from the start,
   never for "on demand" contracts. Status per contract:
   - ``faturado``: an expense of the contract in the month with an invoice (number or NF);
   - ``sem_nf``: charged (boleto, debit) but no invoice;
   - ``em_conferencia``: no invoice yet, but a document of the contract's supplier for the
     month already arrived (upload, delegated link or e-mail) and is still being read, in
     review or not yet matched: it is checked before calling anything missing (LB-052);
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
from datetime import UTC, date, datetime, time, timedelta
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
# Where the supplier and the month of a fiscal document are read (LB-052).
SUPPLIER_FIELDS = ("cnpj_prestador", "cnpj_emitente", "cnpj_beneficiario", "documento_recebedor")
MONTH_FIELDS = ("competencia", "data_emissao", "vencimento", "data")
FISCAL_TYPES = ("nfse", "nfe", "boleto", "recibo", "outro")
READING = ("pending", "processing", "needs_review")


@dataclass
class ContractBilling:
    contract_id: uuid.UUID
    supplier: str
    object: str
    expected_value: Decimal
    status: str  # faturado | em_conferencia | sem_nf | sem_faturamento | aguardando
    expense_id: uuid.UUID | None = None
    billed_value: Decimal | None = None
    invoice_number: str | None = None
    # How the invoice arrived (upload, email, pedido, seed) when it is linked to a document.
    origin: str | None = None
    # Documents of the supplier for the month not yet turned into an expense (LB-052).
    arrived: list[dict[str, str]] = field(default_factory=list)


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
    # Documents still being read whose supplier is not known yet: any of them may be a
    # missing invoice, so "not received" is said with this caveat.
    unread: int = 0

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


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _month_of(extracted: dict[str, Any]) -> date | None:
    for name in MONTH_FIELDS:
        raw = str(extracted.get(name) or "")
        if len(raw) >= 7 and raw[4] == "-" and raw[:4].isdigit() and raw[5:7].isdigit():
            month = int(raw[5:7])
            if 1 <= month <= 12:
                return date(int(raw[:4]), month, 1)
    return None


async def arrivals(
    session: AsyncSession, condominium_id: uuid.UUID, month: date
) -> tuple[dict[str, list[dict[str, str]]], int]:
    """Fiscal documents that arrived through any channel and are not an expense yet (being
    read, in review, or read but not matched), by supplier CNPJ for ``month``; and how many
    are still being read with no supplier known. Received since the month began."""
    linked = select(ExpenseDocument.document_id).where(
        ExpenseDocument.condominium_id == condominium_id
    )
    docs = await session.scalars(
        select(Document).where(
            Document.condominium_id == condominium_id,
            Document.doc_type.in_(FISCAL_TYPES),
            Document.created_at >= datetime.combine(month, time.min, tzinfo=UTC),
            Document.id.not_in(linked),
        )
    )
    by_cnpj: dict[str, list[dict[str, str]]] = {}
    unread = 0
    for doc in docs:
        extracted = doc.extracted or {}
        cnpj = next(
            (d for d in (_digits(extracted.get(f)) for f in SUPPLIER_FIELDS) if len(d) == 14),
            None,
        )
        if cnpj is None:
            unread += int(doc.extraction_status in READING)
            continue
        if _month_of(extracted) not in (month, None):
            continue
        by_cnpj.setdefault(cnpj, []).append(
            {"document_id": str(doc.id), "origin": doc.origin, "status": doc.extraction_status}
        )
    return by_cnpj, unread


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

    origins = dict(
        (
            await session.execute(
                select(ExpenseDocument.expense_id, Document.origin)
                .join(Document, Document.id == ExpenseDocument.document_id)
                .where(
                    ExpenseDocument.condominium_id == condominium_id,
                    ExpenseDocument.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
                )
            )
        ).all()
    )
    cnpjs = {
        s.id: s.cnpj
        for s in await session.scalars(
            select(Supplier).where(Supplier.id.in_([c.supplier_id for c in contracts]))
        )
    }
    arrived_by_cnpj, unread = await arrivals(session, condominium_id, month)

    table = await load_index_table(session)  # expected value with index adjustments
    waiting = today <= month_end(month) + timedelta(days=GRACE_DAYS)
    billing: list[ContractBilling] = []
    for c in sorted(contracts, key=lambda c: suppliers.get(c.supplier_id, "")):
        if not billing_expected(c, month):
            continue
        mine = [e for e in expenses if e.contract_id == c.id]
        invoiced = next((e for e in mine if has_invoice(e)), None)
        charged = invoiced or (mine[0] if mine else None)
        arrived = arrived_by_cnpj.get(cnpjs.get(c.supplier_id, ""), [])
        if invoiced is not None:
            status = "faturado"
        elif arrived:
            status = "em_conferencia"
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
                origin=origins.get(invoiced.id) if invoiced else None,
                arrived=[] if invoiced else arrived,
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
    return MonthPending(month=month, contracts=billing, one_off=one_off, unread=unread)
