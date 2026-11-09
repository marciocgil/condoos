"""Continuous health of a condominium's capabilities (LF6-a, D109).

Capability states (C1..C9) are computed from the data on every read and never stored as the
truth (D89). What this module keeps is their **history**: each change of state becomes one
row in ``audit_log`` (append only), with the state before and after and why it was checked
(daily check, change of síndico, kill switch...). The first check records the starting
state. Nothing here grants or removes a permission: what an operation may do still comes
from ``readiness`` and ``app.policy``.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.actions import revalidate_approvals
from app.core.audit import record_audit
from app.db.models import AuditLog, Condominium
from app.launch.readiness import STATE_LABEL, readiness

logger = logging.getLogger("condoos.launch.health")

CAPABILITY_EVENT = "launch.capability_changed"
HEALTH_JOB = "launch.health"
HISTORY_LIMIT = 50

# Why a check ran, as shown in the history.
REASONS = {
    "diaria": "Verificação diária",
    "troca_sindico": "Troca de síndico",
    "acesso": "Mudança de acesso",
    "pausa": "Pausa ou retomada das automações",
}


async def last_states(session: AsyncSession, condo_id: uuid.UUID) -> dict[str, str]:
    """The latest recorded state of each capability (empty before the first check)."""
    rows = await session.scalars(
        select(AuditLog)
        .where(AuditLog.condominium_id == condo_id, AuditLog.action == CAPABILITY_EVENT)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    out: dict[str, str] = {}
    for row in rows:
        key = str(row.details.get("key"))
        if key not in out:
            out[key] = str(row.details.get("to"))
    return out


async def record_capability_changes(
    session: AsyncSession,
    condo_id: uuid.UUID,
    *,
    reason: str,
    actor_user_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Compare the capabilities now with the last recorded state and record each change.
    Idempotent: a second call with nothing changed records nothing."""
    previous = await last_states(session, condo_id)
    changes: list[dict[str, Any]] = []
    for r in await readiness(session, condo_id):
        before = previous.get(r.key)
        if before == r.state:
            continue
        details = {
            "key": r.key,
            "title": r.title,
            "from": before,
            "to": r.state,
            "missing": list(r.missing),
            "reason": reason,
        }
        await record_audit(
            session,
            action=CAPABILITY_EVENT,
            object_type="capability",
            actor_user_id=actor_user_id,
            condominium_id=condo_id,
            details=details,
        )
        changes.append(details)
    await session.flush()
    return changes


async def history(
    session: AsyncSession, condo_id: uuid.UUID, limit: int = HISTORY_LIMIT
) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(AuditLog)
        .where(AuditLog.condominium_id == condo_id, AuditLog.action == CAPABILITY_EVENT)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return [
        {
            "at": row.created_at.isoformat(),
            "key": row.details.get("key"),
            "title": row.details.get("title"),
            "from": row.details.get("from"),
            "to": row.details.get("to"),
            "from_label": STATE_LABEL.get(str(row.details.get("from")), None),
            "to_label": STATE_LABEL.get(str(row.details.get("to")), str(row.details.get("to"))),
            "missing": row.details.get("missing") or [],
            "reason": REASONS.get(str(row.details.get("reason")), row.details.get("reason")),
        }
        for row in rows
    ]


async def health_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Daily check of every condominium (worker role), or of one when ``condominium_id`` is
    given (a síndico just entered). One condominium failing does not stop the others; it is
    logged by id and checked again the next day."""
    only = payload.get("condominium_id")
    reason = str(payload.get("reason") or "diaria")
    ids = [uuid.UUID(str(only))] if only else list(await session.scalars(select(Condominium.id)))
    for condo_id in ids:
        try:
            async with session.begin_nested():
                # An access that expired since yesterday leaves no approval behind (LB-061).
                await revalidate_approvals(session, condo_id, user_id=None)
                await record_capability_changes(session, condo_id, reason=reason)
        except Exception:
            logger.exception("health check failed condominium=%s", condo_id)
