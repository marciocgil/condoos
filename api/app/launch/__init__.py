"""CondoOS Launch (D88, D89): the guided implementation of a condominium.

A conduction layer over the existing objects, not a new domain: milestones (``journey``) and
readiness per capability (``readiness``) are computed from the data on every read; the only
stored part is the person's choices (``launch_state``: goal, steps put off, card hidden).
A milestone never grants anything; readiness is per capability and its requirements are
binary.
"""

import uuid
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess
from app.core.audit import record_audit
from app.core.time import local_today, utcnow
from app.db.enums import VISIBLE_TO_BOARD, DataIssueStatus, ExtractionStatus, LaunchGoal
from app.db.models import (
    AuditLog,
    CaseRecord,
    Condominium,
    Contract,
    DataIssue,
    Document,
    Finding,
    LaunchState,
)
from app.launch.first_value import CONFLICT_FIELDS, FirstValue
from app.launch.first_value import build as build_first_value
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


async def done_for_you(session: AsyncSession, condo: Condominium) -> list[dict[str, Any]]:
    """LB-008: counts of things that happened, never hours saved or savings estimated."""

    async def count(stmt: Any) -> int:
        return int(await session.scalar(stmt) or 0)

    items = [
        (
            "documentos_lidos",
            await count(
                select(func.count()).where(
                    Document.condominium_id == condo.id,
                    Document.extraction_status == ExtractionStatus.DONE.value,
                )
            ),
            ("documento lido", "documentos lidos"),
        ),
        (
            "contratos_organizados",
            await count(select(func.count()).where(Contract.condominium_id == condo.id)),
            ("contrato organizado", "contratos organizados"),
        ),
        (
            "achados_publicados",
            await count(
                select(func.count()).where(
                    Finding.condominium_id == condo.id,
                    Finding.status.in_([st.value for st in VISIBLE_TO_BOARD]),
                )
            ),
            ("ponto de atenção publicado", "pontos de atenção publicados"),
        ),
        (
            "assuntos_com_responsavel",
            await count(
                select(func.count()).where(
                    CaseRecord.condominium_id == condo.id,
                    CaseRecord.owner_user_id.is_not(None),
                )
            ),
            ("assunto com responsável", "assuntos com responsável"),
        ),
    ]
    return [
        {"key": key, "count": n, "label": f"{n} {one if n == 1 else many}"}
        for key, n, (one, many) in items
        if n > 0
    ]


async def first_value(
    session: AsyncSession, condo: Condominium, document_id: Any
) -> FirstValue | None:
    doc = await session.scalar(
        select(Document).where(Document.id == document_id, Document.condominium_id == condo.id)
    )
    if doc is None:
        return None
    # Open data issues about the contract registered from this document (D95).
    by_attr = {attr: field for field, attr in CONFLICT_FIELDS.items()}
    conflicts: dict[str, str] = {}
    for title, field_name in await session.execute(
        select(DataIssue.title, DataIssue.field_name).where(
            DataIssue.condominium_id == condo.id,
            DataIssue.subject_type == "contract",
            DataIssue.status == DataIssueStatus.ABERTO.value,
            DataIssue.subject_id.in_(
                select(Contract.id).where(Contract.source_document_id == doc.id)
            ),
        )
    ):
        if field_name in by_attr:
            conflicts[by_attr[field_name]] = title
    return build_first_value(doc, conflicts)


async def first_value_shown(
    session: AsyncSession, condo: Condominium, access: CondoAccess, card: FirstValue
) -> bool:
    """Records ``launch.first_value_shown`` once per person and document (LB-090 measures
    the time to first value from it). It is a measurement, not a milestone condition."""
    if card.status not in ("lido", "lido_parcial"):
        return False
    seen = await session.scalar(
        select(AuditLog.id).where(
            AuditLog.action == "launch.first_value_shown",
            AuditLog.actor_user_id == access.user_id,
            AuditLog.condominium_id == condo.id,
            AuditLog.object_id == uuid.UUID(card.document_id),
        )
    )
    if seen is not None:
        return False
    await record_audit(
        session,
        action="launch.first_value_shown",
        object_type="document",
        object_id=uuid.UUID(card.document_id),
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"status": card.status},
    )
    return True


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
        "done_for_you": await done_for_you(session, condo),
    }
