"""Data issues (ADR-L05, LB-030, D95): who sees and who resolves a data conflict.

Everyone who views the condominium sees the open conflicts (they explain why a capability
is partial). Choosing the prevailing version or dismissing needs ``resolve_data_issue``:
the síndico, the management company's manager when it reviews (D74) and the CondoOS team.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.data_issues import DataIssueError, dismiss, resolve
from app.db.enums import DataIssueStatus
from app.db.models import DataIssue
from app.db.session import DbSession

router = APIRouter(prefix="/condominiums/{condominium_id}/data-issues", tags=["data-issues"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanResolve = Annotated[CondoAccess, Depends(require(Permission.RESOLVE_DATA_ISSUE))]


class DataIssueOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    capability: str
    subject_type: str
    subject_id: uuid.UUID
    field_name: str | None
    title: str
    sources: list[dict[str, Any]]
    detected_at: datetime
    resolved_at: datetime | None
    resolution: dict[str, Any] | None
    can_resolve: bool


class ResolveIn(BaseModel):
    prevailing: int = Field(ge=0, le=20)
    reason: str = Field(max_length=1000)


class DismissIn(BaseModel):
    reason: str = Field(max_length=1000)


def _out(issue: DataIssue, access: CondoAccess) -> DataIssueOut:
    return DataIssueOut(
        id=issue.id,
        kind=issue.kind,
        status=issue.status,
        capability=issue.capability,
        subject_type=issue.subject_type,
        subject_id=issue.subject_id,
        field_name=issue.field_name,
        title=issue.title,
        sources=list(issue.sources or []),
        detected_at=issue.detected_at,
        resolved_at=issue.resolved_at,
        resolution=issue.resolution,
        can_resolve=issue.status == DataIssueStatus.ABERTO.value
        and access.can(Permission.RESOLVE_DATA_ISSUE),
    )


async def _issue(db: DbSession, access: CondoAccess, issue_id: uuid.UUID) -> DataIssue:
    issue = await db.scalar(
        select(DataIssue)
        .where(DataIssue.id == issue_id, DataIssue.condominium_id == access.condominium_id)
        .with_for_update()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conflito não encontrado.")
    return issue


@router.get("")
async def list_issues(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    state: Literal["aberto", "todos"] = "aberto",
) -> list[DataIssueOut]:
    stmt = select(DataIssue).where(DataIssue.condominium_id == access.condominium_id)
    if state == "aberto":
        stmt = stmt.where(DataIssue.status == DataIssueStatus.ABERTO.value)
    rows = await db.scalars(stmt.order_by(DataIssue.detected_at.desc()).limit(200))
    return [_out(i, access) for i in rows]


@router.post("/{issue_id}/resolve")
async def post_resolve(
    condominium_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: ResolveIn,
    access: CanResolve,
    db: DbSession,
) -> DataIssueOut:
    """Choose the prevailing version, with a reason. For a contract field the chosen value is
    applied to the contract; the other version stays recorded in the issue."""
    issue = await _issue(db, access, issue_id)
    try:
        await resolve(db, issue, access, prevailing=body.prevailing, reason=body.reason)
    except DataIssueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _out(issue, access)


@router.post("/{issue_id}/dismiss")
async def post_dismiss(
    condominium_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: DismissIn,
    access: CanResolve,
    db: DbSession,
) -> DataIssueOut:
    issue = await _issue(db, access, issue_id)
    try:
        await dismiss(db, issue, access, reason=body.reason)
    except DataIssueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _out(issue, access)
