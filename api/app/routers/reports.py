"""Monthly reports, decision trail export and competence closing (spec §7, §8, §11).

- A closed competence serves the report stored at closing (what was sent to the board).
- An open competence serves a preview generated on the fly, marked as such.
- Closing requires an empty exception queue for that condominium and month.
"""

import asyncio
import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import VISIBLE_TO_BOARD, CompetenceStatus
from app.db.models import AppUser, Competence, Condominium, Decision, Finding
from app.db.session import DbSession
from app.reports.data import build_month_report, pending_for_month
from app.reports.pdf import month_report_pdf, trail_pdf
from app.reports.xlsx import month_report_xlsx
from app.storage.base import get_storage

router = APIRouter(prefix="/condominiums/{condominium_id}", tags=["reports"])

CanExport = Annotated[CondoAccess, Depends(require(Permission.EXPORT))]
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanClose = Annotated[CondoAccess, Depends(require(Permission.CLOSE_COMPETENCE))]
Month = Annotated[str, Path(pattern=r"^\d{4}-\d{2}$")]

PDF = "application/pdf"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ReportOut(BaseModel):
    competence: date
    status: str
    closed_at: datetime | None
    published_at: datetime | None
    findings: int


class ClosingOut(BaseModel):
    competence: date
    status: str
    pending: dict[str, int]
    can_close: bool


def _month(value: str) -> date:
    try:
        return date(int(value[:4]), int(value[5:7]), 1)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Competência inválida.") from exc


async def _competence(db: DbSession, access: CondoAccess, month: date) -> Competence:
    comp = await db.scalar(
        select(Competence).where(
            Competence.condominium_id == access.condominium_id, Competence.month == month
        )
    )
    if comp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competência não encontrada.")
    return comp


async def _slug(db: DbSession, access: CondoAccess) -> str:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo.slug


def _file(body: bytes, media: str, filename: str) -> Response:
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _key(condominium_id: uuid.UUID, month: date, ext: str) -> str:
    return f"cond/{condominium_id}/reports/{month:%Y-%m}.{ext}"


@router.get("/reports")
async def list_reports(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[ReportOut]:
    comps = list(
        await db.scalars(
            select(Competence)
            .where(Competence.condominium_id == access.condominium_id)
            .order_by(Competence.month.desc())
        )
    )
    counts: dict[date, int] = {}
    for month in await db.scalars(
        select(Finding.competence).where(
            Finding.condominium_id == access.condominium_id,
            Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]),
        )
    ):
        counts[month] = counts.get(month, 0) + 1
    return [
        ReportOut(
            competence=c.month,
            status=c.status,
            closed_at=c.closed_at,
            published_at=c.published_at,
            findings=counts.get(c.month, 0),
        )
        for c in comps
    ]


async def _report_file(db: DbSession, access: CondoAccess, month: date, ext: str) -> Response:
    comp = await _competence(db, access, month)
    slug = await _slug(db, access)
    media = PDF if ext == "pdf" else XLSX
    stored = comp.report_pdf_key if ext == "pdf" else comp.report_xlsx_key
    if comp.status == CompetenceStatus.FECHADA.value and stored:
        body = await asyncio.to_thread(get_storage().get, stored)
        return _file(body, media, f"relatorio-{slug}-{month:%Y-%m}.{ext}")
    report = await build_month_report(db, access.condominium_id, month)
    render = month_report_pdf if ext == "pdf" else month_report_xlsx
    body = await asyncio.to_thread(render, report)
    return _file(body, media, f"previa-relatorio-{slug}-{month:%Y-%m}.{ext}")


@router.get("/reports/{month}.pdf")
async def report_pdf(
    condominium_id: uuid.UUID, month: Month, access: CanExport, db: DbSession
) -> Response:
    return await _report_file(db, access, _month(month), "pdf")


@router.get("/reports/{month}.xlsx")
async def report_xlsx(
    condominium_id: uuid.UUID, month: Month, access: CanExport, db: DbSession
) -> Response:
    return await _report_file(db, access, _month(month), "xlsx")


@router.get("/decisions.pdf")
async def decisions_pdf(condominium_id: uuid.UUID, access: CanExport, db: DbSession) -> Response:
    """The decision trail for the assembly (same visibility as the screen)."""
    stmt = (
        select(Decision, Finding, AppUser.name)
        .join(Finding, Finding.id == Decision.finding_id)
        .join(AppUser, AppUser.id == Decision.user_id)
        .where(Decision.condominium_id == access.condominium_id)
        .order_by(Decision.decided_at)
    )
    if not access.can(Permission.VIEW_PENDING_FINDINGS):
        stmt = stmt.where(Finding.status.in_([s.value for s in VISIBLE_TO_BOARD]))
    items: list[dict[str, Any]] = [
        {
            "decided_at": d.decided_at,
            "competence": f.competence,
            "rule_code": f.rule_code,
            "title": f.title,
            "action": d.action,
            "user_name": name,
            "comment": d.comment,
        }
        for d, f, name in (await db.execute(stmt)).all()
    ]
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    body = await asyncio.to_thread(trail_pdf, condo.name, items, utcnow())
    await record_audit(
        db,
        action="decisions.exported",
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"decisions": len(items)},
    )
    return _file(body, PDF, f"trilha-de-decisoes-{condo.slug}.pdf")


@router.get("/competences/{month}/closing")
async def closing_status(
    condominium_id: uuid.UUID, month: Month, access: CanClose, db: DbSession
) -> ClosingOut:
    comp = await _competence(db, access, _month(month))
    pending = await pending_for_month(db, access.condominium_id, comp.month)
    return ClosingOut(
        competence=comp.month,
        status=comp.status,
        pending=pending,
        can_close=comp.status == CompetenceStatus.ABERTA.value and not any(pending.values()),
    )


@router.post("/competences/{month}/close")
async def close_competence(
    condominium_id: uuid.UUID, month: Month, access: CanClose, db: DbSession
) -> ReportOut:
    found = await _competence(db, access, _month(month))
    comp = await db.scalar(select(Competence).where(Competence.id == found.id).with_for_update())
    assert comp is not None
    if comp.status == CompetenceStatus.FECHADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta competência já está fechada.")
    pending = await pending_for_month(db, access.condominium_id, comp.month)
    if any(pending.values()):
        parts = [
            f"{n} {label}"
            for label, n in (
                ("documento(s) para revisar", pending["documentos"]),
                ("casamento(s) ambíguo(s)", pending["casamentos"]),
                ("achado(s) grave(s) para validar", pending["achados_graves"]),
            )
            if n
        ]
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A fila de exceções deste mês precisa estar vazia para fechar: "
            + ", ".join(parts)
            + ".",
        )
    now = utcnow()
    comp.status = CompetenceStatus.FECHADA.value
    comp.closed_at = now
    comp.closed_by_user_id = access.user_id
    await db.flush()
    report = await build_month_report(db, access.condominium_id, comp.month)
    pdf, xlsx = await asyncio.gather(
        asyncio.to_thread(month_report_pdf, report), asyncio.to_thread(month_report_xlsx, report)
    )
    storage = get_storage()
    pdf_key = _key(access.condominium_id, comp.month, "pdf")
    xlsx_key = _key(access.condominium_id, comp.month, "xlsx")
    await asyncio.to_thread(storage.put, pdf_key, pdf, PDF)
    await asyncio.to_thread(storage.put, xlsx_key, xlsx, XLSX)
    comp.report_pdf_key = pdf_key
    comp.report_xlsx_key = xlsx_key
    comp.published_at = now
    await record_audit(
        db,
        action="competence.closed",
        object_type="competence",
        object_id=comp.id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details={"month": f"{comp.month:%Y-%m}", "findings": len(report.findings)},
    )
    await db.flush()
    return ReportOut(
        competence=comp.month,
        status=comp.status,
        closed_at=comp.closed_at,
        published_at=comp.published_at,
        findings=len(report.findings),
    )
