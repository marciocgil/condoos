"""Document ingestion: one entry point for uploads and e-mail attachments.

Idempotent by SHA-256: the same file sent twice to the same condominium is stored once.
The heavy work (classification, extraction, bank import) runs in the ``document.process`` job.
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import record_audit
from app.core.jobs import enqueue
from app.db.enums import DocumentOrigin, DocumentType, ExtractionStatus
from app.db.models import Document
from app.ingestion.filetypes import UnsupportedFile, sniff
from app.storage.base import get_storage
from app.storage.s3 import document_key

PROCESS_JOB = "document.process"


@dataclass(frozen=True)
class IngestOutcome:
    filename: str
    document_id: uuid.UUID | None
    duplicate: bool = False
    error: str | None = None


async def ingest_file(
    session: AsyncSession,
    *,
    condominium_id: uuid.UUID,
    filename: str,
    data: bytes,
    origin: DocumentOrigin,
    actor_user_id: uuid.UUID | None,
    process: bool = True,
) -> IngestOutcome:
    """Store a file as a document of the condominium. ``process=False`` (evidence attached to
    a case, D80) keeps it out of extraction and of the exception queue: it is a photo or a
    report that proves something, not a fiscal document to read."""
    safe_name = filename.replace("/", "_").replace("\\", "_")[:300] or "arquivo"
    limit = get_settings().max_upload_mb * 1024 * 1024
    if not data:
        return IngestOutcome(safe_name, None, error="Arquivo vazio.")
    if len(data) > limit:
        return IngestOutcome(
            safe_name, None, error=f"Arquivo maior que {get_settings().max_upload_mb} MB."
        )
    try:
        mime = sniff(safe_name, data)
    except UnsupportedFile as exc:
        return IngestOutcome(safe_name, None, error=str(exc))

    sha = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document.id).where(Document.condominium_id == condominium_id, Document.sha256 == sha)
    )
    if existing is not None:
        return IngestOutcome(safe_name, existing, duplicate=True)

    key = document_key(condominium_id, sha, safe_name)
    await asyncio.to_thread(get_storage().put, key, data, mime)

    doc = Document(
        id=uuid.uuid4(),
        condominium_id=condominium_id,
        doc_type=DocumentType.OUTRO.value,
        storage_key=key,
        sha256=sha,
        original_filename=safe_name,
        mime_type=mime,
        origin=origin.value,
        extraction_status=(
            ExtractionStatus.PENDING.value if process else ExtractionStatus.DONE.value
        ),
        extracted={},
        field_confidence={},
        needs_review=False,
        classification_source=None if process else "evidencia",
    )
    session.add(doc)
    await session.flush()
    if process:
        await enqueue(
            session,
            PROCESS_JOB,
            {"document_id": str(doc.id)},
            condominium_id=condominium_id,
            dedupe_key=f"doc:{doc.id}:process",
        )
    await record_audit(
        session,
        action="document.uploaded",
        object_type="document",
        object_id=doc.id,
        actor_user_id=actor_user_id,
        condominium_id=condominium_id,
        details={"origin": origin.value, "evidence": not process},
    )
    return IngestOutcome(safe_name, doc.id)
