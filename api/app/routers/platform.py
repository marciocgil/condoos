"""CondoOS staff assigned to a condominium (D77). Only a CondoOS admin assigned to the
condominium (``manage_platform``) lists, assigns and removes."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.time import utcnow
from app.db.enums import PlatformRole
from app.db.models import AppUser, CondoAssignment
from app.db.session import DbSession
from app.platform import PlatformError, assign, unassign, user_by_email

router = APIRouter(prefix="/condominiums/{condominium_id}/assignments", tags=["platform"])
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_PLATFORM))]


class AssignmentOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    platform_role: str
    reason: str
    valid_until: datetime | None
    active: bool


class AssignmentIn(BaseModel):
    email: EmailStr
    platform_role: PlatformRole
    reason: str = Field(min_length=5, max_length=300)
    valid_until: datetime | None = None

    @field_validator("valid_until")
    @classmethod
    def _future(cls, v: datetime | None) -> datetime | None:
        if v is not None and (v.tzinfo is None or v <= utcnow()):
            raise ValueError("o fim da atribuição precisa ser uma data futura com fuso")
        return v


def _unprocessable(exc: PlatformError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


@router.get("")
async def list_assignments(
    condominium_id: uuid.UUID, access: CanManage, db: DbSession
) -> list[AssignmentOut]:
    now = utcnow()
    rows = await db.execute(
        select(CondoAssignment, AppUser.name, AppUser.email)
        .join(AppUser, AppUser.id == CondoAssignment.user_id)
        .where(CondoAssignment.condominium_id == access.condominium_id)
        .order_by(AppUser.name)
    )
    return [
        AssignmentOut(
            id=a.id,
            name=name,
            email=email,
            platform_role=a.platform_role,
            reason=a.reason,
            valid_until=a.valid_until,
            active=a.revoked_at is None and (a.valid_until is None or a.valid_until > now),
        )
        for a, name, email in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_assignment(
    condominium_id: uuid.UUID, body: AssignmentIn, access: CanManage, db: DbSession
) -> dict[str, str]:
    try:
        user = await user_by_email(db, body.email)
        row = await assign(
            db,
            condominium_id=access.condominium_id,
            user=user,
            role=body.platform_role,
            reason=body.reason.strip(),
            actor_user_id=access.user_id,
            valid_until=body.valid_until,
        )
    except PlatformError as exc:
        raise _unprocessable(exc) from exc
    return {"id": str(row.id)}


@router.delete("/{assignment_id}")
async def remove_assignment(
    condominium_id: uuid.UUID, assignment_id: uuid.UUID, access: CanManage, db: DbSession
) -> dict[str, str]:
    row = await db.scalar(
        select(CondoAssignment).where(
            CondoAssignment.id == assignment_id,
            CondoAssignment.condominium_id == access.condominium_id,
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Atribuição não encontrada.")
    if row.user_id == access.user_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Você não pode remover a própria atribuição."
        )
    try:
        await unassign(db, assignment=row, actor_user_id=access.user_id)
    except PlatformError as exc:
        raise _unprocessable(exc) from exc
    return {"message": "Atribuição removida. O acesso termina na próxima ação da pessoa."}
