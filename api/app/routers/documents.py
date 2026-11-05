"""Document upload and reading, scoped to one condominium."""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.db.enums import DocumentOrigin
from app.db.models import Document
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


class DocumentDetailOut(DocumentOut):
    extracted: dict[str, Any]
    field_confidence: dict[str, float]
    file_url: str


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
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    condominium_id: uuid.UUID, files: list[UploadFile], access: CanUpload, db: DbSession
) -> list[UploadResultOut]:
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
    return DocumentDetailOut(
        **_out(doc).model_dump(),
        extracted=doc.extracted,
        field_confidence=doc.field_confidence,
        file_url=url,
    )


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
