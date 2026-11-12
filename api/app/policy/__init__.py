"""Minimal policy engine for actions (spec §9.2–9.3; D83).

Only this module authorises an action; the model, a document or a chat message never do.
Policies are typed code, versioned, deny-by-default: an action type not in the catalogue is
denied. Nothing here sends anything. In the pilot an approved action waits for a person to
carry it out outside the system and record it (no connector exists yet).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import PolicyDecision
from app.db.models import AutomationPause, Condominium

POLICY_VERSION = 1
ALL_AUTOMATIONS = "*"
# How long an approval is valid (spec §9.5: the executor checks it again at the moment of
# the action). Expired approvals need a new decision.
APPROVAL_VALID_DAYS = 7

# Job types the worker skips while paused (FR-007). "action.dispatch" is the outbox.
PAUSABLE_JOBS: dict[str, str] = {
    "action.dispatch": "Despacho de ações aprovadas",
    "finding.explain": "Reescrita das explicações por IA",
    # Not a job: pausing it makes every upload link of the condominium stop (D95).
    "delegation.link": "Links de envio de documentos",
    # Not a job either: messages wait in the inbox, nothing is lost (D101).
    "email.inbound": "Entrada de documentos por e-mail",
    # The only action that sends something out (D103): waits while paused.
    "pedido_documento.enviar_email": "Envio por e-mail dos pedidos de documentos",
    # Not a job of one condominium: the weekly sender skips a paused condominium (D113).
    "conformidade.lembrete_email": "Resumo semanal por e-mail dos vencimentos",
    # D125: no external effect, but the team may want the farol frozen while it reviews.
    "audit.reprocess": "Reprocessamento automático da auditoria",
}


class EmailDraft(BaseModel):
    """The exact e-mail of a document request (D103), frozen with the action. ``body`` holds
    ``{link}``: the link is made when the e-mail is sent, so its token is never stored."""

    model_config = ConfigDict(extra="forbid")

    delegation_request_id: uuid.UUID
    to: str = Field(max_length=254)  # masked after sending; to_sha256 keeps the trail
    to_sha256: str = Field(min_length=64, max_length=64)
    from_name: str = Field(max_length=200)
    reply_to: str | None = Field(default=None, max_length=254)
    subject: str = Field(max_length=200)
    body: str = Field(max_length=5000)
    note: str = Field(default="", max_length=500)


class ActionPayload(BaseModel):
    """What the approver sees and what gets frozen (spec §7.5)."""

    model_config = ConfigDict(extra="forbid")

    effect: str = Field(min_length=10, max_length=1000)  # the exact effect, in plain words
    reason: str = Field(min_length=10, max_length=1000)  # why, and the impact of not acting
    executor: str = Field(min_length=3, max_length=200)  # who carries it out
    supplier_id: uuid.UUID | None = None
    due_date: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD
    risks: str = Field(default="", max_length=1000)
    evidence: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    email: EmailDraft | None = None  # only for the request e-mail (D103)


@dataclass(frozen=True)
class ActionType:
    code: str
    label: str
    level: Literal["L3", "L4", "L5"]
    # Allowed only with no cost (e.g. asking for a quote without commitment).
    zero_cost_only: bool = False
    # Denied whatever the context: the product never does this (CLAUDE.md, spec §9.3).
    always_denied: bool = False
    # The dispatcher really sends an e-mail (D103). Every other type sends nothing.
    sends_email: bool = False
    # Created only from its own screen (the document request), never from the generic form.
    internal: bool = False


CATALOGUE: dict[str, ActionType] = {
    t.code: t
    for t in (
        ActionType("fornecedor.cobrar", "Cobrar o fornecedor", "L3"),
        ActionType(
            "orcamento.solicitar", "Pedir orçamento sem compromisso", "L3", zero_cost_only=True
        ),
        ActionType("visita.agendar", "Agendar visita técnica", "L4"),
        ActionType(
            "pedido_documento.enviar_email",
            "Enviar por e-mail o pedido de documentos",
            "L3",
            zero_cost_only=True,
            sends_email=True,
            internal=True,
        ),
        ActionType("pagamento.aprovar", "Aprovar pagamento", "L5", always_denied=True),
        ActionType("contrato.contratar", "Contratar ou dar aceite", "L5", always_denied=True),
        ActionType("multa.aplicar", "Emitir advertência ou multa", "L5", always_denied=True),
        ActionType("dados_bancarios.alterar", "Alterar dados bancários", "L5", always_denied=True),
    )
}

REQUESTABLE_TYPES: tuple[str, ...] = tuple(
    c for c, t in CATALOGUE.items() if not t.always_denied and not t.internal
)


@dataclass(frozen=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str
    version: int = POLICY_VERSION
    limit: Decimal | None = None  # the approval limit that applied, if any


def approval_limit(condo: Condominium, category: str | None = None) -> Decimal | None:
    limits: dict[str, Any] = condo.approval_limits or {}
    raw = (limits.get("by_category") or {}).get(category) if category else None
    if raw is None:
        raw = limits.get("default")
    return None if raw in (None, "") else Decimal(str(raw))


async def active_pause(
    session: AsyncSession, condominium_id: uuid.UUID, automation_type: str
) -> AutomationPause | None:
    return await session.scalar(
        select(AutomationPause)
        .where(
            AutomationPause.condominium_id == condominium_id,
            AutomationPause.resumed_at.is_(None),
            or_(
                AutomationPause.automation_type == automation_type,
                AutomationPause.automation_type == ALL_AUTOMATIONS,
            ),
        )
        .limit(1)
    )


async def _open_conflict(
    session: AsyncSession, condominium_id: uuid.UUID, supplier_id: uuid.UUID
) -> bool:
    """An open data issue on a contract of this supplier (D93). Read from the database, never
    from any text: documents are data, not instructions (SEC-02)."""
    from app.db.models import DataIssue

    found = await session.scalar(
        select(DataIssue.id)
        .where(
            DataIssue.condominium_id == condominium_id,
            DataIssue.supplier_id == supplier_id,
            DataIssue.status == "aberto",
            DataIssue.kind == "conflito_documentos",  # health alerts never refuse (D110)
        )
        .limit(1)
    )
    return found is not None


async def evaluate(
    session: AsyncSession,
    condo: Condominium,
    *,
    action_type: str,
    cost_cap: Decimal,
    category: str | None = None,
    supplier_id: uuid.UUID | None = None,
) -> PolicyResult:
    """Decide what an action needs. Deny by default; never ``ALLOW`` in this version: every
    allowed action needs a person's approval (no automation has an external effect)."""
    spec = CATALOGUE.get(action_type)
    if spec is None:
        return PolicyResult(PolicyDecision.DENY, "Tipo de ação desconhecido: negado por padrão.")
    if spec.always_denied:
        return PolicyResult(
            PolicyDecision.DENY,
            f"{spec.label} é decisão humana fora do sistema; o CondoOS não executa.",
        )
    if cost_cap < 0:
        return PolicyResult(PolicyDecision.DENY, "O teto de custo não pode ser negativo.")
    if spec.zero_cost_only and cost_cap > 0:
        return PolicyResult(
            PolicyDecision.DENY, f"{spec.label} só é permitido sem custo (teto R$ 0,00)."
        )
    if supplier_id is not None and await _open_conflict(session, condo.id, supplier_id):
        return PolicyResult(
            PolicyDecision.DENY,
            "Há divergência de dados aberta no contrato deste fornecedor: ela precisa ser "
            "resolvida na Central de Validação antes de pedir ações.",
        )
    if await active_pause(session, condo.id, "action.dispatch") is not None:
        return PolicyResult(
            PolicyDecision.PAUSE, "As ações estão pausadas neste condomínio (kill switch)."
        )
    if spec.sends_email and await active_pause(session, condo.id, spec.code) is not None:
        return PolicyResult(
            PolicyDecision.PAUSE, "O envio de pedidos por e-mail está pausado neste condomínio."
        )
    limit = approval_limit(condo, category)
    if cost_cap > 0:
        if limit is None:
            return PolicyResult(
                PolicyDecision.REQUIRE_REVIEW,
                "Ação com custo e sem alçada configurada: configure a alçada antes de aprovar.",
            )
        if cost_cap > limit:
            return PolicyResult(
                PolicyDecision.DENY,
                "O teto de custo supera a alçada do síndico: leve ao conselho ou à assembleia.",
                limit=limit,
            )
    if spec.sends_email:
        return PolicyResult(
            PolicyDecision.REQUIRE_APPROVAL,
            "Exige aprovação do síndico para esta versão exata; só então o CondoOS envia o "
            "e-mail.",
            limit=limit,
        )
    return PolicyResult(
        PolicyDecision.REQUIRE_APPROVAL,
        "Exige aprovação do síndico dentro da alçada; nada é enviado pelo sistema.",
        limit=limit,
    )


async def job_paused(
    session: AsyncSession, job_type: str, condominium_id: uuid.UUID | None
) -> bool:
    """Worker hook: pausable job types do not run while their automation is paused."""
    if job_type not in PAUSABLE_JOBS or condominium_id is None:
        return False
    return await active_pause(session, condominium_id, job_type) is not None
