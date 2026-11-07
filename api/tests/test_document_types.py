"""LB-020 (D91): regimento interno, apólice, balancete, laudo and plano de manutenção are
classified by their title, kept as text (no extraction, never in the exception queue),
searchable, and shown on the first-value card as memory. A contract amendment is still a
contract (D66)."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.chat.search import INDEXED_TYPES, index_document
from app.db.enums import DocumentType
from app.db.models import Condominium, Document
from app.db.session import sessionmaker_for
from app.extraction.heuristics import classify_text
from app.extraction.pipeline import analyze
from app.launch.first_value import first_value
from corpus.generate import Pdf
from tests.helpers import condo_id

REF = date(2026, 11, 7)
NEW_TYPES = {
    DocumentType.REGIMENTO: "REGIMENTO INTERNO DO CONDOMÍNIO RESIDENCIAL FICTÍCIO\n"
    "Capítulo I — Do uso das áreas comuns. O salão de festas funciona até as 22h.",
    DocumentType.APOLICE: "APÓLICE DE SEGURO CONDOMINIAL Nº 0001234\n"
    "Seguradora: Seguros Fictícios S.A. Segurado: Condomínio Residencial Fictício.\n"
    "Cobertura básica: incêndio, raio e explosão.",
    DocumentType.BALANCETE: "BALANCETE MENSAL — OUTUBRO DE 2026\n"
    "Receitas: taxas condominiais. Despesas: portaria, limpeza, energia.",
    DocumentType.LAUDO: "LAUDO TÉCNICO DE INSPEÇÃO PREDIAL\n"
    "Responsável técnico: Eng. Fictício, CREA 000000. Fachada sem fissuras relevantes.",
    DocumentType.PLANO_MANUTENCAO: "PLANO DE MANUTENÇÃO PREVENTIVA — PMOC 2026\n"
    "Contratada: Clima Fictício Ltda. Contratante: Condomínio Fictício. Limpeza mensal dos "
    "filtros dos aparelhos de ar-condicionado.",
}


@pytest.mark.parametrize("doc_type", list(NEW_TYPES))
def test_new_types_are_classified_by_title(doc_type: DocumentType) -> None:
    assert classify_text(NEW_TYPES[doc_type], REF).doc_type == doc_type
    assert doc_type.value in INDEXED_TYPES


def test_amendment_is_still_a_contract() -> None:
    text = (
        "PRIMEIRO TERMO ADITIVO AO CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE LIMPEZA\n"
        "CONTRATANTE: Condomínio Fictício. CONTRATADA: Limpa Bem Serviços Ltda.\n"
        "Cláusula primeira — o valor mensal passa a ser R$ 5.200,00."
    )
    assert classify_text(text, REF).doc_type == DocumentType.CONTRATO


def _pdf(text: str) -> bytes:
    pdf = Pdf()
    for line in text.splitlines():
        pdf.text(line)
    return pdf.bytes()


async def test_new_type_is_text_only_searchable_and_memory(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    text = NEW_TYPES[DocumentType.LAUDO]
    analysis = await analyze(
        None,
        data=_pdf(text),
        mime="application/pdf",
        filename="laudo.pdf",
        condominium_id=acacias,
        condominium_cnpj="00000000000000",
        today=REF,
    )
    assert analysis.doc_type == DocumentType.LAUDO
    assert analysis.complete and analysis.values == {}  # text only: no extraction, no queue

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await s.get(Condominium, acacias)
        assert condo is not None
        doc = Document(
            id=uuid.uuid4(),
            condominium_id=acacias,
            doc_type=DocumentType.LAUDO.value,  # accepted by the CHECK (migration 0019)
            storage_key=f"cond/{acacias}/laudo",
            sha256=uuid.uuid4().hex * 2,
            original_filename="laudo.pdf",
            mime_type="application/pdf",
            origin="upload",
            extraction_status="done",
            extracted={},
            field_confidence={},
            needs_review=False,
            review_reasons=[],
            text_content=analysis.text,
            page_count=1,
        )
        s.add(doc)
        await s.flush()
        assert await index_document(s, doc) >= 1
        card = await first_value(s, doc)
        assert card["state"] == "memoria"
        assert "laudo técnico" in card["message"]
        assert any("profissional" in limit for limit in card["limits"])
        await s.rollback()
