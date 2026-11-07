"""The stored part of the journey: the person's choices (``launch_state``, ADR-L01).

Every change is audited (``launch.*`` in ``audit_log``, ids only). Choosing a goal or putting
a step off changes the order of suggestions, never a permission.
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import CLOSED_CASE
from app.db.models import AuditLog, CaseRecord, Condominium, Document
from app.db.models import LaunchState as LaunchStateRow
from app.launch.first_value import first_value
from app.launch.journey import done_for_you, milestones
from app.launch.readiness import readiness
from app.launch.steps import CATALOGUE, GOALS, next_steps

POSTPONE_DAYS = 7


async def get_state(session: AsyncSession, condo_id: uuid.UUID) -> LaunchStateRow | None:
    return await session.scalar(
        select(LaunchStateRow).where(LaunchStateRow.condominium_id == condo_id)
    )


async def _ensure(session: AsyncSession, condo_id: uuid.UUID) -> LaunchStateRow:
    row = await get_state(session, condo_id)
    if row is None:
        row = LaunchStateRow(id=uuid.uuid4(), condominium_id=condo_id, postponed={})
        session.add(row)
        await session.flush()
    return row


async def set_goal(
    session: AsyncSession, condo_id: uuid.UUID, goal: str | None, user_id: uuid.UUID
) -> None:
    if goal is not None and goal not in GOALS:
        raise ValueError("Objetivo desconhecido.")
    row = await _ensure(session, condo_id)
    row.goal = goal
    row.updated_by_user_id = user_id
    await record_audit(
        session,
        action="launch.goal_selected",
        object_type="launch_state",
        object_id=row.id,
        actor_user_id=user_id,
        condominium_id=condo_id,
        details={"goal": goal},
    )


async def postpone(
    session: AsyncSession, condo_id: uuid.UUID, step: str, user_id: uuid.UUID, today: date
) -> date:
    if step not in CATALOGUE:
        raise ValueError("Passo desconhecido.")
    row = await _ensure(session, condo_id)
    until = today + timedelta(days=POSTPONE_DAYS)
    row.postponed = {**(row.postponed or {}), step: until.isoformat()}
    row.updated_by_user_id = user_id
    await record_audit(
        session,
        action="launch.step_postponed",
        object_type="launch_state",
        object_id=row.id,
        actor_user_id=user_id,
        condominium_id=condo_id,
        details={"step": step, "until": until.isoformat()},
    )
    return until


async def set_dismissed(
    session: AsyncSession, condo_id: uuid.UUID, dismissed: bool, user_id: uuid.UUID
) -> None:
    row = await _ensure(session, condo_id)
    row.dismissed_at = utcnow() if dismissed else None
    row.updated_by_user_id = user_id
    await record_audit(
        session,
        action="launch.dismissed" if dismissed else "launch.reopened",
        object_type="launch_state",
        object_id=row.id,
        actor_user_id=user_id,
        condominium_id=condo_id,
    )


async def overview(session: AsyncSession, condo: Condominium, today: date) -> dict[str, Any]:
    row = await get_state(session, condo.id)
    ready = await readiness(session, condo.id)
    open_cases = int(
        await session.scalar(
            select(func.count())
            .select_from(CaseRecord)
            .where(
                CaseRecord.condominium_id == condo.id,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
            )
        )
        or 0
    )
    goal = row.goal if row else None
    return {
        "goal": goal,
        "dismissed": bool(row and row.dismissed_at),
        "milestones": [m.as_dict() for m in await milestones(session, condo.id)],
        "readiness": [r.as_dict() for r in ready],
        "next_steps": next_steps(goal, ready, open_cases, row.postponed if row else {}, today),
        "done_for_you": await done_for_you(session, condo.id),
    }


async def first_value_seen(
    session: AsyncSession, doc: Document, user_id: uuid.UUID
) -> dict[str, Any]:
    """The card, plus a ``launch.first_value_shown`` event the first time a person sees a
    finished reading of this document (time to first value, LB-090)."""
    card = await first_value(session, doc)
    if card["state"] in ("lido", "parcial", "memoria"):
        seen = await session.scalar(
            select(AuditLog.id)
            .where(
                AuditLog.action == "launch.first_value_shown",
                AuditLog.object_id == doc.id,
                AuditLog.condominium_id == doc.condominium_id,
            )
            .limit(1)
        )
        if seen is None:
            await record_audit(
                session,
                action="launch.first_value_shown",
                object_type="document",
                object_id=doc.id,
                actor_user_id=user_id,
                condominium_id=doc.condominium_id,
                details={"state": card["state"]},
            )
    return card
