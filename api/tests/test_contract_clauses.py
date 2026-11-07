"""CB-060 (FR-041, FR-042; D85): notice period, automatic renewal and termination penalty read
from the contract text by rule, with the excerpt; the agenda shows the notice deadline."""

import random
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agenda import condominium_agenda
from app.core.br import generate_cnpj
from app.db.models import Contract
from app.db.session import sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.extraction.clauses import apply_clauses, read_clauses
from app.onboarding import onboard
from tests.test_onboarding import _spec

SEED_TEXT = (
    "CLÁUSULA 5 — DA RESCISÃO. Qualquer das partes poderá rescindir este contrato mediante "
    "aviso prévio de 30 dias. A rescisão sem o aviso prévio sujeita a parte que a der causa a "
    "multa de R$ 27.000,00.\nCLÁUSULA 6 — DOS SERVIÇOS EXTRAS."
)


def test_reads_terms_with_their_excerpts() -> None:
    c = read_clauses(SEED_TEXT)
    assert c.notice_days == 30 and c.termination_penalty == "R$ 27.000,00"
    assert c.auto_renewal is None  # the text says nothing: not guessed
    assert "aviso prévio de 30 dias" in c.evidence["notice_days"]["excerpt"]
    other = read_clauses(
        "Rescisão mediante comunicação com 90 (noventa) dias de antecedência. O contrato será "
        "prorrogado automaticamente por iguais períodos. Multa equivalente a 3 (três) "
        "mensalidades; demais condições."
    )
    assert other.notice_days == 90 and other.auto_renewal is True
    assert other.termination_penalty == "3 (três) mensalidades"
    assert read_clauses("aviso prévio de sessenta dias. Não será renovado.").notice_days == 60
    assert read_clauses("Não será renovado automaticamente.").auto_renewal is False


def test_nothing_is_invented() -> None:
    empty = read_clauses("Contrato de limpeza. Valor mensal de R$ 5.000,00. Pagamento até o dia 5.")
    assert (empty.notice_days, empty.auto_renewal, empty.termination_penalty) == (None, None, None)
    assert empty.evidence == {}
    # "dias de antecedência" outside a termination clause is not a notice period.
    assert read_clauses("A nota será enviada com 10 dias de antecedência.").notice_days is None


async def test_seed_contracts_have_terms(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        contracts = list(
            await s.scalars(select(Contract).where(Contract.source_document_id.is_not(None)))
        )
    assert contracts and all(c.notice_days for c in contracts)
    assert all("excerpt" in c.clause_evidence["notice_days"] for c in contracts)


async def test_agenda_shows_notice_deadline_and_people_keep_their_values(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        sup = await get_or_create_supplier(
            s, generate_cnpj(random.Random(f"cl-{condo.id}")), "Limpeza Fictícia Ltda"
        )
        contract = Contract(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=sup.id,
            object="Limpeza",
            scope_items=[],
            monthly_value=Decimal("5000.00"),
            adjustment_index="IPCA",
            adjustment_base_month=1,
            billing_frequency_months=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            notice_days=45,  # set by a person: kept
        )
        assert apply_clauses(contract, SEED_TEXT + " Será renovado automaticamente.")
        assert contract.notice_days == 45 and contract.auto_renewal is True
        assert "notice_days" not in contract.clause_evidence
        s.add(contract)
        await s.flush()
        events = await condominium_agenda(
            s, condo.id, date(2026, 11, 1), date(2026, 12, 31), date(2026, 11, 7)
        )
    notice = [e for e in events if e.kind == "aviso_previo"]
    assert len(notice) == 1
    assert notice[0].date == date(2026, 11, 16)  # 45 days before 31/12
    assert notice[0].status == "previsto" and "renova automaticamente" in notice[0].detail
