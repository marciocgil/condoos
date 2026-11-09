"""Action requests (Aprovações, spec §7.5; VS-05, D83) and the per-condominium kill switch
(FR-007). Nothing here sends anything outside the system: an approved action waits for a
person to carry it out and record it."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.actions import (
    ActionError,
    adjust,
    allowed_actions,
    approve,
    cancel,
    create_request,
    record_execution,
    reject,
    request_changes,
    type_label,
)
from app.auth.deps import CurrentPrincipal, access_for, require
from app.auth.rbac import CondoAccess, Permission
from app.cases import user_names
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import OPEN_ACTION, ActionStatus
from app.db.models import (
    ActionDecision,
    ActionRequest,
    AutomationPause,
    CaseRecord,
    Condominium,
    Supplier,
)
from app.db.session import DbSession
from app.launch.health import record_capability_changes
from app.policy import (
    ALL_AUTOMATIONS,
    APPROVAL_VALID_DAYS,
    CATALOGUE,
    PAUSABLE_JOBS,
    POLICY_VERSION,
    REQUESTABLE_TYPES,
    ActionPayload,
    approval_limit,
)

router = APIRouter(tags=["actions"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanPause = Annotated[CondoAccess, Depends(require(Permission.CONFIGURE_POLICY))]


class ActionIn(BaseModel):
    action_type: str = Field(max_length=60)
    title: str = Field(max_length=200)
    payload: ActionPayload
    cost_cap: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    idempotency_key: str = Field(max_length=120)
    case_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None


class AdjustIn(BaseModel):
    title: str = Field(max_length=200)
    payload: ActionPayload
    cost_cap: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    comment: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    action: Literal["aprovar", "pedir_ajustes", "recusar", "cancelar"]
    # The version the person saw: approving another one is refused (frozen scope).
    payload_hash: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)


class ExecutionIn(BaseModel):
    note: str = Field(max_length=2000)
    final_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class PauseIn(BaseModel):
    automation_type: str = Field(max_length=60)
    reason: str = Field(min_length=5, max_length=500)


class ActionRowOut(BaseModel):
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    title: str
    action_type: str
    type_label: str
    status: str
    cost_cap: Decimal
    case_id: uuid.UUID | None
    case_number: str | None
    requested_by: str
    created_at: datetime
    approval_expires_at: datetime | None


class ActionDetailOut(ActionRowOut):
    level: str
    payload: dict[str, Any]
    payload_hash: str
    supplier_name: str | None
    policy_decision: str
    policy_version: int
    policy_reason: str
    approval_limit: Decimal | None
    approval_valid_days: int
    case_title: str | None
    opportunity_id: uuid.UUID | None
    approved_by: str | None
    executed_at: datetime | None
    executed_by: str | None
    execution_note: str | None
    history: list[dict[str, Any]]
    allowed_actions: list[str]


class PauseOut(BaseModel):
    id: uuid.UUID
    automation_type: str
    label: str
    reason: str
    paused_by: str
    paused_at: datetime
    resumed_at: datetime | None
    resumed_by: str | None


class PausesOut(BaseModel):
    can_pause: bool
    types: list[dict[str, str]]
    active: list[PauseOut]
    history: list[PauseOut]


def _error(exc: ActionError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


def _who(names: dict[uuid.UUID, str], user_id: uuid.UUID | None, default: str = "—") -> str:
    return names.get(user_id, default) if user_id else default


async def _get(db: DbSession, access: CondoAccess, action_id: uuid.UUID) -> ActionRequest:
    req = await db.scalar(
        select(ActionRequest).where(
            ActionRequest.id == action_id, ActionRequest.condominium_id == access.condominium_id
        )
    )
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ação não encontrada.")
    return req


async def _condo(db: DbSession, condominium_id: uuid.UUID) -> Condominium:
    condo = await db.get(Condominium, condominium_id)
    assert condo is not None
    return condo


async def _rows(db: DbSession, reqs: list[ActionRequest]) -> list[ActionRowOut]:
    names = await user_names(db, {r.requested_by_user_id for r in reqs if r.requested_by_user_id})
    condo_names = {
        c.id: c.name
        for c in await db.scalars(
            select(Condominium).where(Condominium.id.in_({r.condominium_id for r in reqs}))
        )
    }
    case_numbers = {
        c.id: c.number
        for c in await db.scalars(
            select(CaseRecord).where(CaseRecord.id.in_({r.case_id for r in reqs if r.case_id}))
        )
    }
    return [
        ActionRowOut(
            id=r.id,
            condominium_id=r.condominium_id,
            condominium_name=condo_names.get(r.condominium_id, ""),
            title=r.title,
            action_type=r.action_type,
            type_label=type_label(r.action_type),
            status=r.status,
            cost_cap=r.cost_cap,
            case_id=r.case_id,
            case_number=case_numbers.get(r.case_id) if r.case_id else None,
            requested_by=_who(names, r.requested_by_user_id, "Sistema"),
            created_at=r.created_at,
            approval_expires_at=r.approval_expires_at,
        )
        for r in reqs
    ]


def _order(reqs: list[ActionRequest]) -> list[ActionRequest]:
    """Waiting for approval first, then other open ones, then the rest; newest first."""
    rank = {ActionStatus.AGUARDANDO_APROVACAO.value: 0}
    open_values = {s.value for s in OPEN_ACTION}
    return sorted(
        reqs,
        key=lambda r: (
            rank.get(r.status, 1 if r.status in open_values else 2),
            -r.created_at.timestamp(),
        ),
    )


async def _detail(db: DbSession, access: CondoAccess, req: ActionRequest) -> ActionDetailOut:
    decisions = list(
        await db.scalars(
            select(ActionDecision)
            .where(ActionDecision.action_request_id == req.id)
            .order_by(ActionDecision.created_at, ActionDecision.id)
        )
    )
    ids = {
        u
        for u in (
            req.requested_by_user_id,
            req.approved_by_user_id,
            req.executed_by_user_id,
            *(d.user_id for d in decisions),
        )
        if u
    }
    names = await user_names(db, ids)
    (row,) = await _rows(db, [req])
    condo = await _condo(db, req.condominium_id)
    case = await db.get(CaseRecord, req.case_id) if req.case_id else None
    supplier_id = req.payload.get("supplier_id")
    supplier = await db.get(Supplier, uuid.UUID(supplier_id)) if supplier_id else None
    spec = CATALOGUE.get(req.action_type)
    return ActionDetailOut(
        **row.model_dump(),
        level=spec.level if spec else "L5",
        payload=dict(req.payload),
        payload_hash=req.payload_hash,
        supplier_name=(supplier.trade_name or supplier.legal_name) if supplier else None,
        policy_decision=req.policy_decision,
        policy_version=req.policy_version,
        policy_reason=req.policy_reason,
        approval_limit=approval_limit(condo),
        approval_valid_days=APPROVAL_VALID_DAYS,
        case_title=case.title if case else None,
        opportunity_id=req.opportunity_id,
        approved_by=_who(names, req.approved_by_user_id, "") or None,
        executed_at=req.executed_at,
        executed_by=_who(names, req.executed_by_user_id, "") or None,
        execution_note=req.execution_note,
        history=[
            {
                "at": d.created_at.isoformat(),
                "who": _who(names, d.user_id, "Sistema"),
                "kind": d.kind,
                "from_status": d.from_status,
                "to_status": d.to_status,
                "comment": d.comment,
                "payload_hash": d.payload_hash[:12],
            }
            for d in decisions
        ],
        allowed_actions=allowed_actions(access, req),
    )


@router.get("/action-types")
async def action_types() -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "types": [
            {
                "code": code,
                "label": spec.label,
                "level": spec.level,
                "zero_cost_only": spec.zero_cost_only,
            }
            for code, spec in CATALOGUE.items()
            if code in REQUESTABLE_TYPES
        ],
    }


@router.get("/condominiums/{condominium_id}/actions")
async def list_actions(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    situacao: Literal["abertas", "todas"] = "abertas",
    case_id: uuid.UUID | None = None,
) -> list[ActionRowOut]:
    stmt = select(ActionRequest).where(ActionRequest.condominium_id == access.condominium_id)
    if situacao == "abertas":
        stmt = stmt.where(ActionRequest.status.in_([s.value for s in OPEN_ACTION]))
    if case_id is not None:
        stmt = stmt.where(ActionRequest.case_id == case_id)
    return await _rows(db, _order(list(await db.scalars(stmt))))


@router.get("/portfolio/actions")
async def portfolio_actions(
    db: DbSession,
    principal: CurrentPrincipal,
    situacao: Literal["abertas", "todas"] = "abertas",
    condominium_id: uuid.UUID | None = None,
) -> list[ActionRowOut]:
    ids: list[uuid.UUID] = []
    for c in await db.scalars(
        select(Condominium).where(Condominium.id.in_(principal.condominium_ids))
    ):
        if condominium_id is not None and c.id != condominium_id:
            continue
        if (await access_for(db, principal.user.id, c)).can(Permission.VIEW):
            ids.append(c.id)
    stmt = select(ActionRequest).where(ActionRequest.condominium_id.in_(ids))
    if situacao == "abertas":
        stmt = stmt.where(ActionRequest.status.in_([s.value for s in OPEN_ACTION]))
    return await _rows(db, _order(list(await db.scalars(stmt))))


@router.post("/condominiums/{condominium_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_action(
    condominium_id: uuid.UUID, body: ActionIn, access: CanView, db: DbSession
) -> Any:
    condo = await _condo(db, access.condominium_id)
    try:
        req, created = await create_request(
            db,
            access,
            condo,
            action_type=body.action_type,
            title=body.title,
            payload=body.payload,
            cost_cap=body.cost_cap,
            idempotency_key=body.idempotency_key,
            case_id=body.case_id,
            opportunity_id=body.opportunity_id,
        )
    except ActionError as exc:
        if exc.data:
            # Denied by the policy: the denial is recorded, so answer without rolling back.
            return JSONResponse(
                status_code=exc.status, content={"detail": {"message": str(exc), **exc.data}}
            )
        raise _error(exc) from exc
    await db.flush()
    detail = await _detail(db, access, req)
    if not created:
        return JSONResponse(status_code=200, content=detail.model_dump(mode="json"))
    return detail


@router.get("/condominiums/{condominium_id}/actions/{action_id}")
async def get_action(
    condominium_id: uuid.UUID, action_id: uuid.UUID, access: CanView, db: DbSession
) -> ActionDetailOut:
    return await _detail(db, access, await _get(db, access, action_id))


@router.patch("/condominiums/{condominium_id}/actions/{action_id}")
async def adjust_action(
    condominium_id: uuid.UUID,
    action_id: uuid.UUID,
    body: AdjustIn,
    access: CanView,
    db: DbSession,
) -> ActionDetailOut:
    req = await _get(db, access, action_id)
    condo = await _condo(db, access.condominium_id)
    try:
        await adjust(
            db,
            access,
            condo,
            req,
            title=body.title,
            payload=body.payload,
            cost_cap=body.cost_cap,
            comment=body.comment,
        )
    except ActionError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/actions/{action_id}/decisions")
async def decide_action(
    condominium_id: uuid.UUID,
    action_id: uuid.UUID,
    body: DecisionIn,
    access: CanView,
    db: DbSession,
) -> ActionDetailOut:
    req = await _get(db, access, action_id)
    condo = await _condo(db, access.condominium_id)
    try:
        if body.action == "aprovar":
            await approve(
                db, access, condo, req, seen_hash=body.payload_hash or "", comment=body.comment
            )
        elif body.action == "pedir_ajustes":
            await request_changes(db, access, req, comment=body.comment)
        elif body.action == "recusar":
            await reject(db, access, req, comment=body.comment)
        else:
            await cancel(db, access, req, comment=body.comment)
    except ActionError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/actions/{action_id}/execution")
async def record_action_execution(
    condominium_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ExecutionIn,
    access: CanView,
    db: DbSession,
) -> Any:
    req = await _get(db, access, action_id)
    try:
        _, blocked = await record_execution(
            db, access, req, note=body.note, final_cost=body.final_cost
        )
    except ActionError as exc:
        raise _error(exc) from exc
    await db.flush()
    detail = await _detail(db, access, req)
    if blocked is not None:
        # The approval was voided and recorded; answer 409 without rolling that back.
        return JSONResponse(
            status_code=409,
            content={"detail": {"message": blocked, "action": detail.model_dump(mode="json")}},
        )
    return detail


# --------------------------------------------------------------------------- kill switch


def _pause_label(automation_type: str) -> str:
    if automation_type == ALL_AUTOMATIONS:
        return "Todas as automações"
    return PAUSABLE_JOBS.get(automation_type, automation_type)


async def _pauses(db: DbSession, access: CondoAccess) -> PausesOut:
    rows = list(
        await db.scalars(
            select(AutomationPause)
            .where(AutomationPause.condominium_id == access.condominium_id)
            .order_by(AutomationPause.created_at.desc())
        )
    )
    names = await user_names(
        db,
        {u for p in rows for u in (p.paused_by_user_id, p.resumed_by_user_id) if u},
    )
    out = [
        PauseOut(
            id=p.id,
            automation_type=p.automation_type,
            label=_pause_label(p.automation_type),
            reason=p.reason,
            paused_by=_who(names, p.paused_by_user_id, "Sistema"),
            paused_at=p.created_at,
            resumed_at=p.resumed_at,
            resumed_by=_who(names, p.resumed_by_user_id, "") or None,
        )
        for p in rows
    ]
    return PausesOut(
        can_pause=access.can(Permission.CONFIGURE_POLICY),
        types=[{"code": ALL_AUTOMATIONS, "label": _pause_label(ALL_AUTOMATIONS)}]
        + [{"code": k, "label": v} for k, v in PAUSABLE_JOBS.items()],
        active=[p for p in out if p.resumed_at is None],
        history=[p for p in out if p.resumed_at is not None][:20],
    )


@router.get("/condominiums/{condominium_id}/automation-pauses")
async def list_pauses(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> PausesOut:
    return await _pauses(db, access)


@router.post("/condominiums/{condominium_id}/automation-pauses", status_code=201)
async def pause_automation(
    condominium_id: uuid.UUID, body: PauseIn, access: CanPause, db: DbSession
) -> PausesOut:
    if body.automation_type != ALL_AUTOMATIONS and body.automation_type not in PAUSABLE_JOBS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Automação desconhecida.")
    existing = await db.scalar(
        select(AutomationPause).where(
            AutomationPause.condominium_id == access.condominium_id,
            AutomationPause.automation_type == body.automation_type,
            AutomationPause.resumed_at.is_(None),
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Essa automação já está pausada.")
    pause = AutomationPause(
        id=uuid.uuid4(),
        condominium_id=access.condominium_id,
        automation_type=body.automation_type,
        reason=body.reason.strip(),
        paused_by_user_id=access.user_id,
    )
    db.add(pause)
    await record_audit(
        db,
        action="automation.paused",
        object_type="automation_pause",
        object_id=pause.id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details={"automation_type": body.automation_type},
    )
    await db.flush()
    await record_capability_changes(
        db, access.condominium_id, reason="pausa", actor_user_id=access.user_id
    )
    return await _pauses(db, access)


@router.post("/condominiums/{condominium_id}/automation-pauses/{pause_id}/resume")
async def resume_automation(
    condominium_id: uuid.UUID, pause_id: uuid.UUID, access: CanPause, db: DbSession
) -> PausesOut:
    pause = await db.scalar(
        select(AutomationPause).where(
            AutomationPause.id == pause_id,
            AutomationPause.condominium_id == access.condominium_id,
        )
    )
    if pause is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pausa não encontrada.")
    if pause.resumed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Essa automação já foi retomada.")
    pause.resumed_at = utcnow()
    pause.resumed_by_user_id = access.user_id
    await record_audit(
        db,
        action="automation.resumed",
        object_type="automation_pause",
        object_id=pause.id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details={"automation_type": pause.automation_type},
    )
    await db.flush()
    await record_capability_changes(
        db, access.condominium_id, reason="pausa", actor_user_id=access.user_id
    )
    return await _pauses(db, access)
