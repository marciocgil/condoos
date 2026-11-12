"""Deadline alerts (FR-026, D126): listed inside the app, marked as seen by a person."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app import alerts
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import AlertStatus
from app.db.models import Condominium, DeadlineAlert
from app.db.session import DbSession

router = APIRouter(tags=["alerts"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]


def _audiences(access: CondoAccess) -> set[str]:
    out = {"todos"}
    if access.can(Permission.APPROVE_AUDIT_PUBLICATION) or access.can(Permission.VIEW_AUDIT):
        out.add("sindico")
    if access.can(Permission.VIEW_PENDING_FINDINGS):
        out.add("equipe")
    return out


def _out(a: DeadlineAlert) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "kind": a.kind,
        "kind_label": alerts.label(a.kind),
        "target_type": a.target_type,
        "target_id": str(a.target_id),
        "title": a.title,
        "due_date": a.due_date,
        "level": a.level,
        "status": a.status,
        "channel": a.channel,
        "created_at": a.created_at,
        "seen_at": a.seen_at,
        "policy_version": a.policy_version,
    }


@router.get("/condominiums/{condominium_id}/alerts")
async def list_alerts(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    """Open alerts this person may see (the policy runs first, so the list is current)."""
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    await alerts.refresh(db, condo)
    rows = await db.scalars(
        select(DeadlineAlert)
        .where(
            DeadlineAlert.condominium_id == condo.id,
            DeadlineAlert.status != AlertStatus.RESOLVIDO.value,
            DeadlineAlert.audience.in_(_audiences(access)),
        )
        .order_by(DeadlineAlert.due_date, DeadlineAlert.created_at)
    )
    return {"alerts": [_out(a) for a in rows], "policy_version": alerts.POLICY_VERSION}


@router.post("/condominiums/{condominium_id}/alerts/{alert_id}/seen")
async def mark_seen(
    condominium_id: uuid.UUID, alert_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    a = await db.get(DeadlineAlert, alert_id)
    if (
        a is None
        or a.condominium_id != access.condominium_id
        or a.audience not in _audiences(access)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta não encontrado.")
    if a.status == AlertStatus.CRIADO.value:
        a.status = AlertStatus.VISTO.value
        a.seen_at = utcnow()
        a.seen_by = access.user_id
        await record_audit(
            db,
            action="alert.seen",
            object_type="deadline_alert",
            object_id=a.id,
            actor_user_id=access.user_id,
            condominium_id=a.condominium_id,
            details={"kind": a.kind, "level": a.level},
        )
    await db.flush()
    return _out(a)
