"""The síndico leaves a condominium (D129): what happens, the date, undo and the dossier."""

import asyncio
import uuid
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app import exit as ex
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import local_today, utcnow
from app.db.models import AppUser, Condominium
from app.db.session import DbSession

router = APIRouter(tags=["exit"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


async def _own(db: DbSession, access: CondoAccess) -> None:
    """Only the síndico leaves, and only for themself (anyone else: 403)."""
    if await ex.sindico_membership(db, access.condominium_id, access.user_id) is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o síndico encerra a própria saída.")


@router.get("/condominiums/{condominium_id}/exit")
async def get_exit(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    condo = await _condo(db, access)
    sindico = await ex.sindico_membership(db, condo.id, access.user_id) is not None
    today = local_today(condo.timezone)
    pending = await ex.pending_exit(db, condo.id, access.user_id) if sindico else None
    end = await ex.mandate_end(db, condo.id, access.user_id) if sindico else None
    return {
        "condominium": {"id": str(condo.id), "name": condo.name},
        "can_exit": sindico,
        "pending": pending.as_dict() if pending else None,
        "today": today.isoformat(),
        "max_date": (today + timedelta(days=ex.MAX_DAYS_AHEAD)).isoformat(),
        "mandate_end": end.isoformat() if end and today <= end else None,
        "retention_years": condo.retention_years,
        "reasons": [{"key": k, "label": v} for k, v in ex.REASONS.items()],
    }


class ExitIn(BaseModel):
    reason: str
    note: str = Field(default="", max_length=300)
    on: date


@router.post("/condominiums/{condominium_id}/exit")
async def schedule(
    condominium_id: uuid.UUID, body: ExitIn, access: CanView, db: DbSession
) -> dict[str, Any]:
    await _own(db, access)
    condo = await _condo(db, access)
    try:
        pending = await ex.schedule_exit(
            db, condo, access.user_id, reason_code=body.reason, note=body.note, on=body.on
        )
    except ex.ExitError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"applied": pending is None, "pending": pending.as_dict() if pending else None}


@router.post("/condominiums/{condominium_id}/exit/cancel")
async def cancel(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, str]:
    await _own(db, access)
    condo = await _condo(db, access)
    try:
        await ex.cancel_exit(db, condo, access.user_id)
    except ex.ExitError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"message": "Saída desfeita. Seu acesso continua como antes."}


@router.get("/condominiums/{condominium_id}/exit/dossier.pdf")
async def dossier(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> Response:
    """The síndico's period, downloaded before leaving (or until the exit date)."""
    from app.reports.pdf import exit_dossier_pdf

    await _own(db, access)
    condo = await _condo(db, access)
    user = await db.get(AppUser, access.user_id)
    data = await ex.period_dossier(db, condo, access.user_id, user.name if user else "—")
    body = await asyncio.to_thread(exit_dossier_pdf, data, utcnow())
    await record_audit(
        db,
        action="condominium.exit_dossier_exported",
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
    )
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="dossie-periodo-{condo.slug}.pdf"'},
    )
