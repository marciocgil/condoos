"""Everything the monthly report shows, read once for the PDF and the XLSX (spec §11).

The report is for the board: it carries only findings the board can see (never ones
awaiting validation or discarded). Readers pass a session already scoped to the
condominium (RLS); every query also filters by ``condominium_id``.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.br import format_cnpj
from app.core.time import add_months, utcnow
from app.db.enums import VISIBLE_TO_BOARD, FindingStatus
from app.db.models import (
    AppUser,
    BankTransaction,
    Competence,
    Condominium,
    Contract,
    Decision,
    Document,
    Expense,
    ExpenseDocument,
    Finding,
    MatchIssue,
    Supplier,
)
from app.matching.categories import category_label

FOOTER = "Relatório gerado com apoio de IA. Achados são indícios para verificação, não conclusões."
SEVERITY_LABEL = {"alta": "Grave", "media": "Médio", "baixa": "Baixo"}
STATUS_LABEL = {
    "aguardando_validacao": "Aguardando validação",
    "publicado": "Novo",
    "confirmado": "Confirmado",
    "contestado": "Contestado",
    "ignorado": "Ignorado",
    "descartado": "Descartado",
}
ACTION_LABEL = {
    "confirmar": "Confirmado",
    "contestar": "Contestado",
    "ignorar": "Ignorado",
    "validar": "Validado pela administradora",
    "descartar": "Descartado",
    "reabrir": "Reaberto",
}
DOC_TYPE_LABEL = {
    "nfse": "NFS-e",
    "nfe": "NF-e",
    "boleto": "Boleto / conta",
    "recibo": "Recibo",
    "extrato": "Extrato bancário",
    "cnab_retorno": "Retorno CNAB",
    "contrato": "Contrato",
    "convencao": "Convenção",
    "ata": "Ata",
    "outro": "Outro",
}


@dataclass
class DecisionRow:
    action: str
    user_name: str
    decided_at: datetime
    comment: str | None


@dataclass
class FindingRow:
    id: uuid.UUID
    rule_code: str
    severity: str
    title: str
    explanation: str
    amount_at_risk: Decimal
    status: str
    supplier: str | None
    category: str | None
    evidence: list[str]
    decisions: list[DecisionRow]


@dataclass
class ExpenseRow:
    id: uuid.UUID
    issue_date: date
    due_date: date | None
    supplier: str | None
    supplier_cnpj: str | None
    category: str
    description: str
    invoice_number: str | None
    amount: Decimal
    paid_on: date | None


@dataclass
class SupplierRow:
    name: str
    cnpj: str
    status: str | None
    expenses: int
    total: Decimal
    findings: int


@dataclass
class ContractRow:
    supplier: str
    object: str
    monthly_value: Decimal
    index: str
    base_month: int | None
    start: date
    end: date | None


@dataclass
class DocumentRow:
    name: str
    doc_type: str
    status: str
    received_at: datetime


@dataclass
class MonthReport:
    condominium: str
    condominium_cnpj: str
    month: date
    competence_status: str
    generated_at: datetime
    amount_at_risk: Decimal
    by_severity: dict[str, int]
    findings: list[FindingRow]
    expenses: list[ExpenseRow]
    suppliers: list[SupplierRow]
    contracts: list[ContractRow]
    documents: list[DocumentRow]
    expenses_total: Decimal = Decimal("0")
    preview: bool = False
    top: list[FindingRow] = field(default_factory=list)


def month_of(value: Any) -> date | None:
    """'2026-10', '2026-10-05' or '05/10/2026' → first day of the month."""
    text = str(value or "").strip()
    try:
        if len(text) >= 7 and text[4] == "-":
            return date(int(text[:4]), int(text[5:7]), 1)
        if len(text) == 10 and text[2] == "/":
            return date(int(text[6:]), int(text[3:5]), 1)
    except ValueError:
        return None
    return None


async def build_month_report(
    session: AsyncSession, condominium_id: uuid.UUID, month: date
) -> MonthReport:
    condo = await session.get(Condominium, condominium_id)
    assert condo is not None
    comp = await session.scalar(
        select(Competence).where(
            Competence.condominium_id == condominium_id, Competence.month == month
        )
    )
    visible = [s.value for s in VISIBLE_TO_BOARD]
    findings = list(
        await session.scalars(
            select(Finding)
            .where(
                Finding.condominium_id == condominium_id,
                Finding.competence == month,
                Finding.status.in_(visible),
            )
            .order_by(Finding.amount_at_risk.desc(), Finding.id)
        )
    )
    suppliers = {
        s.id: s
        for s in await session.scalars(
            select(Supplier).where(
                or_(
                    Supplier.id.in_({f.supplier_id for f in findings if f.supplier_id}),
                    Supplier.id.in_(
                        select(Expense.supplier_id).where(
                            Expense.condominium_id == condominium_id, Expense.competence == month
                        )
                    ),
                    Supplier.id.in_(
                        select(Contract.supplier_id).where(
                            Contract.condominium_id == condominium_id
                        )
                    ),
                )
            )
        )
    }
    decisions: dict[uuid.UUID, list[DecisionRow]] = {}
    if findings:
        rows = await session.execute(
            select(Decision, AppUser.name)
            .join(AppUser, AppUser.id == Decision.user_id)
            .where(
                Decision.condominium_id == condominium_id,
                Decision.finding_id.in_([f.id for f in findings]),
            )
            .order_by(Decision.decided_at)
        )
        for d, name in rows:
            decisions.setdefault(d.finding_id, []).append(
                DecisionRow(d.action, name, d.decided_at, d.comment)
            )

    expenses = list(
        await session.scalars(
            select(Expense)
            .where(Expense.condominium_id == condominium_id, Expense.competence == month)
            .order_by(Expense.issue_date, Expense.amount.desc())
        )
    )
    expense_category = {e.id: e.category for e in expenses}
    paid: dict[uuid.UUID, date] = {}
    if expenses:
        for tx_expense, posted in await session.execute(
            select(BankTransaction.expense_id, BankTransaction.posted_at).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.expense_id.in_(list(expense_category)),
            )
        ):
            if tx_expense is not None:
                paid[tx_expense] = posted

    def finding_category(f: Finding) -> str | None:
        if f.rule_inputs.get("categoria"):
            return category_label(str(f.rule_inputs["categoria"]))
        for e in f.evidence:
            if e.get("kind") == "expense":
                try:
                    cat = expense_category.get(uuid.UUID(str(e.get("id"))))
                except ValueError:
                    cat = None
                if cat:
                    return category_label(cat)
        return None

    finding_rows = [
        FindingRow(
            id=f.id,
            rule_code=f.rule_code,
            severity=f.severity,
            title=f.title,
            explanation=f.explanation,
            amount_at_risk=f.amount_at_risk,
            status=f.status,
            supplier=suppliers[f.supplier_id].legal_name if f.supplier_id in suppliers else None,
            category=finding_category(f),
            evidence=[str(e.get("label", "")) for e in f.evidence if e.get("label")],
            decisions=decisions.get(f.id, []),
        )
        for f in findings
    ]
    expense_rows = [
        ExpenseRow(
            id=e.id,
            issue_date=e.issue_date,
            due_date=e.due_date,
            supplier=suppliers[e.supplier_id].legal_name if e.supplier_id in suppliers else None,
            supplier_cnpj=(
                format_cnpj(suppliers[e.supplier_id].cnpj) if e.supplier_id in suppliers else None
            ),
            category=category_label(e.category),
            description=e.description,
            invoice_number=e.invoice_number,
            amount=e.amount,
            paid_on=paid.get(e.id),
        )
        for e in expenses
    ]
    supplier_rows = []
    for s in suppliers.values():
        mine = [e for e in expenses if e.supplier_id == s.id]
        if not mine and not any(f.supplier_id == s.id for f in findings):
            continue
        supplier_rows.append(
            SupplierRow(
                name=s.legal_name,
                cnpj=format_cnpj(s.cnpj),
                status=s.registration_status,
                expenses=len(mine),
                total=sum((e.amount for e in mine), Decimal("0")),
                findings=sum(f.supplier_id == s.id for f in findings),
            )
        )
    supplier_rows.sort(key=lambda r: (-r.total, r.name))

    contracts = list(
        await session.scalars(
            select(Contract)
            .where(
                Contract.condominium_id == condominium_id,
                Contract.start_date < add_months(month, 1),
                or_(Contract.end_date.is_(None), Contract.end_date >= month),
            )
            .order_by(Contract.object)
        )
    )
    contract_rows = [
        ContractRow(
            supplier=suppliers[c.supplier_id].legal_name if c.supplier_id in suppliers else "",
            object=c.object,
            monthly_value=c.monthly_value,
            index=c.adjustment_index,
            base_month=c.adjustment_base_month,
            start=c.start_date,
            end=c.end_date,
        )
        for c in contracts
    ]

    linked = select(ExpenseDocument.document_id).where(
        ExpenseDocument.expense_id.in_(list(expense_category) or [uuid.uuid4()])
    )
    direct = [e.document_id for e in expenses if e.document_id]
    documents = list(
        await session.scalars(
            select(Document)
            .where(
                Document.condominium_id == condominium_id,
                or_(Document.id.in_(linked), Document.id.in_(direct or [uuid.uuid4()])),
            )
            .order_by(Document.created_at)
        )
    )
    document_rows = [
        DocumentRow(
            name=d.original_filename,
            doc_type=DOC_TYPE_LABEL.get(d.doc_type, d.doc_type),
            status="Revisado por pessoa" if d.reviewed_at else "Extração automática",
            received_at=d.created_at,
        )
        for d in documents
    ]

    open_ = [
        f
        for f in finding_rows
        if f.status not in (FindingStatus.IGNORADO.value, FindingStatus.DESCARTADO.value)
    ]
    status = comp.status if comp else "aberta"
    return MonthReport(
        condominium=condo.name,
        condominium_cnpj=format_cnpj(condo.cnpj),
        month=month,
        competence_status=status,
        generated_at=utcnow(),
        amount_at_risk=sum((f.amount_at_risk for f in open_), Decimal("0")),
        by_severity={s: sum(f.severity == s for f in finding_rows) for s in SEVERITY_LABEL},
        findings=finding_rows,
        expenses=expense_rows,
        suppliers=supplier_rows,
        contracts=contract_rows,
        documents=document_rows,
        expenses_total=sum((e.amount for e in expenses), Decimal("0")),
        preview=status != "fechada",
        top=finding_rows[:5],
    )


def document_month(doc: Document) -> date | None:
    extracted = doc.extracted or {}
    return (
        month_of(extracted.get("competencia"))
        or month_of(extracted.get("data_emissao"))
        or month_of(extracted.get("vencimento"))
    )


async def pending_for_month(
    session: AsyncSession, condominium_id: uuid.UUID, month: date
) -> dict[str, int]:
    """Exception-queue items that block closing this month (spec §7).

    A document or match issue whose month cannot be told counts as blocking: closing a
    month with something unresolved that might belong to it is the worse mistake.
    """
    docs = 0
    for d in await session.scalars(
        select(Document).where(
            Document.condominium_id == condominium_id, Document.needs_review.is_(True)
        )
    ):
        when = document_month(d)
        docs += when is None or when == month
    issues = 0
    for issue in await session.scalars(
        select(MatchIssue).where(
            MatchIssue.condominium_id == condominium_id, MatchIssue.status == "aberto"
        )
    ):
        when = None
        if issue.subject_type == "expense":
            when = await session.scalar(
                select(Expense.competence).where(
                    Expense.id == issue.subject_id, Expense.condominium_id == condominium_id
                )
            )
        elif issue.subject_type == "bank_transaction":
            posted = await session.scalar(
                select(BankTransaction.posted_at).where(
                    BankTransaction.id == issue.subject_id,
                    BankTransaction.condominium_id == condominium_id,
                )
            )
            when = posted.replace(day=1) if posted else None
        elif issue.subject_type == "document":
            doc = await session.get(Document, issue.subject_id)
            if doc is not None and doc.condominium_id == condominium_id:
                when = document_month(doc)
        issues += when is None or when == month
    serious = len(
        list(
            await session.scalars(
                select(Finding.id).where(
                    Finding.condominium_id == condominium_id,
                    Finding.competence == month,
                    Finding.status == FindingStatus.AGUARDANDO_VALIDACAO.value,
                )
            )
        )
    )
    return {"documentos": docs, "casamentos": issues, "achados_graves": serious}
