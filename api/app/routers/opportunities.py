"""Opportunities (Optimize, D76, D81). The CondoOS team creates one from an R02/R03 finding
and reviews it; the board sees it only after approval, with the validated estimate; the
síndico decides whether the condominium moves on. No route moves money or sends anything."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, access_for, require
from app.auth.rbac import CondoAccess, Permission
from app.cases import user_names
from app.config import get_settings
from app.core.time import local_today
from app.db.enums import (
    VISIBLE_TO_BOARD,
    DocumentOrigin,
    OpportunityReviewAction,
    SavingsStage,
)
from app.db.models import (
    Condominium,
    Finding,
    Opportunity,
    OpportunityFinding,
    OpportunityReview,
    SavingsRecord,
    Supplier,
)
from app.db.session import DbSession
from app.ingestion.documents import ingest_file
from app.opportunities import (
    OpportunityError,
    adjust,
    allowed_actions,
    create_from_finding,
    decide,
    follow_up_actions,
    is_reviewer,
    measure_realized,
    record_contracted,
    visible,
)

router = APIRouter(tags=["opportunities"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]

# What the board may see of the savings: never the raw potential (D76).
BOARD_STAGES = (
    SavingsStage.ESTIMADA_VALIDADA,
    SavingsStage.APROVADA,
    SavingsStage.CONTRATADA,
    SavingsStage.REALIZADA,
)


class CreateIn(BaseModel):
    finding_id: uuid.UUID


class DecisionIn(BaseModel):
    action: OpportunityReviewAction
    comment: str | None = Field(default=None, max_length=2000)


class AdjustIn(BaseModel):
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    periodicity: Literal["unica", "mensal", "anual"] | None = None
    one_time_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    confidence: Literal["alta", "media", "baixa"] | None = None
    quality_risks: str | None = Field(default=None, max_length=2000)
    assumptions: list[str] | None = Field(default=None, max_length=20)
    reason: str = Field(max_length=1000)


class StageOut(BaseModel):
    stage: str
    amount: Decimal
    periodicity: str
    annualized_amount: Decimal
    one_time_cost: Decimal
    net_amount: Decimal
    baseline_period_start: date
    baseline_period_end: date
    baseline_amount: Decimal
    method_code: str
    assumptions: list[str]
    confidence: str
    quality_risks: str
    recorded_by: str
    recorded_at: datetime


class OpportunityRowOut(BaseModel):
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    number: str
    title: str
    opportunity_type: str
    status: str
    supplier_name: str | None
    presented: bool
    # The most advanced stage the viewer may see (labelled; never a sum of stages).
    headline_stage: str | None
    headline_annualized: Decimal | None
    created_at: datetime


class OpportunityDetailOut(OpportunityRowOut):
    recommendation: str
    operational_impact: str
    legal_contractual_risk: str
    implementation_readiness: str
    review_requirement: str
    findings: list[dict[str, str]]
    stages: list[StageOut]
    history: list[dict[str, str | None]]
    allowed_actions: list[str]
    # Recording the agreement and measuring the result (CB-063); never moves money.
    follow_up_actions: list[str]
    can_adjust: bool


def _error(exc: OpportunityError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


async def _stages(db: DbSession, access: CondoAccess, opp: Opportunity) -> list[SavingsRecord]:
    rows = list(
        await db.scalars(
            select(SavingsRecord)
            .where(SavingsRecord.opportunity_id == opp.id)
            .order_by(SavingsRecord.created_at, SavingsRecord.id)
        )
    )
    latest: dict[str, SavingsRecord] = {}
    for r in rows:
        latest[r.stage] = r
    allowed = (
        list(SavingsStage) if access.can(Permission.VIEW_OPPORTUNITY_DRAFT) else list(BOARD_STAGES)
    )
    return [latest[s.value] for s in allowed if s.value in latest]


async def _rows(
    db: DbSession, access_by_condo: dict[uuid.UUID, CondoAccess], opps: list[Opportunity]
) -> list[OpportunityRowOut]:
    condos = (
        {
            c.id: c
            for c in await db.scalars(
                select(Condominium).where(Condominium.id.in_({o.condominium_id for o in opps}))
            )
        }
        if opps
        else {}
    )
    suppliers = (
        {
            s.id: s.legal_name
            for s in await db.scalars(
                select(Supplier).where(
                    Supplier.id.in_({o.supplier_id for o in opps if o.supplier_id})
                )
            )
        }
        if opps
        else {}
    )
    out = []
    for o in opps:
        access = access_by_condo[o.condominium_id]
        stages = await _stages(db, access, o)
        head = stages[-1] if stages else None
        out.append(
            OpportunityRowOut(
                id=o.id,
                condominium_id=o.condominium_id,
                condominium_name=condos[o.condominium_id].name,
                number=o.number,
                title=o.title,
                opportunity_type=o.opportunity_type,
                status=o.status,
                supplier_name=suppliers.get(o.supplier_id) if o.supplier_id else None,
                presented=o.presented_at is not None,
                headline_stage=head.stage if head else None,
                headline_annualized=head.annualized_amount if head else None,
                created_at=o.created_at,
            )
        )
    return out


async def _get(
    db: DbSession, access: CondoAccess, opportunity_id: uuid.UUID, lock: bool = False
) -> Opportunity:
    stmt = select(Opportunity).where(
        Opportunity.id == opportunity_id, Opportunity.condominium_id == access.condominium_id
    )
    opp = await db.scalar(stmt.with_for_update() if lock else stmt)
    # Not yet approved by the CondoOS review: it does not exist for the board (OPT-01).
    if opp is None or not visible(access, opp):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Oportunidade não encontrada.")
    return opp


async def _detail(db: DbSession, access: CondoAccess, opp: Opportunity) -> OpportunityDetailOut:
    [row] = await _rows(db, {opp.condominium_id: access}, [opp])
    stages = await _stages(db, access, opp)
    reviews = list(
        await db.scalars(
            select(OpportunityReview)
            .where(OpportunityReview.opportunity_id == opp.id)
            .order_by(OpportunityReview.created_at)
        )
    )
    names = await user_names(
        db,
        {r.user_id for r in reviews}
        | {s.recorded_by_user_id for s in stages if s.recorded_by_user_id},
    )
    findings = list(
        await db.scalars(
            select(Finding)
            .join(OpportunityFinding, OpportunityFinding.finding_id == Finding.id)
            .where(OpportunityFinding.opportunity_id == opp.id)
        )
    )
    sees_pending = access.can(Permission.VIEW_PENDING_FINDINGS)
    board = {s.value for s in VISIBLE_TO_BOARD}
    return OpportunityDetailOut(
        **row.model_dump(),
        recommendation=opp.recommendation,
        operational_impact=opp.operational_impact,
        legal_contractual_risk=opp.legal_contractual_risk,
        implementation_readiness=opp.implementation_readiness,
        review_requirement=opp.review_requirement,
        findings=[
            {"id": str(f.id), "title": f.title, "rule_code": f.rule_code, "status": f.status}
            for f in findings
            if sees_pending or f.status in board
        ],
        stages=[
            StageOut(
                stage=s.stage,
                amount=s.amount,
                periodicity=s.periodicity,
                annualized_amount=s.annualized_amount,
                one_time_cost=s.one_time_cost,
                net_amount=s.net_amount,
                baseline_period_start=s.baseline_period_start,
                baseline_period_end=s.baseline_period_end,
                baseline_amount=s.baseline_amount,
                method_code=s.method_code,
                assumptions=list(s.assumptions),
                confidence=s.confidence,
                quality_risks=s.quality_risks,
                recorded_by=(
                    names.get(s.recorded_by_user_id, "Sistema")
                    if s.recorded_by_user_id
                    else "Sistema"
                ),
                recorded_at=s.created_at,
            )
            for s in stages
        ],
        history=sorted(
            [
                {
                    "at": s.created_at.isoformat(),
                    "who": (
                        names.get(s.recorded_by_user_id, "—")
                        if s.recorded_by_user_id
                        else "Sistema"
                    ),
                    "action": s.stage,
                    "from_status": None,
                    "to_status": None,
                    "comment": None,
                }
                for s in stages
                if s.stage in (SavingsStage.CONTRATADA.value, SavingsStage.REALIZADA.value)
            ]
            + [
                {
                    "at": r.created_at.isoformat(),
                    "who": names.get(r.user_id, "—"),
                    "action": r.action,
                    "from_status": r.from_status,
                    "to_status": r.to_status,
                    "comment": r.comment,
                }
                # The board sees its own decisions and that a review happened, not internal notes.
                for r in reviews
                if access.can(Permission.VIEW_OPPORTUNITY_DRAFT)
                or r.action
                in (
                    OpportunityReviewAction.APROVAR.value,
                    OpportunityReviewAction.CONDOMINIO_APROVAR.value,
                    OpportunityReviewAction.CONDOMINIO_RECUSAR.value,
                )
            ],
            key=lambda h: h["at"] or "",
        ),
        allowed_actions=allowed_actions(access, opp),
        follow_up_actions=follow_up_actions(access, opp),
        can_adjust=OpportunityReviewAction.AJUSTAR.value in allowed_actions(access, opp),
    )


@router.get("/condominiums/{condominium_id}/opportunities")
async def list_opportunities(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[OpportunityRowOut]:
    stmt = select(Opportunity).where(Opportunity.condominium_id == access.condominium_id)
    if not access.can(Permission.VIEW_OPPORTUNITY_DRAFT):
        stmt = stmt.where(Opportunity.presented_at.is_not(None))
    opps = list(await db.scalars(stmt.order_by(Opportunity.created_at.desc())))
    return await _rows(db, {access.condominium_id: access}, opps)


@router.get("/portfolio/opportunities")
async def portfolio_opportunities(
    db: DbSession, principal: CurrentPrincipal, condominium_id: uuid.UUID | None = None
) -> list[OpportunityRowOut]:
    accesses: dict[uuid.UUID, CondoAccess] = {}
    for c in await db.scalars(
        select(Condominium).where(Condominium.id.in_(principal.condominium_ids))
    ):
        if condominium_id is None or c.id == condominium_id:
            acc = await access_for(db, principal.user.id, c)
            if acc.can(Permission.VIEW):
                accesses[c.id] = acc
    if not accesses:
        return []
    opps = [
        o
        for o in await db.scalars(
            select(Opportunity)
            .where(Opportunity.condominium_id.in_(accesses))
            .order_by(Opportunity.created_at.desc())
        )
        if visible(accesses[o.condominium_id], o)
    ]
    return await _rows(db, accesses, opps)


@router.post("/condominiums/{condominium_id}/opportunities", status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    condominium_id: uuid.UUID, body: CreateIn, access: CanView, db: DbSession
) -> OpportunityDetailOut:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    try:
        opp = await create_from_finding(db, access, body.finding_id, local_today(condo.timezone))
    except OpportunityError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, opp)


@router.get("/condominiums/{condominium_id}/opportunities/{opportunity_id}")
async def get_opportunity(
    condominium_id: uuid.UUID, opportunity_id: uuid.UUID, access: CanView, db: DbSession
) -> OpportunityDetailOut:
    return await _detail(db, access, await _get(db, access, opportunity_id))


@router.post("/condominiums/{condominium_id}/opportunities/{opportunity_id}/decisions")
async def decide_opportunity(
    condominium_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    body: DecisionIn,
    access: CanView,
    db: DbSession,
) -> OpportunityDetailOut:
    opp = await _get(db, access, opportunity_id, lock=True)
    if body.action == OpportunityReviewAction.AJUSTAR:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Use o ajuste da estimativa.")
    try:
        await decide(db, access, opp, body.action, body.comment)
    except OpportunityError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, opp)


@router.post("/condominiums/{condominium_id}/opportunities/{opportunity_id}/estimate")
async def adjust_estimate(
    condominium_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    body: AdjustIn,
    access: CanView,
    db: DbSession,
) -> OpportunityDetailOut:
    opp = await _get(db, access, opportunity_id, lock=True)
    if not is_reviewer(access, opp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só a revisão CondoOS ajusta a estimativa.")
    try:
        await adjust(db, access, opp, body.model_dump(exclude={"reason"}), body.reason)
    except OpportunityError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, opp)


@router.get("/condominiums/{condominium_id}/findings/{finding_id}/opportunities")
async def opportunities_of_finding(
    condominium_id: uuid.UUID, finding_id: uuid.UUID, access: CanView, db: DbSession
) -> list[dict[str, str]]:
    rows = await db.scalars(
        select(Opportunity)
        .join(OpportunityFinding, OpportunityFinding.opportunity_id == Opportunity.id)
        .where(
            Opportunity.condominium_id == access.condominium_id,
            OpportunityFinding.finding_id == finding_id,
        )
        .order_by(Opportunity.number)
    )
    return [
        {"id": str(o.id), "number": o.number, "title": o.title, "status": o.status}
        for o in rows
        if visible(access, o)
    ]


@router.post("/condominiums/{condominium_id}/opportunities/{opportunity_id}/contracted")
async def record_contracted_route(
    condominium_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    agreed_amount: Annotated[Decimal, Form(ge=0, max_digits=14, decimal_places=2)],
    one_time_cost: Annotated[Decimal, Form(ge=0, max_digits=14, decimal_places=2)] = Decimal("0"),
    comment: Annotated[str | None, Form(max_length=1000)] = None,
) -> OpportunityDetailOut:
    """ "Contratada" with the agreement document (stored, not sent to extraction)."""
    opp = await _get(db, access, opportunity_id)
    if "registrar_contratacao" not in follow_up_actions(access, opp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta ação não está disponível.")
    limit = get_settings().max_upload_mb * 1024 * 1024
    outcome = await ingest_file(
        db,
        condominium_id=access.condominium_id,
        filename=file.filename or "acordo",
        data=await file.read(limit + 1),
        origin=DocumentOrigin.UPLOAD,
        actor_user_id=access.user_id,
        process=False,
    )
    if outcome.document_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, outcome.error or "Arquivo inválido."
        )
    try:
        await record_contracted(
            db,
            access,
            opp,
            document_id=outcome.document_id,
            agreed_amount=agreed_amount,
            one_time_cost=one_time_cost,
            comment=comment,
        )
    except OpportunityError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, opp)


@router.post("/condominiums/{condominium_id}/opportunities/{opportunity_id}/measurement")
async def measure_route(
    condominium_id: uuid.UUID, opportunity_id: uuid.UUID, access: CanView, db: DbSession
) -> OpportunityDetailOut:
    opp = await _get(db, access, opportunity_id)
    try:
        await measure_realized(db, access, opp)
    except OpportunityError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, opp)
