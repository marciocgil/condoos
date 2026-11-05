"""FastAPI dependencies for authentication and per-condominium authorization."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.auth.service import user_from_session_token
from app.config import get_settings
from app.db.enums import Role
from app.db.models import AppUser, Condominium, Membership
from app.db.session import DbSession, accessible_condominium_ids, set_tenant_scope


@dataclass(frozen=True)
class Principal:
    user: AppUser
    condominium_ids: frozenset[uuid.UUID]


async def get_principal(request: Request, session: DbSession) -> Principal:
    raw = request.cookies.get(get_settings().session_cookie_name)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão não encontrada.")
    user = await user_from_session_token(session, raw)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente.")
    ids = await accessible_condominium_ids(session, user.id)
    # Row-Level Security: from here on this transaction only sees these condominiums.
    await set_tenant_scope(session, ids)
    return Principal(user=user, condominium_ids=frozenset(ids))


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


async def roles_on_condominium(
    session: AsyncSession, user_id: uuid.UUID, condominium: Condominium
) -> frozenset[Role]:
    scope = [Membership.condominium_id == condominium.id]
    if condominium.management_company_id is not None:
        scope.append(Membership.management_company_id == condominium.management_company_id)
    rows = await session.scalars(
        select(Membership.role).where(Membership.user_id == user_id, or_(*scope))
    )
    return frozenset(Role(r) for r in rows)


NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")


async def get_condo_access(
    condominium_id: uuid.UUID,
    principal: CurrentPrincipal,
    session: DbSession,
) -> CondoAccess:
    # 404 (not 403) so that the existence of other tenants' ids is not revealed.
    if condominium_id not in principal.condominium_ids:
        raise NOT_FOUND
    condo = await session.get(Condominium, condominium_id)
    if condo is None:
        raise NOT_FOUND
    roles = await roles_on_condominium(session, principal.user.id, condo)
    if not roles:
        raise NOT_FOUND
    return CondoAccess(user_id=principal.user.id, condominium_id=condominium_id, roles=roles)


def require(permission: Permission) -> Callable[..., Awaitable[CondoAccess]]:
    async def dependency(access: CondoAccess = Depends(get_condo_access)) -> CondoAccess:
        if not access.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite esta ação.")
        return access

    return dependency
