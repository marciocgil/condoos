"""CondoOS Launch (D88, D89): the guided implementation of a condominium.

A conduction layer over the existing objects, not a new domain: milestones (``journey``) and
readiness per capability (``readiness``) are computed from the data on every read; the only
stored part is the person's choices (``launch_state``: goal, steps put off, card hidden).
A milestone never grants anything; readiness is per capability and its requirements are
binary.
"""

from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess
from app.core.audit import record_audit
from app.core.time import local_today, utcnow
from app.db.enums import LaunchGoal
from app.db.models import Condominium, LaunchState
from app.launch.journey import milestones
from app.launch.readiness import STATE_LABELS
from app.launch.readiness import readiness as capability_readiness
from app.launch.steps import STEP_KEYS, choose, pending_keys

MAX_POSTPONE_DAYS = 90
DEFAULT_POSTPONE_DAYS = 7


class LaunchError(ValueError):
    """A choice the journey does not accept (pt-BR message for the person)."""


async def get_state(session: AsyncSession, condo: Condominium) -> LaunchState | None:
    return await session.scalar(select(LaunchState).where(LaunchState.condominium_id == condo.id))


async def _state_for_update(
    session: AsyncSession, condo: Condominium, access: CondoAccess
) -> LaunchState:
    state = await get_state(session, condo)
    if state is None:
        state = LaunchState(condominium_id=condo.id, postponed={})
        session.add(state)
    state.updated_by_user_id = access.user_id
    return state


async def set_goal(
    session: AsyncSession, condo: Condominium, access: CondoAccess, goal: str | None
) -> LaunchState:
    """A goal, or ``None`` for "Prefiro decidir depois". Both answer the question."""
    if goal is not None and goal not in {g.value for g in LaunchGoal}:
        raise LaunchError("Objetivo desconhecido.")
    state = await _state_for_update(session, condo, access)
    state.goal = goal
    state.goal_answered_at = utcnow()
    await session.flush()
    await record_audit(
        session,
        action="launch.goal_selected",
        object_type="launch_state",
        object_id=state.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"goal": goal},
    )
    return state


async def postpone(
    session: AsyncSession,
    condo: Condominium,
    access: CondoAccess,
    step: str,
    until: date | None = None,
) -> LaunchState:
    """ "Fazer depois": hide a step until a date. It changes the order of suggestions only."""
    if step not in STEP_KEYS:
        raise LaunchError("Passo desconhecido.")
    today = local_today(condo.timezone)
    until = until or today + timedelta(days=DEFAULT_POSTPONE_DAYS)
    if not today <= until <= today + timedelta(days=MAX_POSTPONE_DAYS):
        raise LaunchError(f"Escolha uma data entre hoje e {MAX_POSTPONE_DAYS} dias.")
    state = await _state_for_update(session, condo, access)
    # A new dict: the JSON column is not tracked for in-place changes.
    state.postponed = {**(state.postponed or {}), step: until.isoformat()}
    await session.flush()
    await record_audit(
        session,
        action="launch.step_postponed",
        object_type="launch_state",
        object_id=state.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"step": step, "until": until.isoformat()},
    )
    return state


async def set_dismissed(
    session: AsyncSession, condo: Condominium, access: CondoAccess, dismissed: bool
) -> LaunchState:
    """Hide or show the journey card. The data and the readiness do not change."""
    state = await _state_for_update(session, condo, access)
    state.dismissed_at = utcnow() if dismissed else None
    await session.flush()
    await record_audit(
        session,
        action="launch.card_dismissed" if dismissed else "launch.card_restored",
        object_type="launch_state",
        object_id=state.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
    )
    return state


def _when(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


async def overview(session: AsyncSession, condo: Condominium) -> dict[str, Any]:
    """Everything the journey card needs, built from the data (LB-004)."""
    state = await get_state(session, condo)
    goal = state.goal if state else None
    postponed = dict(state.postponed or {}) if state else {}
    caps = await capability_readiness(session, condo)
    today = local_today(condo.timezone)
    steps = choose(await pending_keys(session, condo, caps), goal, postponed, today)
    return {
        "goal": goal,
        "goal_answered": bool(state and state.goal_answered_at),
        "dismissed": bool(state and state.dismissed_at),
        "postponed": postponed,
        "milestones": [
            {
                "key": m.key,
                "name": m.name,
                "done": m.done,
                "fact": m.fact,
                "when": _when(m.when),
                "missing": m.missing,
                "details": m.details,
            }
            for m in await milestones(session, condo)
        ],
        "readiness": [
            {
                "capability": r.capability,
                "name": r.name,
                "state": r.state,
                "state_label": STATE_LABELS[r.state],
                "requirements": [asdict(req) for req in r.requirements],
                "coverage": r.coverage,
            }
            for r in caps
        ],
        "steps": [{**asdict(s), "primary": i == 0} for i, s in enumerate(steps)],
    }
