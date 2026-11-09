"""Compliance and expiry dates (D112, FR-057, WP-16 first cut).

- An obligation applies only when a person says so (``validate``); the catalogue only
  suggests candidates (``catalog.py``).
- Evidence is append only: a person types dates, or links a document and the model reads
  its dates (``read_validity_job``), always "a confirmar" until a person confirms.
- The situation is computed on every read (``status.py``). Nothing leaves the system.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.catalog import BY_KEY, CATALOG
from app.compliance.status import ORDER, Situation, situation
from app.core.jobs import enqueue
from app.core.time import utcnow
from app.db.enums import (
    ComplianceApplicability,
    ComplianceCategory,
    ComplianceEventKind,
    EvidenceSource,
)
from app.db.models import (
    ComplianceEvent,
    ComplianceEvidence,
    ComplianceObligation,
    Document,
)

logger = logging.getLogger(__name__)

READ_JOB = "compliance.read_validity"
DEFAULT_LEAD_DAYS = 60
NOT_FOUND_NOTE = "Não encontrei a validade no documento. Informe a data."


class ComplianceError(ValueError):
    """Message shown to the user (pt-BR)."""


@dataclass
class Row:
    obligation: ComplianceObligation
    evidence: ComplianceEvidence | None
    situation: Situation


# --------------------------------------------------------------------------- reading


async def latest_evidence(
    session: AsyncSession, obligation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ComplianceEvidence]:
    if not obligation_ids:
        return {}
    rows = await session.scalars(
        select(ComplianceEvidence)
        .where(ComplianceEvidence.obligation_id.in_(obligation_ids))
        .order_by(ComplianceEvidence.created_at.desc(), ComplianceEvidence.id)
    )
    latest: dict[uuid.UUID, ComplianceEvidence] = {}
    for e in rows:
        latest.setdefault(e.obligation_id, e)
    return latest


async def rows_for(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    today: date,
    *,
    include_archived: bool = False,
) -> list[Row]:
    stmt = select(ComplianceObligation).where(ComplianceObligation.condominium_id == condominium_id)
    if not include_archived:
        stmt = stmt.where(ComplianceObligation.archived_at.is_(None))
    obligations = list(await session.scalars(stmt))
    latest = await latest_evidence(session, [o.id for o in obligations])
    rows = [Row(o, latest.get(o.id), situation(o, latest.get(o.id), today)) for o in obligations]
    order = {code: i for i, code in enumerate(ORDER)}
    rows.sort(
        key=lambda r: (
            order[r.situation.code],
            r.situation.valid_until or date.max,
            r.obligation.name,
        )
    )
    return rows


async def get_obligation(
    session: AsyncSession, condominium_id: uuid.UUID, obligation_id: uuid.UUID
) -> ComplianceObligation:
    ob = await session.get(ComplianceObligation, obligation_id)
    if ob is None or ob.condominium_id != condominium_id:
        raise LookupError("obrigação não encontrada")
    return ob


# --------------------------------------------------------------------------- changes


def _event(
    ob: ComplianceObligation,
    kind: ComplianceEventKind,
    user_id: uuid.UUID | None,
    **payload: Any,
) -> ComplianceEvent:
    return ComplianceEvent(
        id=uuid.uuid4(),
        condominium_id=ob.condominium_id,
        obligation_id=ob.id,
        kind=kind.value,
        user_id=user_id,
        payload=payload,
    )


def _clean_name(name: str) -> str:
    name = " ".join(name.split())
    if len(name) < 3:
        raise ComplianceError("Informe o nome da obrigação.")
    return name[:200]


def _check_lead(lead_days: int) -> int:
    if not 1 <= lead_days <= 365:
        raise ComplianceError("A antecedência do aviso vai de 1 a 365 dias.")
    return lead_days


async def activate_catalog(
    session: AsyncSession, condominium_id: uuid.UUID, user_id: uuid.UUID | None
) -> int:
    """Add the catalogue's candidates that are not there yet, all ``a_validar``."""
    have = set(
        await session.scalars(
            select(ComplianceObligation.catalog_key).where(
                ComplianceObligation.condominium_id == condominium_id,
                ComplianceObligation.catalog_key.is_not(None),
            )
        )
    )
    created = 0
    for item in CATALOG:
        if item.key in have:
            continue
        ob = ComplianceObligation(
            id=uuid.uuid4(),
            condominium_id=condominium_id,
            catalog_key=item.key,
            name=item.name,
            category=item.category.value,
            suggested_months=item.months,
            lead_days=DEFAULT_LEAD_DAYS,
            applicability=ComplianceApplicability.A_VALIDAR.value,
            created_by=user_id,
        )
        session.add(ob)
        await session.flush()
        session.add(_event(ob, ComplianceEventKind.CRIADA, user_id, catalog_key=item.key))
        created += 1
    return created


async def create_obligation(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    user_id: uuid.UUID | None,
    *,
    name: str,
    category: str,
    lead_days: int = DEFAULT_LEAD_DAYS,
    responsible: str | None = None,
    supplier_id: uuid.UUID | None = None,
) -> ComplianceObligation:
    """An obligation the síndico adds by hand. It still needs validation to raise alerts."""
    if category not in {c.value for c in ComplianceCategory}:
        raise ComplianceError("Categoria desconhecida.")
    ob = ComplianceObligation(
        id=uuid.uuid4(),
        condominium_id=condominium_id,
        name=_clean_name(name),
        category=category,
        lead_days=_check_lead(lead_days),
        responsible=(responsible or "").strip()[:200] or None,
        supplier_id=supplier_id,
        applicability=ComplianceApplicability.A_VALIDAR.value,
        created_by=user_id,
    )
    session.add(ob)
    await session.flush()
    session.add(_event(ob, ComplianceEventKind.CRIADA, user_id))
    return ob


async def update_obligation(
    session: AsyncSession,
    ob: ComplianceObligation,
    user_id: uuid.UUID | None,
    *,
    name: str | None = None,
    lead_days: int | None = None,
    responsible: str | None = None,
    supplier_id: uuid.UUID | None = None,
    clear_supplier: bool = False,
) -> None:
    changed: list[str] = []
    if name is not None and _clean_name(name) != ob.name:
        ob.name = _clean_name(name)
        changed.append("nome")
    if lead_days is not None and lead_days != ob.lead_days:
        ob.lead_days = _check_lead(lead_days)
        changed.append("antecedencia")
    if responsible is not None and (responsible.strip()[:200] or None) != ob.responsible:
        ob.responsible = responsible.strip()[:200] or None
        changed.append("responsavel")
    if clear_supplier and ob.supplier_id is not None:
        ob.supplier_id = None
        changed.append("fornecedor")
    elif supplier_id is not None and supplier_id != ob.supplier_id:
        ob.supplier_id = supplier_id
        changed.append("fornecedor")
    if changed:
        session.add(_event(ob, ComplianceEventKind.ALTERADA, user_id, campos=changed))


async def validate(
    session: AsyncSession,
    ob: ComplianceObligation,
    user_id: uuid.UUID,
    *,
    applies: bool,
    reason: str,
    periodicity_months: int | None = None,
) -> None:
    """A person decides whether the obligation applies and how often it renews."""
    reason = " ".join(reason.split())
    if len(reason) < 3:
        raise ComplianceError("Diga o motivo (por exemplo, quem orientou ou onde consta).")
    if periodicity_months is not None and not 1 <= periodicity_months <= 120:
        raise ComplianceError("A periodicidade vai de 1 a 120 meses.")
    ob.applicability = (
        ComplianceApplicability.APLICAVEL.value
        if applies
        else ComplianceApplicability.NAO_APLICAVEL.value
    )
    ob.periodicity_months = periodicity_months if applies else None
    ob.validated_by = user_id
    ob.validated_at = utcnow()
    ob.validation_reason = reason[:1000]
    session.add(
        _event(
            ob,
            ComplianceEventKind.VALIDADA,
            user_id,
            aplicabilidade=ob.applicability,
            periodicidade_meses=ob.periodicity_months,
        )
    )


async def add_evidence(
    session: AsyncSession,
    ob: ComplianceObligation,
    user_id: uuid.UUID | None,
    *,
    document_id: uuid.UUID | None,
    issued_on: date | None,
    valid_until: date | None,
    note: str | None = None,
) -> ComplianceEvidence:
    """Dates typed by a person are confirmed. A document without dates is read by the model
    (``read_validity_job``) and its dates wait for a person to confirm them."""
    if ob.archived_at is not None:
        raise ComplianceError("A obrigação está arquivada.")
    if document_id is None and issued_on is None and valid_until is None:
        raise ComplianceError("Escolha um documento ou informe as datas.")
    if issued_on and valid_until and valid_until < issued_on:
        raise ComplianceError("A validade não pode ser anterior à emissão.")
    if document_id is not None:
        doc = await session.get(Document, document_id)
        if doc is None or doc.condominium_id != ob.condominium_id:
            raise ComplianceError("Documento não encontrado neste condomínio.")
    typed = issued_on is not None or valid_until is not None
    ev = ComplianceEvidence(
        id=uuid.uuid4(),
        condominium_id=ob.condominium_id,
        obligation_id=ob.id,
        document_id=document_id,
        issued_on=issued_on,
        valid_until=valid_until,
        source=(EvidenceSource.PESSOA if typed else EvidenceSource.LENDO).value,
        confirmed=typed,
        note=(note or "").strip()[:500] or None,
        user_id=user_id,
    )
    session.add(ev)
    await session.flush()
    session.add(_event(ob, ComplianceEventKind.EVIDENCIA, user_id, fonte=ev.source))
    if not typed:
        await enqueue(
            session,
            READ_JOB,
            {"evidence_id": str(ev.id)},
            condominium_id=ob.condominium_id,
            dedupe_key=f"{READ_JOB}:{ev.id}",
        )
    return ev


async def confirm_evidence(
    session: AsyncSession,
    ob: ComplianceObligation,
    evidence_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    issued_on: date | None,
    valid_until: date | None,
) -> ComplianceEvidence:
    """A person confirms (or corrects) the dates read from a document: a new row."""
    base = await session.get(ComplianceEvidence, evidence_id)
    if base is None or base.obligation_id != ob.id:
        raise ComplianceError("Registro não encontrado.")
    if issued_on is None and valid_until is None:
        raise ComplianceError("Informe ao menos uma data.")
    return await add_evidence(
        session,
        ob,
        user_id,
        document_id=base.document_id,
        issued_on=issued_on,
        valid_until=valid_until,
        note="Datas conferidas por pessoa",
    )


async def set_archived(
    session: AsyncSession, ob: ComplianceObligation, user_id: uuid.UUID, archived: bool
) -> None:
    if archived == (ob.archived_at is not None):
        return
    ob.archived_at = utcnow() if archived else None
    kind = ComplianceEventKind.ARQUIVADA if archived else ComplianceEventKind.REATIVADA
    session.add(_event(ob, kind, user_id))


async def counts(session: AsyncSession, condominium_id: uuid.UUID, today: date) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in await rows_for(session, condominium_id, today):
        out[row.situation.code] = out.get(row.situation.code, 0) + 1
    return out


async def has_obligations(session: AsyncSession, condominium_id: uuid.UUID) -> bool:
    n = await session.scalar(
        select(func.count())
        .select_from(ComplianceObligation)
        .where(ComplianceObligation.condominium_id == condominium_id)
    )
    return bool(n)


# --------------------------------------------------------------------------- AI reading


class ValidityReading(BaseModel):
    emissao: str | None = None
    validade: str | None = None
    trecho: str | None = None
    confidence: float = Field(ge=0, le=1)


_DATE = r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})"
_PERIOD = re.compile(
    r"(?:vig[êe]ncia|per[íi]odo).{0,40}?" + _DATE + r".{1,25}?" + _DATE, re.IGNORECASE | re.DOTALL
)
_UNTIL = re.compile(
    r"(?:v[áa]lid[oa]s?\s+at[ée]|validade|vencimento|vence\s+em|expira\s+em).{0,30}?" + _DATE,
    re.IGNORECASE,
)
_ISSUED = re.compile(r"(?:emiss[ãa]o|emitid[oa]\s+em|expedi[çc][ãa]o).{0,30}?" + _DATE, re.I)


def _mk(day: str, month: str, year: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def _snippet(text: str, match: re.Match[str]) -> str:
    return " ".join(text[match.start() : match.end()].split())[:200]


def read_dates_from_text(text: str) -> tuple[date | None, date | None, str | None]:
    """Dates written next to the usual words (vigência, válido até, emissão). Returns
    (issued_on, valid_until, quote). Nothing is computed: only dates written in the text."""
    if m := _PERIOD.search(text):
        return _mk(*m.groups()[:3]), _mk(*m.groups()[3:]), _snippet(text, m)
    issued = None
    quote = None
    if m := _ISSUED.search(text):
        issued = _mk(*m.groups())
        quote = _snippet(text, m)
    if m := _UNTIL.search(text):
        return issued, _mk(*m.groups()), _snippet(text, m)
    return issued, None, quote


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _written_in(text: str, value: date | None) -> bool:
    """The date must be written in the text (any usual format) to be kept."""
    if value is None:
        return True
    forms = {
        value.strftime("%d/%m/%Y"),
        f"{value.day}/{value.month}/{value.year}",
        value.strftime("%d.%m.%Y"),
        value.strftime("%d-%m-%Y"),
        value.isoformat(),
    }
    return any(f in text for f in forms)


async def _llm_read(
    session: AsyncSession, ob: ComplianceObligation, doc: Document
) -> ValidityReading | None:
    from app.extraction.convert import Converted
    from app.extraction.llm_extract import _inputs
    from app.llm.client import LLMRequest, LLMUnavailable, call_structured
    from app.llm.prompts import load_prompt
    from app.storage.base import get_storage

    text = doc.text_content or ""
    data = b""
    if not text.strip() or doc.mime_type.startswith("image/"):
        data = get_storage().get(doc.storage_key)
    converted = Converted(text=text, page_count=doc.page_count or 1, engine="none")
    user_text, attachments = _inputs(converted, data, doc.mime_type)
    try:
        result = await call_structured(
            session,
            LLMRequest(
                purpose="compliance.validity",
                role="extraction",
                system=load_prompt("compliance_validity"),
                user_text=f"Obrigação: {ob.name}\n\n{user_text}",
                output_model=ValidityReading,
                attachments=attachments,
                condominium_id=ob.condominium_id,
                max_tokens=1500,
                effort="low",
            ),
        )
    except LLMUnavailable as exc:
        logger.info("compliance validity reading without the model: %s", type(exc).__name__)
        return None
    return result.output


async def read_validity_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Read the dates of a linked document. Appends an unconfirmed row; does nothing if a
    newer row exists (a person typed the dates meanwhile)."""
    ev = await session.get(ComplianceEvidence, uuid.UUID(str(payload["evidence_id"])))
    if ev is None or ev.source != EvidenceSource.LENDO.value or ev.document_id is None:
        return
    newest = (await latest_evidence(session, [ev.obligation_id])).get(ev.obligation_id)
    if newest is None or newest.id != ev.id:
        return
    ob = await session.get(ComplianceObligation, ev.obligation_id)
    doc = await session.get(Document, ev.document_id)
    if ob is None or doc is None:
        return
    text = doc.text_content or ""

    issued: date | None = None
    until: date | None = None
    quote: str | None = None
    source = EvidenceSource.TEXTO
    reading = await _llm_read(session, ob, doc)
    if reading is not None:
        source = EvidenceSource.IA
        issued, until = _parse_iso(reading.emissao), _parse_iso(reading.validade)
        quote = (reading.trecho or "").strip()[:200] or None
        if text.strip():
            # With text, a date the model returns must be written there (no invented dates).
            if not _written_in(text, issued):
                issued = None
            if not _written_in(text, until):
                until = None
    if issued is None and until is None and text.strip():
        issued, until, quote = read_dates_from_text(text)
        source = EvidenceSource.TEXTO
    if issued and until and until < issued:
        issued = None
    session.add(
        ComplianceEvidence(
            id=uuid.uuid4(),
            condominium_id=ev.condominium_id,
            obligation_id=ev.obligation_id,
            document_id=ev.document_id,
            issued_on=issued,
            valid_until=until,
            source=source.value,
            confirmed=False,
            quote=quote if (issued or until) else None,
            note=None if (issued or until) else NOT_FOUND_NOTE,
            user_id=None,
        )
    )
    session.add(
        _event(ob, ComplianceEventKind.EVIDENCIA, None, fonte=source.value, leitura=bool(until))
    )


def as_of(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


__all__ = [
    "BY_KEY",
    "CATALOG",
    "READ_JOB",
    "ComplianceError",
    "Row",
    "activate_catalog",
    "add_evidence",
    "confirm_evidence",
    "create_obligation",
    "get_obligation",
    "read_dates_from_text",
    "read_validity_job",
    "rows_for",
    "set_archived",
    "update_obligation",
    "validate",
]
