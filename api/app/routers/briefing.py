"""The day's briefing (VS-04, D82): read inside the app, per person and condominium."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, access_for, require
from app.auth.rbac import CondoAccess, Permission
from app.briefing import generate
from app.core.time import utcnow
from app.db.models import Briefing, Condominium
from app.db.session import DbSession

router = APIRouter(tags=["briefing"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]


class BriefingOut(BaseModel):
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    local_date: date
    version: int
    timezone: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    read_at: datetime | None
    headline: str
    sections: list[dict[str, Any]]
    partial_sources: list[dict[str, Any]]


def _out(b: Briefing, condo: Condominium) -> BriefingOut:
    return BriefingOut(
        id=b.id,
        condominium_id=b.condominium_id,
        condominium_name=condo.name,
        local_date=b.local_date,
        version=b.version,
        timezone=b.timezone,
        period_start=b.period_start,
        period_end=b.period_end,
        generated_at=b.generated_at,
        read_at=b.read_at,
        headline=str(b.content.get("headline", "")),
        sections=list(b.content.get("sections", [])),
        partial_sources=list(b.partial_sources),
    )


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


@router.get("/condominiums/{condominium_id}/briefing")
async def get_briefing(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> BriefingOut:
    """Today's briefing; created on the first visit of the day."""
    condo = await _condo(db, access)
    return _out(await generate(db, access, condo), condo)


@router.post("/condominiums/{condominium_id}/briefing/refresh")
async def refresh_briefing(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> BriefingOut:
    """A new version with what changed since the previous one (the old one is kept)."""
    condo = await _condo(db, access)
    return _out(await generate(db, access, condo, refresh=True), condo)


@router.post("/condominiums/{condominium_id}/briefing/{briefing_id}/read")
async def mark_read(
    condominium_id: uuid.UUID, briefing_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, str]:
    """Records that the person opened it (VS-04: "registrar recebimento")."""
    b = await db.scalar(
        select(Briefing).where(
            Briefing.id == briefing_id,
            Briefing.condominium_id == access.condominium_id,
            Briefing.user_id == access.user_id,
        )
    )
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Briefing não encontrado.")
    if b.read_at is None:
        b.read_at = utcnow()
    return {"read_at": b.read_at.isoformat()}


@router.get("/portfolio/briefing")
async def portfolio_briefing(db: DbSession, principal: CurrentPrincipal) -> list[BriefingOut]:
    """One briefing per condominium the person reaches: never mixed together."""
    out = []
    condos = await db.scalars(
        select(Condominium)
        .where(Condominium.id.in_(principal.condominium_ids))
        .order_by(Condominium.name)
    )
    for condo in condos:
        access = await access_for(db, principal.user.id, condo)
        if access.can(Permission.VIEW):
            out.append(_out(await generate(db, access, condo), condo))
    return out
