"""Minimal policy engine for actions (spec §9.2–9.3; D83).

Only this module authorises an action; the model, a document or a chat message never do.
Policies are typed code, versioned, deny-by-default: an action type not in the catalogue is
denied. Nothing here sends anything. In the pilot an approved action waits for a person to
carry it out outside the system and record it (no connector exists yet).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import DataIssueStatus, PolicyDecision
from app.db.models import AutomationPause, Condominium, DataIssue

# Version 2 (D89, D93): a condominium without the síndico's approval limit configured gets
# no action request at all (capability C7 "nao_configurado"), whatever the cost.
# Version 3 (D95, LB-035): an action tied to a contract with an open data conflict is denied
# until a person resolves the conflict.
POLICY_VERSION = 3
ALL_AUTOMATIONS = "*"
# How long an approval is valid (spec §9.5: the executor checks it again at the moment of
# the action). Expired approvals need a new decision.
APPROVAL_VALID_DAYS = 7

# Job types the worker skips while paused (FR-007). "action.dispatch" is the outbox.
PAUSABLE_JOBS: dict[str, str] = {
    "action.dispatch": "Despacho de ações aprovadas",
    "finding.explain": "Reescrita das explicações por IA",
}


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


@dataclass(frozen=True)
class ActionType:
    code: str
    label: str
    level: Literal["L3", "L4", "L5"]
    # Allowed only with no cost (e.g. asking for a quote without commitment).
    zero_cost_only: bool = False
    # Denied whatever the context: the product never does this (CLAUDE.md, spec §9.3).
    always_denied: bool = False


CATALOGUE: dict[str, ActionType] = {
    t.code: t
    for t in (
        ActionType("fornecedor.cobrar", "Cobrar o fornecedor", "L3"),
        ActionType(
            "orcamento.solicitar", "Pedir orçamento sem compromisso", "L3", zero_cost_only=True
        ),
        ActionType("visita.agendar", "Agendar visita técnica", "L4"),
        ActionType("pagamento.aprovar", "Aprovar pagamento", "L5", always_denied=True),
        ActionType("contrato.contratar", "Contratar ou dar aceite", "L5", always_denied=True),
        ActionType("multa.aplicar", "Emitir advertência ou multa", "L5", always_denied=True),
        ActionType("dados_bancarios.alterar", "Alterar dados bancários", "L5", always_denied=True),
    )
}

REQUESTABLE_TYPES: tuple[str, ...] = tuple(c for c, t in CATALOGUE.items() if not t.always_denied)


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


async def evaluate(
    session: AsyncSession,
    condo: Condominium,
    *,
    action_type: str,
    cost_cap: Decimal,
    category: str | None = None,
    contract_ids: Iterable[uuid.UUID] = (),
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
    limit = approval_limit(condo, category)
    if limit is None and approval_limit(condo) is None:
        return PolicyResult(
            PolicyDecision.DENY,
            "A alçada do síndico ainda não foi configurada: configure-a antes de pedir ações.",
        )
    ids = list(contract_ids)
    if ids:
        conflict = await session.scalar(
            select(DataIssue.title)
            .where(
                DataIssue.condominium_id == condo.id,
                DataIssue.subject_type == "contract",
                DataIssue.subject_id.in_(ids),
                DataIssue.status == DataIssueStatus.ABERTO.value,
            )
            .limit(1)
        )
        if conflict is not None:
            return PolicyResult(
                PolicyDecision.DENY,
                f"Há um conflito de dados aberto neste contrato ({conflict}): "
                "resolva-o antes de pedir a ação.",
            )
    if await active_pause(session, condo.id, "action.dispatch") is not None:
        return PolicyResult(
            PolicyDecision.PAUSE, "As ações estão pausadas neste condomínio (kill switch)."
        )
    if cost_cap > 0:
        if limit is None:  # unreachable while the default limit exists; kept as a guard
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
