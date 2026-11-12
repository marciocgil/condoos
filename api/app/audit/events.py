"""Continuous operation of CondoOS Audit (D125): reprocessing by event and the SLA of the
audit's pending items.

Reprocessing: a document read, a bank statement matched, a contract or an approval recorded,
or an input of the cycle-3 controls changed re-runs the audit of that month (and of the
next, whose continuity depends on it) — only for months a person already audited: the
first run of a month is always a person's decision. Events within five minutes collapse into
one job that waits a minute; the run reuses every result whose inputs did not change, so a
reprocess only replaces what the event affected. The job can be paused per condominium.

SLA: an open pending item is "em dia" in its first competence, "atenção" from the second and
"escalada" from the third once it is 30 days old; the farol sent to the síndico is "atrasado" after 7 days. The
daily job writes the escalation once in the item's history (append only). Nothing is sent
outside: the levels show in the team's screens.
"""

import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.jobs import enqueue
from app.core.time import add_months, local_today, utcnow
from app.db.enums import AuditIssueStatus, PublicationStatus
from app.db.models import (
    AuditIssue,
    AuditIssueEvent,
    AuditPeriod,
    AuditPublication,
    BankTransaction,
    Condominium,
)

logger = logging.getLogger("condoos.audit")
REPROCESS_JOB = "audit.reprocess"
SLA_JOB = "audit.sla"
DEBOUNCE = timedelta(seconds=60)
ATTENTION_MONTHS = 2
ESCALATE_MONTHS = 3
PUBLICATION_DAYS = 7
MIN_AGE_DAYS = 30


def _bucket() -> str:
    now = utcnow()
    return f"{now:%Y%m%d%H}{now.minute // 5}"


async def request_reprocess(
    session: AsyncSession, condominium_id: uuid.UUID, month: date, reason: str
) -> list[str]:
    """Queue a reprocess of ``month`` and the month after, when they were audited before.
    Returns the months queued (as AAAA-MM)."""
    first = month.replace(day=1)
    audited = set(
        await session.scalars(
            select(AuditPeriod.competence).where(
                AuditPeriod.condominium_id == condominium_id,
                AuditPeriod.competence.in_([first, add_months(first, 1)]),
            )
        )
    )
    queued = []
    for m in sorted(audited):
        key = f"{REPROCESS_JOB}:{condominium_id}:{m:%Y-%m}:{_bucket()}"
        job = await enqueue(
            session,
            REPROCESS_JOB,
            {"condominium_id": str(condominium_id), "competence": f"{m:%Y-%m}", "reason": reason},
            condominium_id=condominium_id,
            dedupe_key=key,
            run_after=utcnow() + DEBOUNCE,
        )
        if job is not None:
            queued.append(f"{m:%Y-%m}")
    return queued


async def reprocess_recent_lines(session: AsyncSession, condominium_id: uuid.UUID) -> None:
    """After a statement is matched: the months of the lines imported in the last two hours."""
    since = utcnow() - timedelta(hours=2)
    months = {
        d.replace(day=1)
        for d in await session.scalars(
            select(BankTransaction.posted_at).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.created_at >= since,
            )
        )
    }
    for m in sorted(months):
        await request_reprocess(session, condominium_id, m, "extrato")


async def reprocess_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``audit.reprocess``: {"condominium_id", "competence": "AAAA-MM", "reason"}."""
    from app.audit.run import run_audit

    condo = await session.get(Condominium, uuid.UUID(payload["condominium_id"]))
    if condo is None:
        return
    month = date.fromisoformat(payload["competence"] + "-01")
    await run_audit(
        session,
        condo,
        month,
        today=local_today(condo.timezone),
        user_id=None,
        trigger="evento",
    )


# --------------------------------------------------------------------------- SLA


def months_open(issue: AuditIssue, current: date) -> int:
    """How many competences the item has been open, counting the first one."""
    first = issue.first_competence
    end = max(issue.last_competence, current)
    return (end.year - first.year) * 12 + end.month - first.month + 1


def sla_level(issue: AuditIssue, current: date) -> str:
    if issue.status != AuditIssueStatus.ABERTA.value:
        return "resolvida"
    n = months_open(issue, current)
    # Auditing past months at once creates old items today: escalation also needs the item
    # to have been on the team's list for MIN_AGE_DAYS (time to act on it).
    created = issue.created_at.date() if issue.created_at else None
    young = created is not None and (utcnow().date() - created).days < MIN_AGE_DAYS
    if n >= ESCALATE_MONTHS and not young:
        return "escalada"
    if n >= ATTENTION_MONTHS:
        return "atencao"
    return "em_dia"


SLA_LABEL = {
    "em_dia": "Em dia",
    "atencao": "Atenção (2º mês)",
    "escalada": "Escalada (3 meses ou mais)",
    "resolvida": "Resolvida",
}


def publication_overdue(pub: AuditPublication, today: date) -> bool:
    return (
        pub.status == PublicationStatus.AGUARDANDO.value
        and (today - pub.submitted_at.date()).days > PUBLICATION_DAYS
    )


async def sla_for_condo(session: AsyncSession, condo: Condominium) -> dict[str, int]:
    """Record each escalation once (since the item last opened) and each overdue sending."""
    today = local_today(condo.timezone)
    current = add_months(today.replace(day=1), -1)
    escalated = 0
    issues = list(
        await session.scalars(
            select(AuditIssue).where(
                AuditIssue.condominium_id == condo.id,
                AuditIssue.status == AuditIssueStatus.ABERTA.value,
            )
        )
    )
    for issue in issues:
        if sla_level(issue, current) != "escalada":
            continue
        events = list(
            await session.scalars(
                select(AuditIssueEvent)
                .where(AuditIssueEvent.issue_id == issue.id)
                .order_by(AuditIssueEvent.created_at)
            )
        )
        last_open = max(
            (e.created_at for e in events if e.kind in ("aberta", "reaberta")), default=None
        )
        already = any(
            e.kind == "escalada" and (last_open is None or e.created_at >= last_open)
            for e in events
        )
        if already:
            continue
        session.add(
            AuditIssueEvent(
                condominium_id=condo.id,
                issue_id=issue.id,
                kind="escalada",
                competence=current,
                detail={"meses_aberta": months_open(issue, current)},
            )
        )
        escalated += 1
    overdue = 0
    for pub in await session.scalars(
        select(AuditPublication).where(
            AuditPublication.condominium_id == condo.id,
            AuditPublication.status == PublicationStatus.AGUARDANDO.value,
        )
    ):
        if publication_overdue(pub, today):
            overdue += 1
    await session.flush()
    if escalated or overdue:
        await record_audit(
            session,
            action="audit.sla.checked",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=None,
            condominium_id=condo.id,
            details={"escaladas": escalated, "envios_atrasados": overdue},
        )
    return {"escaladas": escalated, "envios_atrasados": overdue}


async def sla_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``audit.sla`` (daily): every condominium with an audited month."""
    ids = list(await session.scalars(select(AuditPeriod.condominium_id).distinct()))
    for condo_id in ids:
        try:
            async with session.begin_nested():
                condo = await session.get(Condominium, condo_id)
                if condo is not None:
                    await sla_for_condo(session, condo)
        except Exception:
            logger.exception("audit sla failed condominium=%s", condo_id)


async def request_reprocess_audited(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    reason: str,
    *,
    since: date | None = None,
    until: date | None = None,
    limit: int = 3,
) -> list[str]:
    """An input that is not tied to one month (an account's kind, a fund, a budget, units):
    the latest audited months (or those in ``since``..``until``, up to 12) are reprocessed."""
    stmt = select(AuditPeriod.competence).where(AuditPeriod.condominium_id == condominium_id)
    if since is not None:
        stmt = stmt.where(AuditPeriod.competence >= since.replace(day=1))
    if until is not None:
        stmt = stmt.where(AuditPeriod.competence <= until.replace(day=1))
    cap = 12 if since is not None else limit
    months = list(await session.scalars(stmt.order_by(AuditPeriod.competence.desc()).limit(cap)))
    queued: list[str] = []
    for m in sorted(months):
        key = f"{REPROCESS_JOB}:{condominium_id}:{m:%Y-%m}:{_bucket()}"
        job = await enqueue(
            session,
            REPROCESS_JOB,
            {"condominium_id": str(condominium_id), "competence": f"{m:%Y-%m}", "reason": reason},
            condominium_id=condominium_id,
            dedupe_key=key,
            run_after=utcnow() + DEBOUNCE,
        )
        if job is not None:
            queued.append(f"{m:%Y-%m}")
    return queued
