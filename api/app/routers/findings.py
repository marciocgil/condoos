"""Findings for one condominium: summary, list, detail, decisions, comments, decision trail.

Board members (síndico, subsíndico, conselheiro) never see findings awaiting validation or
discarded ones; the management company sees everything.
"""

import asyncio
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.sql import Select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.br import format_cnpj
from app.db.enums import VISIBLE_TO_BOARD, DecisionAction, FindingStatus
from app.db.models import (
    AppUser,
    Competence,
    Decision,
    Document,
    Expense,
    Finding,
    FindingComment,
    Supplier,
)
from app.db.session import DbSession
from app.findings.decisions import DecisionError, allowed_actions, decide
from app.matching.categories import category_label
from app.storage.base import get_storage

router = APIRouter(prefix="/condominiums/{condominium_id}", tags=["findings"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanComment = Annotated[CondoAccess, Depends(require(Permission.COMMENT_FINDING))]


class FindingOut(BaseModel):
    id: uuid.UUID
    rule_code: str
    severity: str
    title: str
    explanation: str
    amount_at_risk: Decimal
    status: str
    competence: date
    ai_assisted: bool
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    category: str | None
    category_label: str | None


class EvidenceOut(BaseModel):
    kind: str
    id: str
    label: str
    excerpt: str
    file_url: str | None = None
    page: int | None = None


class DecisionOut(BaseModel):
    id: uuid.UUID
    action: str
    comment: str | None
    user_name: str
    decided_at: datetime


class CommentOut(BaseModel):
    id: uuid.UUID
    body: str
    user_name: str
    created_at: datetime


class SupplierBrief(BaseModel):
    id: uuid.UUID
    name: str
    cnpj: str
    registration_status: str | None


class FindingDetailOut(FindingOut):
    rule_inputs: dict[str, Any]
    evidence: list[EvidenceOut]
    supplier: SupplierBrief | None
    decisions: list[DecisionOut]
    comments: list[CommentOut]
    validated_by_management: bool
    allowed_actions: list[str]
    can_comment: bool


class SummaryOut(BaseModel):
    competence: date | None
    competence_status: str | None
    amount_at_risk: Decimal
    findings: int
    by_severity: dict[str, int]
    top: list[FindingOut]
    expenses: int
    expenses_total: Decimal


class DecisionIn(BaseModel):
    action: DecisionAction
    comment: str | None = Field(default=None, max_length=2000)


class CommentIn(BaseModel):
    body: str = Field(min_length=2, max_length=2000)


class TrailItemOut(BaseModel):
    finding_id: uuid.UUID
    finding_title: str
    rule_code: str
    competence: date
    action: str
    comment: str | None
    user_name: str
    decided_at: datetime


def _month(value: str | None) -> date | None:
    if value is None:
        return None
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def _visible(stmt: Select[Any], access: CondoAccess) -> Select[Any]:
    if access.can(Permission.VIEW_PENDING_FINDINGS):
        return stmt
    return stmt.where(Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]))


async def _categories(db: DbSession, findings: list[Finding]) -> dict[uuid.UUID, str]:
    """Category of each finding: from its inputs, else from the first expense in evidence."""
    out: dict[uuid.UUID, str] = {}
    expense_for: dict[uuid.UUID, uuid.UUID] = {}
    for f in findings:
        if f.rule_inputs.get("categoria"):
            out[f.id] = str(f.rule_inputs["categoria"])
            continue
        first = next((e["id"] for e in f.evidence if e.get("kind") == "expense"), None)
        if first:
            expense_for[f.id] = uuid.UUID(first)
    if expense_for:
        rows = await db.execute(
            select(Expense.id, Expense.category).where(Expense.id.in_(set(expense_for.values())))
        )
        cats = {r[0]: r[1] for r in rows}
        for fid, eid in expense_for.items():
            if eid in cats:
                out[fid] = cats[eid]
    return out


async def _to_out(db: DbSession, findings: list[Finding]) -> list[FindingOut]:
    supplier_ids = {f.supplier_id for f in findings if f.supplier_id}
    names: dict[uuid.UUID, str] = {}
    if supplier_ids:
        rows = await db.execute(
            select(Supplier.id, Supplier.legal_name).where(Supplier.id.in_(supplier_ids))
        )
        names = {r[0]: r[1] for r in rows}
    cats = await _categories(db, findings)
    return [
        FindingOut(
            id=f.id,
            rule_code=f.rule_code,
            severity=f.severity,
            title=f.title,
            explanation=f.explanation,
            amount_at_risk=f.amount_at_risk,
            status=f.status,
            competence=f.competence,
            ai_assisted=f.ai_assisted,
            supplier_id=f.supplier_id,
            supplier_name=names.get(f.supplier_id) if f.supplier_id else None,
            category=cats.get(f.id),
            category_label=category_label(cats[f.id]) if f.id in cats else None,
        )
        for f in findings
    ]


# --------------------------------------------------------------------------- list / summary


@router.get("/findings")
async def list_findings(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    competence: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    severity: Annotated[list[str] | None, Query()] = None,
    status_: Annotated[list[str] | None, Query(alias="status")] = None,
    category: Annotated[list[str] | None, Query()] = None,
) -> list[FindingOut]:
    stmt = _visible(select(Finding).where(Finding.condominium_id == access.condominium_id), access)
    if (month := _month(competence)) is not None:
        stmt = stmt.where(Finding.competence == month)
    if severity:
        stmt = stmt.where(Finding.severity.in_(severity))
    if status_:
        stmt = stmt.where(Finding.status.in_(status_))
    rows = list(await db.scalars(stmt.order_by(Finding.amount_at_risk.desc(), Finding.id)))
    out = await _to_out(db, rows)
    if category:
        out = [f for f in out if f.category in category]
    return out


@router.get("/summary")
async def month_summary(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    competence: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> SummaryOut:
    month = _month(competence)
    if month is None:
        # Default: the most recent closed month (spec §8), else the most recent one.
        comps = list(
            await db.scalars(
                select(Competence)
                .where(Competence.condominium_id == access.condominium_id)
                .order_by(Competence.month.desc())
            )
        )
        chosen = next((c for c in comps if c.status == "fechada"), comps[0] if comps else None)
        month = chosen.month if chosen else None
    if month is None:
        return SummaryOut(
            competence=None,
            competence_status=None,
            amount_at_risk=Decimal("0"),
            findings=0,
            by_severity={"alta": 0, "media": 0, "baixa": 0},
            top=[],
            expenses=0,
            expenses_total=Decimal("0"),
        )
    comp = await db.scalar(
        select(Competence).where(
            Competence.condominium_id == access.condominium_id, Competence.month == month
        )
    )
    findings = list(
        await db.scalars(
            _visible(
                select(Finding).where(
                    Finding.condominium_id == access.condominium_id, Finding.competence == month
                ),
                access,
            ).order_by(Finding.amount_at_risk.desc(), Finding.id)
        )
    )
    # "Em risco" counts what is still open; ignored findings are not risk anymore.
    open_ = [
        f
        for f in findings
        if f.status not in (FindingStatus.IGNORADO.value, FindingStatus.DESCARTADO.value)
    ]
    expenses = list(
        await db.scalars(
            select(Expense.amount).where(
                Expense.condominium_id == access.condominium_id, Expense.competence == month
            )
        )
    )
    return SummaryOut(
        competence=month,
        competence_status=comp.status if comp else None,
        amount_at_risk=sum((f.amount_at_risk for f in open_), Decimal("0")),
        findings=len(findings),
        by_severity={s: sum(f.severity == s for f in findings) for s in ("alta", "media", "baixa")},
        top=await _to_out(db, findings[:3]),
        expenses=len(expenses),
        expenses_total=sum(expenses, Decimal("0")),
    )


# --------------------------------------------------------------------------- detail / actions


async def _finding(db: DbSession, access: CondoAccess, finding_id: uuid.UUID) -> Finding:
    finding: Finding | None = await db.scalar(
        _visible(
            select(Finding).where(
                Finding.id == finding_id, Finding.condominium_id == access.condominium_id
            ),
            access,
        ).with_for_update()
    )
    if finding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Achado não encontrado.")
    return finding


async def _detail(db: DbSession, access: CondoAccess, f: Finding) -> FindingDetailOut:
    [base] = await _to_out(db, [f])
    supplier = await db.get(Supplier, f.supplier_id) if f.supplier_id else None
    doc_ids = [uuid.UUID(e["id"]) for e in f.evidence if e.get("kind") == "document"]
    docs = (
        {
            d.id: d
            for d in await db.scalars(
                select(Document).where(
                    Document.id.in_(doc_ids), Document.condominium_id == f.condominium_id
                )
            )
        }
        if doc_ids
        else {}
    )
    evidence = []
    for e in f.evidence:
        url = None
        if e.get("kind") == "document" and uuid.UUID(e["id"]) in docs:
            url = await asyncio.to_thread(
                get_storage().presigned_url, docs[uuid.UUID(e["id"])].storage_key
            )
        evidence.append(
            EvidenceOut(
                kind=e["kind"],
                id=e["id"],
                label=e.get("label", ""),
                excerpt=e.get("excerpt", ""),
                file_url=url,
                page=e.get("page"),
            )
        )
    decisions = (
        await db.execute(
            select(Decision, AppUser.name)
            .join(AppUser, AppUser.id == Decision.user_id)
            .where(Decision.finding_id == f.id, Decision.condominium_id == f.condominium_id)
            .order_by(Decision.decided_at)
        )
    ).all()
    comments = (
        await db.execute(
            select(FindingComment, AppUser.name)
            .join(AppUser, AppUser.id == FindingComment.user_id)
            .where(
                FindingComment.finding_id == f.id, FindingComment.condominium_id == f.condominium_id
            )
            .order_by(FindingComment.created_at)
        )
    ).all()
    return FindingDetailOut(
        **base.model_dump(),
        rule_inputs=f.rule_inputs,
        evidence=evidence,
        supplier=(
            SupplierBrief(
                id=supplier.id,
                name=supplier.legal_name,
                cnpj=format_cnpj(supplier.cnpj),
                registration_status=supplier.registration_status,
            )
            if supplier
            else None
        ),
        decisions=[
            DecisionOut(
                id=d.id, action=d.action, comment=d.comment, user_name=name, decided_at=d.decided_at
            )
            for d, name in decisions
        ],
        comments=[
            CommentOut(id=c.id, body=c.body, user_name=name, created_at=c.created_at)
            for c, name in comments
        ],
        validated_by_management=any(d.action == DecisionAction.VALIDAR.value for d, _ in decisions),
        allowed_actions=[a.value for a in allowed_actions(access, f)],
        can_comment=access.can(Permission.COMMENT_FINDING),
    )


@router.get("/findings/{finding_id}")
async def get_finding(
    condominium_id: uuid.UUID, finding_id: uuid.UUID, access: CanView, db: DbSession
) -> FindingDetailOut:
    return await _detail(db, access, await _finding(db, access, finding_id))


@router.post("/findings/{finding_id}/decisions")
async def post_decision(
    condominium_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: DecisionIn,
    access: CanView,
    db: DbSession,
) -> FindingDetailOut:
    finding = await _finding(db, access, finding_id)
    try:
        await decide(db, access, finding, body.action, body.comment)
    except DecisionError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    return await _detail(db, access, finding)


@router.post("/findings/{finding_id}/comments", status_code=status.HTTP_201_CREATED)
async def post_comment(
    condominium_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: CommentIn,
    access: CanComment,
    db: DbSession,
) -> FindingDetailOut:
    finding = await _finding(db, access, finding_id)
    db.add(
        FindingComment(
            condominium_id=finding.condominium_id,
            finding_id=finding.id,
            user_id=access.user_id,
            body=body.body.strip(),
        )
    )
    await db.flush()
    return await _detail(db, access, finding)


@router.get("/decisions")
async def decision_trail(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[TrailItemOut]:
    """Every decision of the condominium, newest first (the trail for the assembly)."""
    stmt = (
        select(Decision, Finding, AppUser.name)
        .join(Finding, Finding.id == Decision.finding_id)
        .join(AppUser, AppUser.id == Decision.user_id)
        .where(Decision.condominium_id == access.condominium_id)
        .order_by(Decision.decided_at.desc())
    )
    if not access.can(Permission.VIEW_PENDING_FINDINGS):
        stmt = stmt.where(Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]))
    rows = (await db.execute(stmt)).all()
    return [
        TrailItemOut(
            finding_id=f.id,
            finding_title=f.title,
            rule_code=f.rule_code,
            competence=f.competence,
            action=d.action,
            comment=d.comment,
            user_name=name,
            decided_at=d.decided_at,
        )
        for d, f, name in rows
    ]
