"""The day's briefing (VS-04, FR-032; D82): what needs the person, built by code from the
records of one condominium only.

Rules (Plano Diretor VS-04, spec §13.1, US-008):
- every item comes from a record and points to it (``ref``); nothing is invented, and
  "Concluído" lists only what has a recorded event in the period;
- one condominium per briefing (``condominium_id`` filter + RLS): information never mixes;
- each source is read on its own savepoint: if it fails or is stale, the briefing still
  comes out and says which source is partial;
- the period runs from the person's previous briefing (or the last 24 h) in the
  condominium's time zone; a refresh is a new version, never an edit;
- delivered inside the app only (Plano D-04): no e-mail, no message.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agenda import condominium_agenda
from app.auth.rbac import CondoAccess, Permission
from app.core.time import DEFAULT_TIMEZONE, local_today, utcnow
from app.db.enums import (
    CLOSED_CASE,
    CLOSED_TASK,
    UNDER_REVIEW,
    VISIBLE_TO_BOARD,
    ActionStatus,
    CaseSeverity,
    FindingStatus,
)
from app.db.models import (
    ActionRequest,
    AppUser,
    BankTransaction,
    Briefing,
    CaseEvent,
    CaseRecord,
    CaseTask,
    Condominium,
    Decision,
    DelegationRequest,
    Document,
    Expense,
    Finding,
    MatchIssue,
    Opportunity,
    OpportunityReview,
    SavingsRecord,
)
from app.opportunities import is_reviewer

logger = logging.getLogger(__name__)

STALE_DAYS = 35  # no document or bank entry for longer than this: data may be partial
MAX_ITEMS = 8
STAGE_LABEL = {
    "potencial": "Economia potencial identificada",
    "estimada_validada": "Economia estimada validada",
    "aprovada": "Economia aprovada para execução",
    "contratada": "Economia contratada ou negociada",
    "realizada": "Economia realizada e comprovada",
}
BOARD_STAGES = ("estimada_validada", "aprovada", "contratada", "realizada")
CASE_STATUS = {
    "resolvido": "resolvido",
    "cancelado": "cancelado",
}
DECISION_VERB = {
    "confirmar": "confirmado",
    "contestar": "contestado",
    "ignorar": "ignorado",
    "validar": "validado",
    "descartar": "descartado",
    "reabrir": "reaberto",
    "solicitar_evidencia": "com evidência pedida",
}
OPP_VERB = {
    "aprovar": "aprovada na revisão CondoOS",
    "condominio_aprovar": "aprovada pelo condomínio",
    "condominio_recusar": "recusada pelo condomínio",
    "rejeitar": "rejeitada na revisão",
    "devolver": "devolvida para ajuste",
}


def _count(n: int, one: str, many: str) -> str:
    return "" if n == 0 else f"1 {one}" if n == 1 else f"{n} {many}"


def _brl(value: Decimal | str) -> str:
    q = Decimal(str(value)).quantize(Decimal("0.01"))
    whole, cents = f"{q:,.2f}".split(".")
    return f"R$ {whole.replace(',', '.')},{cents}"


COMPLIANCE_SOON_DAYS = 30


def _item(
    kind: str,
    title: str,
    detail: str = "",
    *,
    ref: tuple[str, uuid.UUID] | None = None,
    when: datetime | date | None = None,
    tone: str = "neutral",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "ref": {"type": ref[0], "id": str(ref[1])} if ref else None,
        "when": when.isoformat() if when else None,
        "tone": tone,
    }


class Builder:
    def __init__(
        self,
        session: AsyncSession,
        access: CondoAccess,
        condo: Condominium,
        period_start: datetime,
        now: datetime,
    ) -> None:
        self.s = session
        self.access = access
        self.condo = condo
        self.cid = condo.id
        self.uid = access.user_id
        self.start = period_start
        self.now = now
        self.today = local_today(condo.timezone)
        self.partial: list[dict[str, Any]] = []

    async def _safe(
        self, source: str, label: str, fn: Callable[[], Awaitable[list[dict[str, Any]]]]
    ) -> list[dict[str, Any]]:
        try:
            async with self.s.begin_nested():  # a failing source does not abort the others
                return await fn()
        except Exception:
            logger.exception("briefing source failed source=%s condominium=%s", source, self.cid)
            self.partial.append(
                {
                    "source": source,
                    "label": label,
                    "reason": "Não foi possível ler esta fonte agora.",
                }
            )
            return []

    # ------------------------------------------------------------------ sources

    def _board_findings(self) -> list[str]:
        return (
            [s.value for s in FindingStatus]
            if self.access.can(Permission.VIEW_PENDING_FINDINGS)
            else [s.value for s in VISIBLE_TO_BOARD]
        )

    async def risks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cases = await self.s.scalars(
            select(CaseRecord)
            .where(
                CaseRecord.condominium_id == self.cid,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
            )
            .order_by(CaseRecord.next_action_due_at.asc().nulls_first())
        )
        for c in cases:
            late = c.next_action_due_at is not None and c.next_action_due_at < self.now
            suspended_over = (
                c.status == "suspenso_justificadamente"
                and c.suspended_until is not None
                and c.suspended_until < self.today
            )
            critical = c.severity == CaseSeverity.CRITICA.value
            if late and c.status != "suspenso_justificadamente":
                out.append(
                    _item(
                        "case",
                        f"{c.number} — {c.title}",
                        f"Próxima ação atrasada: {c.next_action}",
                        ref=("case", c.id),
                        when=c.next_action_due_at,
                        tone="danger",
                    )
                )
            elif suspended_over:
                out.append(
                    _item(
                        "case",
                        f"{c.number} — {c.title}",
                        "Suspensão vencida: reavaliar o assunto",
                        ref=("case", c.id),
                        when=c.suspended_until,
                        tone="warning",
                    )
                )
            elif critical:
                out.append(
                    _item(
                        "case",
                        f"{c.number} — {c.title}",
                        f"Crítico · próxima ação: {c.next_action}",
                        ref=("case", c.id),
                        when=c.next_action_due_at,
                        tone="danger",
                    )
                )
        serious = await self.s.scalars(
            select(Finding)
            .where(
                Finding.condominium_id == self.cid,
                Finding.severity == "alta",
                Finding.status == FindingStatus.PUBLICADO.value,
            )
            .order_by(Finding.amount_at_risk.desc())
            .limit(MAX_ITEMS)
        )
        for f in serious:
            out.append(
                _item(
                    "finding",
                    f.title,
                    f"Achado grave sem decisão · {_brl(f.amount_at_risk)} em risco",
                    ref=("finding", f.id),
                    tone="danger",
                )
            )
        events = await condominium_agenda(
            self.s, self.cid, self.today - timedelta(days=30), self.today, self.today
        )
        for e in events:
            if e.kind == "vencimento" and e.status == "vencido":
                out.append(
                    _item(
                        "agenda",
                        e.title,
                        f"Vencido sem pagamento identificado · {e.detail}",
                        when=e.date,
                        tone="warning",
                    )
                )
        out.extend(await self.compliance_alerts())
        return out

    async def compliance_alerts(self) -> list[dict[str, Any]]:
        """Documents of applicable obligations that expired or expire within 30 days (D112).
        A missing document is not listed here: it shows on the compliance screen."""
        from app.compliance import rows_for

        out: list[dict[str, Any]] = []
        for row in await rows_for(self.s, self.cid, self.today):
            sit = row.situation
            soon = sit.code == "vence_em_breve" and (sit.days_left or 0) <= COMPLIANCE_SOON_DAYS
            if sit.code != "vencido" and not soon:
                continue
            detail = sit.text + (f" · {sit.to_confirm}" if sit.to_confirm else "")
            out.append(
                _item(
                    "compliance",
                    row.obligation.name,
                    detail,
                    ref=("compliance", row.obligation.id),
                    when=sit.valid_until,
                    tone="danger" if sit.code == "vencido" else "warning",
                )
            )
        return out

    async def decisions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        a = self.access
        if a.can(Permission.DECIDE_FINDING):
            for f in await self.s.scalars(
                select(Finding)
                .where(
                    Finding.condominium_id == self.cid,
                    Finding.status == FindingStatus.PUBLICADO.value,
                )
                .order_by(Finding.amount_at_risk.desc())
                .limit(MAX_ITEMS)
            ):
                out.append(
                    _item(
                        "finding",
                        f.title,
                        f"Confirmar, contestar ou ignorar · {_brl(f.amount_at_risk)}",
                        ref=("finding", f.id),
                        tone="info",
                    )
                )
        if a.can(Permission.APPROVE_IN_CONDO):
            for o in await self.s.scalars(
                select(Opportunity).where(
                    Opportunity.condominium_id == self.cid,
                    Opportunity.status == "aprovada_para_cliente",
                )
            ):
                out.append(
                    _item(
                        "opportunity",
                        f"{o.number} — {o.title}",
                        "Oportunidade apresentada: aprovar ou recusar",
                        ref=("opportunity", o.id),
                        tone="info",
                    )
                )
        if a.can(Permission.APPROVE_IN_CONDO) or a.can(Permission.MANAGE_CASES):
            for req in await self.s.scalars(
                select(ActionRequest)
                .where(
                    ActionRequest.condominium_id == self.cid,
                    ActionRequest.status.in_(
                        [
                            ActionStatus.AGUARDANDO_APROVACAO.value,
                            ActionStatus.AGUARDANDO_EXECUCAO_MANUAL.value,
                        ]
                    ),
                )
                .order_by(ActionRequest.created_at)
                .limit(MAX_ITEMS)
            ):
                waiting = req.status == ActionStatus.AGUARDANDO_APROVACAO.value
                if waiting and a.can(Permission.APPROVE_IN_CONDO):
                    detail = f"Ação aguardando sua aprovação · teto {_brl(req.cost_cap)}"
                elif not waiting and a.can(Permission.MANAGE_CASES):
                    detail = "Ação aprovada: executar fora do sistema e registrar"
                else:
                    continue
                out.append(_item("action", req.title, detail, ref=("action", req.id), tone="info"))
        if a.can(Permission.VALIDATE_FINDING):
            for f in await self.s.scalars(
                select(Finding)
                .where(
                    Finding.condominium_id == self.cid,
                    Finding.status.in_([s.value for s in UNDER_REVIEW]),
                )
                .order_by(Finding.amount_at_risk.desc())
                .limit(MAX_ITEMS)
            ):
                out.append(
                    _item(
                        "finding",
                        f.title,
                        "Achado aguardando revisão antes de publicar",
                        ref=("finding", f.id),
                        tone="warning",
                    )
                )
        if a.can(Permission.REVIEW_OPPORTUNITY):
            for o in await self.s.scalars(
                select(Opportunity).where(
                    Opportunity.condominium_id == self.cid,
                    Opportunity.status.in_(["em_revisao_interna", "devolvida"]),
                )
            ):
                if is_reviewer(a, o):
                    out.append(
                        _item(
                            "opportunity",
                            f"{o.number} — {o.title}",
                            "Oportunidade aguardando revisão CondoOS",
                            ref=("opportunity", o.id),
                            tone="warning",
                        )
                    )
        if a.can(Permission.CORRECT_EXTRACTION):
            docs = (
                await self.s.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.condominium_id == self.cid, Document.needs_review.is_(True))
                )
                or 0
            )
            issues = (
                await self.s.scalar(
                    select(func.count())
                    .select_from(MatchIssue)
                    .where(MatchIssue.condominium_id == self.cid, MatchIssue.status == "aberto")
                )
                or 0
            )
            if docs or issues:
                out.append(
                    _item(
                        "queue",
                        "Fila de exceções",
                        f"{docs} documento(s) para corrigir e {issues} casamento(s) ambíguo(s)",
                        tone="warning",
                    )
                )
        return out

    async def in_progress(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        rows = await self.s.execute(
            select(CaseTask, CaseRecord)
            .join(CaseRecord, CaseRecord.id == CaseTask.case_id)
            .where(
                CaseTask.condominium_id == self.cid,
                CaseTask.assignee_user_id == self.uid,
                CaseTask.status.not_in([s.value for s in CLOSED_TASK]),
            )
            .order_by(CaseTask.due_at)
            .limit(MAX_ITEMS)
        )
        for t, c in rows:
            out.append(
                _item(
                    "task",
                    t.title,
                    f"Sua tarefa no assunto {c.number}",
                    ref=("case", c.id),
                    when=t.due_at,
                    tone="danger" if t.due_at < self.now else "neutral",
                )
            )
        for c in await self.s.scalars(
            select(CaseRecord)
            .where(
                CaseRecord.condominium_id == self.cid,
                CaseRecord.owner_user_id == self.uid,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
            )
            .order_by(CaseRecord.next_action_due_at)
            .limit(MAX_ITEMS)
        ):
            out.append(
                _item(
                    "case",
                    f"{c.number} — {c.title}",
                    f"Próxima ação: {c.next_action or '—'}",
                    ref=("case", c.id),
                    when=c.next_action_due_at,
                )
            )
        return out

    async def done(self) -> list[dict[str, Any]]:
        """Only what has a recorded event in the period: never claims what did not happen."""
        out: list[dict[str, Any]] = []
        rows = await self.s.execute(
            select(CaseEvent, CaseRecord)
            .join(CaseRecord, CaseRecord.id == CaseEvent.case_id)
            .where(
                CaseEvent.condominium_id == self.cid,
                CaseEvent.created_at >= self.start,
                CaseEvent.created_at <= self.now,
                CaseEvent.kind.in_(["status_changed", "task_status_changed"]),
            )
            .order_by(CaseEvent.created_at)
        )
        case_rows = list(rows.all())
        visible = self._board_findings()
        decision_rows = list(
            (
                await self.s.execute(
                    select(Decision, Finding)
                    .join(Finding, Finding.id == Decision.finding_id)
                    .where(
                        Decision.condominium_id == self.cid,
                        Decision.decided_at >= self.start,
                        Decision.decided_at <= self.now,
                        Finding.status.in_(visible),
                    )
                    .order_by(Decision.decided_at)
                )
            ).all()
        )
        review_rows = list(
            (
                await self.s.execute(
                    select(OpportunityReview, Opportunity)
                    .join(Opportunity, Opportunity.id == OpportunityReview.opportunity_id)
                    .where(
                        OpportunityReview.condominium_id == self.cid,
                        OpportunityReview.created_at >= self.start,
                        OpportunityReview.created_at <= self.now,
                        OpportunityReview.action.in_(list(OPP_VERB)),
                    )
                    .order_by(OpportunityReview.created_at)
                )
            ).all()
        )
        # Names only of the people in these records (app_user has no RLS: never load all).
        ids = {e.actor_user_id for e, _ in case_rows if e.actor_user_id}
        ids |= {d.user_id for d, _ in decision_rows} | {r.user_id for r, _ in review_rows}
        names: dict[uuid.UUID, str] = (
            dict(
                (
                    await self.s.execute(
                        select(AppUser.id, AppUser.name).where(AppUser.id.in_(ids))
                    )
                ).all()
            )
            if ids
            else {}
        )
        for e, c in case_rows:
            who = names.get(e.actor_user_id, "Sistema") if e.actor_user_id else "Sistema"
            if e.kind == "status_changed" and e.to_value in CASE_STATUS:
                out.append(
                    _item(
                        "case",
                        f"{c.number} — {c.title}",
                        f"{CASE_STATUS[e.to_value].capitalize()} por {who}",
                        ref=("case", c.id),
                        when=e.created_at,
                        tone="success",
                    )
                )
            elif e.kind == "task_status_changed" and e.to_value == "concluida":
                out.append(
                    _item(
                        "task",
                        f"Tarefa concluída no assunto {c.number}",
                        f"Por {who}",
                        ref=("case", c.id),
                        when=e.created_at,
                        tone="success",
                    )
                )
        for d, f in decision_rows:
            out.append(
                _item(
                    "finding",
                    f.title,
                    f"Achado {DECISION_VERB.get(d.action, d.action)} por {names.get(d.user_id, '—')}",
                    ref=("finding", f.id),
                    when=d.decided_at,
                    tone="success",
                )
            )
        drafts = self.access.can(Permission.VIEW_OPPORTUNITY_DRAFT)
        for r, o in review_rows:
            if not drafts and (o.presented_at is None or r.action in ("rejeitar", "devolver")):
                continue
            out.append(
                _item(
                    "opportunity",
                    f"{o.number} — {o.title}",
                    f"Oportunidade {OPP_VERB[r.action]} por {names.get(r.user_id, '—')}",
                    ref=("opportunity", o.id),
                    when=r.created_at,
                    tone="success",
                )
            )
        return out

    async def agenda(self) -> list[dict[str, Any]]:
        events = await condominium_agenda(
            self.s, self.cid, self.today, self.today + timedelta(days=7), self.today
        )
        out = []
        for e in events:
            if e.status in ("pago", "recebida"):
                continue
            prefix = "Previsto · " if e.predicted else ""
            amount = f" · {_brl(e.amount)}" if e.amount is not None else ""
            out.append(_item("agenda", e.title, f"{prefix}{e.detail}{amount}", when=e.date))
        return out[:MAX_ITEMS]

    async def opportunities(self) -> list[dict[str, Any]]:
        drafts = self.access.can(Permission.VIEW_OPPORTUNITY_DRAFT)
        stmt = select(Opportunity).where(
            Opportunity.condominium_id == self.cid,
            Opportunity.status.not_in(["rejeitada", "recusada_pelo_condominio", "encerrada"]),
        )
        if not drafts:
            stmt = stmt.where(Opportunity.presented_at.is_not(None))
        out = []
        for o in await self.s.scalars(
            stmt.order_by(Opportunity.created_at.desc()).limit(MAX_ITEMS)
        ):
            stages = list(BOARD_STAGES) if not drafts else list(STAGE_LABEL)
            rec = await self.s.scalar(
                select(SavingsRecord)
                .where(SavingsRecord.opportunity_id == o.id, SavingsRecord.stage.in_(stages))
                .order_by(SavingsRecord.created_at.desc())
                .limit(1)
            )
            # Each value keeps its stage name; values of different opportunities are not added.
            detail = (
                f"{STAGE_LABEL[rec.stage]}: {_brl(rec.annualized_amount)} por ano" if rec else ""
            )
            out.append(
                _item("opportunity", f"{o.number} — {o.title}", detail, ref=("opportunity", o.id))
            )
        return out

    async def data_quality(self) -> list[dict[str, Any]]:
        out = []
        last_doc = await self.s.scalar(
            select(func.max(Document.created_at)).where(
                Document.condominium_id == self.cid, Document.origin.in_(["upload", "email"])
            )
        )
        last_bank = await self.s.scalar(
            select(func.max(BankTransaction.posted_at)).where(
                BankTransaction.condominium_id == self.cid
            )
        )
        limit_dt = self.now - timedelta(days=STALE_DAYS)
        if last_doc is None or last_doc < limit_dt:
            # "Not started" and "late" read differently (LB-083, D108): a condominium that has
            # not sent anything yet is starting, not failing. Both stay partial sources.
            self.partial.append(
                {
                    "source": "documentos",
                    "label": "Documentos recebidos",
                    "reason": (
                        f"Nenhum documento novo há mais de {STALE_DAYS} dias "
                        f"(o último em {last_doc:%d/%m/%Y})."
                        if last_doc
                        else "Ainda não recebemos documentos. Assim que chegarem, eu aviso aqui."
                    ),
                    "not_started": last_doc is None,
                }
            )
        out.append(
            _item(
                "data",
                "Documentos",
                (
                    f"Último recebido em {last_doc:%d/%m/%Y}"
                    if last_doc
                    else "Nenhum documento recebido ainda"
                ),
                when=last_doc,
                tone="warning" if last_doc is None or last_doc < limit_dt else "neutral",
            )
        )
        if last_bank is None or last_bank < limit_dt.date():
            self.partial.append(
                {
                    "source": "extrato",
                    "label": "Extrato bancário",
                    "reason": (
                        f"Extrato sem lançamentos há mais de {STALE_DAYS} dias (o último em "
                        f"{last_bank:%d/%m/%Y}): pagamentos podem não aparecer."
                        if last_bank
                        else "Nenhum extrato recebido ainda. Quando chegar, confiro os "
                        "pagamentos com o banco."
                    ),
                    "not_started": last_bank is None,
                }
            )
        out.append(
            _item(
                "data",
                "Extrato bancário",
                (
                    f"Último lançamento em {last_bank:%d/%m/%Y}"
                    if last_bank
                    else "Nenhum extrato importado ainda"
                ),
                when=last_bank,
                tone="warning" if last_bank is None or last_bank < limit_dt.date() else "neutral",
            )
        )
        return out

    # ------------------------------------------------------------------ assembly

    async def build(self) -> dict[str, Any]:
        sections_spec: list[tuple[str, str, str, Callable[[], Awaitable[list[dict[str, Any]]]]]] = [
            ("riscos", "Riscos e atrasos", "riscos e atrasos", self.risks),
            ("decisoes", "Decisões aguardando você", "decisões pendentes", self.decisions),
            ("andamento", "Em andamento com você", "assuntos e tarefas", self.in_progress),
            ("concluido", "Concluído desde o último briefing", "registros do período", self.done),
            ("agenda", "Agenda dos próximos 7 dias", "agenda", self.agenda),
            ("oportunidades", "Oportunidades de economia", "oportunidades", self.opportunities),
            ("dados", "Qualidade dos dados", "documentos e extrato", self.data_quality),
        ]
        sections = []
        for key, title, label, fn in sections_spec:
            items = await self._safe(key, label, fn)
            sections.append(
                {"key": key, "title": title, "count": len(items), "items": items[:MAX_ITEMS]}
            )
        counts: dict[str, int] = {str(s["key"]): int(str(s["count"])) for s in sections}
        hour = self.now.astimezone(ZoneInfo(self.condo.timezone or DEFAULT_TIMEZONE)).hour
        greeting = "Bom dia" if hour < 12 else "Boa tarde" if hour < 18 else "Boa noite"
        # Plain sentences without "(ões)" and without zeros (LB-083, D108).
        parts = [
            _count(counts["decisoes"], "decisão aguarda você", "decisões aguardam você"),
            _count(counts["riscos"], "risco ou atraso", "riscos ou atrasos"),
            _count(
                counts["agenda"],
                "compromisso nos próximos 7 dias",
                "compromissos nos próximos 7 dias",
            ),
        ]
        said = [p for p in parts if p]
        headline = f"{greeting}. Em {self.condo.name}: " + (
            "; ".join(said) + "." if said else "nada pendente com você hoje."
        )
        if any(not p.get("not_started") for p in self.partial):
            headline += " Algumas fontes estão parciais: veja os avisos."
        return {"headline": headline, "sections": sections}


async def latest_for_today(
    session: AsyncSession, condo: Condominium, user_id: uuid.UUID
) -> Briefing | None:
    return await session.scalar(
        select(Briefing)
        .where(
            Briefing.condominium_id == condo.id,
            Briefing.user_id == user_id,
            Briefing.local_date == local_today(condo.timezone),
        )
        .order_by(Briefing.version.desc())
        .limit(1)
    )


# Records a briefing is built from (D82). A change in any of them after today's latest
# version makes that version stale (D111).
SOURCES = (
    Document,
    Expense,
    BankTransaction,
    Finding,
    CaseRecord,
    CaseTask,
    ActionRequest,
    Opportunity,
    DelegationRequest,
)


async def changed_since(session: AsyncSession, condo_id: uuid.UUID, since: datetime) -> bool:
    """Whether any source record of this condominium was created or changed after ``since``.
    One indexed lookup per table, stopping at the first hit."""
    for model in SOURCES:
        found = await session.scalar(
            select(model.id)
            .where(model.condominium_id == condo_id, model.updated_at > since)
            .limit(1)
        )
        if found is not None:
            return True
    return False


async def generate(
    session: AsyncSession, access: CondoAccess, condo: Condominium, *, refresh: bool = False
) -> Briefing:
    """Today's briefing for this person: the latest version, or a new one when asked, when
    none exists yet today, or when its sources changed since it was generated (D111: a
    document that arrived in the afternoon shows without pressing "Atualizar"). The period
    starts at the person's previous briefing."""
    today_row = await latest_for_today(session, condo, access.user_id)
    if (
        today_row is not None
        and not refresh
        and not await changed_since(session, condo.id, today_row.generated_at)
    ):
        return today_row
    now = utcnow()
    previous = await session.scalar(
        select(Briefing.generated_at)
        .where(Briefing.condominium_id == condo.id, Briefing.user_id == access.user_id)
        .order_by(Briefing.generated_at.desc())
        .limit(1)
    )
    start = previous or now - timedelta(hours=24)
    builder = Builder(session, access, condo, start, now)
    content = await builder.build()
    row = Briefing(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        user_id=access.user_id,
        local_date=builder.today,
        version=(today_row.version + 1) if today_row else 1,
        timezone=condo.timezone or DEFAULT_TIMEZONE,
        period_start=start,
        period_end=now,
        content=content,
        partial_sources=builder.partial,
        generated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


RETENTION_DAYS = 90


async def purge(session: AsyncSession, today: date) -> int:
    """Briefings are a convenience, not a record: kept for 90 days."""
    from sqlalchemy import delete

    result = await session.execute(
        delete(Briefing).where(Briefing.local_date < today - timedelta(days=RETENTION_DAYS))
    )
    return int(getattr(result, "rowcount", 0) or 0)
