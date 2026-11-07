"""Data issues (ADR-L05, LB-030, D95): two sources of the same fact disagree.

Detection is deterministic and idempotent (``scan``). The contract checks of this version:

1. **Contract × its own document:** the registered value or start date differs from what the
   document says, counting only document values that are facts (read at >= 0.9 or confirmed
   by a person). The end date is compared only when no amendment changed it (D66).
2. **Two amendments of the same contract with the same effective date** and a different
   value or end date.
3. **An amendment effective before the contract starts.**

An issue is never deleted. A person resolves it (choosing the prevailing version, with a
reason; for a contract field the chosen value is applied to the contract) or dismisses it
(with a reason). An open issue that the data no longer shows is closed by the system with the
reason "os dados deixaram de divergir". Every step goes to ``audit_log`` (ids only).
An open issue lowers the capability it names (C2 here) and the policy denies actions tied to
the contract (LB-035). It is not a finding: it accuses no one.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import DataIssueKind, DataIssueStatus
from app.db.models import Contract, ContractAmendment, DataIssue, Document
from app.extraction.fields import REVIEW_THRESHOLD

AUTO_REASON = "Os dados deixaram de divergir."

# Contract field -> (document field, label). Values applied when a person picks a version.
CONTRACT_FIELDS: dict[str, tuple[str, str]] = {
    "monthly_value": ("valor_mensal", "valor mensal"),
    "start_date": ("data_inicio", "início da vigência"),
    "end_date": ("data_fim", "fim da vigência"),
}


class DataIssueError(ValueError):
    """A resolution the data issue does not accept (pt-BR message)."""


@dataclass
class Detected:
    kind: str
    capability: str
    subject_type: str
    subject_id: uuid.UUID
    field_name: str | None
    title: str
    sources: list[dict[str, Any]] = field(default_factory=list)

    @property
    def dedupe_key(self) -> str:
        # The values are part of the key: a person's resolution holds for these values, and
        # different values later are a new issue.
        values = json.dumps([s.get("value") for s in self.sources], default=str, sort_keys=True)
        digest = hashlib.sha256(values.encode()).hexdigest()[:16]
        return f"{self.kind}:{self.subject_id}:{self.field_name or '-'}:{digest}"


def _money(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01")) if value not in (None, "") else None
    except InvalidOperation:
        return None


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _is_fact(doc: Document, name: str) -> bool:
    prov = (doc.field_provenance or {}).get(name) or {}
    if doc.reviewed_at is not None or prov.get("source") == "pessoa":
        return True
    return float((doc.field_confidence or {}).get(name, 0.0)) >= REVIEW_THRESHOLD


def _show(value: Any) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


async def detect_contracts(session: AsyncSession, condominium_id: uuid.UUID) -> list[Detected]:
    contracts = (
        await session.scalars(select(Contract).where(Contract.condominium_id == condominium_id))
    ).all()
    amendments: dict[uuid.UUID, list[ContractAmendment]] = {}
    for a in await session.scalars(
        select(ContractAmendment).where(ContractAmendment.condominium_id == condominium_id)
    ):
        amendments.setdefault(a.contract_id, []).append(a)
    docs = {
        d.id: d
        for d in await session.scalars(
            select(Document).where(
                Document.condominium_id == condominium_id,
                Document.id.in_([c.source_document_id for c in contracts if c.source_document_id]),
            )
        )
    }
    out: list[Detected] = []
    for c in contracts:
        mine = amendments.get(c.id, [])
        doc = docs.get(c.source_document_id) if c.source_document_id else None
        if doc is not None:
            amended_end = any(a.end_date is not None for a in mine)
            for attr, (doc_field, label) in CONTRACT_FIELDS.items():
                if attr == "end_date" and amended_end:
                    continue
                raw = (doc.extracted or {}).get(doc_field)
                if raw in (None, "") or not _is_fact(doc, doc_field):
                    continue
                read: Any = _money(raw) if attr == "monthly_value" else _day(raw)
                current = getattr(c, attr)
                if read is None or current is None or read == current:
                    continue
                prov = (doc.field_provenance or {}).get(doc_field) or {}
                out.append(
                    Detected(
                        DataIssueKind.CONFLITO_DOCUMENTOS.value,
                        "C2",
                        "contract",
                        c.id,
                        attr,
                        f"{c.object}: {label} do cadastro difere do documento do contrato",
                        [
                            {"label": "Contrato cadastrado", "value": _show(current)},
                            {
                                "label": "Documento do contrato",
                                "value": _show(read),
                                "document_id": str(doc.id),
                                "page": prov.get("page"),
                                "excerpt": prov.get("excerpt"),
                            },
                        ],
                    )
                )
        by_date: dict[date, list[ContractAmendment]] = {}
        for a in mine:
            by_date.setdefault(a.effective_date, []).append(a)
            if a.effective_date < c.start_date:
                out.append(
                    Detected(
                        DataIssueKind.CONFLITO_DOCUMENTOS.value,
                        "C2",
                        "contract",
                        c.id,
                        "start_date",
                        f"{c.object}: termo aditivo com data anterior ao início do contrato",
                        [
                            {"label": "Início do contrato", "value": c.start_date.isoformat()},
                            {
                                "label": "Vigência do termo aditivo",
                                "value": a.effective_date.isoformat(),
                                "document_id": str(a.document_id) if a.document_id else None,
                            },
                        ],
                    )
                )
        for when, same_day in by_date.items():
            values = {(a.monthly_value, a.end_date) for a in same_day}
            if len(same_day) < 2 or len(values) < 2:
                continue
            out.append(
                Detected(
                    DataIssueKind.CONFLITO_DOCUMENTOS.value,
                    "C2",
                    "contract",
                    c.id,
                    "amendment",
                    f"{c.object}: termos aditivos de {when:%d/%m/%Y} com valores diferentes",
                    [
                        {
                            "label": f"Termo aditivo {i + 1}",
                            "value": (
                                f"valor {_show(a.monthly_value) if a.monthly_value else '—'}; "
                                f"fim {a.end_date.isoformat() if a.end_date else '—'}"
                            ),
                            "document_id": str(a.document_id) if a.document_id else None,
                        }
                        for i, a in enumerate(sorted(same_day, key=lambda a: str(a.id)))
                    ],
                )
            )
    return out


async def scan(session: AsyncSession, condominium_id: uuid.UUID) -> list[DataIssue]:
    """Record what is detected now; close (as resolved by the system) open issues the data
    no longer shows. Idempotent: running it twice changes nothing."""
    detected = {d.dedupe_key: d for d in await detect_contracts(session, condominium_id)}
    existing = {
        i.dedupe_key: i
        for i in await session.scalars(
            select(DataIssue).where(DataIssue.condominium_id == condominium_id)
        )
    }
    now = utcnow()
    for key, d in detected.items():
        if key in existing:
            continue  # open, or already decided by a person for these same values
        issue = DataIssue(
            id=uuid.uuid4(),
            condominium_id=condominium_id,
            kind=d.kind,
            status=DataIssueStatus.ABERTO.value,
            capability=d.capability,
            subject_type=d.subject_type,
            subject_id=d.subject_id,
            field_name=d.field_name,
            title=d.title[:300],
            sources=d.sources,
            dedupe_key=key,
            detected_at=now,
        )
        session.add(issue)
        existing[key] = issue
        await record_audit(
            session,
            action="data_issue.detected",
            object_type="data_issue",
            object_id=issue.id,
            condominium_id=condominium_id,
            details={"kind": d.kind, "subject_id": str(d.subject_id), "field": d.field_name},
        )
    for key, issue in existing.items():
        if issue.status == DataIssueStatus.ABERTO.value and key not in detected:
            issue.status = DataIssueStatus.RESOLVIDO.value
            issue.resolved_at = now
            issue.resolution = {"auto": True, "prevailing": None, "reason": AUTO_REASON}
            await record_audit(
                session,
                action="data_issue.auto_resolved",
                object_type="data_issue",
                object_id=issue.id,
                condominium_id=condominium_id,
            )
    await session.flush()
    return [i for i in existing.values() if i.status == DataIssueStatus.ABERTO.value]


async def open_issues(
    session: AsyncSession, condominium_id: uuid.UUID, *, subject_id: uuid.UUID | None = None
) -> list[DataIssue]:
    stmt = select(DataIssue).where(
        DataIssue.condominium_id == condominium_id,
        DataIssue.status == DataIssueStatus.ABERTO.value,
    )
    if subject_id is not None:
        stmt = stmt.where(DataIssue.subject_id == subject_id)
    return list(await session.scalars(stmt.order_by(DataIssue.detected_at)))


def _reason(reason: str) -> str:
    text = (reason or "").strip()
    if len(text) < 10:
        raise DataIssueError("Explique o motivo (pelo menos 10 caracteres).")
    return text[:1000]


async def resolve(
    session: AsyncSession,
    issue: DataIssue,
    access: CondoAccess,
    *,
    prevailing: int,
    reason: str,
) -> DataIssue:
    """Pick the prevailing version. For a contract field, its value is applied to the
    contract; for other conflicts the choice is recorded (nothing is deleted)."""
    if issue.status != DataIssueStatus.ABERTO.value:
        raise DataIssueError("Este conflito já foi tratado.")
    why = _reason(reason)
    if not 0 <= prevailing < len(issue.sources):
        raise DataIssueError("Escolha uma das versões mostradas.")
    chosen = issue.sources[prevailing]
    applied: dict[str, str] | None = None
    if issue.subject_type == "contract" and issue.field_name in CONTRACT_FIELDS:
        contract = await session.scalar(
            select(Contract).where(
                Contract.id == issue.subject_id,
                Contract.condominium_id == issue.condominium_id,
            )
        )
        if contract is not None:
            before = getattr(contract, issue.field_name)
            value: Any = (
                _money(chosen["value"])
                if issue.field_name == "monthly_value"
                else _day(chosen["value"])
            )
            if value is not None and value != before:
                setattr(contract, issue.field_name, value)
                applied = {"field": issue.field_name, "before": _show(before)}
    issue.status = DataIssueStatus.RESOLVIDO.value
    issue.resolved_at = utcnow()
    issue.resolved_by_user_id = access.user_id
    issue.resolution = {
        "auto": False,
        "prevailing": prevailing,
        "value": chosen.get("value"),
        "reason": why,
        "applied": applied,
    }
    await record_audit(
        session,
        action="data_issue.resolved",
        object_type="data_issue",
        object_id=issue.id,
        actor_user_id=access.user_id,
        condominium_id=issue.condominium_id,
        details={"prevailing": prevailing, "applied": bool(applied)},
    )
    await session.flush()
    return issue


async def dismiss(
    session: AsyncSession, issue: DataIssue, access: CondoAccess, *, reason: str
) -> DataIssue:
    if issue.status != DataIssueStatus.ABERTO.value:
        raise DataIssueError("Este conflito já foi tratado.")
    issue.status = DataIssueStatus.DESCARTADO.value
    issue.resolved_at = utcnow()
    issue.resolved_by_user_id = access.user_id
    issue.resolution = {"auto": False, "prevailing": None, "reason": _reason(reason)}
    await record_audit(
        session,
        action="data_issue.dismissed",
        object_type="data_issue",
        object_id=issue.id,
        actor_user_id=access.user_id,
        condominium_id=issue.condominium_id,
    )
    await session.flush()
    return issue


SCAN_JOB = "data_issues.scan"


async def scan_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Worker job: one condominium (``condominium_id``) or, daily, every condominium."""
    from app.db.models import Condominium

    if payload.get("condominium_id"):
        await scan(session, uuid.UUID(payload["condominium_id"]))
        return
    for cid in (await session.scalars(select(Condominium.id))).all():
        await scan(session, cid)
