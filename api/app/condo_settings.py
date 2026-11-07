"""Versioned approval limits and rule parameters (CB-012, D85).

``condominium.approval_limits`` and ``condominium.rule_params`` keep the current values, as
before. Every change also writes a new ``condominium_settings_version`` row (append only) with
who changed it, why and from when. Rules evaluate a month with the version in force at the end
of that month; months before the first version use the first one.
"""

import uuid
from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.models import Condominium, CondominiumSettingsVersion


async def _versions(
    session: AsyncSession, condominium_id: uuid.UUID
) -> list[CondominiumSettingsVersion]:
    return list(
        await session.scalars(
            select(CondominiumSettingsVersion)
            .where(CondominiumSettingsVersion.condominium_id == condominium_id)
            .order_by(CondominiumSettingsVersion.version)
        )
    )


async def ensure_baseline(session: AsyncSession, condo: Condominium) -> None:
    """Version 1 with the values as they are now, if the condominium has no version yet
    (created after migration 0017 by the seed). Call before changing the values."""
    count = await session.scalar(
        select(func.count())
        .select_from(CondominiumSettingsVersion)
        .where(CondominiumSettingsVersion.condominium_id == condo.id)
    )
    if not count:
        session.add(
            CondominiumSettingsVersion(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                version=1,
                approval_limits=dict(condo.approval_limits or {}),
                rule_params=dict(condo.rule_params or {}),
                reason="Versão inicial",
                valid_from=utcnow(),  # earlier months use the first version anyway
            )
        )
        await session.flush()


async def record_version(
    session: AsyncSession,
    condo: Condominium,
    *,
    actor_user_id: uuid.UUID | None,
    reason: str | None,
) -> CondominiumSettingsVersion:
    """A new version with the condominium's current values, in force from now."""
    last = await session.scalar(
        select(func.max(CondominiumSettingsVersion.version)).where(
            CondominiumSettingsVersion.condominium_id == condo.id
        )
    )
    row = CondominiumSettingsVersion(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        version=(last or 0) + 1,
        approval_limits=dict(condo.approval_limits or {}),
        rule_params=dict(condo.rule_params or {}),
        changed_by_user_id=actor_user_id,
        reason=(reason or "").strip()[:300] or None,
        valid_from=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


async def settings_at(
    session: AsyncSession, condo: Condominium, day: date
) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """(approval limits, rule params, version) in force at the end of ``day``."""
    versions = await _versions(session, condo.id)
    if not versions:
        return dict(condo.approval_limits or {}), dict(condo.rule_params or {}), None
    moment = datetime.combine(day, time.max, tzinfo=UTC)
    chosen = versions[0]
    for v in versions:
        if v.valid_from <= moment:
            chosen = v
    return dict(chosen.approval_limits), dict(chosen.rule_params), chosen.version


async def history(
    session: AsyncSession, condominium_id: uuid.UUID, limit: int = 10
) -> list[CondominiumSettingsVersion]:
    return list(reversed((await _versions(session, condominium_id))[-limit:]))
