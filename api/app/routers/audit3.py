"""CondoOS Audit, cycle 3 API (D124): funds and backing accounts, budget and variance notes,
formal approval of the accounts, historical revalidation and the monthly farol approved by
the síndico.

Internal inputs need ``run_audit``; sending the farol needs ``review_audit``; approving or
returning it needs ``approve_audit_publication`` (the síndico only). The síndico, the
subsíndico and the conselho read only what was approved (``view``), never unit data.
"""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import defer

from app.audit import governance as gov
from app.audit import publication as pubs
from app.audit.imports import ImportFileError
from app.audit.run import RunError, month_start, run_audit
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.time import add_months, local_today
from app.db.enums import AccountKind, AccountsApprovalBody, FundKind, PublicationStatus
from app.db.models import (
    AccountsApproval,
    AppUser,
    AuditPublication,
    BankAccount,
    BankStatement,
    BoardMember,
    Budget,
    BudgetLine,
    BudgetNote,
    Condominium,
    Document,
    Expense,
    Fund,
    FundAccount,
    FundBalance,
)
from app.db.session import DbSession
from app.matching.categories import CATEGORY_LABEL, category_label

router = APIRouter(tags=["audit"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW_AUDIT))]
CanRun = Annotated[CondoAccess, Depends(require(Permission.RUN_AUDIT))]
CanReview = Annotated[CondoAccess, Depends(require(Permission.REVIEW_AUDIT))]
CanApprove = Annotated[CondoAccess, Depends(require(Permission.APPROVE_AUDIT_PUBLICATION))]
CanSee = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
MAX_FILE = 5 * 1024 * 1024
MAX_REVALIDATE = 12


def _422(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    if condo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")
    return condo


def _month(value: str | None, condo: Condominium) -> date:
    if value:
        try:
            return gov.parse_month(value)
        except gov.GovernanceError as exc:
            raise _422("Competência inválida (AAAA-MM).") from exc
    return add_months(month_start(local_today(condo.timezone)), -1)


def _money(value: Any) -> str | None:
    return str(value) if value is not None else None


# --------------------------------------------------------------------------- read


@router.get("/condominiums/{condominium_id}/audit/governance")
async def governance(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    """Funds and their accounts, the budget of the year, variance notes and the approvals of
    the accounts that cover the month."""
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    accounts = list(
        await db.scalars(
            select(BankAccount)
            .where(BankAccount.condominium_id == condo.id)
            .order_by(BankAccount.label)
        )
    )
    last = add_months(month, 1)
    closing: dict[uuid.UUID, Any] = {}
    for st in await db.scalars(
        select(BankStatement)
        .where(
            BankStatement.condominium_id == condo.id,
            BankStatement.period_end >= month,
            BankStatement.period_end < last,
            BankStatement.format != "cnab",
        )
        .order_by(BankStatement.period_end)
    ):
        if st.bank_account_id is not None:
            closing[st.bank_account_id] = st.closing_balance
    funds = list(
        await db.scalars(select(Fund).where(Fund.condominium_id == condo.id).order_by(Fund.name))
    )
    links: dict[uuid.UUID, list[str]] = {}
    for fa in await db.scalars(select(FundAccount).where(FundAccount.condominium_id == condo.id)):
        links.setdefault(fa.fund_id, []).append(str(fa.bank_account_id))
    balances = {
        fb.fund_id: fb
        for fb in await db.scalars(
            select(FundBalance).where(
                FundBalance.condominium_id == condo.id, FundBalance.competence == month
            )
        )
    }
    budget = await db.scalar(
        select(Budget)
        .where(Budget.condominium_id == condo.id, Budget.year == month.year)
        .order_by(Budget.version.desc())
        .limit(1)
    )
    lines: dict[str, Any] = {}
    if budget is not None:
        for ln in await db.scalars(
            select(BudgetLine).where(BudgetLine.budget_id == budget.id, BudgetLine.month == month)
        ):
            lines[ln.category] = ln.amount
    realized: dict[str, Any] = {}
    for e in await db.scalars(
        select(Expense).where(Expense.condominium_id == condo.id, Expense.competence == month)
    ):
        realized[e.category] = realized.get(e.category, 0) + e.amount
    notes = list(
        await db.scalars(
            select(BudgetNote)
            .where(BudgetNote.condominium_id == condo.id, BudgetNote.competence == month)
            .order_by(BudgetNote.created_at)
        )
    )
    approvals = list(
        await db.scalars(
            select(AccountsApproval)
            .where(
                AccountsApproval.condominium_id == condo.id,
                AccountsApproval.period_start <= month,
                AccountsApproval.period_end >= month,
            )
            .order_by(AccountsApproval.approved_on)
        )
    )
    docs = {
        d.id: d.original_filename
        for d in await db.scalars(
            select(Document)
            .options(defer(Document.text_content))
            .where(
                Document.id.in_(
                    [a.document_id for a in approvals]
                    + ([budget.source_document_id] if budget and budget.source_document_id else [])
                    or [uuid.uuid4()]
                )
            )
        )
    }
    board = list(
        await db.scalars(
            select(BoardMember)
            .where(BoardMember.condominium_id == condo.id)
            .order_by(BoardMember.full_name)
        )
    )
    candidates = list(
        await db.scalars(
            select(Document)
            .options(defer(Document.text_content))
            .where(
                Document.condominium_id == condo.id,
                Document.doc_type.in_(("ata", "balancete", "relatorio_adm", "outro")),
            )
            .order_by(Document.created_at.desc())
            .limit(60)
        )
    )
    return {
        "competencia": month.strftime("%Y-%m"),
        "can_edit": access.can(Permission.RUN_AUDIT),
        "accounts": [
            {
                "id": str(a.id),
                "label": a.label,
                "kind": a.kind,
                "closing_balance": _money(closing.get(a.id)),
            }
            for a in accounts
        ],
        "funds": [
            {
                "id": str(f.id),
                "name": f.name,
                "kind": f.kind,
                "purpose": f.purpose,
                "account_ids": sorted(links.get(f.id, [])),
                "balance": (
                    {
                        "opening": _money(balances[f.id].opening),
                        "inflows": _money(balances[f.id].inflows),
                        "outflows": _money(balances[f.id].outflows),
                        "yield": _money(balances[f.id].yield_amount),
                        "closing": _money(balances[f.id].closing),
                    }
                    if f.id in balances
                    else None
                ),
            }
            for f in funds
        ],
        "budget": (
            {
                "id": str(budget.id),
                "year": budget.year,
                "version": budget.version,
                "approved_on": budget.approved_on,
                "document": (
                    docs.get(budget.source_document_id) if budget.source_document_id else None
                ),
                "lines": [
                    {
                        "category": cat,
                        "label": category_label(cat),
                        "budgeted": _money(lines.get(cat, 0)),
                        "realized": _money(realized.get(cat, 0)),
                    }
                    for cat in sorted(set(lines) | set(realized))
                ],
            }
            if budget is not None
            else None
        ),
        "notes": [
            {
                "id": str(n.id),
                "category": n.category,
                "label": category_label(n.category),
                "text": n.text,
                "at": n.created_at,
            }
            for n in notes
        ],
        "categories": [{"key": k, "label": v} for k, v in CATEGORY_LABEL.items()],
        "approvals": [
            {
                "id": str(a.id),
                "body": a.body,
                "period": f"{a.period_start:%m/%Y} a {a.period_end:%m/%Y}",
                "approved_on": a.approved_on,
                "document": docs.get(a.document_id),
                "signatories": a.signatories,
                "with_reservations": a.with_reservations,
            }
            for a in approvals
        ],
        "board": [
            {"id": str(m.id), "name": m.full_name, "position": m.position, "term_end": m.term_end}
            for m in board
        ],
        "documents": [
            {"id": str(d.id), "name": d.original_filename, "doc_type": d.doc_type}
            for d in candidates
        ],
    }


# --------------------------------------------------------------------------- write


class AccountIn(BaseModel):
    kind: AccountKind
    label: str | None = Field(default=None, max_length=120)


@router.put("/condominiums/{condominium_id}/audit/accounts/{account_id}")
async def put_account(
    condominium_id: uuid.UUID, account_id: uuid.UUID, body: AccountIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        a = await gov.set_account_kind(db, condo, account_id, body.kind, body.label, access.user_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada.") from exc
    return {"id": str(a.id), "kind": a.kind, "label": a.label}


class FundIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    kind: FundKind | None = None
    purpose: str | None = Field(default=None, max_length=300)
    account_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


@router.post("/condominiums/{condominium_id}/audit/funds", status_code=status.HTTP_201_CREATED)
async def create_fund(
    condominium_id: uuid.UUID, body: FundIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        fund, created = await gov.get_or_create_fund(db, condo, body.name, body.kind)
        if not created:
            raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um fundo com esse nome.")
        await gov.update_fund(
            db,
            condo,
            fund.id,
            kind=body.kind,
            purpose=body.purpose,
            account_ids=body.account_ids,
            user_id=access.user_id,
        )
    except gov.GovernanceError as exc:
        raise _422(str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada.") from exc
    return {"id": str(fund.id), "name": fund.name, "kind": fund.kind}


class FundPatch(BaseModel):
    kind: FundKind | None = None
    purpose: str | None = Field(default=None, max_length=300)
    account_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)


@router.put("/condominiums/{condominium_id}/audit/funds/{fund_id}")
async def put_fund(
    condominium_id: uuid.UUID, fund_id: uuid.UUID, body: FundPatch, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        fund = await gov.update_fund(
            db,
            condo,
            fund_id,
            kind=body.kind,
            purpose=body.purpose,
            account_ids=body.account_ids,
            user_id=access.user_id,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fundo ou conta não encontrado.") from exc
    return {"id": str(fund.id), "kind": fund.kind}


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_FILE:
        raise _422("Planilha maior que 5 MB.")
    return data


@router.post("/condominiums/{condominium_id}/audit/funds/import")
async def import_funds(
    condominium_id: uuid.UUID,
    access: CanRun,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Fund balances of the statement of accounts (CSV: fundo, competencia, saldo inicial,
    entradas, saidas, rendimentos, saldo final)."""
    condo = await _condo(db, access)
    try:
        result = await gov.import_fund_balances(db, condo, await _read(file), access.user_id)
    except (ImportFileError, gov.GovernanceError) as exc:
        raise _422(str(exc)) from exc
    return result.as_dict()


@router.post("/condominiums/{condominium_id}/audit/budget/import")
async def import_budget(
    condominium_id: uuid.UUID,
    access: CanRun,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    year: Annotated[int, Form(ge=2000, le=2100)],
    approved_on: Annotated[date | None, Form()] = None,
    source_document_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict[str, Any]:
    """The approved budget (CSV: categoria, mes, valor; a line without month is annual)."""
    condo = await _condo(db, access)
    if approved_on is not None and approved_on > local_today(condo.timezone):
        raise _422("A data da aprovação não pode estar no futuro.")
    try:
        result = await gov.import_budget(
            db,
            condo,
            await _read(file),
            year=year,
            approved_on=approved_on,
            source_document_id=source_document_id,
            user_id=access.user_id,
        )
    except (ImportFileError, gov.GovernanceError) as exc:
        raise _422(str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.") from exc
    return result.as_dict()


class NoteIn(BaseModel):
    competencia: str
    category: str = Field(max_length=60)
    text: str = Field(max_length=2000)


@router.post(
    "/condominiums/{condominium_id}/audit/budget/notes", status_code=status.HTTP_201_CREATED
)
async def add_note(
    condominium_id: uuid.UUID, body: NoteIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    month = _month(body.competencia, condo)
    try:
        note = await gov.add_budget_note(db, condo, month, body.category, body.text, access.user_id)
    except gov.GovernanceError as exc:
        raise _422(str(exc)) from exc
    return {"id": str(note.id)}


class Signatory(BaseModel):
    board_member_id: uuid.UUID | None = None
    nome: str | None = Field(default=None, max_length=120)
    papel: str | None = Field(default=None, max_length=60)


class AccountsApprovalIn(BaseModel):
    body: AccountsApprovalBody
    period_start: str
    period_end: str
    approved_on: date
    document_id: uuid.UUID
    signatories: list[Signatory] = Field(min_length=1, max_length=20)
    with_reservations: bool = False
    notes: str | None = Field(default=None, max_length=2000)


@router.post(
    "/condominiums/{condominium_id}/audit/accounts-approvals", status_code=status.HTTP_201_CREATED
)
async def add_accounts_approval(
    condominium_id: uuid.UUID, body: AccountsApprovalIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        row = await gov.record_accounts_approval(
            db,
            condo,
            body=body.body,
            period_start=gov.parse_month(body.period_start),
            period_end=gov.parse_month(body.period_end),
            approved_on=body.approved_on,
            document_id=body.document_id,
            signatories=[s.model_dump(mode="json", exclude_none=True) for s in body.signatories],
            with_reservations=body.with_reservations,
            notes=body.notes,
            user_id=access.user_id,
            today=local_today(condo.timezone),
        )
    except gov.GovernanceError as exc:
        raise _422(str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc).capitalize() + ".") from exc
    return {"id": str(row.id)}


class RevalidateIn(BaseModel):
    months: int = Field(ge=1, le=MAX_REVALIDATE)
    until: str | None = None


@router.post("/condominiums/{condominium_id}/audit/revalidate")
async def revalidate(
    condominium_id: uuid.UUID, body: RevalidateIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    """Run the past months again (oldest first). Unchanged results are reused (same
    fingerprint); a changed one supersedes the old, which is kept."""
    condo = await _condo(db, access)
    today = local_today(condo.timezone)
    last = _month(body.until, condo)
    out = []
    for i in range(body.months - 1, -1, -1):
        month = add_months(last, -i)
        try:
            run = await run_audit(
                db, condo, month, today=today, user_id=access.user_id, trigger="revalidacao"
            )
        except RunError as exc:
            raise _422(str(exc)) from exc
        out.append(
            {
                "competencia": month.strftime("%Y-%m"),
                "run_id": str(run.id),
                "novos": run.summary.get("novos_resultados", 0),
                "mudancas": run.summary.get("mudancas_de_status", []),
            }
        )
    return {"meses": out}


# --------------------------------------------------------------------------- publication


def _pub_out(
    p: AuditPublication, names: dict[uuid.UUID, str], changed: bool | None = None
) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "competencia": p.snapshot.get("competencia"),
        "status": p.status,
        "snapshot": p.snapshot,
        "sha256": p.snapshot_sha256,
        "submitted_at": p.submitted_at,
        "submitted_by": names.get(p.submitted_by) if p.submitted_by else None,
        "decided_at": p.decided_at,
        "decided_by": names.get(p.decided_by) if p.decided_by else None,
        "reason": p.reason,
        "changed_since": changed,
    }


async def _names(db: DbSession, pubs_: list[AuditPublication]) -> dict[uuid.UUID, str]:
    ids = {x for p in pubs_ for x in (p.submitted_by, p.decided_by) if x}
    return {
        u.id: u.name or "Pessoa"
        for u in await db.scalars(select(AppUser).where(AppUser.id.in_(ids or {uuid.uuid4()})))
    }


class SubmitIn(BaseModel):
    competencia: str


@router.post(
    "/condominiums/{condominium_id}/audit/publications", status_code=status.HTTP_201_CREATED
)
async def submit(
    condominium_id: uuid.UUID, body: SubmitIn, access: CanReview, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        pub = await pubs.submit(db, condo.id, _month(body.competencia, condo), access.user_id)
    except pubs.PublicationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _pub_out(pub, await _names(db, [pub]))


class DecisionIn(BaseModel):
    approve: bool
    sha256: str = Field(min_length=64, max_length=64)
    reason: str | None = Field(default=None, max_length=2000)


@router.post("/condominiums/{condominium_id}/audit/publications/{publication_id}/decision")
async def decide(
    condominium_id: uuid.UUID,
    publication_id: uuid.UUID,
    body: DecisionIn,
    access: CanApprove,
    db: DbSession,
) -> dict[str, Any]:
    try:
        pub = await pubs.decide(
            db,
            access.condominium_id,
            publication_id,
            approve=body.approve,
            seen_sha256=body.sha256,
            reason=body.reason,
            user_id=access.user_id,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Envio não encontrado.") from exc
    except pubs.PublicationError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _pub_out(pub, await _names(db, [pub]))


@router.get("/condominiums/{condominium_id}/audit/publications")
async def list_publications(
    condominium_id: uuid.UUID, access: CanSee, db: DbSession
) -> dict[str, Any]:
    """What the condominium sees: approved months (with "changed since" when a revalidation
    changed a result) and, for whoever approves or reviews, the sending waiting."""
    internal = access.can(Permission.VIEW_AUDIT)
    approver = access.can(Permission.APPROVE_AUDIT_PUBLICATION)
    statuses = [PublicationStatus.APROVADA.value]
    if approver or internal:
        statuses.append(PublicationStatus.AGUARDANDO.value)
    if internal:
        statuses += [PublicationStatus.DEVOLVIDA.value, PublicationStatus.SUPERADA.value]
    rows = await pubs.latest(db, access.condominium_id, statuses=tuple(statuses))
    names = await _names(db, rows)
    out = []
    seen_months: set[str] = set()
    for p in rows:
        month = str(p.snapshot.get("competencia"))
        if p.status == PublicationStatus.APROVADA.value:
            if month in seen_months and not internal:
                continue
            seen_months.add(month)
            out.append(_pub_out(p, names, await pubs.changed_since(db, p)))
        else:
            out.append(_pub_out(p, names))
    return {
        "publications": out,
        "can_approve": approver,
        "can_submit": access.can(Permission.REVIEW_AUDIT),
    }
