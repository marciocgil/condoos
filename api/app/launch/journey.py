"""The five milestones of the Launch journey (LM1-LM5), computed from facts.

Each milestone names the fact that completes it and, when there is one, the record and the
moment. Nothing here is stored and nothing here grants a permission: what a capability may do
comes from ``readiness`` and ``app.policy`` (R-L06).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEXED_TYPES
from app.core.time import utcnow
from app.db.enums import (
    VISIBLE_TO_BOARD,
    ExtractionStatus,
    PlatformRole,
    Role,
)
from app.db.models import (
    ActionRequest,
    CaseRecord,
    Competence,
    CondoAssignment,
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    Membership,
)


@dataclass(frozen=True)
class Milestone:
    key: str
    title: str
    value: str  # what the person gains
    criterion: str  # the fact that completes it, in plain words
    done: bool
    at: datetime | None = None
    ref: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "value": self.value,
            "criterion": self.criterion,
            "done": self.done,
            "at": self.at.isoformat() if self.at else None,
            "ref": self.ref,
        }


async def _lm1(session: AsyncSession, condo_id: uuid.UUID) -> Milestone:
    now = utcnow()
    row = (
        await session.execute(
            select(Membership.id, Membership.accepted_at)
            .where(
                Membership.condominium_id == condo_id,
                Membership.role == Role.SINDICO.value,
                Membership.accepted_at.is_not(None),
                Membership.revoked_at.is_(None),
                or_(Membership.expires_at.is_(None), Membership.expires_at > now),
            )
            .order_by(Membership.accepted_at)
            .limit(1)
        )
    ).first()
    return Milestone(
        "LM1",
        "Prazer, condomínio!",
        "Ambiente e assessor identificados.",
        "Condomínio cadastrado e síndico com acesso ativo que já entrou no CondoOS.",
        row is not None,
        row.accepted_at if row else None,
        {"kind": "membership", "id": str(row.id)} if row else None,
    )


async def _lm2(session: AsyncSession, condo_id: uuid.UUID) -> Milestone:
    row = (
        await session.execute(
            select(Document.id, Document.updated_at)
            .where(
                Document.condominium_id == condo_id,
                Document.doc_type.in_(INDEXED_TYPES),
                Document.extraction_status == ExtractionStatus.DONE.value,
                Document.text_content.is_not(None),
            )
            .order_by(Document.created_at)
            .limit(1)
        )
    ).first()
    return Milestone(
        "LM2",
        "Seu condomínio ganhou memória",
        "Primeira leitura útil de um documento, com os trechos de origem.",
        "Um contrato, a convenção ou uma ata lido por completo, com o texto guardado.",
        row is not None,
        row.updated_at if row else None,
        {"kind": "document", "id": str(row.id)} if row else None,
    )


async def _lm3(session: AsyncSession, condo_id: uuid.UUID) -> Milestone:
    row = (
        await session.execute(
            select(Expense.id, Competence.month, Competence.updated_at)
            .join(
                Competence,
                and_(
                    Competence.condominium_id == Expense.condominium_id,
                    Competence.month == Expense.competence,
                ),
            )
            .where(Expense.condominium_id == condo_id, Expense.contract_id.is_not(None))
            .order_by(Competence.month)
            .limit(1)
        )
    ).first()
    return Milestone(
        "LM3",
        "Seu assessor começou a investigar",
        "Primeira avaliação de contratos e despesas de um mês.",
        "Uma despesa ligada a um contrato num mês que já passou pelas regras de auditoria.",
        row is not None,
        row.updated_at if row else None,
        {"kind": "competence", "id": row.month.strftime("%Y-%m")} if row else None,
    )


async def _lm4(session: AsyncSession, condo_id: uuid.UUID) -> Milestone:
    now = utcnow()
    reviewer = (
        await session.execute(
            select(CondoAssignment.id, CondoAssignment.created_at).where(
                CondoAssignment.condominium_id == condo_id,
                CondoAssignment.platform_role == PlatformRole.CONDOOS_REVIEWER.value,
                CondoAssignment.revoked_at.is_(None),
                or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
            )
        )
    ).first()
    condo = await session.get(Condominium, condo_id)
    by_email = await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.condominium_id == condo_id, Document.origin == "email")
    )
    has_channel = bool(by_email) or (condo is not None and condo.management_company_id is not None)
    done = reviewer is not None and has_channel
    return Milestone(
        "LM4",
        "Seu condomínio está conectado",
        "Pessoas e fontes trabalhando junto com você.",
        "Revisor CondoOS atribuído e documentos chegando por outro caminho além do seu envio "
        "(e-mail do condomínio ou administradora).",
        done,
        reviewer.created_at if done and reviewer else None,
        {"kind": "condo_assignment", "id": str(reviewer.id)} if done and reviewer else None,
    )


async def _lm5(session: AsyncSession, condo_id: uuid.UUID) -> Milestone:
    row = (
        await session.execute(
            select(ActionRequest.id, ActionRequest.executed_at)
            .where(
                ActionRequest.condominium_id == condo_id,
                ActionRequest.executed_at.is_not(None),
            )
            .order_by(ActionRequest.executed_at)
            .limit(1)
        )
    ).first()
    return Milestone(
        "LM5",
        "Seu assessor começou a agir",
        "Primeira ação aprovada por você e realizada.",
        "Uma ação aprovada pelo síndico com a execução registrada por quem a realizou.",
        row is not None,
        row.executed_at if row else None,
        {"kind": "action", "id": str(row.id)} if row else None,
    )


async def milestones(session: AsyncSession, condo_id: uuid.UUID) -> list[Milestone]:
    return [
        await _lm1(session, condo_id),
        await _lm2(session, condo_id),
        await _lm3(session, condo_id),
        await _lm4(session, condo_id),
        await _lm5(session, condo_id),
    ]


async def done_for_you(session: AsyncSession, condo_id: uuid.UUID) -> list[dict[str, Any]]:
    """What the CondoOS has already done, as counts of facts only: never hours saved and never
    an estimated saving presented as realised (D76)."""

    async def count(stmt: Any) -> int:
        return int(await session.scalar(stmt) or 0)

    docs = await count(
        select(func.count())
        .select_from(Document)
        .where(
            Document.condominium_id == condo_id,
            Document.extraction_status == ExtractionStatus.DONE.value,
        )
    )
    contracts = await count(
        select(func.count()).select_from(Contract).where(Contract.condominium_id == condo_id)
    )
    findings = await count(
        select(func.count())
        .select_from(Finding)
        .where(
            Finding.condominium_id == condo_id,
            Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]),
        )
    )
    cases = await count(
        select(func.count())
        .select_from(CaseRecord)
        .where(CaseRecord.condominium_id == condo_id, CaseRecord.owner_user_id.is_not(None))
    )
    items = [
        ("documentos", docs, "documento lido", "documentos lidos"),
        ("contratos", contracts, "contrato organizado", "contratos organizados"),
        ("achados", findings, "ponto de atenção apontado", "pontos de atenção apontados"),
        ("assuntos", cases, "assunto com responsável", "assuntos com responsável"),
    ]
    return [
        {"key": key, "count": n, "label": one if n == 1 else many}
        for key, n, one, many in items
        if n > 0
    ]
