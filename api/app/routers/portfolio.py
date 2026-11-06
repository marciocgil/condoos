"""Management company views across its whole portfolio (spec §9): indicators per
condominium, consolidated suppliers and contracts. Only condominiums the user can reach."""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth.deps import CurrentPrincipal, access_for
from app.auth.rbac import Permission
from app.core.br import format_cnpj
from app.core.time import add_months, local_today
from app.db.enums import UNDER_REVIEW, FindingStatus
from app.db.models import (
    Competence,
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    MatchIssue,
    Supplier,
)
from app.db.session import DbSession
from app.metrics import Bucket as MetricBucket
from app.metrics import compute as compute_metrics
from app.pending import month_pending
from app.rules.contracts import amendments_by_contract, anniversaries, terms_at

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

OPEN = (
    FindingStatus.AGUARDANDO_VALIDACAO.value,
    FindingStatus.PUBLICADO.value,
    FindingStatus.CONTESTADO.value,
)
REVIEW = tuple(s.value for s in UNDER_REVIEW)


class CondoRow(BaseModel):
    id: uuid.UUID
    name: str
    amount_at_risk: Decimal
    open_findings: int
    serious: int
    pending_validation: int
    queue_items: int
    status: str  # revisar | enviado | em_dia
    can_close: bool  # the user may close this condominium's competences
    has_competence: bool  # a competence exists for the portfolio's latest month


class PortfolioOut(BaseModel):
    condominiums: list[CondoRow]
    amount_at_risk: Decimal
    open_findings: int
    serious: int
    queue_items: int
    latest_competence: date | None


class SupplierRow(BaseModel):
    id: uuid.UUID
    name: str
    cnpj: str
    registration_status: str | None
    condominiums: list[str]
    total_paid_12m: Decimal
    open_findings: int
    amount_at_risk: Decimal


class ContractRow(BaseModel):
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    supplier_name: str
    object: str
    monthly_value: Decimal
    adjustment_index: str
    adjustment_index_other: str | None = None
    next_adjustment: date | None
    end_date: date | None
    amendments: int = 0


async def _manager_condos(db: DbSession, principal: CurrentPrincipal) -> list[Condominium]:
    return [c for c, _ in await _manager_access(db, principal)]


async def _manager_access(
    db: DbSession, principal: CurrentPrincipal
) -> list[tuple[Condominium, CondoAccess]]:
    condos = list(
        await db.scalars(
            select(Condominium)
            .where(Condominium.id.in_(principal.condominium_ids))
            .order_by(Condominium.name)
        )
    )
    out: list[tuple[Condominium, CondoAccess]] = []
    for c in condos:
        access = await access_for(db, principal.user.id, c)
        if access.can(Permission.VIEW_PENDING_FINDINGS):
            out.append((c, access))
    return out


@router.get("")
async def portfolio(db: DbSession, principal: CurrentPrincipal) -> PortfolioOut:
    accesses = await _manager_access(db, principal)
    condos = [c for c, _ in accesses]
    can_close = {c.id: a.can(Permission.CLOSE_COMPETENCE) for c, a in accesses}
    ids = [c.id for c in condos]
    findings = (
        list(await db.scalars(select(Finding).where(Finding.condominium_id.in_(ids))))
        if ids
        else []
    )
    docs_review = dict.fromkeys(ids, 0)
    for d in await db.scalars(
        select(Document).where(Document.condominium_id.in_(ids), Document.needs_review.is_(True))
    ):
        docs_review[d.condominium_id] += 1
    for m in await db.scalars(
        select(MatchIssue).where(MatchIssue.condominium_id.in_(ids), MatchIssue.status == "aberto")
    ):
        docs_review[m.condominium_id] += 1
    comps = (
        list(await db.scalars(select(Competence).where(Competence.condominium_id.in_(ids))))
        if ids
        else []
    )
    latest = max((c.month for c in comps), default=None)
    rows = []
    for c in condos:
        mine = [f for f in findings if f.condominium_id == c.id and f.status in OPEN]
        pending = sum(
            f.condominium_id == c.id and f.status in REVIEW for f in findings
        )  # waiting for review, including the ones waiting for evidence (D74)
        current = next((x for x in comps if x.condominium_id == c.id and x.month == latest), None)
        published = current is not None and current.published_at is not None
        rows.append(
            CondoRow(
                id=c.id,
                name=c.name,
                amount_at_risk=sum((f.amount_at_risk for f in mine), Decimal("0")),
                open_findings=len(mine),
                serious=sum(f.severity == "alta" for f in mine),
                pending_validation=pending,
                queue_items=pending + docs_review[c.id],
                status="revisar" if pending else ("enviado" if published else "em_dia"),
                can_close=can_close[c.id],
                has_competence=current is not None,
            )
        )
    rows.sort(key=lambda r: r.amount_at_risk, reverse=True)
    return PortfolioOut(
        condominiums=rows,
        amount_at_risk=sum((r.amount_at_risk for r in rows), Decimal("0")),
        open_findings=sum(r.open_findings for r in rows),
        serious=sum(r.serious for r in rows),
        queue_items=sum(r.queue_items for r in rows),
        latest_competence=latest,
    )


def _only(condos: list[Condominium], condominium_id: uuid.UUID | None) -> list[Condominium]:
    """Optional filter by one condominium of the portfolio (an unknown id gives nothing)."""
    return condos if condominium_id is None else [c for c in condos if c.id == condominium_id]


@router.get("/suppliers")
async def suppliers(
    db: DbSession, principal: CurrentPrincipal, condominium_id: uuid.UUID | None = None
) -> list[SupplierRow]:
    condos = {c.id: c.name for c in _only(await _manager_condos(db, principal), condominium_id)}
    if not condos:
        return []
    since = add_months(date.today().replace(day=1), -11)
    expenses = list(
        await db.scalars(
            select(Expense).where(
                Expense.condominium_id.in_(condos), Expense.supplier_id.is_not(None)
            )
        )
    )
    findings = list(
        await db.scalars(
            select(Finding).where(Finding.condominium_id.in_(condos), Finding.status.in_(OPEN))
        )
    )
    names: dict[uuid.UUID, set[str]] = defaultdict(set)
    paid: dict[uuid.UUID, Decimal] = defaultdict(Decimal)
    for e in expenses:
        if e.supplier_id is None:
            continue
        names[e.supplier_id].add(condos[e.condominium_id])
        if e.competence >= since:
            paid[e.supplier_id] += e.amount
    sups = {
        s.id: s for s in await db.scalars(select(Supplier).where(Supplier.id.in_(names.keys())))
    }
    rows = []
    for sid, condo_names in names.items():
        s = sups[sid]
        mine = [f for f in findings if f.supplier_id == sid]
        rows.append(
            SupplierRow(
                id=s.id,
                name=s.legal_name,
                cnpj=format_cnpj(s.cnpj),
                registration_status=s.registration_status,
                condominiums=sorted(condo_names),
                total_paid_12m=paid[sid],
                open_findings=len(mine),
                amount_at_risk=sum((f.amount_at_risk for f in mine), Decimal("0")),
            )
        )
    rows.sort(key=lambda r: (r.open_findings, r.total_paid_12m), reverse=True)
    return rows


@router.get("/contracts")
async def contracts(db: DbSession, principal: CurrentPrincipal) -> list[ContractRow]:
    condos = {c.id: c.name for c in await _manager_condos(db, principal)}
    if not condos:
        return []
    rows = (
        await db.execute(
            select(Contract, Supplier.legal_name)
            .join(Supplier, Supplier.id == Contract.supplier_id)
            .where(Contract.condominium_id.in_(condos))
        )
    ).all()
    today = date.today()
    amendments = await amendments_by_contract(db, [c.id for c, _ in rows])
    out = []
    for c, supplier_name in rows:
        mine = amendments.get(c.id, [])
        upcoming = [
            a
            for a in anniversaries(
                c.start_date, c.adjustment_base_month, date(today.year + 2, 12, 1)
            )
            if a > today
        ]
        out.append(
            ContractRow(
                id=c.id,
                condominium_id=c.condominium_id,
                condominium_name=condos[c.condominium_id],
                supplier_name=supplier_name,
                object=c.object,
                monthly_value=terms_at(c, mine, today.replace(day=1))[0],  # in force (D66)
                adjustment_index=c.adjustment_index,
                adjustment_index_other=c.adjustment_index_other,
                next_adjustment=(
                    upcoming[0]
                    if upcoming and c.adjustment_index in ("IPCA", "IGPM", "INPC", "OUTRO")
                    else None
                ),
                end_date=c.end_date,
                amendments=len(mine),
            )
        )
    out.sort(key=lambda r: (r.end_date or date.max, r.condominium_name))
    return out


class MetricsOut(BaseModel):
    months: list[date]
    totals: dict[str, object]
    by_month: list[dict[str, object]]  # portfolio, one row per month
    condominiums: list[dict[str, object]]  # one row per condominium, period totals


@router.get("/metrics")
async def metrics(
    db: DbSession,
    principal: CurrentPrincipal,
    months: Annotated[int, Query(ge=1, le=24)] = 6,
    condominium_id: uuid.UUID | None = None,
) -> MetricsOut:
    """Internal pilot metrics (D60): precision, automatic extraction, review time, LLM cost."""
    condos = _only(await _manager_condos(db, principal), condominium_id)
    last = date.today().replace(day=1)
    first = add_months(last, -(months - 1))
    month_list = [add_months(first, i) for i in range(months)]
    buckets = await compute_metrics(db, [c.id for c in condos], first, last)
    totals = MetricBucket()
    per_month = {m: MetricBucket() for m in month_list}
    rows = []
    for c in condos:
        condo_total = MetricBucket()
        for m, b in buckets[c.id].items():
            condo_total.add(b)
            per_month.setdefault(m, MetricBucket()).add(b)
        totals.add(condo_total)
        rows.append({"id": str(c.id), "name": c.name, **condo_total.summary()})
    return MetricsOut(
        months=month_list,
        totals=totals.summary(),
        by_month=[{"month": m.isoformat(), **per_month[m].summary()} for m in month_list],
        condominiums=rows,
    )


class PendingCondoOut(BaseModel):
    id: uuid.UUID
    name: str
    open_count: int
    contracts: list[dict[str, Any]]
    one_off: list[dict[str, Any]]


class PendingOut(BaseModel):
    month: date
    months: list[dict[str, Any]]  # recent months with the number of open items
    condominiums: list[PendingCondoOut]


@router.get("/pending")
async def pending(
    db: DbSession,
    principal: CurrentPrincipal,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    condominium_id: uuid.UUID | None = None,
) -> PendingOut:
    """Cockpit of pending items (D70): contract billing and one-off services to back."""
    condos = _only(await _manager_condos(db, principal), condominium_id)
    today = local_today(condos[0].timezone if condos else None)
    if month:
        chosen = date(int(month[:4]), int(month[5:7]), 1)
    else:
        latest = await db.scalar(
            select(func.max(Expense.competence)).where(
                Expense.condominium_id.in_([c.id for c in condos] or [uuid.uuid4()])
            )
        )
        chosen = latest or today.replace(day=1)
    recent = [add_months(chosen, -i) for i in range(5, -1, -1)]
    per_month: dict[date, int] = {m: 0 for m in recent}
    out: list[PendingCondoOut] = []
    for c in condos:
        for m in recent:
            result = await month_pending(db, c.id, m, local_today(c.timezone))
            per_month[m] += result.open_count
            if m != chosen:
                continue
            out.append(
                PendingCondoOut(
                    id=c.id,
                    name=c.name,
                    open_count=result.open_count,
                    contracts=[
                        {
                            "contract_id": str(b.contract_id),
                            "supplier": b.supplier,
                            "object": b.object,
                            "expected_value": str(b.expected_value),
                            "status": b.status,
                            "expense_id": str(b.expense_id) if b.expense_id else None,
                            "billed_value": str(b.billed_value) if b.billed_value else None,
                            "invoice_number": b.invoice_number,
                        }
                        for b in result.contracts
                    ],
                    one_off=[
                        {
                            "expense_id": str(o.expense_id),
                            "supplier": o.supplier,
                            "description": o.description,
                            "amount": str(o.amount),
                            "issue_date": o.issue_date.isoformat(),
                            "invoice_number": o.invoice_number,
                            "approvals": o.approvals,
                            "pending": o.pending,
                        }
                        for o in result.one_off
                    ],
                )
            )
    out.sort(key=lambda r: (-r.open_count, r.name))
    return PendingOut(
        month=chosen,
        months=[{"month": m.isoformat(), "open": per_month[m]} for m in recent],
        condominiums=out,
    )
