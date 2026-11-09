"""Compliance and expiry dates of a condominium (D108, FR-057).

Seeing: everyone with VIEW. Turning the catalogue on, creating obligations and linking
documents: MANAGE_COMPLIANCE. Deciding whether an obligation applies: VALIDATE_COMPLIANCE
(síndico and the management company's manager; a person, never the system).
"""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import compliance as svc
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.compliance.catalog import CATEGORY_LABEL
from app.compliance.status import LABEL, situation
from app.core.time import local_today
from app.db.enums import ComplianceCategory
from app.db.models import (
    AppUser,
    ComplianceEvent,
    ComplianceEvidence,
    ComplianceObligation,
    Condominium,
    Contract,
    Document,
    Supplier,
)
from app.db.session import DbSession

router = APIRouter(tags=["compliance"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_COMPLIANCE))]
CanValidate = Annotated[CondoAccess, Depends(require(Permission.VALIDATE_COMPLIANCE))]
NOT_FOUND = "Obrigação não encontrada."
DOCUMENT_CHOICES = 80


def _bad(exc: ValueError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))


async def _today(db: DbSession, access: CondoAccess) -> date:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return local_today(condo.timezone)


async def _obligation(db: DbSession, access: CondoAccess, oid: uuid.UUID) -> ComplianceObligation:
    try:
        return await svc.get_obligation(db, access.condominium_id, oid)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from exc


async def _names(db: DbSession, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    real = {i for i in ids if i is not None}
    if not real:
        return {}
    return {u.id: u.name for u in await db.scalars(select(AppUser).where(AppUser.id.in_(real)))}


def _evidence(ev: ComplianceEvidence, docs: dict[uuid.UUID, Document]) -> dict[str, Any]:
    doc = docs.get(ev.document_id) if ev.document_id else None
    return {
        "id": str(ev.id),
        "created_at": ev.created_at.isoformat(),
        "source": ev.source,
        "confirmed": ev.confirmed,
        "issued_on": ev.issued_on.isoformat() if ev.issued_on else None,
        "valid_until": ev.valid_until.isoformat() if ev.valid_until else None,
        "quote": ev.quote,
        "note": ev.note,
        "document": (
            {"id": str(doc.id), "filename": doc.original_filename, "doc_type": doc.doc_type}
            if doc
            else None
        ),
    }


def _summary(row: svc.Row) -> dict[str, Any]:
    ob = row.obligation
    return {
        "id": str(ob.id),
        "name": ob.name,
        "category": ob.category,
        "category_label": CATEGORY_LABEL.get(ob.category, ob.category),
        "from_catalog": ob.catalog_key is not None,
        "applicability": ob.applicability,
        "periodicity_months": ob.periodicity_months,
        "suggested_months": ob.suggested_months,
        "lead_days": ob.lead_days,
        "responsible": ob.responsible,
        "situation": row.situation.as_dict(),
        "has_document": bool(row.evidence and row.evidence.document_id),
    }


@router.get("/condominiums/{condominium_id}/compliance")
async def list_compliance(access: CanView, db: DbSession) -> dict[str, Any]:
    today = await _today(db, access)
    every = await svc.rows_for(db, access.condominium_id, today, include_archived=True)
    rows = [r for r in every if r.obligation.archived_at is None]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.situation.code] = counts.get(r.situation.code, 0) + 1
    catalog_keys = {r.obligation.catalog_key for r in every if r.obligation.catalog_key}
    return {
        "today": today.isoformat(),
        "can_manage": access.can(Permission.MANAGE_COMPLIANCE),
        "can_validate": access.can(Permission.VALIDATE_COMPLIANCE),
        "catalog_missing": len(svc.CATALOG) - len(catalog_keys),
        "counts": counts,
        "labels": LABEL,
        "categories": [
            {"value": c.value, "label": CATEGORY_LABEL[c.value]} for c in ComplianceCategory
        ],
        "obligations": [_summary(r) for r in rows],
        "archived": [_summary(r) for r in every if r.obligation.archived_at is not None],
    }


@router.get("/condominiums/{condominium_id}/compliance/{obligation_id}")
async def get_compliance(
    obligation_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    ob = await _obligation(db, access, obligation_id)
    today = await _today(db, access)
    history = list(
        await db.scalars(
            select(ComplianceEvidence)
            .where(ComplianceEvidence.obligation_id == ob.id)
            .order_by(ComplianceEvidence.created_at.desc())
        )
    )
    events = list(
        await db.scalars(
            select(ComplianceEvent)
            .where(ComplianceEvent.obligation_id == ob.id)
            .order_by(ComplianceEvent.created_at.desc())
        )
    )
    doc_ids = {e.document_id for e in history if e.document_id}
    docs = (
        {d.id: d for d in await db.scalars(select(Document).where(Document.id.in_(doc_ids)))}
        if doc_ids
        else {}
    )
    names = await _names(
        db, {e.user_id for e in events} | {e.user_id for e in history} | {ob.validated_by}
    )
    supplier = await db.get(Supplier, ob.supplier_id) if ob.supplier_id else None
    can_manage = access.can(Permission.MANAGE_COMPLIANCE)
    choices: list[dict[str, Any]] = []
    suppliers: list[dict[str, Any]] = []
    if can_manage:
        recent = await db.scalars(
            select(Document)
            .where(Document.condominium_id == ob.condominium_id)
            .order_by(Document.created_at.desc())
            .limit(DOCUMENT_CHOICES)
        )
        choices = [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "doc_type": d.doc_type,
                "created_at": d.created_at.isoformat(),
            }
            for d in recent
        ]
        rows = await db.execute(
            select(Supplier.id, Supplier.legal_name)
            .join(Contract, Contract.supplier_id == Supplier.id)
            .where(Contract.condominium_id == ob.condominium_id)
            .distinct()
            .order_by(Supplier.legal_name)
        )
        suppliers = [{"id": str(i), "name": n} for i, n in rows]
    latest = history[0] if history else None
    return {
        **_summary(svc.Row(ob, latest, situation(ob, latest, today))),
        "archived": ob.archived_at is not None,
        "validated_by": names.get(ob.validated_by) if ob.validated_by else None,
        "validated_at": ob.validated_at.isoformat() if ob.validated_at else None,
        "validation_reason": ob.validation_reason,
        "supplier": {"id": str(supplier.id), "name": supplier.legal_name} if supplier else None,
        "can_manage": can_manage,
        "can_validate": access.can(Permission.VALIDATE_COMPLIANCE),
        "pending_confirmation": (
            str(latest.id)
            if latest and not latest.confirmed and latest.source in ("ia", "texto")
            else None
        ),
        "evidence": [_evidence(e, docs) for e in history],
        "events": [
            {
                "kind": e.kind,
                "at": e.created_at.isoformat(),
                "by": names.get(e.user_id) if e.user_id else None,
                "payload": e.payload,
            }
            for e in events
        ],
        "documents": choices,
        "suppliers": suppliers,
    }


@router.post("/condominiums/{condominium_id}/compliance/catalog")
async def activate_catalog(access: CanManage, db: DbSession) -> dict[str, int]:
    created = await svc.activate_catalog(db, access.condominium_id, access.user_id)
    return {"created": created}


class ObligationIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    category: str = ComplianceCategory.OUTROS.value
    lead_days: int = Field(default=svc.DEFAULT_LEAD_DAYS, ge=1, le=365)
    responsible: str | None = Field(default=None, max_length=200)


@router.post("/condominiums/{condominium_id}/compliance", status_code=status.HTTP_201_CREATED)
async def create_obligation(body: ObligationIn, access: CanManage, db: DbSession) -> dict[str, str]:
    try:
        ob = await svc.create_obligation(
            db,
            access.condominium_id,
            access.user_id,
            name=body.name,
            category=body.category,
            lead_days=body.lead_days,
            responsible=body.responsible,
        )
    except svc.ComplianceError as exc:
        raise _bad(exc) from exc
    return {"id": str(ob.id)}


class ObligationPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    lead_days: int | None = Field(default=None, ge=1, le=365)
    responsible: str | None = Field(default=None, max_length=200)
    supplier_id: uuid.UUID | None = None
    clear_supplier: bool = False


@router.patch("/condominiums/{condominium_id}/compliance/{obligation_id}")
async def update_obligation(
    obligation_id: uuid.UUID, body: ObligationPatch, access: CanManage, db: DbSession
) -> dict[str, bool]:
    ob = await _obligation(db, access, obligation_id)
    if body.supplier_id is not None:
        ok = await db.scalar(
            select(Contract.id).where(
                Contract.condominium_id == ob.condominium_id,
                Contract.supplier_id == body.supplier_id,
            )
        )
        if ok is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Fornecedor sem contrato neste condomínio."
            )
    try:
        await svc.update_obligation(
            db,
            ob,
            access.user_id,
            name=body.name,
            lead_days=body.lead_days,
            responsible=body.responsible,
            supplier_id=body.supplier_id,
            clear_supplier=body.clear_supplier,
        )
    except svc.ComplianceError as exc:
        raise _bad(exc) from exc
    return {"ok": True}


class ValidationIn(BaseModel):
    applies: bool
    reason: str = Field(min_length=3, max_length=1000)
    periodicity_months: int | None = Field(default=None, ge=1, le=120)


@router.post("/condominiums/{condominium_id}/compliance/{obligation_id}/validation")
async def validate_obligation(
    obligation_id: uuid.UUID, body: ValidationIn, access: CanValidate, db: DbSession
) -> dict[str, bool]:
    ob = await _obligation(db, access, obligation_id)
    try:
        await svc.validate(
            db,
            ob,
            access.user_id,
            applies=body.applies,
            reason=body.reason,
            periodicity_months=body.periodicity_months,
        )
    except svc.ComplianceError as exc:
        raise _bad(exc) from exc
    return {"ok": True}


class EvidenceIn(BaseModel):
    document_id: uuid.UUID | None = None
    issued_on: date | None = None
    valid_until: date | None = None
    note: str | None = Field(default=None, max_length=500)


@router.post(
    "/condominiums/{condominium_id}/compliance/{obligation_id}/evidence",
    status_code=status.HTTP_201_CREATED,
)
async def add_evidence(
    obligation_id: uuid.UUID, body: EvidenceIn, access: CanManage, db: DbSession
) -> dict[str, str]:
    ob = await _obligation(db, access, obligation_id)
    try:
        ev = await svc.add_evidence(
            db,
            ob,
            access.user_id,
            document_id=body.document_id,
            issued_on=body.issued_on,
            valid_until=body.valid_until,
            note=body.note,
        )
    except svc.ComplianceError as exc:
        raise _bad(exc) from exc
    return {"id": str(ev.id), "source": ev.source}


class ConfirmIn(BaseModel):
    issued_on: date | None = None
    valid_until: date | None = None


@router.post(
    "/condominiums/{condominium_id}/compliance/{obligation_id}/evidence/{evidence_id}/confirm"
)
async def confirm_evidence(
    obligation_id: uuid.UUID,
    evidence_id: uuid.UUID,
    body: ConfirmIn,
    access: CanManage,
    db: DbSession,
) -> dict[str, str]:
    ob = await _obligation(db, access, obligation_id)
    try:
        ev = await svc.confirm_evidence(
            db,
            ob,
            evidence_id,
            access.user_id,
            issued_on=body.issued_on,
            valid_until=body.valid_until,
        )
    except svc.ComplianceError as exc:
        raise _bad(exc) from exc
    return {"id": str(ev.id)}


class ArchiveIn(BaseModel):
    archived: bool


@router.post("/condominiums/{condominium_id}/compliance/{obligation_id}/archive")
async def archive_obligation(
    obligation_id: uuid.UUID, body: ArchiveIn, access: CanManage, db: DbSession
) -> dict[str, bool]:
    ob = await _obligation(db, access, obligation_id)
    await svc.set_archived(db, ob, access.user_id, body.archived)
    return {"ok": True}
