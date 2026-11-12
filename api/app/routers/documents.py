"""Document upload and reading, scoped to one condominium."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.core.audit import record_audit
from app.db.enums import DocumentOrigin, DocumentType, ExtractionStatus
from app.db.models import Contract, Document, DocumentChunk
from app.db.session import DbSession
from app.ingestion.documents import ingest_file
from app.storage.base import get_storage

router = APIRouter(prefix="/condominiums/{condominium_id}/documents", tags=["documents"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanUpload = Annotated[CondoAccess, Depends(require(Permission.UPLOAD_DOCUMENT))]
MAX_FILES_PER_REQUEST = 30


class UploadResultOut(BaseModel):
    filename: str
    document_id: uuid.UUID | None
    duplicate: bool
    error: str | None


class DocumentOut(BaseModel):
    id: uuid.UUID
    doc_type: str
    original_filename: str
    mime_type: str
    origin: str
    extraction_status: str
    needs_review: bool
    created_at: datetime
    version: int = 1
    supersedes_id: uuid.UUID | None = None


class DocumentDetailOut(DocumentOut):
    extracted: dict[str, Any]
    field_confidence: dict[str, float]
    field_provenance: dict[str, Any] = {}
    file_url: str
    superseded_by_id: uuid.UUID | None = None  # set when a newer version exists (CB-031)


def _out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        doc_type=doc.doc_type,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        origin=doc.origin,
        extraction_status=doc.extraction_status,
        needs_review=doc.needs_review,
        created_at=doc.created_at,
        version=doc.version,
        supersedes_id=doc.supersedes_id,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    condominium_id: uuid.UUID,
    files: list[UploadFile],
    access: CanUpload,
    db: DbSession,
    tipo: str | None = None,
) -> list[UploadResultOut]:
    """``tipo`` (ata or convencao, D130): what the person says the file is; used only when
    the reading does not find a type."""
    from app.extraction.pipeline import TYPE_HINTS

    if tipo is not None and tipo not in TYPE_HINTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo não aceito.")
    if not files:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nenhum arquivo enviado.")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Envie no máximo {MAX_FILES_PER_REQUEST} arquivos por vez.",
        )
    limit = get_settings().max_upload_mb * 1024 * 1024
    results = []
    for upload_file in files:
        data = await upload_file.read(limit + 1)
        outcome = await ingest_file(
            db,
            condominium_id=access.condominium_id,
            filename=upload_file.filename or "arquivo",
            data=data,
            origin=DocumentOrigin.UPLOAD,
            actor_user_id=access.user_id,
        )
        if tipo is not None and outcome.document_id is not None and outcome.error is None:
            doc = await db.get(Document, outcome.document_id)
            if (
                doc is not None
                and doc.reviewed_at is None
                and doc.doc_type == DocumentType.OUTRO.value
            ):
                doc.doc_type, doc.classification_source = tipo, "pessoa"
                if outcome.duplicate and doc.text_content:
                    # Already read without a type: the declaration completes it now.
                    doc.needs_review, doc.review_reasons = False, []
                    doc.extraction_status = ExtractionStatus.DONE.value
                    from app.extraction.pipeline import enqueue_index

                    await enqueue_index(db, doc)
        results.append(
            UploadResultOut(
                filename=outcome.filename,
                document_id=outcome.document_id,
                duplicate=outcome.duplicate,
                error=outcome.error,
            )
        )
    return results


@router.get("")
async def list_documents(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[DocumentOut]:
    rows = await db.scalars(
        select(Document)
        .where(Document.condominium_id == access.condominium_id)
        .order_by(Document.created_at.desc())
        .limit(500)
    )
    return [_out(d) for d in rows]


@router.get("/{document_id}")
async def get_document(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanView, db: DbSession
) -> DocumentDetailOut:
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id, Document.condominium_id == access.condominium_id
        )
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    url = await asyncio.to_thread(get_storage().presigned_url, doc.storage_key)
    newer = await db.scalar(select(Document.id).where(Document.supersedes_id == doc.id))
    return DocumentDetailOut(
        **_out(doc).model_dump(),
        extracted=doc.extracted,
        field_confidence=doc.field_confidence,
        field_provenance=doc.field_provenance or {},
        file_url=url,
        superseded_by_id=newer,
    )


@router.post("/{document_id}/versions", status_code=status.HTTP_201_CREATED)
async def upload_new_version(
    condominium_id: uuid.UUID,
    document_id: uuid.UUID,
    access: CanUpload,
    db: DbSession,
    file: UploadFile,
) -> DocumentOut:
    """A new file of the same logical document (CB-031): the previous one is kept, leaves the
    search and stops being the source of its contract. Extraction runs on the new one."""
    old = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.condominium_id == access.condominium_id)
        .with_for_update()
    )
    if old is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    if await db.scalar(select(Document.id).where(Document.supersedes_id == old.id)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este documento já tem uma versão mais nova; envie a partir dela.",
        )
    limit = get_settings().max_upload_mb * 1024 * 1024
    outcome = await ingest_file(
        db,
        condominium_id=access.condominium_id,
        filename=file.filename or old.original_filename,
        data=await file.read(limit + 1),
        origin=DocumentOrigin.UPLOAD,
        actor_user_id=access.user_id,
    )
    if outcome.document_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, outcome.error or "Arquivo inválido."
        )
    if outcome.duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Esse arquivo já está no sistema: não é uma versão nova."
        )
    new = await db.get(Document, outcome.document_id)
    assert new is not None
    new.supersedes_id = old.id
    new.version = old.version + 1
    if new.doc_type == DocumentType.OUTRO.value:
        new.doc_type = old.doc_type  # same logical document until extraction says otherwise
    for contract in await db.scalars(select(Contract).where(Contract.source_document_id == old.id)):
        contract.source_document_id = new.id
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == old.id))
    await record_audit(
        db,
        action="document.new_version",
        object_type="document",
        object_id=new.id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details={"supersedes_id": str(old.id), "version": new.version},
    )
    await db.flush()
    return _out(new)


@router.get("/{document_id}/file", response_class=RedirectResponse, status_code=307)
async def open_document_file(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanView, db: DbSession
) -> RedirectResponse:
    """Open the original file (used by chat citations): a short-lived storage link."""
    doc = await db.scalar(
        select(Document).where(
            Document.id == document_id, Document.condominium_id == access.condominium_id
        )
    )
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    url = await asyncio.to_thread(get_storage().presigned_url, doc.storage_key)
    return RedirectResponse(url, status_code=307)
