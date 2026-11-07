"""The five milestones of the Launch journey (LM1-LM5, D89), computed from facts.

Each milestone names the record that completes it and when. Nothing here is stored and
nothing here grants a permission: a milestone is a celebration of something that already
happened in the data, never a box someone ticks (there is no route that marks one).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEXED_TYPES
from app.core.time import utcnow
from app.db.enums import ActionStatus, DocumentOrigin, ExtractionStatus, PlatformRole, Role
from app.db.models import (
    ActionRequest,
    Competence,
    CondoAssignment,
    Condominium,
    Contract,
    Document,
    DocumentChunk,
    Expense,
    Membership,
)
from app.pending import billing_expected


@dataclass(frozen=True)
class Milestone:
    key: str
    name: str
    done: bool
    # The record that proves it ({"type": ..., "id": ...}) and when it happened.
    fact: dict[str, str] | None = None
    when: datetime | date | None = None
    missing: list[str] = field(default_factory=list)  # pt-BR, what is still lacking
    details: dict[str, Any] = field(default_factory=dict)


def _ref(kind: str, obj_id: uuid.UUID) -> dict[str, str]:
    return {"type": kind, "id": str(obj_id)}


def _active_membership() -> Any:
    now = utcnow()
    return and_(
        Membership.revoked_at.is_(None),
        or_(Membership.expires_at.is_(None), Membership.expires_at > now),
    )


async def _lm1(session: AsyncSession, condo: Condominium) -> Milestone:
    name = "Prazer, condomínio!"
    row = (
        await session.execute(
            select(Membership.id, Membership.accepted_at)
            .where(
                Membership.condominium_id == condo.id,
                Membership.role == Role.SINDICO.value,
                _active_membership(),
            )
            .order_by(Membership.accepted_at.is_(None), Membership.accepted_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return Milestone("LM1", name, False, missing=["Nenhum síndico com acesso cadastrado."])
    if row.accepted_at is None:
        return Milestone("LM1", name, False, missing=["O síndico ainda não fez o primeiro acesso."])
    return Milestone("LM1", name, True, _ref("membership", row.id), row.accepted_at)


async def _lm2(session: AsyncSession, condo: Condominium) -> Milestone:
    name = "Seu condomínio ganhou memória"
    row = (
        await session.execute(
            select(Document.id, Document.created_at)
            .where(
                Document.condominium_id == condo.id,
                Document.extraction_status == ExtractionStatus.DONE.value,
                Document.doc_type.in_(INDEXED_TYPES),
                exists().where(DocumentChunk.document_id == Document.id),
            )
            .order_by(Document.created_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return Milestone(
            "LM2",
            name,
            False,
            missing=["Nenhum contrato, convenção ou ata lido e com trechos para consulta."],
        )
    return Milestone("LM2", name, True, _ref("document", row.id), row.created_at)


async def month_coverage(
    session: AsyncSession, condominium_id: uuid.UUID, month: date
) -> tuple[int, int]:
    """(contracts with a matched invoice in the month, contracts expecting one)."""
    contracts = (
        await session.scalars(select(Contract).where(Contract.condominium_id == condominium_id))
    ).all()
    expected = [c for c in contracts if billing_expected(c, month)]
    if not expected:
        return 0, 0
    matched = set(
        (
            await session.scalars(
                select(Expense.contract_id).where(
                    Expense.condominium_id == condominium_id,
                    Expense.competence == month,
                    Expense.contract_id.in_([c.id for c in expected]),
                )
            )
        ).all()
    )
    return len(matched), len(expected)


async def _lm3(session: AsyncSession, condo: Condominium) -> Milestone:
    name = "Seu assessor começou a investigar"
    # A month already evaluated by the rules (a competence exists only then) with at least one
    # invoice matched to a contract. The latest such month is the one shown.
    row = (
        await session.execute(
            select(Competence.id, Competence.month, Competence.created_at)
            .where(
                Competence.condominium_id == condo.id,
                exists().where(
                    Expense.condominium_id == condo.id,
                    Expense.competence == Competence.month,
                    Expense.contract_id.is_not(None),
                ),
            )
            .order_by(Competence.month.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return Milestone(
            "LM3",
            name,
            False,
            missing=["Nenhum mês com contrato e fatura casada já conferido pelas regras."],
        )
    with_invoice, expected = await month_coverage(session, condo.id, row.month)
    return Milestone(
        "LM3",
        name,
        True,
        _ref("competence", row.id),
        row.created_at,
        details={
            "mes": f"{row.month:%Y-%m}",
            "contratos_com_fatura": with_invoice,
            "contratos_esperados": expected,
        },
    )


async def _lm4(session: AsyncSession, condo: Condominium) -> Milestone:
    name = "Seu condomínio está conectado"
    now = utcnow()
    missing: list[str] = []
    reviewer = await session.scalar(
        select(CondoAssignment.id).where(
            CondoAssignment.condominium_id == condo.id,
            CondoAssignment.platform_role == PlatformRole.CONDOOS_REVIEWER.value,
            CondoAssignment.revoked_at.is_(None),
            or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
        )
    )
    if reviewer is None:
        missing.append("Nenhum revisor CondoOS atribuído.")
    emailed = await session.scalar(
        select(Document.id)
        .where(
            Document.condominium_id == condo.id,
            Document.origin == DocumentOrigin.EMAIL.value,
        )
        .order_by(Document.created_at)
        .limit(1)
    )
    company = None
    if condo.management_company_id is not None:
        company = await session.scalar(
            select(Membership.id).where(
                Membership.management_company_id == condo.management_company_id,
                _active_membership(),
            )
        )
    if emailed is None and company is None:
        missing.append(
            "Nenhum canal de entrada: documento por e-mail ou administradora com acesso."
        )
    if missing:
        return Milestone("LM4", name, False, missing=missing)
    assert reviewer is not None
    return Milestone(
        "LM4",
        name,
        True,
        _ref("condo_assignment", reviewer),
        details={"canal": "email" if emailed is not None else "administradora"},
    )


async def _lm5(session: AsyncSession, condo: Condominium) -> Milestone:
    name = "Seu assessor começou a agir"
    row = (
        await session.execute(
            select(ActionRequest.id, ActionRequest.executed_at)
            .where(
                ActionRequest.condominium_id == condo.id,
                ActionRequest.status == ActionStatus.EXECUTADA.value,
                ActionRequest.executed_at.is_not(None),
            )
            .order_by(ActionRequest.executed_at)
            .limit(1)
        )
    ).first()
    if row is None:
        return Milestone(
            "LM5",
            name,
            False,
            missing=["Nenhuma ação aprovada com a execução registrada por uma pessoa."],
        )
    return Milestone("LM5", name, True, _ref("action_request", row.id), row.executed_at)


async def milestones(session: AsyncSession, condo: Condominium) -> list[Milestone]:
    """LM1-LM5 in their fixed order. They are not sequential: any may be done first."""
    return [
        await _lm1(session, condo),
        await _lm2(session, condo),
        await _lm3(session, condo),
        await _lm4(session, condo),
        await _lm5(session, condo),
    ]
