"""Rules and prompts screen (D121): read only, for the CondoOS team."""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import or_, select

from app import catalog
from app.auth.deps import CurrentPrincipal
from app.core.time import utcnow
from app.db.models import Condominium, PlatformRoleGrant
from app.db.session import DbSession

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("")
async def get_catalog(db: DbSession, principal: CurrentPrincipal) -> dict[str, Any]:
    """Audit rules, prompts per purpose, reading rules, automatic checks and the action
    policy. Only CondoOS Admin and Reviewer (an active platform role)."""
    now = utcnow()
    role = await db.scalar(
        select(PlatformRoleGrant.id)
        .where(
            PlatformRoleGrant.user_id == principal.user.id,
            PlatformRoleGrant.revoked_at.is_(None),
            or_(PlatformRoleGrant.expires_at.is_(None), PlatformRoleGrant.expires_at > now),
        )
        .limit(1)
    )
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só a equipe CondoOS vê esta tela.")
    condos = list(
        await db.scalars(
            select(Condominium)
            .where(Condominium.id.in_(principal.condominium_ids))
            .order_by(Condominium.name)
        )
    )
    return await catalog.build(db, condos, date.today())
