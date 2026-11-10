"""D120 (A1, A3): confidence by evidence and the CNPJ search in the text.

Fictitious contracts reproduce the cases found in testing: fields read at 80-89% that are
written in the document, a legal name that matches the Receita, and a contracted party's
CNPJ the model did not find although the text shows it."""

import random
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.br import format_cnpj, generate_cnpj
from app.db.enums import DocumentType
from app.db.models import Supplier
from app.db.session import sessionmaker_for
from app.extraction import evidence
from app.extraction.confidence import assess
from app.extraction.pipeline import _suggest_counterparty, registry_names

REF = date(2026, 11, 10)
CONDO = generate_cnpj(random.Random("ev-condo"))
SUPPLIER = generate_cnpj(random.Random("ev-supplier"))
MANAGER = generate_cnpj(random.Random("ev-manager"))

TEXT = f"""CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE JARDINAGEM
CONTRATANTE: Condomínio Residencial Fictício, CNPJ {format_cnpj(CONDO)},
representado por sua administradora, CNPJ {format_cnpj(MANAGER)}.
CONTRATADA: Verde Vivo Jardinagem Ltda, CNPJ {format_cnpj(SUPPLIER)}.
OBJETO: manutenção mensal dos jardins das áreas comuns.
Escopo: poda; adubação; irrigação.
Valor mensal de R$ 2.350,00, reajustado anualmente pelo IPCA.
Vigência a partir de 01/02/2026.
"""


def _raw(**over: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "cnpj_contratada": SUPPLIER,
        "razao_social_contratada": "Verde Vivo Jardinagem Ltda",
        "cnpj_contratante": CONDO,
        "objeto": "manutenção mensal dos jardins das áreas comuns",
        "itens_escopo": ["poda", "adubação", "irrigação"],
        "valor_mensal": "2350.00",
        "indice_reajuste": "IPCA",
        "data_inicio": "2026-02-01",
    }
    raw.update(over)
    return raw


def _assess(raw: dict[str, Any], conf: float, **kw: Any) -> Any:
    return assess(
        DocumentType.CONTRATO,
        raw,
        {k: conf for k in raw},
        condominium_cnpj=CONDO,
        today=REF,
        **kw,
    )


def test_written_values_are_confirmed() -> None:
    a = _assess(_raw(), 0.85, text=TEXT)
    assert a.reasons == []  # before D120 every field at 0.85 sent it to the queue
    assert a.confidence["valor_mensal"] == evidence.CONFIRMED
    assert a.evidence["valor_mensal"] == evidence.WRITTEN
    assert a.evidence["cnpj_contratante"] == evidence.OWN


def test_without_proof_the_model_confidence_stands() -> None:
    # No text: nothing is proven, the 0.9 rule sends it to the queue.
    a = _assess(_raw(), 0.85)
    assert any("Objeto" in r for r in a.reasons)
    assert "valor_mensal" not in a.evidence
    # A value not written in the text (the model's paraphrase, another amount) is not raised.
    a = _assess(_raw(valor_mensal="2530.00", objeto="jardinagem e paisagismo"), 0.85, text=TEXT)
    assert a.confidence["valor_mensal"] == 0.85
    assert any("Valor mensal" in r for r in a.reasons)
    assert any("Objeto" in r for r in a.reasons)


def test_a_doubted_value_is_not_raised_by_being_written() -> None:
    a = _assess(_raw(), 0.4, text=TEXT)
    assert a.confidence["valor_mensal"] == 0.4
    assert a.confidence["cnpj_contratante"] == evidence.CONFIRMED  # matches the registry


def test_a_flagged_field_is_never_raised() -> None:
    # The contracting party is the management company: written in the text, but the
    # validation note (not the condominium's CNPJ) keeps it in the queue.
    a = _assess(_raw(cnpj_contratante=MANAGER), 0.85, text=TEXT)
    assert a.confidence["cnpj_contratante"] <= 0.3
    assert any("não é o CNPJ do condomínio" in r for r in a.reasons)


def test_legal_name_matching_the_receita_confirms_both() -> None:
    raw = _raw(razao_social_contratada="VERDE VIVO JARDINAGEM LTDA.")
    a = _assess(raw, 0.8, registry_names={SUPPLIER: "Verde Vivo Jardinagem Ltda - ME"})
    assert a.evidence["cnpj_contratada"] == evidence.RECEITA
    assert a.evidence["razao_social_contratada"] == evidence.RECEITA
    a = _assess(raw, 0.8, registry_names={SUPPLIER: "Outra Empresa de Jardins Ltda"})
    assert "cnpj_contratada" not in a.evidence
    assert a.confidence["razao_social_contratada"] == 0.8


def test_same_legal_name() -> None:
    assert evidence.same_legal_name("Açaí & Cia Ltda", "ACAI CIA LTDA")
    assert not evidence.same_legal_name("Alfa Serviços Ltda", "Alfa Serviços Gerais Ltda")
    assert not evidence.same_legal_name(None, "Alfa")


def test_lone_cnpj_in_text_is_suggested() -> None:
    raw: dict[str, Any] = {"cnpj_contratante": CONDO}
    found = _suggest_counterparty(DocumentType.CONTRATO, raw, TEXT, CONDO, frozenset({MANAGER}))
    assert found == "cnpj_contratada" and raw["cnpj_contratada"] == SUPPLIER


def test_cnpj_search_needs_a_single_candidate() -> None:
    # Without excluding the management company there are two candidates: no suggestion.
    raw: dict[str, Any] = {}
    assert _suggest_counterparty(DocumentType.CONTRATO, raw, TEXT, CONDO, frozenset()) is None
    assert "cnpj_contratada" not in raw
    # The model's own valid CNPJ is never replaced.
    other = generate_cnpj(random.Random("ev-other"))
    raw = {"cnpj_contratada": other}
    assert (
        _suggest_counterparty(DocumentType.CONTRATO, raw, TEXT, CONDO, frozenset({MANAGER})) is None
    )
    assert raw["cnpj_contratada"] == other
    # Invalid check digits in the text are not CNPJs.
    assert evidence.cnpjs_in_text("CNPJ 11.111.111/1111-11") == []


def test_suggested_cnpj_needs_the_receita() -> None:
    from app.extraction.pipeline import SUGGESTED_FROM_TEXT

    raw = _raw()
    conf = {k: 0.95 for k in raw} | {"cnpj_contratada": SUGGESTED_FROM_TEXT}
    a = assess(DocumentType.CONTRATO, raw, conf, condominium_cnpj=CONDO, today=REF, text=TEXT)
    assert a.confidence["cnpj_contratada"] == SUGGESTED_FROM_TEXT  # written, but suggested
    a = assess(
        DocumentType.CONTRATO,
        raw,
        conf,
        condominium_cnpj=CONDO,
        today=REF,
        text=TEXT,
        registry_names={SUPPLIER: "Verde Vivo Jardinagem Ltda"},
    )
    assert a.confidence["cnpj_contratada"] == evidence.CONFIRMED


async def test_registry_names_come_from_trusted_supplier_data(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        seeded = await s.scalar(
            select(Supplier).where(Supplier.enrichment_source == "seed").limit(1)
        )
        assert seeded is not None
        names = await registry_names(
            s, {"cnpj_contratada": seeded.cnpj, "cnpj_prestador": SUPPLIER}, allow_network=True
        )
        # The seed supplier is trusted; the unknown CNPJ would need the Receita, which is
        # offline in tests: no proof, no failure.
        assert names == {seeded.cnpj: seeded.legal_name}
        await s.rollback()
