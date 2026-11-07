"""FastAPI dependencies for authentication and per-condominium authorization."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.auth.service import user_from_session_token
from app.config import get_settings
from app.core.audit import record_security_event
from app.core.time import utcnow
from app.db.enums import Role
from app.db.models import AppUser, CondoAssignment, Condominium, Membership, PlatformRoleGrant
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


def active_membership() -> list[ColumnElement[bool]]:
    """A membership counts while not revoked and not expired (D77)."""
    now = utcnow()
    return [
        Membership.revoked_at.is_(None),
        or_(Membership.expires_at.is_(None), Membership.expires_at > now),
    ]


async def roles_on_condominium(
    session: AsyncSession, user_id: uuid.UUID, condominium: Condominium
) -> frozenset[Role]:
    scope = [Membership.condominium_id == condominium.id]
    if condominium.management_company_id is not None:
        scope.append(Membership.management_company_id == condominium.management_company_id)
    rows = await session.scalars(
        select(Membership.role).where(
            Membership.user_id == user_id, or_(*scope), *active_membership()
        )
    )
    roles = {Role(r) for r in rows}
    now = utcnow()
    staff = await session.scalars(
        select(CondoAssignment.platform_role)
        .join(
            PlatformRoleGrant,
            and_(
                PlatformRoleGrant.user_id == CondoAssignment.user_id,
                PlatformRoleGrant.role == CondoAssignment.platform_role,
            ),
        )
        .where(
            CondoAssignment.user_id == user_id,
            CondoAssignment.condominium_id == condominium.id,
            CondoAssignment.revoked_at.is_(None),
            or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
            PlatformRoleGrant.revoked_at.is_(None),
            or_(PlatformRoleGrant.expires_at.is_(None), PlatformRoleGrant.expires_at > now),
        )
    )
    roles |= {Role(r) for r in staff}
    return frozenset(roles)


async def access_for(
    session: AsyncSession, user_id: uuid.UUID, condominium: Condominium
) -> CondoAccess:
    """Roles and per-condominium flags of a user on one condominium."""
    return CondoAccess(
        user_id=user_id,
        condominium_id=condominium.id,
        roles=await roles_on_condominium(session, user_id, condominium),
        company_reviews=condominium.management_company_reviews,
    )


NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")

ACCESS_DENIED = "security.access_denied"
PERMISSION_DENIED = "security.permission_denied"


def _route(request: Request) -> str:
    """Route template (e.g. ``/condominiums/{condominium_id}/expenses``): no ids, no query."""
    route = request.scope.get("route")
    return str(getattr(route, "path", "")) or "?"


async def get_condo_access(
    condominium_id: uuid.UUID,
    principal: CurrentPrincipal,
    session: DbSession,
    request: Request,
) -> CondoAccess:
    # 404 (not 403) so that the existence of other tenants' ids is not revealed (D15). The
    # attempt is still recorded as a security event (D78), with the requested id in details.
    access: CondoAccess | None = None
    if condominium_id in principal.condominium_ids:
        condo = await session.get(Condominium, condominium_id)
        if condo is not None:
            access = await access_for(session, principal.user.id, condo)
    if access is None or not access.roles:
        await record_security_event(
            action=ACCESS_DENIED,
            actor_user_id=principal.user.id,
            details={
                "requested_condominium_id": str(condominium_id),
                "method": request.method,
                "route": _route(request),
            },
        )
        raise NOT_FOUND
    return access


def require(permission: Permission) -> Callable[..., Awaitable[CondoAccess]]:
    async def dependency(
        request: Request, access: CondoAccess = Depends(get_condo_access)
    ) -> CondoAccess:
        if not access.can(permission):
            await record_security_event(
                action=PERMISSION_DENIED,
                actor_user_id=access.user_id,
                condominium_id=access.condominium_id,
                details={
                    "permission": permission.value,
                    "roles": sorted(r.value for r in access.roles),
                    "method": request.method,
                    "route": _route(request),
                },
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite esta ação.")
        return access

    return dependency
