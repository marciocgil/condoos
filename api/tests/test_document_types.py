"""LB-020 (D93): apólice, balancete, regimento interno, laudo técnico and plano de manutenção
are classified by their title and kept as searchable text, with no structured extraction.
A termo aditivo stays a contract document (D66)."""

import random
import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.rbac import CondoAccess
from app.chat.search import index_document
from app.chat.tools import ChatTools
from app.core.br import generate_cnpj
from app.db.enums import DocumentOrigin, DocumentType, Role
from app.db.models import Condominium, Document
from app.db.session import sessionmaker_for, set_tenant_scope
from app.extraction.heuristics import classify_text
from app.extraction.pipeline import process_document
from app.ingestion.documents import ingest_file
from app.onboarding import OnboardingIn, onboard
from corpus.generate import Pdf

REF = date(2026, 11, 7)

POSITIVE = {
    DocumentType.APOLICE: (
        "APÓLICE DE SEGURO CONDOMINIAL Nº 123\nSeguradora Fictícia S.A.\n"
        "Segurado: Condomínio Modelo. Cobertura básica de incêndio, raio e explosão."
    ),
    DocumentType.BALANCETE: (
        "BALANCETE MENSAL — OUTUBRO DE 2026\nReceitas: taxa condominial.\n"
        "Despesas: portaria, limpeza, energia. Saldo do mês."
    ),
    DocumentType.REGIMENTO: (
        "REGIMENTO INTERNO DO CONDOMÍNIO MODELO\nCapítulo I — Do uso das áreas comuns.\n"
        "Art. 1º O salão de festas pode ser reservado com 7 dias de antecedência."
    ),
    DocumentType.LAUDO: (
        "LAUDO TÉCNICO DE INSPEÇÃO PREDIAL\nResponsável técnico: Eng. Fictício, CREA 0000.\n"
        "Constatou-se fissura na laje da garagem, nível de risco médio."
    ),
    DocumentType.PLANO_MANUTENCAO: (
        "PLANO DE MANUTENÇÃO PREVENTIVA 2027\nElevadores: mensal. Bombas: trimestral.\n"
        "Para-raios: anual, conforme norma."
    ),
}


@pytest.mark.parametrize(("expected", "text"), list(POSITIVE.items()))
def test_new_types_are_told_by_their_title(expected: DocumentType, text: str) -> None:
    assert classify_text(text, REF).doc_type == expected


def test_contracts_and_amendments_stay_contracts() -> None:
    contract = (
        "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE MANUTENÇÃO\nCONTRATANTE: Condomínio Modelo.\n"
        "CONTRATADA: Manutenção Fictícia Ltda. Cláusula 1ª — a CONTRATADA seguirá o plano de "
        "manutenção preventiva e emitirá laudo anual."
    )
    assert classify_text(contract, REF).doc_type == DocumentType.CONTRATO
    amendment = (
        "PRIMEIRO TERMO ADITIVO AO CONTRATO DE LIMPEZA\nCONTRATANTE: Condomínio Modelo.\n"
        "CONTRATADA: Limpeza Fictícia Ltda. O valor mensal passa a R$ 9.500,00."
    )
    assert classify_text(amendment, REF).doc_type == DocumentType.CONTRATO


def test_a_mention_in_the_body_is_not_a_title() -> None:
    receipt = "RECIBO\nRecebi do condomínio R$ 300,00 pela emissão do laudo de vistoria."
    assert classify_text(receipt, REF).doc_type == DocumentType.RECIBO
    minutes = (
        "ATA DA ASSEMBLEIA GERAL ORDINÁRIA\nAprovado o balancete anual e o novo regimento "
        "interno, conforme votação."
    )
    assert classify_text(minutes, REF).doc_type == DocumentType.ATA


async def test_rules_document_is_read_as_text_and_searchable(
    admin_engine: AsyncEngine, worker_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    tag = uuid.uuid4().hex[:8]
    spec = OnboardingIn.model_validate(
        {
            "management_company_name": "Atlântida Gestão Condominial Ltda (fictícia)",
            "condominium": {
                "name": f"Condomínio Tipos {tag} (fictício)",
                "slug": f"tipos-{tag}",
                "cnpj": generate_cnpj(random.Random(tag)),
                "units": 10,
                "address": "Rua Fictícia, 40 — Cidade Modelo/SP",
            },
            "board": [
                {
                    "name": "Síndica Tipos",
                    "position": "sindico",
                    "term_start": "2026-01-01",
                    "email": f"sindica.{tag}@tipos.example.com",
                }
            ],
        }
    )
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, spec)
    p = Pdf()
    p.text("REGIMENTO INTERNO DO CONDOMÍNIO", 11, True, gap=22)
    p.text("Art. 1º O salão de festas pode ser reservado com 7 dias de antecedência.", 9)
    p.text("Art. 2º Mudanças só de segunda a sábado, das 8h às 18h.", 9)
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        out = await ingest_file(
            s,
            condominium_id=condo.id,
            filename="regimento.pdf",
            data=p.bytes(),
            origin=DocumentOrigin.UPLOAD,
            actor_user_id=None,
        )
    assert out.document_id is not None, out.error
    async with maker() as s, s.begin():
        await process_document(s, {"document_id": str(out.document_id)})
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        doc = await s.get(Document, out.document_id)
        assert doc is not None
        assert doc.doc_type == DocumentType.REGIMENTO.value
        assert doc.extraction_status == "done" and not doc.needs_review
        assert doc.extracted == {}  # text only: no field is extracted
        assert await index_document(s, doc) > 0
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [condo.id])
        tools = ChatTools(
            s,
            CondoAccess(
                user_id=uuid.uuid4(), condominium_id=condo.id, roles=frozenset({Role.SINDICO})
            ),
        )
        found = await tools.run("search_documents", {"query": "salão de festas reserva"})
    assert any(t["tipo"] == "regimento" for t in found["trechos"])
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.scalar(select(Condominium).where(Condominium.id == condo.id))
    assert stored is not None and stored.approval_limits == {}  # created without a limit
