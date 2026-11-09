"""Daily health monitors (LF6-b, LB-060, D110): deterministic checks that open internal
alerts as ``data_issue`` rows, reconciled like the conflicts (D93): what is no longer found
and nobody acted on becomes "superado"; what a person resolved stays.

Detectors (versioned in ``detector``):

- ``canal_parado_v1`` (team): a contract in force expects invoices, the condominium has
  received documents before, and none arrived by any channel for more than 35 days.
- ``contrato_aditado_v1`` (team): an amendment that changes value, end or scope takes effect
  between 45 days ago and 30 days ahead: rules, agenda and reminders need a look.
- ``revisor_ausente_v1`` (team): no management company and no active CondoOS reviewer:
  nobody can review findings or close the month.
- ``sindico_sem_acesso_v1`` (team): no síndico with an active access, or the síndico's access
  ends within 7 days.
- ``acao_parada_v1`` (condominium): an approved action handed to a person more than 7 days
  ago with no execution recorded.

No monitor changes a permission: alerts have no capability and no supplier, so readiness and
the policy ignore them (``open_issues`` and the policy read conflicts only).
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.data_issues import DetectionResult, Found, reconcile
from app.db.enums import (
    ALERT_KINDS,
    ActionStatus,
    DataIssueAudience,
    DataIssueKind,
    PlatformRole,
    Role,
)
from app.db.models import (
    ActionDecision,
    ActionRequest,
    CondoAssignment,
    Condominium,
    Contract,
    ContractAmendment,
    Document,
    Membership,
)

STALE_CHANNEL_DAYS = 35  # Q-L13
ACCESS_ENDING_DAYS = 7  # Q-L13
STALLED_ACTION_DAYS = 7  # Q-L13
AMENDMENT_BEFORE_DAYS = 45
AMENDMENT_AHEAD_DAYS = 30

EQUIPE = DataIssueAudience.EQUIPE.value
CONDOMINIO = DataIssueAudience.CONDOMINIO.value


def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _alert(
    kind: DataIssueKind,
    detector: str,
    key: str,
    subject_type: str,
    subject_id: uuid.UUID,
    title: str,
    detail: str,
    audience: str = EQUIPE,
    evidence: list[dict[str, Any]] | None = None,
) -> Found:
    return Found(
        dedupe_key=f"{detector}:{key}",
        detector=detector,
        subject_id=subject_id,
        supplier_id=None,
        title=title,
        detail=detail,
        field=None,
        evidence=evidence or [],
        kind=kind.value,
        subject_type=subject_type,
        capabilities=[],
        audience=audience,
    )


async def _stale_channel(session: AsyncSession, condo: Condominium, today: date) -> list[Found]:
    expecting = await session.scalar(
        select(Contract.id)
        .where(
            Contract.condominium_id == condo.id,
            Contract.billing_frequency_months > 0,
            Contract.start_date <= today,
            or_(Contract.end_date.is_(None), Contract.end_date >= today),
        )
        .limit(1)
    )
    if expecting is None:
        return []
    last = await session.scalar(
        select(func.max(Document.created_at)).where(Document.condominium_id == condo.id)
    )
    if last is None:  # never received anything: still implementing, the guide leads (D108)
        return []
    days = (utcnow() - last).days
    if days <= STALE_CHANNEL_DAYS:
        return []
    return [
        _alert(
            DataIssueKind.CANAL_PARADO,
            "canal_parado_v1",
            "condominio",
            "condominium",
            condo.id,
            "Nenhum documento recebido há mais de 35 dias",
            f"O último documento chegou em {_br(last.date())} ({days} dias). Há contrato que "
            "espera nota fiscal: confira o e-mail de entrada e com quem envia os documentos.",
        )
    ]


async def _amended(session: AsyncSession, condo: Condominium, today: date) -> list[Found]:
    out = []
    rows = await session.execute(
        select(ContractAmendment, Contract)
        .join(Contract, Contract.id == ContractAmendment.contract_id)
        .where(
            ContractAmendment.condominium_id == condo.id,
            ContractAmendment.effective_date >= today - timedelta(days=AMENDMENT_BEFORE_DAYS),
            ContractAmendment.effective_date <= today + timedelta(days=AMENDMENT_AHEAD_DAYS),
        )
    )
    for amendment, contract in rows.all():
        changes = []
        if (
            amendment.monthly_value is not None
            and amendment.monthly_value != contract.monthly_value
        ):
            changes.append("valor mensal")
        if amendment.end_date is not None and amendment.end_date != contract.end_date:
            changes.append("fim da vigência")
        if amendment.scope_items:
            changes.append("escopo")
        if not changes:
            continue
        out.append(
            _alert(
                DataIssueKind.CONTRATO_ADITADO,
                "contrato_aditado_v1",
                str(amendment.id),
                "contract",
                contract.id,
                f"Contrato aditado: {contract.object}"[:300],
                f"Aditivo com efeito em {_br(amendment.effective_date)} muda "
                f"{', '.join(changes)}. Confira as regras, a agenda e os lembretes do contrato.",
                evidence=[
                    {
                        "contract_id": str(contract.id),
                        "document_id": (
                            str(amendment.document_id) if amendment.document_id else None
                        ),
                        "label": "Aditivo",
                        "value": ", ".join(changes),
                    }
                ],
            )
        )
    return out


async def _no_reviewer(session: AsyncSession, condo: Condominium) -> list[Found]:
    if condo.management_company_id is not None:
        return []
    now = utcnow()
    reviewer = await session.scalar(
        select(CondoAssignment.id)
        .where(
            CondoAssignment.condominium_id == condo.id,
            CondoAssignment.platform_role == PlatformRole.CONDOOS_REVIEWER.value,
            CondoAssignment.revoked_at.is_(None),
            or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
        )
        .limit(1)
    )
    if reviewer is not None:
        return []
    return [
        _alert(
            DataIssueKind.REVISOR_AUSENTE,
            "revisor_ausente_v1",
            "condominio",
            "condominium",
            condo.id,
            "Sem revisora CondoOS atribuída",
            "O condomínio não tem administradora e nenhuma revisora CondoOS ativa: ninguém "
            "revisa os achados graves nem fecha o mês. Atribua uma revisora em Configurações.",
        )
    ]


async def _sindico_access(session: AsyncSession, condo: Condominium) -> list[Found]:
    now = utcnow()
    active = list(
        await session.scalars(
            select(Membership).where(
                Membership.condominium_id == condo.id,
                Membership.role == Role.SINDICO.value,
                Membership.revoked_at.is_(None),
                or_(Membership.expires_at.is_(None), Membership.expires_at > now),
            )
        )
    )
    if not active:
        return [
            _alert(
                DataIssueKind.SINDICO_SEM_ACESSO,
                "sindico_sem_acesso_v1",
                "sem_sindico",
                "condominium",
                condo.id,
                "Nenhum síndico com acesso ativo",
                "Ninguém pode aprovar ações nem decidir os achados pelo condomínio. Confirme "
                "quem é o síndico e dê o acesso em Configurações.",
            )
        ]
    out = []
    limit = now + timedelta(days=ACCESS_ENDING_DAYS)
    for m in active:
        if m.expires_at is not None and m.expires_at <= limit:
            out.append(
                _alert(
                    DataIssueKind.SINDICO_SEM_ACESSO,
                    "sindico_sem_acesso_v1",
                    f"vencendo:{m.id}",
                    "membership",
                    m.id,
                    "Acesso do síndico termina em até 7 dias",
                    f"O acesso termina em {_br(m.expires_at.date())}. Se o mandato continua, "
                    "renove o acesso; se vai mudar, cadastre quem assume.",
                )
            )
    return out


async def _stalled_actions(session: AsyncSession, condo: Condominium) -> list[Found]:
    limit = utcnow() - timedelta(days=STALLED_ACTION_DAYS)
    out = []
    for req in await session.scalars(
        select(ActionRequest).where(
            ActionRequest.condominium_id == condo.id,
            ActionRequest.status == ActionStatus.AGUARDANDO_EXECUCAO_MANUAL.value,
        )
    ):
        since = await session.scalar(
            select(func.max(ActionDecision.created_at)).where(
                ActionDecision.action_request_id == req.id,
                ActionDecision.to_status == ActionStatus.AGUARDANDO_EXECUCAO_MANUAL.value,
            )
        )
        if since is None or since > limit:
            continue
        out.append(
            _alert(
                DataIssueKind.ACAO_PARADA,
                "acao_parada_v1",
                str(req.id),
                "action_request",
                req.id,
                f"Ação aprovada sem execução registrada: {req.title}"[:300],
                f"Entregue para execução em {_br(since.date())}. Registre o que foi feito ou "
                "cancele a ação.",
                audience=CONDOMINIO,
            )
        )
    return out


async def run_monitors(session: AsyncSession, condo_id: uuid.UUID, today: date) -> DetectionResult:
    """Every monitor for one condominium, reconciled with the open alerts. Idempotent."""
    condo = await session.get(Condominium, condo_id)
    if condo is None:
        return DetectionResult()
    found = [
        *await _stale_channel(session, condo, today),
        *await _amended(session, condo, today),
        *await _no_reviewer(session, condo),
        *await _sindico_access(session, condo),
        *await _stalled_actions(session, condo),
    ]
    return await reconcile(session, condo_id, found, {k.value for k in ALERT_KINDS})
