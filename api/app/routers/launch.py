"""CondoOS Launch (D88, D89): the implementation journey of a condominium.

Reading is open to whoever views the condominium; choosing the goal, putting a step off or
hiding the card is for the síndico and the assigned CondoOS admin (``MANAGE_LAUNCH``). These
are preferences: they change the order of suggestions, never what anyone may do.
"""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.db.models import Condominium
from app.db.session import DbSession
from app.launch import (
    LaunchError,
    first_value,
    first_value_shown,
    overview,
    postpone,
    set_dismissed,
    set_goal,
)

router = APIRouter(prefix="/condominiums/{condominium_id}/launch", tags=["launch"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_LAUNCH))]


class GoalIn(BaseModel):
    goal: str | None = Field(default=None, max_length=20)  # None: "Prefiro decidir depois"


class PostponeIn(BaseModel):
    step: str = Field(max_length=40)
    until: date | None = None


class DismissIn(BaseModel):
    dismissed: bool


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


@router.get("")
async def get_launch(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    """Milestones, readiness per capability and up to three next steps."""
    return await overview(db, await _condo(db, access))


@router.put("/goal")
async def put_goal(
    condominium_id: uuid.UUID, body: GoalIn, access: CanManage, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        await set_goal(db, condo, access, body.goal)
    except LaunchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await overview(db, condo)


@router.post("/postpone")
async def post_postpone(
    condominium_id: uuid.UUID, body: PostponeIn, access: CanManage, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        await postpone(db, condo, access, body.step, body.until)
    except LaunchError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return await overview(db, condo)


@router.post("/dismiss")
async def post_dismiss(
    condominium_id: uuid.UUID, body: DismissIn, access: CanManage, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    await set_dismissed(db, condo, access, body.dismissed)
    return await overview(db, condo)


@router.get("/first-value/{document_id}")
async def get_first_value(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    """The first-value card of a document (LB-006): what was read, from where, and what is
    still to confirm. ``status`` is ``lendo`` while the document is being processed."""
    card = await first_value(db, await _condo(db, access), document_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return card.as_dict()


@router.post("/first-value/{document_id}/shown")
async def post_first_value_shown(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, bool]:
    """The card was on the person's screen (measurement only, once per person and document)."""
    condo = await _condo(db, access)
    card = await first_value(db, condo, document_id)
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return {"recorded": await first_value_shown(db, condo, access, card)}
