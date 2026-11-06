"""Agenda (D71): due dates, expected invoices, adjustments and contract ends, by date.

Per condominium for everyone who can view it (board included: these are the condominium's
own expenses and contracts) and across the portfolio for the management company.
"""

import uuid
from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.agenda import KINDS, condominium_agenda
from app.auth.deps import CurrentPrincipal, require
from app.auth.rbac import CondoAccess, Permission
from app.db.models import Condominium
from app.db.session import DbSession
from app.routers.portfolio import _manager_condos, _only

router = APIRouter(tags=["agenda"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
MAX_DAYS = 93


class AgendaOut(BaseModel):
    start: date
    end: date
    events: list[dict[str, Any]]


def _window(start: date | None, end: date | None, default_days: int) -> tuple[date, date]:
    start = start or date.today()
    end = end or start + timedelta(days=default_days)
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O fim é anterior ao início.")
    if (end - start).days > MAX_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Período de no máximo {MAX_DAYS} dias."
        )
    return start, end


def _kinds(kinds: list[str] | None) -> set[str]:
    return set(kinds or KINDS) & set(KINDS)


@router.get("/condominiums/{condominium_id}/agenda")
async def condominium_agenda_route(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    start: date | None = None,
    end: date | None = None,
    kind: Annotated[list[str] | None, Query()] = None,
) -> AgendaOut:
    first, last = _window(start, end, 30)
    events = await condominium_agenda(db, access.condominium_id, first, last, date.today())
    wanted = _kinds(kind)
    return AgendaOut(
        start=first, end=last, events=[e.as_dict() for e in events if e.kind in wanted]
    )


@router.get("/portfolio/agenda")
async def portfolio_agenda(
    db: DbSession,
    principal: CurrentPrincipal,
    start: date | None = None,
    end: date | None = None,
    condominium_id: uuid.UUID | None = None,
    kind: Annotated[list[str] | None, Query()] = None,
) -> AgendaOut:
    first, last = _window(start, end, 30)
    condos: list[Condominium] = _only(await _manager_condos(db, principal), condominium_id)
    wanted = _kinds(kind)
    out: list[dict[str, Any]] = []
    for c in condos:
        for e in await condominium_agenda(db, c.id, first, last, date.today()):
            if e.kind in wanted:
                out.append({**e.as_dict(), "condominium_id": str(c.id), "condominium": c.name})
    out.sort(key=lambda e: (e["date"], KINDS.index(e["kind"]), e["condominium"]))
    return AgendaOut(start=first, end=last, events=out)
