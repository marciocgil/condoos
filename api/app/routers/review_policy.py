"""Review policy of a condominium (D74). Everyone who sees the condominium can read which
findings are reviewed before publication and by whom. The síndico or a CondoOS admin
(``configure_policy``) decides whether the management company's manager reviews. The rules
themselves are the platform default in the pilot (not editable per condominium yet)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.db.models import Condominium
from app.db.session import DbSession
from app.review import current_policy

router = APIRouter(prefix="/condominiums/{condominium_id}/review-policy", tags=["review"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanConfigurePolicy = Annotated[CondoAccess, Depends(require(Permission.CONFIGURE_POLICY))]


class ReviewPolicyOut(BaseModel):
    version: int
    condominium_specific: bool
    rules: list[dict[str, Any]]
    has_management_company: bool
    management_company_reviews: bool
    can_configure: bool


class ReviewPolicyIn(BaseModel):
    management_company_reviews: bool


async def _out(db: DbSession, access: CondoAccess, condo: Condominium) -> ReviewPolicyOut:
    policy = await current_policy(db, condo.id)
    return ReviewPolicyOut(
        version=policy.version,
        condominium_specific=policy.condominium_specific,
        rules=[r.model_dump(mode="json", exclude_none=True) for r in policy.rules],
        has_management_company=condo.management_company_id is not None,
        management_company_reviews=condo.management_company_reviews,
        can_configure=access.can(Permission.CONFIGURE_POLICY),
    )


@router.get("")
async def get_review_policy(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> ReviewPolicyOut:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return await _out(db, access, condo)


@router.put("")
async def update_review_policy(
    condominium_id: uuid.UUID, body: ReviewPolicyIn, access: CanConfigurePolicy, db: DbSession
) -> ReviewPolicyOut:
    condo = await db.get(Condominium, access.condominium_id, with_for_update=True)
    assert condo is not None
    if body.management_company_reviews and condo.management_company_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Este condomínio não tem administradora cadastrada.",
        )
    if condo.management_company_reviews != body.management_company_reviews:
        condo.management_company_reviews = body.management_company_reviews
        await record_audit(
            db,
            action="review_policy.management_company_reviews",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=access.user_id,
            condominium_id=condo.id,
            details={"value": body.management_company_reviews},
        )
    # The caller may have just removed its own review permission: recompute.
    access = CondoAccess(
        access.user_id, access.condominium_id, access.roles, condo.management_company_reviews
    )
    return await _out(db, access, condo)
