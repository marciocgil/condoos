"""CondoOS Launch (D88, D89): the implementation journey of a condominium.

Reading is open to whoever views the condominium; changing the goal, putting a step off or
hiding the card is for the síndico and the CondoOS admin (``MANAGE_LAUNCH``). Nothing here
grants a permission: milestones and readiness are computed from the data.
"""

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.deps import CurrentPrincipal, require
from app.auth.rbac import CondoAccess, Permission
from app.core.time import local_today
from app.db.models import Condominium, Document
from app.db.session import DbSession
from app.launch.state import (
    first_value_seen,
    overview,
    portfolio_row,
    postpone,
    set_dismissed,
    set_goal,
)
from app.routers.portfolio import _manager_condos

router = APIRouter(tags=["launch"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_LAUNCH))]


class GoalIn(BaseModel):
    goal: Literal["economizar", "pendencias", "fornecedores", "panorama"] | None


class PostponeIn(BaseModel):
    step: str


class DismissIn(BaseModel):
    dismissed: bool


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


@router.get("/condominiums/{condominium_id}/launch")
async def get_launch(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    condo = await _condo(db, access)
    out = await overview(db, condo, local_today(condo.timezone))
    out["can_manage"] = Permission.MANAGE_LAUNCH in access.permissions
    return out


@router.put("/condominiums/{condominium_id}/launch/goal")
async def put_goal(
    condominium_id: uuid.UUID, body: GoalIn, access: CanManage, db: DbSession
) -> dict[str, str | None]:
    await set_goal(db, access.condominium_id, body.goal, access.user_id)
    return {"goal": body.goal}


@router.post("/condominiums/{condominium_id}/launch/postpone")
async def post_postpone(
    condominium_id: uuid.UUID, body: PostponeIn, access: CanManage, db: DbSession
) -> dict[str, date]:
    condo = await _condo(db, access)
    try:
        until = await postpone(
            db, access.condominium_id, body.step, access.user_id, local_today(condo.timezone)
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"until": until}


@router.put("/condominiums/{condominium_id}/launch/dismissed")
async def put_dismissed(
    condominium_id: uuid.UUID, body: DismissIn, access: CanManage, db: DbSession
) -> dict[str, bool]:
    await set_dismissed(db, access.condominium_id, body.dismissed, access.user_id)
    return {"dismissed": body.dismissed}


@router.get("/condominiums/{condominium_id}/documents/{document_id}/first-value")
async def get_first_value(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    doc = await db.get(Document, document_id)
    if doc is None or doc.condominium_id != access.condominium_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return await first_value_seen(db, doc, access.user_id)


@router.get("/portfolio/launch")
async def portfolio_launch(db: DbSession, principal: CurrentPrincipal) -> list[dict[str, Any]]:
    """Implementations across the portfolio (LB-012): only condominiums the person reviews."""
    return [
        await portfolio_row(db, c, local_today(c.timezone))
        for c in await _manager_condos(db, principal)
    ]
