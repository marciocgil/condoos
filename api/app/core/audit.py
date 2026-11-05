"""Audit trail helper. Store ids and codes only, never personal data."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


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
