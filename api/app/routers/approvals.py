"""Approvals of expenses above the approval limit (rule R12).

The board or the assembly approves; the management company records it here, with the
approver, the date and, when there is one, the minutes. Recording an approval re-evaluates
the month, so an R12 finding nobody acted on yet becomes "superado" (D61).
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.jobs import enqueue
from app.db.models import Approval, Document, Expense, Supplier
from app.db.session import DbSession

router = APIRouter(prefix="/condominiums/{condominium_id}", tags=["approvals"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanRecord = Annotated[CondoAccess, Depends(require(Permission.RECORD_APPROVAL))]


class ApprovalIn(BaseModel):
    approved_by: str = Field(min_length=3, max_length=200)  # e.g. "Conselho consultivo"
    approved_at: date
    notes: str | None = Field(default=None, max_length=2000)
    source_document_id: uuid.UUID | None = None  # the minutes, when uploaded

    @field_validator("approved_at")
    @classmethod
    def _not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("a data da aprovação não pode estar no futuro")
        return v


class ApprovalOut(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    expense_description: str
    expense_amount: str
    supplier_name: str | None
    approved_by: str
    approved_at: date
    notes: str | None


@router.get("/approvals")
async def list_approvals(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[ApprovalOut]:
    rows = await db.execute(
        select(Approval, Expense, Supplier.legal_name)
        .join(Expense, Expense.id == Approval.expense_id)
        .outerjoin(Supplier, Supplier.id == Expense.supplier_id)
        .where(Approval.condominium_id == access.condominium_id)
        .order_by(Approval.approved_at.desc())
    )
    return [
        ApprovalOut(
            id=a.id,
            expense_id=e.id,
            expense_description=e.description,
            expense_amount=f"{e.amount:.2f}",
            supplier_name=name,
            approved_by=a.approved_by,
            approved_at=a.approved_at,
            notes=a.notes,
        )
        for a, e, name in rows
    ]


@router.post("/expenses/{expense_id}/approvals", status_code=status.HTTP_201_CREATED)
async def record_approval(
    condominium_id: uuid.UUID,
    expense_id: uuid.UUID,
    body: ApprovalIn,
    access: CanRecord,
    db: DbSession,
) -> ApprovalOut:
    expense = await db.scalar(
        select(Expense).where(
            Expense.id == expense_id, Expense.condominium_id == access.condominium_id
        )
    )
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Despesa não encontrada.")
    if body.source_document_id is not None:
        doc = await db.scalar(
            select(Document.id).where(
                Document.id == body.source_document_id,
                Document.condominium_id == access.condominium_id,
            )
        )
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.")
    approval = Approval(
        id=uuid.uuid4(),
        condominium_id=access.condominium_id,
        expense_id=expense.id,
        approved_by=body.approved_by.strip(),
        approved_at=body.approved_at,
        source_document_id=body.source_document_id,
        notes=(body.notes or "").strip() or None,
        recorded_by_user_id=access.user_id,
    )
    db.add(approval)
    await record_audit(
        db,
        action="approval.recorded",
        object_type="expense",
        object_id=expense.id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details={"approval_id": str(approval.id), "approved_at": body.approved_at.isoformat()},
    )
    await enqueue(
        db,
        "rules.evaluate",
        {"condominium_id": str(access.condominium_id), "competence": f"{expense.competence:%Y-%m}"},
        condominium_id=access.condominium_id,
        priority=True,
    )
    await db.flush()
    supplier = await db.get(Supplier, expense.supplier_id) if expense.supplier_id else None
    return ApprovalOut(
        id=approval.id,
        expense_id=expense.id,
        expense_description=expense.description,
        expense_amount=f"{expense.amount:.2f}",
        supplier_name=supplier.legal_name if supplier else None,
        approved_by=approval.approved_by,
        approved_at=approval.approved_at,
        notes=approval.notes,
    )
