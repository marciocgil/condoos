"""Audit trail helper. Store ids and codes only, never personal data."""

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    object_type: str,
    object_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    condominium_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            action=action,
            object_type=object_type,
            object_id=object_id,
            actor_user_id=actor_user_id,
            condominium_id=condominium_id,
            details=details or {},
        )
    )


async def record_security_event(
    *,
    action: str,
    actor_user_id: uuid.UUID,
    condominium_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record a denied access in its own transaction (decision D78).

    The request transaction is rolled back when the endpoint answers 403/404, so the event
    is written separately. ``condominium_id`` is set only when the user is a member of that
    condominium (a 403); for other tenants' ids (a 404) the requested id goes in ``details``,
    because it may not exist. A failure to record never changes the response.
    """
    from app.db.session import get_app_engine, sessionmaker_for

    try:
        async with sessionmaker_for(get_app_engine())() as session, session.begin():
            await record_audit(
                session,
                action=action,
                object_type="condominium",
                actor_user_id=actor_user_id,
                condominium_id=condominium_id,
                details=details,
            )
    except Exception:  # the denial itself must still reach the client
        logger.exception("could not record security event action=%s", action)
