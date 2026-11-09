"""CondoOS staff access (D77): platform roles and per-condominium assignments.

A platform role (``condoos_admin`` or ``condoos_reviewer``) grants no condominium by itself.
Each condominium needs an active ``condo_assignment`` (least privilege). Everything here is
audited with ids and codes only.
"""

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import normalize_email
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import PlatformRole
from app.db.models import AppUser, CondoAssignment, PlatformRoleGrant


class PlatformError(ValueError):
    """Message shown to the operator (pt-BR)."""


async def user_by_email(session: AsyncSession, email: str) -> AppUser:
    user = await session.scalar(select(AppUser).where(AppUser.email == normalize_email(email)))
    if user is None:
        raise PlatformError("Pessoa não encontrada. Ela precisa ter sido cadastrada antes.")
    return user


async def add_person(session: AsyncSession, *, email: str, name: str) -> AppUser:
    """Register a person with no access at all, so a platform role can be granted to them
    on an empty database (the first CondoOS admin in production)."""
    normalized = normalize_email(email)
    name = name.strip()
    if "@" not in normalized or not name:
        raise PlatformError("Informe um e-mail válido e o nome.")
    if await session.scalar(select(AppUser.id).where(AppUser.email == normalized)):
        raise PlatformError("Essa pessoa já está cadastrada.")
    user = AppUser(id=uuid.uuid4(), name=name[:200], email=normalized)
    session.add(user)
    await session.flush()
    await record_audit(
        session, action="platform.person_added", object_type="app_user", object_id=user.id
    )
    return user


async def active_grant(
    session: AsyncSession, user_id: uuid.UUID, role: PlatformRole
) -> PlatformRoleGrant | None:
    now = utcnow()
    return await session.scalar(
        select(PlatformRoleGrant).where(
            PlatformRoleGrant.user_id == user_id,
            PlatformRoleGrant.role == role.value,
            PlatformRoleGrant.revoked_at.is_(None),
            or_(PlatformRoleGrant.expires_at.is_(None), PlatformRoleGrant.expires_at > now),
        )
    )


async def grant_role(
    session: AsyncSession,
    *,
    user: AppUser,
    role: PlatformRole,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> PlatformRoleGrant:
    grant = await session.scalar(
        select(PlatformRoleGrant).where(
            PlatformRoleGrant.user_id == user.id, PlatformRoleGrant.role == role.value
        )
    )
    if grant is None:
        grant = PlatformRoleGrant(id=uuid.uuid4(), user_id=user.id, role=role.value, reason=reason)
        session.add(grant)
    grant.revoked_at = None
    grant.expires_at = expires_at
    grant.reason = reason
    grant.granted_by_user_id = actor_user_id
    await session.flush()
    await record_audit(
        session,
        action="platform.role_granted",
        object_type="platform_role",
        object_id=grant.id,
        actor_user_id=actor_user_id,
        details={"role": role.value, "temporary": expires_at is not None},
    )
    return grant


async def revoke_role(
    session: AsyncSession,
    *,
    user: AppUser,
    role: PlatformRole,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    grant = await active_grant(session, user.id, role)
    if grant is None:
        raise PlatformError("Essa pessoa não tem esse papel ativo.")
    grant.revoked_at = utcnow()
    await record_audit(
        session,
        action="platform.role_revoked",
        object_type="platform_role",
        object_id=grant.id,
        actor_user_id=actor_user_id,
        details={"role": role.value},
    )


async def assign(
    session: AsyncSession,
    *,
    condominium_id: uuid.UUID,
    user: AppUser,
    role: PlatformRole,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
    valid_until: datetime | None = None,
) -> CondoAssignment:
    if await active_grant(session, user.id, role) is None:
        raise PlatformError("Essa pessoa não tem esse papel CondoOS ativo.")
    row = await session.scalar(
        select(CondoAssignment).where(
            CondoAssignment.condominium_id == condominium_id,
            CondoAssignment.user_id == user.id,
            CondoAssignment.platform_role == role.value,
        )
    )
    now = utcnow()
    if (
        row is not None
        and row.revoked_at is None
        and (row.valid_until is None or row.valid_until > now)
    ):
        raise PlatformError("Essa pessoa já está atribuída a este condomínio com esse papel.")
    if row is None:
        row = CondoAssignment(
            id=uuid.uuid4(),
            condominium_id=condominium_id,
            user_id=user.id,
            platform_role=role.value,
            reason=reason,
        )
        session.add(row)
    row.revoked_at = None
    row.valid_until = valid_until
    row.reason = reason
    row.granted_by_user_id = actor_user_id
    await session.flush()
    await record_audit(
        session,
        action="platform.assigned",
        object_type="condo_assignment",
        object_id=row.id,
        actor_user_id=actor_user_id,
        condominium_id=condominium_id,
        details={"role": role.value, "temporary": valid_until is not None},
    )
    return row


async def unassign(
    session: AsyncSession,
    *,
    assignment: CondoAssignment,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    if assignment.revoked_at is not None:
        raise PlatformError("Essa atribuição já foi removida.")
    assignment.revoked_at = utcnow()
    await record_audit(
        session,
        action="platform.unassigned",
        object_type="condo_assignment",
        object_id=assignment.id,
        actor_user_id=actor_user_id,
        condominium_id=assignment.condominium_id,
        details={"role": assignment.platform_role},
    )
