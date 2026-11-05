"""Milestone 6: a new condominium enters without the seed — onboarding file, contracts from
the uploaded contract documents, and a competence created when its month is evaluated."""

import random
import uuid
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.br import generate_cnpj
from app.db.models import (
    AppUser,
    AuditLog,
    BoardMember,
    Competence,
    Condominium,
    Contract,
    Document,
    Membership,
)
from app.db.session import sessionmaker_for
from app.matching.documents import match_document
from app.onboarding import OnboardingIn, onboard
from app.rules.engine import evaluate
from tests.test_matching import _doc

COMPANY = "Atlântida Gestão Condominial Ltda (fictícia)"


def _spec(**over: Any) -> OnboardingIn:
    tag = uuid.uuid4().hex[:8]
    raw: dict[str, Any] = {
        "management_company_name": COMPANY,
        "condominium": {
            "name": f"Condomínio Teste {tag} (fictício)",
            "slug": f"teste-{tag}",
            "cnpj": generate_cnpj(random.Random(tag)),
            "units": 40,
            "address": "Rua Fictícia, 10 — Cidade Modelo/SP",
            "approval_limits": {"default": "6.000,00", "by_category": {"obras": "3000.00"}},
        },
        "board": [
            {
                "name": "Síndica Teste",
                "position": "sindico",
                "term_start": "2026-01-01",
                "email": f"sindica.{tag}@teste.example.com",
            },
            {
                "name": "Conselheiro Sem Login",
                "position": "conselheiro",
                "term_start": "2026-01-01",
            },
        ],
    }
    raw.update(over)
    return OnboardingIn.model_validate(raw)


async def test_onboarding_creates_condo_board_and_logins(admin_engine: AsyncEngine) -> None:
    spec = _spec()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, spec)
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(Condominium, condo.id)
        board = (
            await s.scalars(select(BoardMember).where(BoardMember.condominium_id == condo.id))
        ).all()
        roles = (
            await s.execute(
                select(AppUser.email, Membership.role)
                .join(Membership, Membership.user_id == AppUser.id)
                .where(Membership.condominium_id == condo.id)
            )
        ).all()
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.action == "condominium.onboarded", AuditLog.object_id == condo.id
            )
        )
    assert stored is not None and stored.management_company_id is not None
    assert stored.approval_limits["default"] == "6000.00"
    assert len(board) == 2
    assert [r for _, r in roles] == ["sindico"]  # the board member without e-mail has no login
    assert audit is not None

    with pytest.raises(ValueError, match="já existe"):
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await onboard(s, spec)


def test_onboarding_file_is_validated() -> None:
    with pytest.raises(ValidationError):
        _spec(condominium={**_spec().condominium.model_dump(), "cnpj": "11.111.111/1111-11"})
    with pytest.raises(ValidationError):
        _spec(board=[])


async def test_contract_document_registers_contract_once(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
    supplier_cnpj = generate_cnpj(random.Random(str(condo.id)))
    fields = {
        "cnpj_contratada": supplier_cnpj,
        "razao_social_contratada": "Limpa Tudo Serviços Ltda (fictícia)",
        "cnpj_contratante": condo.cnpj,
        "objeto": "Limpeza das áreas comuns",
        "itens_escopo": ["limpeza de áreas comuns", "limpeza de garagem"],
        "valor_mensal": "7300.00",
        "indice_reajuste": "IPCA",
        "mes_base_reajuste": 3,
        "data_inicio": "2025-03-01",
        "data_fim": "2027-02-28",
    }
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        first = _doc(condo, "contrato", fields)
        again = _doc(condo, "contrato", fields)  # the same contract sent twice
        foreign = _doc(
            condo, "contrato", {**fields, "cnpj_contratante": generate_cnpj(random.Random(1))}
        )
        pending = _doc(condo, "contrato", fields, needs_review=True)
        s.add_all([first, again, foreign, pending])
        await s.flush()
        for d in (first, again, foreign, pending):
            await match_document(s, d)
    async with sessionmaker_for(admin_engine)() as s:
        contracts = (
            await s.scalars(select(Contract).where(Contract.condominium_id == condo.id))
        ).all()
        sent_back = await s.get(Document, foreign.id)
    assert len(contracts) == 1
    c = contracts[0]
    assert c.monthly_value == 7300 and c.adjustment_index == "IPCA" and c.adjustment_base_month == 3
    assert c.source_document_id == first.id and c.end_date == date(2027, 2, 28)
    assert sent_back is not None and sent_back.needs_review
    assert "outro CNPJ" in sent_back.review_reasons[0]


async def test_evaluating_a_month_opens_its_competence(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
    month = date(2026, 10, 1)
    for _ in range(2):  # idempotent
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await evaluate(s, condo.id, month, date(2026, 11, 5))
    async with sessionmaker_for(admin_engine)() as s:
        comps = (
            await s.scalars(select(Competence).where(Competence.condominium_id == condo.id))
        ).all()
    assert [(c.month, c.status) for c in comps] == [(month, "aberta")]
