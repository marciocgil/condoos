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
from app.core.time import add_months, local_today
from app.db.models import Condominium
from app.db.session import DbSession
from app.pending import month_pending
from app.routers.portfolio import _manager_condos, _only

router = APIRouter(tags=["agenda"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
MAX_DAYS = 93


class AgendaOut(BaseModel):
    start: date
    end: date
    events: list[dict[str, Any]]


def _window(
    start: date | None, end: date | None, default_days: int, today: date
) -> tuple[date, date]:
    start = start or today
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
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    today = local_today(condo.timezone)
    first, last = _window(start, end, 30, today)
    events = await condominium_agenda(db, access.condominium_id, first, last, today)
    wanted = _kinds(kind)
    return AgendaOut(
        start=first, end=last, events=[e.as_dict() for e in events if e.kind in wanted]
    )


@router.get("/condominiums/{condominium_id}/coverage")
async def month_coverage(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
) -> dict[str, Any]:
    """LB-055: for a month (default: the previous one), the invoice each contract in force
    expects and whether it arrived, through which channel, or is still in review. Follow-up
    only: a gap is "not received by any channel", never an accusation (D70, D71)."""
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    today = local_today(condo.timezone)
    chosen = (
        date(int(month[:4]), int(month[5:7]), 1) if month else add_months(today.replace(day=1), -1)
    )
    result = await month_pending(db, condo.id, chosen, today)
    rows = [
        {
            "contract_id": str(c.contract_id),
            "supplier": c.supplier,
            "object": c.object,
            "status": c.status,
            "origin": c.origin,
            "invoice_number": c.invoice_number,
            "arrived": [{"origin": a["origin"], "status": a["status"]} for a in c.arrived],
        }
        for c in result.contracts
    ]

    def count(status: str) -> int:
        return sum(r["status"] == status for r in rows)

    return {
        "month": f"{chosen:%Y-%m}",
        "expected": len(rows),
        "received": count("faturado"),
        "in_review": count("em_conferencia"),
        "waiting": count("aguardando"),
        "missing": count("sem_nf") + count("sem_faturamento"),
        "unread": result.unread,
        "contracts": rows,
    }


@router.get("/portfolio/agenda")
async def portfolio_agenda(
    db: DbSession,
    principal: CurrentPrincipal,
    start: date | None = None,
    end: date | None = None,
    condominium_id: uuid.UUID | None = None,
    kind: Annotated[list[str] | None, Query()] = None,
) -> AgendaOut:
    condos: list[Condominium] = _only(await _manager_condos(db, principal), condominium_id)
    first, last = _window(start, end, 30, local_today(condos[0].timezone if condos else None))
    wanted = _kinds(kind)
    out: list[dict[str, Any]] = []
    for c in condos:
        for e in await condominium_agenda(db, c.id, first, last, local_today(c.timezone)):
            if e.kind in wanted:
                out.append({**e.as_dict(), "condominium_id": str(c.id), "condominium": c.name})
    out.sort(key=lambda e: (e["date"], KINDS.index(e["kind"]), e["condominium"]))
    return AgendaOut(start=first, end=last, events=out)
