"""Management company views across its whole portfolio (spec §9): indicators per
condominium, consolidated suppliers and contracts. Only condominiums the user can reach."""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, roles_on_condominium
from app.auth.rbac import CondoAccess, Permission
from app.core.br import format_cnpj
from app.core.time import add_months
from app.db.enums import FindingStatus
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
from app.rules.contracts import amendments_by_contract, anniversaries, terms_at

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

OPEN = (
    FindingStatus.AGUARDANDO_VALIDACAO.value,
    FindingStatus.PUBLICADO.value,
    FindingStatus.CONTESTADO.value,
)


class CondoRow(BaseModel):
    id: uuid.UUID
    name: str
    amount_at_risk: Decimal
    open_findings: int
    serious: int
    pending_validation: int
    queue_items: int
    status: str  # revisar | enviado | em_dia


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
    next_adjustment: date | None
    end_date: date | None
    amendments: int = 0


async def _manager_condos(db: DbSession, principal: CurrentPrincipal) -> list[Condominium]:
    condos = list(
        await db.scalars(
            select(Condominium)
            .where(Condominium.id.in_(principal.condominium_ids))
            .order_by(Condominium.name)
        )
    )
    out = []
    for c in condos:
        access = CondoAccess(
            principal.user.id, c.id, await roles_on_condominium(db, principal.user.id, c)
        )
        if access.can(Permission.VIEW_PENDING_FINDINGS):
            out.append(c)
    return out


@router.get("")
async def portfolio(db: DbSession, principal: CurrentPrincipal) -> PortfolioOut:
    condos = await _manager_condos(db, principal)
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
        pending = sum(f.status == FindingStatus.AGUARDANDO_VALIDACAO.value for f in mine)
        published = any(
            x.condominium_id == c.id and x.month == latest and x.published_at is not None
            for x in comps
        )
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


@router.get("/suppliers")
async def suppliers(db: DbSession, principal: CurrentPrincipal) -> list[SupplierRow]:
    condos = {c.id: c.name for c in await _manager_condos(db, principal)}
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
                next_adjustment=(
                    upcoming[0]
                    if upcoming and c.adjustment_index in ("IPCA", "IGPM", "INPC")
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
) -> MetricsOut:
    """Internal pilot metrics (D60): precision, automatic extraction, review time, LLM cost."""
    condos = await _manager_condos(db, principal)
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
