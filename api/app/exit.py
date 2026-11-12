"""The síndico leaves a condominium (D127 decision 4, D129).

Leaving ends the person's access and pauses the automations, and deletes nothing: documents
and history stay under the condominium's retention, waiting for the next síndico. The exit
may be today or on a later date (the end of the mandate, say); until then it can be undone.

No table of its own: the exit is the síndico's membership (``revoked_at`` today, or
``expires_at`` at the end of the chosen day in the condominium's time zone) plus the mandate's
``term_end``, and the trail in ``audit_log`` (scheduled, cancelled, applied) is the record.
A later exit is applied by the daily health job the day after its date.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import active_membership
from app.core.audit import record_audit
from app.core.changes import record_change
from app.core.time import local_today, utcnow
from app.db.enums import BoardPosition, Role
from app.db.models import AuditLog, AutomationPause, BoardMember, Condominium, Membership

SCHEDULED = "condominium.exit_scheduled"
CANCELLED = "condominium.exit_cancelled"
APPLIED = "condominium.exit_applied"
MAX_DAYS_AHEAD = 90
REASONS: dict[str, str] = {
    "fim_mandato": "Fim do mandato",
    "renuncia": "Renúncia",
    "destituicao": "Destituição em assembleia",
    "contrato": "Fim do contrato com o condomínio",
    "outro": "Outro motivo",
}


class ExitError(ValueError):
    pass


@dataclass(frozen=True)
class PendingExit:
    event_id: uuid.UUID
    user_id: uuid.UUID
    on: date
    reason: str
    previous_expires_at: str | None
    previous_term_end: str | None

    def as_dict(self) -> dict[str, Any]:
        return {"on": self.on.isoformat(), "reason": self.reason}


async def sindico_membership(
    session: AsyncSession, condo_id: uuid.UUID, user_id: uuid.UUID
) -> Membership | None:
    return await session.scalar(
        select(Membership).where(
            Membership.condominium_id == condo_id,
            Membership.user_id == user_id,
            Membership.role == Role.SINDICO.value,
            *active_membership(),
        )
    )


async def pending_exit(
    session: AsyncSession, condo_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> PendingExit | None:
    """The latest exit scheduled that no cancellation or application refers to. Events of one
    transaction share their timestamp, so the link is by id (``saida``), never by order."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.condominium_id == condo_id, AuditLog.action == SCHEDULED)
        .order_by(AuditLog.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(AuditLog.details["sindico"].as_string() == str(user_id))
    closed = set(
        await session.scalars(
            select(AuditLog.details["saida"].as_string()).where(
                AuditLog.condominium_id == condo_id,
                AuditLog.action.in_([CANCELLED, APPLIED]),
            )
        )
    )
    last = next((e for e in await session.scalars(stmt) if str(e.id) not in closed), None)
    if last is None:
        return None
    d = last.details
    return PendingExit(
        event_id=last.id,
        user_id=uuid.UUID(d["sindico"]),
        on=date.fromisoformat(d["vale_em"]),
        reason=d.get("motivo") or "",
        previous_expires_at=d.get("expires_at_anterior"),
        previous_term_end=d.get("fim_mandato_anterior"),
    )


def _end_of_day(day: date, timezone: str | None) -> datetime:
    zone = ZoneInfo(timezone or "America/Sao_Paulo")
    return datetime.combine(day + timedelta(days=1), time.min, zone)


async def _mandate(
    session: AsyncSession, condo_id: uuid.UUID, user_id: uuid.UUID
) -> BoardMember | None:
    return await session.scalar(
        select(BoardMember)
        .where(
            BoardMember.condominium_id == condo_id,
            BoardMember.position == BoardPosition.SINDICO.value,
            BoardMember.user_id == user_id,
        )
        .order_by(BoardMember.term_start.desc())
        .limit(1)
    )


async def mandate_end(
    session: AsyncSession, condo_id: uuid.UUID, user_id: uuid.UUID
) -> date | None:
    member = await _mandate(session, condo_id, user_id)
    return member.term_end if member else None


async def schedule_exit(
    session: AsyncSession,
    condo: Condominium,
    user_id: uuid.UUID,
    *,
    reason_code: str,
    note: str,
    on: date,
) -> PendingExit | None:
    """Today: the access ends now and the automations stop. A later date: the access ends at
    the end of that day and the daily check applies the rest. Returns the pending exit (None
    when it was applied now)."""
    if reason_code not in REASONS:
        raise ExitError("Motivo desconhecido.")
    clean = note.strip()
    if reason_code == "outro" and len(clean) < 5:
        raise ExitError("Conte em poucas palavras o motivo.")
    today = local_today(condo.timezone)
    membership = await sindico_membership(session, condo.id, user_id)
    if membership is None:
        raise ExitError("Você não é síndico deste condomínio.")
    # Up to 90 days ahead, or exactly the end of the mandate (which may be further away).
    end = await mandate_end(session, condo.id, user_id)
    if on < today or (on > today + timedelta(days=MAX_DAYS_AHEAD) and on != end):
        raise ExitError(
            f"Escolha uma data entre hoje e os próximos {MAX_DAYS_AHEAD} dias, "
            "ou o fim do mandato."
        )
    if await pending_exit(session, condo.id, user_id) is not None:
        raise ExitError("Sua saída já está marcada; desfaça antes de marcar outra.")
    member = await _mandate(session, condo.id, user_id)
    previous_expires = membership.expires_at
    previous_term = member.term_end if member else None
    if on == today:
        membership.revoked_at = utcnow()
    else:
        membership.expires_at = _end_of_day(on, condo.timezone)
    if member is not None and (member.term_end is None or member.term_end > on):
        member.term_end = on
    await session.flush()
    label = REASONS[reason_code] + (f": {clean}" if clean else "")
    await record_change(
        session,
        action=SCHEDULED,
        object_type="membership",
        object_id=membership.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        before={"expires_at": previous_expires, "term_end": previous_term},
        after={
            "expires_at": membership.expires_at,
            "revoked_at": membership.revoked_at,
            "term_end": member.term_end if member else None,
        },
        reason=label,
        extra={
            "sindico": str(user_id),
            "vale_em": on.isoformat(),
            "codigo_motivo": reason_code,
            "expires_at_anterior": previous_expires.isoformat() if previous_expires else None,
            "fim_mandato_anterior": previous_term.isoformat() if previous_term else None,
        },
    )
    await session.flush()
    pending = await pending_exit(session, condo.id, user_id)
    if on == today and pending is not None:
        await apply_exit(session, condo, pending, actor_user_id=user_id)
        return None
    return pending


async def cancel_exit(session: AsyncSession, condo: Condominium, user_id: uuid.UUID) -> None:
    """Undo a later exit before its date: the access and the mandate go back to what they
    were. An exit already applied is not undone here (a new access is a new invitation)."""
    pending = await pending_exit(session, condo.id, user_id)
    if pending is None:
        raise ExitError("Não há saída marcada.")
    membership = await sindico_membership(session, condo.id, user_id)
    if membership is None:
        raise ExitError("A saída já aconteceu.")
    membership.expires_at = (
        datetime.fromisoformat(pending.previous_expires_at) if pending.previous_expires_at else None
    )
    member = await _mandate(session, condo.id, user_id)
    if member is not None and member.term_end == pending.on:
        member.term_end = (
            date.fromisoformat(pending.previous_term_end) if pending.previous_term_end else None
        )
    await session.flush()
    await record_change(
        session,
        action=CANCELLED,
        object_type="membership",
        object_id=membership.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        before={"vale_em": pending.on},
        after={"vale_em": None},
        reason="Saída desfeita pelo síndico",
        extra={"sindico": str(user_id), "saida": str(pending.event_id)},
    )


async def apply_exit(
    session: AsyncSession,
    condo: Condominium,
    pending: PendingExit,
    *,
    actor_user_id: uuid.UUID | None,
) -> None:
    """What happens when the exit is in force: approvals given by the person go back to
    approval and, when no síndico is left, every automation of the condominium is paused
    (resumed by the CondoOS team or the next síndico). Nothing is deleted."""
    from app.actions import revalidate_approvals
    from app.launch.health import record_capability_changes
    from app.policy import ALL_AUTOMATIONS

    reverted = await revalidate_approvals(session, condo.id, user_id=actor_user_id)
    others = int(
        await session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.condominium_id == condo.id,
                Membership.role == Role.SINDICO.value,
                Membership.user_id != pending.user_id,
                *active_membership(),
            )
        )
        or 0
    )
    paused = False
    if others == 0:
        existing = await session.scalar(
            select(AutomationPause.id).where(
                AutomationPause.condominium_id == condo.id,
                AutomationPause.automation_type == ALL_AUTOMATIONS,
                AutomationPause.resumed_at.is_(None),
            )
        )
        if existing is None:
            pause = AutomationPause(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                automation_type=ALL_AUTOMATIONS,
                reason=f"Saída do síndico em {pending.on:%d/%m/%Y}: aguardando o próximo.",
                paused_by_user_id=actor_user_id,
            )
            session.add(pause)
            await session.flush()
            await record_audit(
                session,
                action="automation.paused",
                object_type="automation_pause",
                object_id=pause.id,
                actor_user_id=actor_user_id,
                condominium_id=condo.id,
                details={"automation_type": ALL_AUTOMATIONS, "origem": "saida_sindico"},
            )
        paused = True
    await record_audit(
        session,
        action=APPLIED,
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=actor_user_id,
        condominium_id=condo.id,
        details={
            "sindico": str(pending.user_id),
            "saida": str(pending.event_id),
            "automacoes_pausadas": paused,
            "aprovacoes_devolvidas": reverted,
        },
    )
    await session.flush()
    await record_capability_changes(
        session, condo.id, reason="troca_sindico", actor_user_id=actor_user_id
    )


async def apply_due_exits(session: AsyncSession, condo: Condominium) -> bool:
    """Daily (health job): a later exit whose day has passed is applied once."""
    pending = await pending_exit(session, condo.id)
    if pending is None or pending.on >= local_today(condo.timezone):
        return False
    await apply_exit(session, condo, pending, actor_user_id=None)
    return True


DECISION_LABEL = {
    "validar": "Validou",
    "descartar": "Descartou",
    "confirmar": "Confirmou",
    "contestar": "Contestou",
    "ignorar": "Ignorou",
    "reabrir": "Reabriu",
    "solicitar_evidencia": "Pediu evidência",
}


async def period_dossier(
    session: AsyncSession, condo: Condominium, user_id: uuid.UUID, user_name: str
) -> dict[str, Any]:
    """What the síndico leaves behind, from records only: the faróis they approved, their
    decisions, the documents received in the period and what stays open for the next one."""
    from app.db.enums import CLOSED_CASE, ActionStatus, FindingStatus, PublicationStatus
    from app.db.models import (
        ActionRequest,
        AuditPublication,
        CaseRecord,
        Decision,
        Document,
        Finding,
    )
    from app.reports.data import DOC_TYPE_LABEL

    cid = condo.id
    member = await _mandate(session, cid, user_id)
    membership = await session.scalar(
        select(Membership)
        .where(
            Membership.condominium_id == cid,
            Membership.user_id == user_id,
            Membership.role == Role.SINDICO.value,
        )
        .order_by(Membership.created_at.desc())
        .limit(1)
    )
    today = local_today(condo.timezone)
    start = member.term_start if member else (membership.created_at.date() if membership else today)
    end = min(member.term_end, today) if member and member.term_end else today
    since = datetime.combine(start, time.min, ZoneInfo(condo.timezone or "America/Sao_Paulo"))

    farois = [
        {
            "competencia": p.snapshot.get("competencia"),
            "decided_at": p.decided_at,
            **{k.lower(): v for k, v in (p.snapshot.get("contagem") or {}).items()},
        }
        for p in await session.scalars(
            select(AuditPublication)
            .where(
                AuditPublication.condominium_id == cid,
                AuditPublication.decided_by == user_id,
                AuditPublication.status == PublicationStatus.APROVADA.value,
            )
            .order_by(AuditPublication.decided_at)
        )
    ]
    decisions = [
        (DECISION_LABEL.get(action, action), int(n))
        for action, n in await session.execute(
            select(Decision.action, func.count())
            .where(Decision.condominium_id == cid, Decision.user_id == user_id)
            .group_by(Decision.action)
            .order_by(func.count().desc())
        )
    ]
    documents = [
        (DOC_TYPE_LABEL.get(t, t), int(n))
        for t, n in await session.execute(
            select(Document.doc_type, func.count())
            .where(Document.condominium_id == cid, Document.created_at >= since)
            .group_by(Document.doc_type)
            .order_by(func.count().desc())
        )
    ]
    open_findings = list(
        await session.scalars(
            select(Finding.title)
            .where(Finding.condominium_id == cid, Finding.status == FindingStatus.PUBLICADO.value)
            .order_by(Finding.amount_at_risk.desc())
        )
    )
    open_cases = [
        f"{n} — {t}"
        for n, t in await session.execute(
            select(CaseRecord.number, CaseRecord.title)
            .where(
                CaseRecord.condominium_id == cid,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
            )
            .order_by(CaseRecord.number)
        )
    ]
    waiting_farol = await session.scalar(
        select(func.count())
        .select_from(AuditPublication)
        .where(
            AuditPublication.condominium_id == cid,
            AuditPublication.status == PublicationStatus.AGUARDANDO.value,
        )
    )
    open_actions = await session.scalar(
        select(func.count())
        .select_from(ActionRequest)
        .where(
            ActionRequest.condominium_id == cid,
            ActionRequest.status.in_(
                [ActionStatus.AGUARDANDO_APROVACAO.value, ActionStatus.ENFILEIRADA.value]
            ),
        )
    )
    return {
        "condominium": condo.name,
        "cnpj": condo.cnpj,
        "sindico": user_name,
        "start": start,
        "end": end,
        "retention_years": condo.retention_years,
        "farois": farois,
        "decisions": decisions,
        "documents": documents,
        "open_findings": open_findings,
        "open_cases": open_cases,
        "waiting_farol": int(waiting_farol or 0),
        "open_actions": int(open_actions or 0),
    }
