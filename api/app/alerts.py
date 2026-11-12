"""Deadline alerts (FR-026, D126).

A versioned policy (code) says when a deadline becomes an alert: a case's next action or a
task two days before and after its due date; a compliance obligation when the Compliance
situation is "vence em breve" or "vencido" (each obligation's own lead days); a contract 60
days before its end in force; the farol waiting for the síndico after 7 days. Each alert is
recorded once per target, due date and level (``antes`` or ``vencido``), shown inside the
app (channel "app"; nothing is sent out), marked as seen by a person and resolved by the
policy itself when its condition is gone (task closed, document renewed, contract amended).

Generation is idempotent: the daily job and the screens call it; what exists is kept.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import local_date, local_today, utcnow
from app.db.enums import (
    CLOSED_CASE,
    CLOSED_TASK,
    AlertKind,
    AlertStatus,
    ComplianceApplicability,
    PublicationStatus,
)
from app.db.models import (
    AuditPublication,
    CaseRecord,
    CaseTask,
    Condominium,
    Contract,
    ContractAmendment,
    DeadlineAlert,
)

logger = logging.getLogger("condoos.alerts")
ALERTS_JOB = "alerts.deadlines"
POLICY_VERSION = 1
# The alert policy v1 (FR-026): days before the due date an alert starts.
LEAD_DAYS = {
    AlertKind.ASSUNTO_PRAZO: 2,
    AlertKind.TAREFA_PRAZO: 2,
    AlertKind.CONTRATO_FIM: 60,
}
FAROL_WAIT_DAYS = 7
# Who sees each kind: the board and the team, only the síndico, or only the team.
AUDIENCE = {
    AlertKind.ASSUNTO_PRAZO: "todos",
    AlertKind.TAREFA_PRAZO: "todos",
    AlertKind.CONFORMIDADE: "todos",
    AlertKind.CONTRATO_FIM: "todos",
    AlertKind.FAROL_AGUARDANDO: "sindico",
}
KIND_LABEL = {
    AlertKind.ASSUNTO_PRAZO: "Prazo de assunto",
    AlertKind.TAREFA_PRAZO: "Prazo de tarefa",
    AlertKind.CONFORMIDADE: "Vencimento de obrigação",
    AlertKind.CONTRATO_FIM: "Fim de contrato",
    AlertKind.FAROL_AGUARDANDO: "Farol aguardando o síndico",
}


@dataclass(frozen=True)
class Wanted:
    kind: AlertKind
    target_type: str
    target_id: uuid.UUID
    title: str
    due: date
    level: str

    @property
    def key(self) -> str:
        return f"{self.kind.value}:{self.target_id}:{self.due.isoformat()}:{self.level}"


def _level(due: date, today: date, lead: int) -> str | None:
    if due < today:
        return "vencido"
    if (due - today).days <= lead:
        return "antes"
    return None


async def _wanted(session: AsyncSession, condo: Condominium, today: date) -> list[Wanted]:
    from app.compliance import rows_for

    tz = condo.timezone
    out: list[Wanted] = []
    lead = LEAD_DAYS[AlertKind.ASSUNTO_PRAZO]
    for case in await session.scalars(
        select(CaseRecord).where(
            CaseRecord.condominium_id == condo.id,
            CaseRecord.status.notin_([s.value for s in CLOSED_CASE]),
            CaseRecord.next_action_due_at.is_not(None),
        )
    ):
        assert case.next_action_due_at is not None
        due = local_date(case.next_action_due_at, tz)
        if (level := _level(due, today, lead)) is not None:
            out.append(
                Wanted(
                    AlertKind.ASSUNTO_PRAZO,
                    "case",
                    case.id,
                    f"{case.number} · {case.next_action or case.title}"[:300],
                    due,
                    level,
                )
            )
    lead = LEAD_DAYS[AlertKind.TAREFA_PRAZO]
    for task, number in (
        await session.execute(
            select(CaseTask, CaseRecord.number)
            .join(CaseRecord, CaseRecord.id == CaseTask.case_id)
            .where(
                CaseTask.condominium_id == condo.id,
                CaseTask.status.notin_([s.value for s in CLOSED_TASK]),
                CaseRecord.status.notin_([s.value for s in CLOSED_CASE]),
            )
        )
    ).all():
        due = local_date(task.due_at, tz)
        if (level := _level(due, today, lead)) is not None:
            out.append(
                Wanted(
                    AlertKind.TAREFA_PRAZO,
                    "task",
                    task.id,
                    f"{number} · {task.title}"[:300],
                    due,
                    level,
                )
            )
    for row in await rows_for(session, condo.id, today):
        ob, sit = row.obligation, row.situation
        if ob.applicability != ComplianceApplicability.APLICAVEL.value or sit.valid_until is None:
            continue
        level = {"vencido": "vencido", "vence_em_breve": "antes"}.get(sit.code)
        if level is not None:
            out.append(
                Wanted(AlertKind.CONFORMIDADE, "obligation", ob.id, ob.name, sit.valid_until, level)
            )
    lead = LEAD_DAYS[AlertKind.CONTRATO_FIM]
    contracts = list(
        await session.scalars(
            select(Contract).where(
                Contract.condominium_id == condo.id, Contract.end_date.is_not(None)
            )
        )
    )
    ends: dict[uuid.UUID, date] = {}
    for a in await session.scalars(
        select(ContractAmendment).where(
            ContractAmendment.contract_id.in_([c.id for c in contracts] or [uuid.uuid4()]),
            ContractAmendment.end_date.is_not(None),
        )
    ):
        assert a.end_date is not None
        if a.end_date > ends.get(a.contract_id, date.min):
            ends[a.contract_id] = a.end_date
    for c in contracts:
        assert c.end_date is not None
        end = max(c.end_date, ends.get(c.id, date.min))
        # An ended contract stops alerting 30 days after its end (it is history then).
        if end < today - timedelta(days=30):
            continue
        if (level := _level(end, today, lead)) is not None:
            out.append(Wanted(AlertKind.CONTRATO_FIM, "contract", c.id, c.object[:300], end, level))
    for pub in await session.scalars(
        select(AuditPublication).where(
            AuditPublication.condominium_id == condo.id,
            AuditPublication.status == PublicationStatus.AGUARDANDO.value,
        )
    ):
        due = local_date(pub.submitted_at, tz) + timedelta(days=FAROL_WAIT_DAYS)
        if due < today:
            month = str(pub.snapshot.get("competencia", ""))
            out.append(
                Wanted(
                    AlertKind.FAROL_AGUARDANDO,
                    "audit_publication",
                    pub.id,
                    f"Farol de {month[5:]}/{month[:4]} aguardando a sua apreciação",
                    due,
                    "vencido",
                )
            )
    return out


async def refresh(
    session: AsyncSession, condo: Condominium, today: date | None = None
) -> dict[str, int]:
    """Create the alerts the policy wants and resolve those whose condition is gone."""
    today = today or local_today(condo.timezone)
    wanted = {w.key: w for w in await _wanted(session, condo, today)}
    existing = {
        a.dedupe_key: a
        for a in await session.scalars(
            select(DeadlineAlert).where(DeadlineAlert.condominium_id == condo.id)
        )
    }
    created = resolved = 0
    for key, w in wanted.items():
        if key in existing:
            continue
        session.add(
            DeadlineAlert(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                kind=w.kind.value,
                target_type=w.target_type,
                target_id=w.target_id,
                title=w.title,
                due_date=w.due,
                level=w.level,
                audience=AUDIENCE[w.kind],
                channel="app",
                status=AlertStatus.CRIADO.value,
                policy_version=POLICY_VERSION,
                dedupe_key=key,
            )
        )
        created += 1
    now = utcnow()
    for key, a in existing.items():
        if a.status != AlertStatus.RESOLVIDO.value and key not in wanted:
            a.status = AlertStatus.RESOLVIDO.value
            a.resolved_at = now
            a.resolution = "condição encerrada (concluído, renovado ou venceu)"
            resolved += 1
    await session.flush()
    return {"criados": created, "resolvidos": resolved}


async def alerts_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``alerts.deadlines`` (daily): every condominium, one failing does not stop the
    others."""
    for condo_id in list(await session.scalars(select(Condominium.id))):
        try:
            async with session.begin_nested():
                condo = await session.get(Condominium, condo_id)
                if condo is not None:
                    await refresh(session, condo)
        except Exception:
            logger.exception("deadline alerts failed condominium=%s", condo_id)


def label(kind: str) -> str:
    try:
        return KIND_LABEL[AlertKind(kind)]
    except ValueError:
        return kind
