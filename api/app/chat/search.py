"""Document search for the chat: contracts, convention, internal rules and minutes.

Hybrid ranking (decision D52): cosine similarity from a local multilingual embedding model
(fastembed, ONNX, Apache-2.0) plus PostgreSQL Portuguese full-text rank. The model alone
confused topics in our tests; full text alone misses paraphrases. Without the model
(``EMBEDDINGS_ENABLED=false``) the search is full text only.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.enums import DocumentType
from app.db.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

INDEXED_TYPES = {DocumentType.CONTRATO.value, DocumentType.CONVENCAO.value, DocumentType.ATA.value}
INDEX_JOB = "document.index"
CHUNK_CHARS = 900
OVERLAP_CHARS = 150


@lru_cache
def _model() -> Any:
    from fastembed import TextEmbedding

    s = get_settings()
    return TextEmbedding(s.embedding_model, cache_dir=s.embedding_cache_dir)


def embed(texts: list[str]) -> list[list[float]] | None:
    if not get_settings().embeddings_enabled or not texts:
        return None
    return [list(map(float, v)) for v in _model().embed(texts)]


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def chunk_text(content: str) -> list[str]:
    """Split by paragraphs into ~900-character passages with a little overlap."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\f", content) if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if current and len(current) + len(p) + 1 > CHUNK_CHARS:
            chunks.append(current)
            current = current[-OVERLAP_CHARS:] + "\n" + p
        else:
            current = f"{current}\n{p}" if current else p
        while len(current) > CHUNK_CHARS * 1.5:
            chunks.append(current[:CHUNK_CHARS])
            current = current[CHUNK_CHARS - OVERLAP_CHARS :]
    if current:
        chunks.append(current)
    return chunks


async def index_document(session: AsyncSession, doc: Document) -> int:
    """(Re)build the passages of one document. Idempotent."""
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    if doc.doc_type not in INDEXED_TYPES or not doc.text_content:
        return 0
    chunks = chunk_text(doc.text_content)
    embedded = embed(chunks)
    vectors: list[list[float] | None] = list(embedded) if embedded else [None] * len(chunks)
    for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        await session.execute(
            text(
                "INSERT INTO document_chunk (id, condominium_id, document_id, chunk_index, text, embedding) "
                "VALUES (:id, :condo, :doc, :i, :text, CAST(:emb AS vector))"
            ),
            {
                "id": uuid.uuid4(),
                "condo": doc.condominium_id,
                "doc": doc.id,
                "i": i,
                "text": chunk,
                "emb": _vec(vector) if vector else None,
            },
        )
    return len(chunks)


async def index_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    doc = await session.get(Document, uuid.UUID(payload["document_id"]))
    if doc is not None:
        await index_document(session, doc)


# Full-text rank uses OR semantics (any meaningful word of the question). Two static
# statements: with and without the embedding term. Chunks without a vector score 0 there.
_SEARCH_SQL = """
    WITH q AS (
      SELECT to_tsquery('portuguese', coalesce(nullif(
        array_to_string(tsvector_to_array(to_tsvector('portuguese', :q)), ' | '), ''), 'x')) AS tsq
    )
    SELECT c.document_id, d.original_filename, d.doc_type, c.chunk_index, c.text,
           0.5 * SEMANTIC + 0.5 * ts_rank_cd(c.search_vector, q.tsq, 32) AS score
      FROM document_chunk c
      JOIN document d ON d.id = c.document_id, q
     WHERE c.condominium_id = :condo
     ORDER BY score DESC
     LIMIT :limit
"""
_HYBRID_SQL = text(
    _SEARCH_SQL.replace("SEMANTIC", "coalesce(1 - (c.embedding <=> CAST(:emb AS vector)), 0)")
)
_FULL_TEXT_SQL = text(_SEARCH_SQL.replace("SEMANTIC", "0"))


@dataclass(frozen=True)
class Passage:
    document_id: uuid.UUID
    document_name: str
    doc_type: str
    chunk_index: int
    text: str
    score: float


async def search(
    session: AsyncSession, condominium_id: uuid.UUID, query: str, limit: int = 5
) -> list[Passage]:
    vectors = embed([query])
    params: dict[str, Any] = {"condo": condominium_id, "q": query, "limit": limit}
    if vectors:
        params["emb"] = _vec(vectors[0])
    rows = await session.execute(_HYBRID_SQL if vectors else _FULL_TEXT_SQL, params)
    return [Passage(r[0], r[1], r[2], r[3], r[4], float(r[5])) for r in rows if float(r[5]) > 0.05]
