"""Exception queue (spec §7): extraction items to correct and serious findings to validate.

Corrections are stored field by field in ``extraction_correction`` as training data. Once a
person reviews a document it is never overwritten by automatic extraction again.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, require, roles_on_condominium
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.br import is_valid_cnpj, is_valid_cpf
from app.core.time import utcnow
from app.db.enums import DocumentType, ExtractionStatus, FindingStatus
from app.db.models import Condominium, Document, ExtractionCorrection, Finding
from app.db.session import DbSession
from app.extraction.confidence import COUNTERPARTY_CNPJ, OWN_CNPJ
from app.extraction.fields import REVIEW_THRESHOLD, SPECS, InvalidValue, normalize, specs_for
from app.storage.base import get_storage

router = APIRouter(tags=["queue"])

CanCorrect = Annotated[CondoAccess, Depends(require(Permission.CORRECT_EXTRACTION))]
REVIEWABLE_TYPES = [t.value for t in SPECS]


class QueueItemOut(BaseModel):
    kind: Literal["extracao", "achado_grave"]
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    title: str
    detail: str
    created_at: datetime


class FieldSpecOut(BaseModel):
    name: str
    label: str
    kind: str
    required: bool


class ReviewOut(BaseModel):
    document_id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_cnpj: str
    original_filename: str
    mime_type: str
    doc_type: str
    reviewable_types: list[str]
    fields_by_type: dict[str, list[FieldSpecOut]]
    values: dict[str, Any]
    confidence: dict[str, float]
    reasons: list[str]
    threshold: float
    file_url: str
    text_content: str | None
    reviewed_at: datetime | None


class ReviewIn(BaseModel):
    doc_type: str
    values: dict[str, Any]


class DiscardIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


# --------------------------------------------------------------------------- queue listing


async def _queue(db: DbSession, principal: CurrentPrincipal) -> list[QueueItemOut]:
    condos = (
        await db.scalars(select(Condominium).where(Condominium.id.in_(principal.condominium_ids)))
    ).all()
    can_correct: dict[uuid.UUID, str] = {}
    can_validate: dict[uuid.UUID, str] = {}
    for condo in condos:
        access = CondoAccess(
            principal.user.id, condo.id, await roles_on_condominium(db, principal.user.id, condo)
        )
        if access.can(Permission.CORRECT_EXTRACTION):
            can_correct[condo.id] = condo.name
        if access.can(Permission.VALIDATE_FINDING):
            can_validate[condo.id] = condo.name

    items: list[QueueItemOut] = []
    if can_correct:
        docs = await db.scalars(
            select(Document)
            .where(Document.condominium_id.in_(can_correct), Document.needs_review.is_(True))
            .order_by(Document.created_at)
        )
        for d in docs:
            items.append(
                QueueItemOut(
                    kind="extracao",
                    id=d.id,
                    condominium_id=d.condominium_id,
                    condominium_name=can_correct[d.condominium_id],
                    title=f"Extração com baixa confiança: {d.original_filename}",
                    detail="; ".join(d.review_reasons[:2]),
                    created_at=d.created_at,
                )
            )
    if can_validate:
        findings = await db.scalars(
            select(Finding)
            .where(
                Finding.condominium_id.in_(can_validate),
                Finding.status == FindingStatus.AGUARDANDO_VALIDACAO.value,
            )
            .order_by(Finding.amount_at_risk.desc())
        )
        for f in findings:
            items.append(
                QueueItemOut(
                    kind="achado_grave",
                    id=f.id,
                    condominium_id=f.condominium_id,
                    condominium_name=can_validate[f.condominium_id],
                    title=f"Grave: {f.title}",
                    detail=f"R$ {f.amount_at_risk}",
                    created_at=f.created_at,
                )
            )
    return items


@router.get("/queue")
async def list_queue(db: DbSession, principal: CurrentPrincipal) -> list[QueueItemOut]:
    return await _queue(db, principal)


@router.get("/queue/count")
async def queue_count(db: DbSession, principal: CurrentPrincipal) -> dict[str, int]:
    items = await _queue(db, principal)
    return {
        "total": len(items),
        "extracao": sum(i.kind == "extracao" for i in items),
        "achado_grave": sum(i.kind == "achado_grave" for i in items),
    }


# --------------------------------------------------------------------------- review


async def _doc_and_condo(
    db: DbSession, access: CondoAccess, document_id: uuid.UUID
) -> tuple[Document, Condominium]:
    doc = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.condominium_id == access.condominium_id)
        .with_for_update()
    )
    condo = await db.get(Condominium, access.condominium_id)
    if doc is None or condo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    return doc, condo


@router.get("/condominiums/{condominium_id}/documents/{document_id}/review")
async def get_review(
    condominium_id: uuid.UUID, document_id: uuid.UUID, access: CanCorrect, db: DbSession
) -> ReviewOut:
    doc, condo = await _doc_and_condo(db, access, document_id)
    return ReviewOut(
        document_id=doc.id,
        condominium_id=condo.id,
        condominium_cnpj=condo.cnpj,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        doc_type=doc.doc_type,
        reviewable_types=REVIEWABLE_TYPES,
        fields_by_type={
            t.value: [
                FieldSpecOut(name=s.name, label=s.label, kind=s.kind, required=s.required)
                for s in specs
            ]
            for t, specs in SPECS.items()
        },
        values=doc.extracted,
        confidence=doc.field_confidence,
        reasons=doc.review_reasons,
        threshold=REVIEW_THRESHOLD,
        file_url=await asyncio.to_thread(get_storage().presigned_url, doc.storage_key),
        text_content=doc.text_content,
        reviewed_at=doc.reviewed_at,
    )


def _validate(doc_type: DocumentType, raw: dict[str, Any], condo_cnpj: str) -> dict[str, Any]:
    errors: dict[str, str] = {}
    values: dict[str, Any] = {}
    for spec in specs_for(doc_type):
        try:
            value = normalize(spec.kind, raw.get(spec.name))
        except InvalidValue as exc:
            errors[spec.name] = str(exc)
            continue
        if value is None and spec.required:
            errors[spec.name] = "Campo obrigatório."
        elif spec.kind == "cnpj" and value is not None and not is_valid_cnpj(value):
            errors[spec.name] = "CNPJ com dígito verificador inválido."
        elif (
            spec.kind == "doc"
            and value is not None
            and not (is_valid_cnpj(value) or is_valid_cpf(value))
        ):
            errors[spec.name] = "CPF/CNPJ com dígito verificador inválido."
        elif spec.name in OWN_CNPJ and value is not None and value != condo_cnpj:
            errors[spec.name] = (
                "Não é o CNPJ deste condomínio. Se o documento é de outro condomínio, descarte-o."
            )
        elif spec.name in COUNTERPARTY_CNPJ and value == condo_cnpj:
            errors[spec.name] = "Este é o CNPJ do próprio condomínio, não do fornecedor."
        values[spec.name] = value
    if errors:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": "Corrija os campos indicados.", "fields": errors},
        )
    return values


@router.put("/condominiums/{condominium_id}/documents/{document_id}/review")
async def save_review(
    condominium_id: uuid.UUID,
    document_id: uuid.UUID,
    body: ReviewIn,
    access: CanCorrect,
    db: DbSession,
) -> ReviewOut:
    doc, condo = await _doc_and_condo(db, access, document_id)
    if body.doc_type not in REVIEWABLE_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Tipo de documento inválido.")
    doc_type = DocumentType(body.doc_type)
    values = _validate(doc_type, body.values, condo.cnpj)

    # Training data: one row per field whose final value differs from what was extracted.
    type_changed = doc.doc_type != doc_type.value
    if type_changed:
        db.add(
            ExtractionCorrection(
                condominium_id=condo.id,
                document_id=doc.id,
                user_id=access.user_id,
                doc_type=doc_type.value,
                field_name="_doc_type",
                extracted_value=doc.doc_type,
                corrected_value=doc_type.value,
                extracted_confidence=None,
                extraction_source=doc.classification_source,
            )
        )
    for name, value in values.items():
        before = None if type_changed else doc.extracted.get(name)
        if before != value:
            db.add(
                ExtractionCorrection(
                    condominium_id=condo.id,
                    document_id=doc.id,
                    user_id=access.user_id,
                    doc_type=doc_type.value,
                    field_name=name,
                    extracted_value=before,
                    corrected_value=value,
                    extracted_confidence=None if type_changed else doc.field_confidence.get(name),
                    extraction_source=doc.extraction_source,
                )
            )

    doc.doc_type = doc_type.value
    doc.extracted = values
    doc.field_confidence = {name: 1.0 for name in values}  # verified by a person
    doc.needs_review = False
    doc.review_reasons = []
    doc.extraction_status = ExtractionStatus.DONE.value
    doc.reviewed_at = utcnow()
    doc.reviewed_by_user_id = access.user_id
    await record_audit(
        db,
        action="document.reviewed",
        object_type="document",
        object_id=doc.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"doc_type": doc_type.value, "type_changed": type_changed},
    )
    # Milestone 3: enqueue matching (document -> expense -> contract) from here.
    await db.flush()
    return await get_review(condominium_id, document_id, access, db)


@router.post("/condominiums/{condominium_id}/documents/{document_id}/review/discard")
async def discard(
    condominium_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DiscardIn,
    access: CanCorrect,
    db: DbSession,
) -> dict[str, str]:
    doc, condo = await _doc_and_condo(db, access, document_id)
    doc.doc_type = DocumentType.OUTRO.value
    doc.extracted = {"descartado": True, "motivo": body.motivo}
    doc.field_confidence = {}
    doc.needs_review = False
    doc.review_reasons = []
    doc.extraction_status = ExtractionStatus.DONE.value
    doc.reviewed_at = utcnow()
    doc.reviewed_by_user_id = access.user_id
    await record_audit(
        db,
        action="document.discarded",
        object_type="document",
        object_id=doc.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
    )
    return {"message": "Documento descartado."}
