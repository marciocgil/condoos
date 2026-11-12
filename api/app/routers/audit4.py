"""CondoOS Audit, cycle 4 API (D125): history and trend of the farol, export of the month
(PDF and XLSX, audited) and the links with Operate (cases) and Optimize (opportunities).

Internal views need ``view_audit``; exports also need ``export``. The síndico's export is the
farol he approved (the frozen snapshot), never the internal results.
"""

import io
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from app.audit.catalog import CONTROLS, CONTROLS_BY_ID, PILLARS
from app.audit.events import SLA_LABEL, publication_overdue, sla_level
from app.audit.run import month_start
from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import add_months, local_today, utcnow
from app.db.enums import OpportunityStatus, PublicationStatus
from app.db.models import (
    AuditControlResult,
    AuditIssue,
    AuditPeriod,
    AuditPublication,
    CaseRecord,
    Condominium,
    Contract,
    Opportunity,
)
from app.db.session import DbSession

router = APIRouter(tags=["audit"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW_AUDIT))]
CanSee = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
STATUS_LABEL = {
    "VALIDADO": "Validado",
    "COM_RESSALVA": "Com ressalva",
    "PENDENTE": "Pendente",
    "DIVERGENTE": "Divergente",
    "NAO_AVALIADO": "Não avaliado",
    "NAO_APLICAVEL": "Não aplicável",
}
FOOTER = (
    "Gerado pelo CondoOS Audit. Status por regras determinísticas versionadas; a IA não "
    "decide status. Indícios e pontos de atenção, não conclusões."
)
# Opportunities a condominium may see (D81): only after the CondoOS review approved them.
VISIBLE_TO_CONDO = {
    OpportunityStatus.APROVADA_PARA_CLIENTE.value,
    OpportunityStatus.APROVADA_PELO_CONDOMINIO.value,
    OpportunityStatus.EM_EXECUCAO.value,
    OpportunityStatus.IMPLEMENTADA.value,
    OpportunityStatus.RESULTADO_MEDIDO.value,
}


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    if condo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")
    return condo


def _month(value: str | None, condo: Condominium) -> date:
    if value:
        try:
            return date(int(value[:4]), int(value[5:7]), 1)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Competência inválida (AAAA-MM)."
            ) from exc
    return add_months(month_start(local_today(condo.timezone)), -1)


async def _results(db: DbSession, period_id: uuid.UUID) -> dict[str, AuditControlResult]:
    return {
        r.control_id: r
        for r in await db.scalars(
            select(AuditControlResult).where(
                AuditControlResult.period_id == period_id,
                AuditControlResult.superseded_by_id.is_(None),
            )
        )
    }


# --------------------------------------------------------------------------- history


@router.get("/condominiums/{condominium_id}/audit/history")
async def history(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    ate: str | None = None,
    meses: int = 12,
) -> dict[str, Any]:
    """Status of each control month by month, counts and trend (green and red over time)."""
    condo = await _condo(db, access)
    last = _month(ate, condo)
    n = max(1, min(meses, 24))
    first = add_months(last, -(n - 1))
    periods = {
        p.competence: p
        for p in await db.scalars(
            select(AuditPeriod).where(
                AuditPeriod.condominium_id == condo.id,
                AuditPeriod.competence.between(first, last),
            )
        )
    }
    approved = {
        p.period_id
        for p in await db.scalars(
            select(AuditPublication).where(
                AuditPublication.condominium_id == condo.id,
                AuditPublication.status == PublicationStatus.APROVADA.value,
            )
        )
    }
    months: list[dict[str, Any]] = []
    matrix: dict[str, list[str | None]] = {c.id: [] for c in CONTROLS}
    for i in range(n):
        m = add_months(first, i)
        period = periods.get(m)
        results = await _results(db, period.id) if period else {}
        counts: dict[str, int] = {}
        for c in CONTROLS:
            st = results[c.id].status if c.id in results else None
            matrix[c.id].append(st)
            if st:
                counts[st] = counts.get(st, 0) + 1
        months.append(
            {
                "competencia": m.strftime("%Y-%m"),
                "auditado": period is not None,
                "aprovado_pelo_sindico": bool(period and period.id in approved),
                "contagem": counts,
                "diferencas": str(sum((r.differences for r in results.values()), start=0)),
            }
        )
    audited = [x for x in months if x["auditado"]]
    trend: dict[str, Any] = {}
    if len(audited) >= 2:
        a, b = audited[-2]["contagem"], audited[-1]["contagem"]
        trend = {
            "validados": b.get("VALIDADO", 0) - a.get("VALIDADO", 0),
            "divergentes": b.get("DIVERGENTE", 0) - a.get("DIVERGENTE", 0),
            "pendentes": b.get("PENDENTE", 0) - a.get("PENDENTE", 0),
            "de": audited[-2]["competencia"],
            "para": audited[-1]["competencia"],
        }
    return {
        "months": months,
        "controls": [
            {
                "id": c.id,
                "name": c.name,
                "pillar": PILLARS[c.pillar],
                "statuses": matrix[c.id],
                # Months in a row the control is not green, ending in the last audited month.
                "streak": _streak(matrix[c.id]),
            }
            for c in CONTROLS
        ],
        "trend": trend,
    }


def _streak(statuses: list[str | None]) -> int:
    n = 0
    for st in reversed(statuses):
        if st is None:
            if n:
                break
            continue
        if st in ("VALIDADO", "NAO_APLICAVEL"):
            break
        n += 1
    return n


# --------------------------------------------------------------------------- operate / optimize


@router.get("/condominiums/{condominium_id}/audit/links")
async def links(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    """Operate: pending items with their case (or escalated without one). Optimize:
    opportunities on the contracts the contract controls flagged this month."""
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    current = add_months(month_start(local_today(condo.timezone)), -1)
    issues = list(
        await db.scalars(
            select(AuditIssue).where(
                AuditIssue.condominium_id == condo.id, AuditIssue.status == "aberta"
            )
        )
    )
    cases = {
        c.id: c
        for c in await db.scalars(
            select(CaseRecord).where(
                CaseRecord.id.in_([i.case_id for i in issues if i.case_id] or [uuid.uuid4()])
            )
        )
    }
    shown = [i for i in issues if i.case_id or sla_level(i, current) == "escalada"]
    operate = [
        {
            "issue_id": str(i.id),
            "control_id": i.control_id,
            "title": i.title,
            "sla": sla_level(i, current),
            "sla_label": SLA_LABEL[sla_level(i, current)],
            "case": (
                {
                    "id": str(i.case_id),
                    "title": cases[i.case_id].title,
                    "status": cases[i.case_id].status,
                }
                if i.case_id in cases
                else None
            ),
        }
        for i in shown[:10]
    ]
    period = await db.scalar(
        select(AuditPeriod).where(
            AuditPeriod.condominium_id == condo.id, AuditPeriod.competence == month
        )
    )
    flagged: set[uuid.UUID] = set()
    if period is not None:
        results = await _results(db, period.id)
        for cid in ("CON-01", "CON-02", "CON-03"):
            r = results.get(cid)
            if r is None or r.status in ("VALIDADO", "NAO_APLICAVEL"):
                continue
            for ev in r.evidence_refs or []:
                if ev.get("tipo") == "contrato" and ev.get("situacao") not in (None, "confere"):
                    flagged.add(uuid.UUID(ev["id"]))
            if cid == "CON-01":
                for ev in r.evidence_refs or []:
                    if ev.get("tipo") == "contrato":
                        flagged.add(uuid.UUID(ev["id"]))
    contracts = {
        c.id: c
        for c in await db.scalars(
            select(Contract).where(
                Contract.condominium_id == condo.id, Contract.id.in_(flagged or {uuid.uuid4()})
            )
        )
    }
    stmt = select(Opportunity).where(
        Opportunity.condominium_id == condo.id,
        Opportunity.contract_id.in_(list(contracts) or [uuid.uuid4()]),
    )
    if not access.can(Permission.VIEW_OPPORTUNITY_DRAFT):
        stmt = stmt.where(Opportunity.status.in_(VISIBLE_TO_CONDO))
    opportunities = list(await db.scalars(stmt))
    with_opp = {o.contract_id for o in opportunities}
    return {
        "competencia": month.strftime("%Y-%m"),
        "operate": operate,
        "operate_total": len(shown),
        "optimize": {
            "opportunities": [
                {"id": str(o.id), "number": o.number, "title": o.title, "status": o.status}
                for o in opportunities
            ],
            # Contracts flagged by the audit with no opportunity yet: a hint for the
            # CondoOS team, never an opportunity by itself (D81: savings by code, reviewed).
            "candidates": [
                {"contract_id": str(c.id), "object": c.object}
                for c in contracts.values()
                if c.id not in with_opp
            ],
        },
    }


# --------------------------------------------------------------------------- export


def _rows_internal(results: dict[str, AuditControlResult]) -> list[dict[str, Any]]:
    out = []
    for c in CONTROLS:
        r = results.get(c.id)
        out.append(
            {
                "id": c.id,
                "pilar": PILLARS[c.pillar],
                "nome": c.name,
                "status": STATUS_LABEL.get(r.status, r.status) if r else "Sem execução",
                "motivo": r.rationale if r else "",
                "cobertura": (
                    f"{float(r.coverage) * 100:.1f}%" if r and r.coverage is not None else ""
                ),
                "diferencas": r.differences if r else None,
                "pendencias": "; ".join((r.missing or [])[:5]) if r else "",
                "regra": r.rule_version if r else "",
            }
        )
    return out


def _rows_snapshot(p: AuditPublication) -> list[dict[str, Any]]:
    return [
        {
            "id": c["id"],
            "pilar": c["pilar"],
            "nome": c["nome"],
            "status": STATUS_LABEL.get(c["status"], c["status"]),
            "motivo": c["motivo"],
            "cobertura": "",
            "diferencas": c.get("diferencas"),
            "pendencias": "; ".join(c.get("pendencias") or []),
            "regra": CONTROLS_BY_ID[c["id"]].rule_version if c["id"] in CONTROLS_BY_ID else "",
        }
        for c in p.snapshot.get("controles", [])
    ]


def _pdf(title: str, subtitle: str, rows: list[dict[str, Any]]) -> bytes:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from app.reports.pdf import BODY, H1, SMALL, _doc, _esc, _footer, _table

    buffer = io.BytesIO()
    doc = _doc(buffer, title)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    story: list[Any] = [
        Paragraph(_esc(title), H1),
        Paragraph(_esc(subtitle), SMALL),
        Spacer(1, 6),
        Paragraph(" · ".join(f"{k}: {v}" for k, v in sorted(counts.items())), BODY),
        Spacer(1, 6),
    ]
    table = [["Controle", "Estado", "Motivo e pendências"]]
    for r in rows:
        text = r["motivo"] + (f" Falta: {r['pendencias']}" if r["pendencias"] else "")
        table.append([f"{r['id']} — {r['nome']}", r["status"], text])
    story.append(_table(table, [52 * mm, 26 * mm, 96 * mm]))
    draw = _footer(title, FOOTER)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()


def _xlsx(title: str, rows: list[dict[str, Any]]) -> bytes:
    from openpyxl import Workbook

    from app.reports.xlsx import _format, _sheet

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Farol"
    _sheet(
        ws,
        title,
        [
            "Controle",
            "Pilar",
            "Nome",
            "Estado",
            "Motivo",
            "Cobertura",
            "Diferenças (R$)",
            "Pendências",
            "Regra",
        ],
        [10, 18, 34, 16, 70, 11, 15, 60, 8],
    )
    for r in rows:
        ws.append(
            [
                r["id"],
                r["pilar"],
                r["nome"],
                r["status"],
                r["motivo"],
                r["cobertura"],
                float(r["diferencas"]) if r["diferencas"] not in (None, "") else None,
                r["pendencias"],
                r["regra"],
            ]
        )
    _format(ws, money_cols=[7], date_cols=[])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _send(data: bytes, fmt: str, filename: str) -> Response:
    media = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{fmt}"'},
    )


@router.get("/condominiums/{condominium_id}/audit/export.{fmt}")
async def export_internal(
    condominium_id: uuid.UUID,
    fmt: str,
    access: CanView,
    db: DbSession,
    competencia: str | None = None,
) -> Response:
    """The month's internal farol (current results), for the team. Audited."""
    if fmt not in ("pdf", "xlsx"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formato desconhecido.")
    if not access.can(Permission.EXPORT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não exporta.")
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    period = await db.scalar(
        select(AuditPeriod).where(
            AuditPeriod.condominium_id == condo.id, AuditPeriod.competence == month
        )
    )
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Auditoria não executada neste mês.")
    rows = _rows_internal(await _results(db, period.id))
    title = f"Farol da auditoria — {month:%m/%Y}"
    subtitle = (
        f"{condo.name} · resultado interno (antes da apreciação pelo síndico) · gerado em "
        f"{utcnow():%d/%m/%Y %H:%M} UTC"
    )
    data = _pdf(title, subtitle, rows) if fmt == "pdf" else _xlsx(title, rows)
    await record_audit(
        db,
        action="audit.export",
        object_type="audit_period",
        object_id=period.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"formato": fmt, "competencia": month.isoformat(), "versao": "interna"},
    )
    return _send(data, fmt, f"farol-{month:%Y-%m}")


@router.get("/condominiums/{condominium_id}/audit/publications/{publication_id}/export.{fmt}")
async def export_published(
    condominium_id: uuid.UUID,
    publication_id: uuid.UUID,
    fmt: str,
    access: CanSee,
    db: DbSession,
) -> Response:
    """The farol the síndico approved (frozen snapshot, without unit data). Audited."""
    if fmt not in ("pdf", "xlsx"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formato desconhecido.")
    if not access.can(Permission.EXPORT):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não exporta.")
    pub = await db.get(AuditPublication, publication_id)
    if (
        pub is None
        or pub.condominium_id != access.condominium_id
        or pub.status != PublicationStatus.APROVADA.value
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Farol aprovado não encontrado.")
    condo = await _condo(db, access)
    rows = _rows_snapshot(pub)
    month = pub.snapshot.get("competencia", "")
    title = f"Farol da auditoria — {month[5:]}/{month[:4]}"
    decided = pub.decided_at.strftime("%d/%m/%Y") if pub.decided_at else "—"
    subtitle = (
        f"{condo.name} · aprovado pelo síndico em {decided} · versão {pub.snapshot_sha256[:12]}"
    )
    data = _pdf(title, subtitle, rows) if fmt == "pdf" else _xlsx(title, rows)
    await record_audit(
        db,
        action="audit.export",
        object_type="audit_publication",
        object_id=pub.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"formato": fmt, "competencia": month, "versao": "aprovada"},
    )
    return _send(data, fmt, f"farol-{month}-aprovado")


@router.get("/condominiums/{condominium_id}/audit/operations")
async def operations(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    """The continuous operation at a glance: last runs by trigger, SLA counts and sendings
    waiting for the síndico (overdue after 7 days)."""
    from app.db.models import AuditRun

    condo = await _condo(db, access)
    today = local_today(condo.timezone)
    current = add_months(month_start(today), -1)
    runs = list(
        await db.scalars(
            select(AuditRun)
            .where(AuditRun.condominium_id == condo.id)
            .order_by(AuditRun.started_at.desc())
            .limit(10)
        )
    )
    periods = {
        p.id: p.competence
        for p in await db.scalars(
            select(AuditPeriod).where(
                AuditPeriod.id.in_([r.period_id for r in runs] or [uuid.uuid4()])
            )
        )
    }
    issues = list(
        await db.scalars(
            select(AuditIssue).where(
                AuditIssue.condominium_id == condo.id, AuditIssue.status == "aberta"
            )
        )
    )
    sla: dict[str, int] = {}
    for i in issues:
        lvl = sla_level(i, current)
        sla[lvl] = sla.get(lvl, 0) + 1
    waiting = list(
        await db.scalars(
            select(AuditPublication).where(
                AuditPublication.condominium_id == condo.id,
                AuditPublication.status == PublicationStatus.AGUARDANDO.value,
            )
        )
    )
    return {
        "runs": [
            {
                "id": str(r.id),
                "competencia": (
                    periods[r.period_id].strftime("%Y-%m") if r.period_id in periods else None
                ),
                "number": r.number,
                "trigger": r.trigger,
                "status": r.status,
                "started_at": r.started_at,
                "novos": (r.summary or {}).get("novos_resultados"),
                "mudancas": (r.summary or {}).get("mudancas_de_status", []),
            }
            for r in runs
        ],
        "sla": sla,
        "waiting": [
            {
                "id": str(p.id),
                "competencia": p.snapshot.get("competencia"),
                "submitted_at": p.submitted_at,
                "overdue": publication_overdue(p, today),
            }
            for p in waiting
        ],
        "reprocess_paused": await _paused(db, condo.id),
    }


async def _paused(db: DbSession, condo_id: uuid.UUID) -> bool:
    from app.audit.events import REPROCESS_JOB
    from app.policy import active_pause

    return await active_pause(db, condo_id, REPROCESS_JOB) is not None
