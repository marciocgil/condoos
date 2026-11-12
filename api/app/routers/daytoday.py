"""The síndico's day to day of one condominium (D127)."""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.time import local_today
from app.daytoday import day_to_day
from app.db.models import Condominium
from app.db.session import DbSession

router = APIRouter(tags=["day-to-day"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]


@router.get("/condominiums/{condominium_id}/day")
async def get_day(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    month = None
    if competencia:
        try:
            month = date(int(competencia[:4]), int(competencia[5:7]), 1)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Competência inválida (AAAA-MM)."
            ) from exc
    out = await day_to_day(db, condo, local_today(condo.timezone), month)
    out["can_upload"] = access.can(Permission.UPLOAD_DOCUMENT)
    return out
