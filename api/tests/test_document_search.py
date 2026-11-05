"""Milestone 5: governing documents are chunked, indexed and searched per condominium."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.chat.search import chunk_text, search
from app.db.models import Contract, DocumentChunk
from app.db.session import sessionmaker_for
from tests.helpers import condo_id


def test_chunk_text_splits_long_text_with_overlap() -> None:
    paragraphs = [f"Parágrafo {i}. " + "texto " * 40 for i in range(12)]
    chunks = chunk_text("\n\n".join(paragraphs))
    assert len(chunks) > 1
    assert all(len(c) <= 1400 for c in chunks)
    assert "Parágrafo 0." in chunks[0] and "Parágrafo 11." in chunks[-1]


async def test_seed_documents_are_indexed(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(admin_engine)() as s:
        n = await s.scalar(select(func.count()).where(DocumentChunk.condominium_id == acacias))
        linked = await s.scalar(
            select(func.count()).where(
                Contract.condominium_id == acacias, Contract.source_document_id.is_not(None)
            )
        )
    assert n and n >= 5
    assert linked and linked >= 3


async def test_search_finds_clause_and_stays_in_condominium(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with sessionmaker_for(admin_engine)() as s:
        hits = await search(s, acacias, "qual a multa de rescisão do contrato de portaria?")
        approval = await search(s, acacias, "quem aprova despesas de obras acima do limite?")
        other = await search(s, mirante, "pintura da fachada orçamentos")
        nothing = await search(s, acacias, "xyzzy plutônio")
    assert hits and hits[0].doc_type == "contrato" and "Portaria" in hits[0].text
    assert "multa" in hits[0].text
    assert any("Art. 14" in p.text and p.doc_type == "convencao" for p in approval)
    assert other and all(p.document_name for p in other)
    mirante_ids = {p.document_id for p in other}
    acacias_ids = {p.document_id for p in hits + approval}
    assert not mirante_ids & acacias_ids
    assert nothing == []
