"""Data issues and the Validation Centre (D93, LB-032).

Whoever views the condominium sees its conflicts; resolving, discarding and reopening are
for the CondoOS reviewer and the management's manager (``CORRECT_EXTRACTION``). Another
condominium's conflict answers 404, like every record.
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, require
from app.auth.rbac import CondoAccess, Permission
from app.data_issues import DataIssueError, as_dict, discard, reopen, resolve
from app.db.models import DataIssue, DataIssueEvent
from app.db.session import DbSession
from app.routers.portfolio import _manager_access

router = APIRouter(tags=["data-issues"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanResolve = Annotated[CondoAccess, Depends(require(Permission.CORRECT_EXTRACTION))]
Status = Literal["aberto", "resolvido", "descartado"]


class ResolveIn(BaseModel):
    prevailing: int = Field(ge=0)
    reason: str = Field(max_length=1000)


class ReasonIn(BaseModel):
    reason: str = Field(max_length=1000)


async def _issue(db: DbSession, access: CondoAccess, issue_id: uuid.UUID) -> DataIssue:
    issue = await db.scalar(
        select(DataIssue).where(
            DataIssue.id == issue_id, DataIssue.condominium_id == access.condominium_id
        )
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Divergência não encontrada.")
    return issue


def _http(exc: DataIssueError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("/condominiums/{condominium_id}/data-issues")
async def list_issues(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    status_: Annotated[Status | None, Query(alias="status")] = None,
) -> list[dict[str, Any]]:
    stmt = select(DataIssue).where(DataIssue.condominium_id == access.condominium_id)
    if status_ is not None:
        stmt = stmt.where(DataIssue.status == status_)
    rows = await db.scalars(stmt.order_by(DataIssue.created_at.desc()))
    return [as_dict(i) for i in rows]


@router.get("/condominiums/{condominium_id}/data-issues/{issue_id}")
async def get_issue(
    condominium_id: uuid.UUID, issue_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    issue = await _issue(db, access, issue_id)
    events = await db.scalars(
        select(DataIssueEvent)
        .where(DataIssueEvent.issue_id == issue.id)
        .order_by(DataIssueEvent.created_at)
    )
    return {
        **as_dict(issue),
        "can_resolve": access.can(Permission.CORRECT_EXTRACTION),
        "events": [
            {
                "kind": e.kind,
                "by_person": e.user_id is not None,
                "at": e.created_at.isoformat(),
                "payload": e.payload,
            }
            for e in events
        ],
    }


@router.post("/condominiums/{condominium_id}/data-issues/{issue_id}/resolve")
async def resolve_issue(
    condominium_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: ResolveIn,
    access: CanResolve,
    db: DbSession,
) -> dict[str, Any]:
    issue = await _issue(db, access, issue_id)
    try:
        await resolve(
            db,
            issue,
            user_id=access.user_id,
            prevailing_index=body.prevailing,
            reason=body.reason,
        )
    except DataIssueError as exc:
        raise _http(exc) from exc
    return as_dict(issue)


@router.post("/condominiums/{condominium_id}/data-issues/{issue_id}/discard")
async def discard_issue(
    condominium_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: ReasonIn,
    access: CanResolve,
    db: DbSession,
) -> dict[str, Any]:
    issue = await _issue(db, access, issue_id)
    try:
        await discard(db, issue, user_id=access.user_id, reason=body.reason)
    except DataIssueError as exc:
        raise _http(exc) from exc
    return as_dict(issue)


@router.post("/condominiums/{condominium_id}/data-issues/{issue_id}/reopen")
async def reopen_issue(
    condominium_id: uuid.UUID,
    issue_id: uuid.UUID,
    body: ReasonIn,
    access: CanResolve,
    db: DbSession,
) -> dict[str, Any]:
    issue = await _issue(db, access, issue_id)
    try:
        await reopen(db, issue, user_id=access.user_id, reason=body.reason)
    except DataIssueError as exc:
        raise _http(exc) from exc
    return as_dict(issue)


@router.get("/portfolio/data-issues")
async def portfolio_issues(
    db: DbSession,
    principal: CurrentPrincipal,
    condominium_id: uuid.UUID | None = None,
    status_: Annotated[Status, Query(alias="status")] = "aberto",
) -> list[dict[str, Any]]:
    """The Validation Centre: open conflicts across the portfolio, largest amount first."""
    accesses = [
        (c, a)
        for c, a in await _manager_access(db, principal)
        if condominium_id is None or c.id == condominium_id
    ]
    out: list[dict[str, Any]] = []
    for condo, access in accesses:
        rows = await db.scalars(
            select(DataIssue).where(
                DataIssue.condominium_id == condo.id, DataIssue.status == status_
            )
        )
        for issue in rows:
            out.append(
                {
                    **as_dict(issue),
                    "condominium": condo.name,
                    "can_resolve": access.can(Permission.CORRECT_EXTRACTION),
                }
            )
    out.sort(key=lambda i: (-float(i["amount_at_stake"] or 0), i["created_at"] or ""))
    return out
