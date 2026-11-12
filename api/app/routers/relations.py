"""Relations of a document, a contract or a supplier (FR-014, D126)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app import relations
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.db.session import DbSession

router = APIRouter(tags=["relations"])

CanSee = Annotated[CondoAccess, Depends(require(Permission.VIEW_PENDING_FINDINGS))]


@router.get("/condominiums/{condominium_id}/relations/{kind}/{object_id}")
async def get_relations(
    condominium_id: uuid.UUID, kind: str, object_id: uuid.UUID, access: CanSee, db: DbSession
) -> dict[str, Any]:
    resolver = relations.RESOLVERS.get(kind)
    if resolver is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo desconhecido.")
    try:
        return await resolver(
            db,
            access.condominium_id,
            object_id,
            access.can(Permission.VIEW_OPPORTUNITY_DRAFT),
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Não encontrado.") from exc
