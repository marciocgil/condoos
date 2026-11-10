"""Job ``document.process``: classify, extract and route one document. Idempotent.

Order of trust when merging field values:
1. Fiscal XML and check-digit-validated codes (confidence 1.0) — never overridden.
2. The model's structured extraction (its own confidence).
3. Text heuristics (low confidence: a pre-fill for the human).
Then ``confidence.assess`` applies the deterministic validations. A document with a
required field below 0.9 goes to the exception queue and produces no findings until fixed.
A document already corrected by a person is never re-extracted.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEX_JOB, INDEXED_TYPES
from app.core.audit import record_audit
from app.core.br import is_valid_cnpj, only_digits
from app.core.jobs import enqueue
from app.db.enums import DocumentType, ExtractionStatus
from app.db.models import Condominium, Document, ManagementCompany, Supplier
from app.enrichment.suppliers import (
    SupplierLookupUnavailable,
    apply_record,
    get_or_create_supplier,
    get_provider,
)
from app.extraction.confidence import assess
from app.extraction.convert import Converted, convert
from app.extraction.evidence import NAME_PAIRS, cnpjs_in_text, lone_counterparty
from app.extraction.fields import BANK_TYPES, REVIEW_THRESHOLD, SPECS, TEXT_ONLY_TYPES
from app.extraction.heuristics import CERTAIN, REFUSED_DEBTORS, classify_text, prefill
from app.extraction.llm_extract import classify_with_llm, extract_with_llm
from app.extraction.provenance import build as build_provenance
from app.extraction.xml_fiscal import NotFiscalXml, parse_fiscal_xml
from app.ingestion.bank.base import BankFileError
from app.ingestion.bank.service import parse_bank_file, store_statement
from app.ingestion.filetypes import CNAB, CSV, IMAGE_TYPES, OFX, XML
from app.llm.client import LLMUnavailable
from app.storage.base import get_storage

logger = logging.getLogger(__name__)

LLM_CLASSIFY_MIN_CONFIDENCE = 0.8
BANK_MIMES = (CNAB, OFX, CSV)


@dataclass
class Analysis:
    doc_type: DocumentType
    classification_source: str | None
    values: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    text: str | None = None
    page_count: int | None = None
    complete: bool = False  # True when no human review is needed
    provenance: dict[str, Any] = field(default_factory=dict)  # per field (CB-030)
    refused: str | None = None  # the file must not stay in the CondoOS (D120, B5)

    @property
    def extraction_source(self) -> str:
        return "+".join(self.sources) or "nenhuma"


async def analyze(
    session: AsyncSession | None,
    *,
    data: bytes,
    mime: str,
    filename: str,
    condominium_id: uuid.UUID | None,  # None: a measurement, not a condominium (corpus)
    condominium_cnpj: str,
    today: date,
    other_own_cnpjs: frozenset[str] = frozenset(),
) -> Analysis:
    """Classify and extract a non-bank document. No database writes except ``llm_calls``
    and the supplier registry cache. ``other_own_cnpjs``: CNPJs that are never the
    counterparty (the management company), for the CNPJ search in the text (D120)."""
    raw: dict[str, Any] = {}
    origin: dict[str, str] = {}  # where each raw value came from (CB-030)
    source_conf: dict[str, float] = {}
    sources: list[str] = []
    converted: Converted | None = None
    doc_type: DocumentType | None = None
    classification_source: str | None = None

    if mime == XML:
        try:
            xml = parse_fiscal_xml(data)
        except NotFiscalXml as exc:
            return Analysis(DocumentType.OUTRO, None, reasons=[f"XML não reconhecido: {exc}"])
        doc_type, classification_source = xml.doc_type, "xml"
        for name, value in xml.values.items():
            if value not in (None, "", []):
                raw[name], source_conf[name] = value, CERTAIN
                origin[name] = "xml"
        sources.append(xml.layout)
        page_count = 1
    else:
        converted = await asyncio.to_thread(convert, data, mime, filename)
        page_count = converted.page_count
        classification = classify_text(converted.text, today)
        if classification.refused:
            return Analysis(
                DocumentType.OUTRO,
                "heuristica",
                reasons=[classification.refused],
                refused=classification.refused,
                page_count=page_count,
            )
        if classification.doc_type is not None:
            doc_type, classification_source = classification.doc_type, "heuristica"
        else:
            try:
                out = await classify_with_llm(
                    session,
                    converted=converted,
                    data=data,
                    mime=mime,
                    condominium_id=condominium_id,
                )
                if out.doc_type == "relacao_devedores" and out.confidence >= 0.8:
                    return Analysis(
                        DocumentType.OUTRO,
                        "ia",
                        reasons=[REFUSED_DEBTORS],
                        refused=REFUSED_DEBTORS,
                        page_count=page_count,
                    )
                if out.confidence >= LLM_CLASSIFY_MIN_CONFIDENCE:
                    doc_type, classification_source = DocumentType(out.doc_type), "ia"
            except LLMUnavailable as exc:
                logger.info("classification without model reason=%s", type(exc).__name__)

    text = converted.text if converted is not None and converted.text else None
    if doc_type is None:
        reason = (
            "Documento sem texto legível (foto ou digitalização): é preciso ler e preencher."
            if converted is not None and converted.quality == "none"
            else "Não foi possível identificar o tipo do documento automaticamente."
        )
        return Analysis(
            DocumentType.OUTRO, None, reasons=[reason], text=text, page_count=page_count
        )

    base = Analysis(doc_type, classification_source, text=text, page_count=page_count)
    if doc_type in TEXT_ONLY_TYPES:
        base.sources, base.complete = ["texto"], True
        return base
    if doc_type in BANK_TYPES:
        base.reasons = ["Extrato em PDF ou imagem não é importado. Envie o extrato em OFX ou CSV."]
        return base
    if doc_type not in SPECS:
        base.reasons = ["Tipo de documento sem extração automática."]
        return base

    if converted is not None:
        pf = prefill(doc_type, converted.text, condominium_cnpj, today)
        for name, value in pf.values.items():
            if source_conf.get(name, 0.0) < pf.confidence[name]:
                raw[name], source_conf[name] = value, pf.confidence[name]
                origin[name] = "texto"
        if pf.values:
            sources.append("texto")

    notes = ""
    missing_certain = [s.name for s in SPECS[doc_type] if source_conf.get(s.name, 0.0) < CERTAIN]
    if converted is not None and missing_certain:
        try:
            values, model_conf, notes = await extract_with_llm(
                session,
                doc_type=doc_type,
                converted=converted,
                data=data,
                mime=mime,
                condominium_id=condominium_id,
            )
            for name in missing_certain:
                if values.get(name) not in (None, "", []):
                    raw[name], source_conf[name] = values[name], model_conf.get(name, 0.0)
                    origin[name] = "ia"
            sources.append("ia")
        except LLMUnavailable as exc:
            logger.info("extraction without model reason=%s", type(exc).__name__)

    suggested = _suggest_counterparty(doc_type, raw, text, condominium_cnpj, other_own_cnpjs)
    if suggested:
        source_conf[suggested], origin[suggested] = SUGGESTED_FROM_TEXT, "texto"
    absent = (
        doc_type in COUNTERPARTY_SEARCH
        and text is not None
        # Only a good text layer proves absence: OCR of a photo may have lost the digits.
        and converted is not None
        and converted.quality == "good"
        and mime not in IMAGE_TYPES
        and not [
            c
            for c in cnpjs_in_text(text)
            if c not in {condominium_cnpj, *other_own_cnpjs}
            and c != only_digits(str(raw.get("cnpj_contratante") or ""))
        ]
    )
    names = await registry_names(
        session, raw, allow_network=session is not None and condominium_id is not None
    )
    result = assess(
        doc_type,
        raw,
        source_conf,
        condominium_cnpj=condominium_cnpj,
        today=today,
        text=text,
        registry_names=names,
        counterparty_absent=absent,
    )
    base.values = result.values
    base.confidence = {k: round(v, 3) for k, v in result.confidence.items()}
    base.sources = sources
    base.reasons = list(result.reasons)
    if suggested and result.confidence.get(suggested, 0.0) < REVIEW_THRESHOLD:
        label = next(s.label for s in SPECS[doc_type] if s.name == suggested)
        base.reasons = [
            (
                f"{label}: sugerido do texto (o único CNPJ além do condomínio); confira"
                if r.startswith(f"{label}:")
                else r
            )
            for r in base.reasons
        ]
    if base.reasons and notes:
        base.reasons.append(f"Observação da IA: {notes}")
    base.complete = not result.needs_review
    base.provenance = build_provenance(doc_type, result.values, origin, text, result.inferred)
    for name, proof in result.evidence.items():
        if name in base.provenance:
            base.provenance[name]["evidence"] = proof
    for name, note in result.observations.items():
        if name in base.provenance:
            base.provenance[name]["note"] = note
    return base


# Confidence of a CNPJ found by the text search: below the "written in the text" floor, so
# only the Receita (legal name matches) can confirm it (D120, A3).
SUGGESTED_FROM_TEXT = 0.5
COUNTERPARTY_SEARCH = {DocumentType.CONTRATO: ("cnpj_contratada", ("cnpj_contratante",))}


def _suggest_counterparty(
    doc_type: DocumentType,
    raw: dict[str, Any],
    text: str | None,
    condominium_cnpj: str,
    other_own: frozenset[str],
) -> str | None:
    """When the model did not find the counterparty CNPJ, the only valid CNPJ in the text
    other than the condominium, the management company and the other party is suggested."""
    if doc_type not in COUNTERPARTY_SEARCH or not text:
        return None
    target, others = COUNTERPARTY_SEARCH[doc_type]
    current = only_digits(str(raw.get(target) or ""))
    if len(current) == 14 and is_valid_cnpj(current):
        return None
    exclude = {condominium_cnpj, *other_own}
    exclude |= {only_digits(str(raw.get(o) or "")) for o in others}
    found = lone_counterparty(text, exclude)
    if found is None:
        return None
    raw[target] = found
    return target


async def registry_names(
    session: AsyncSession | None, raw: dict[str, Any], *, allow_network: bool
) -> dict[str, str]:
    """Legal name at the Receita for each counterparty CNPJ read (D120). First the supplier
    cache (data from the registry or the seed, never what a document showed); then, when
    allowed, the registry itself. A failure only means no proof."""
    out: dict[str, str] = {}
    for field_name in NAME_PAIRS:
        cnpj = only_digits(str(raw.get(field_name) or ""))
        if len(cnpj) != 14 or not is_valid_cnpj(cnpj) or cnpj in out:
            continue
        name = await _registry_name(session, cnpj, allow_network)
        if name:
            out[cnpj] = name
    return out


async def _registry_name(
    session: AsyncSession | None, cnpj: str, allow_network: bool
) -> str | None:
    if session is None:
        return None
    supplier = await session.scalar(select(Supplier).where(Supplier.cnpj == cnpj))
    if supplier is not None and supplier.enrichment_source not in (None, "documento"):
        return supplier.legal_name
    if not allow_network:
        return None
    try:
        record = await get_provider().lookup(cnpj)
    except (SupplierLookupUnavailable, httpx.HTTPError) as exc:
        logger.info("registry lookup unavailable reason=%s", type(exc).__name__)
        return None
    if record is None:
        return None
    if supplier is None:
        supplier = await get_or_create_supplier(session, cnpj, record.legal_name)
    apply_record(supplier, record)
    return record.legal_name


async def process_document(session: AsyncSession, payload: dict[str, Any]) -> None:
    doc = await session.get(Document, uuid.UUID(payload["document_id"]), with_for_update=True)
    if doc is None:
        return
    if doc.reviewed_at is not None:
        logger.info("document already reviewed by a person id=%s", doc.id)
        return
    condo = await session.get(Condominium, doc.condominium_id)
    assert condo is not None
    data = await asyncio.to_thread(get_storage().get, doc.storage_key)

    if doc.mime_type in BANK_MIMES:
        await _import_bank_file(session, doc, condo, data)
        return

    analysis = await analyze(
        session,
        data=data,
        mime=doc.mime_type,
        filename=doc.original_filename,
        condominium_id=condo.id,
        condominium_cnpj=condo.cnpj,
        today=date.today(),
        other_own_cnpjs=await _management_cnpjs(session, condo),
    )
    if analysis.refused:
        await _refuse(session, doc, analysis.refused)
        return
    doc.doc_type = analysis.doc_type.value
    doc.classification_source = analysis.classification_source
    doc.extraction_source = analysis.extraction_source
    doc.text_content = analysis.text
    doc.page_count = analysis.page_count
    doc.extracted = analysis.values
    doc.field_confidence = analysis.confidence
    doc.field_provenance = analysis.provenance
    doc.needs_review = not analysis.complete
    doc.review_reasons = [] if analysis.complete else analysis.reasons
    doc.extraction_status = (
        ExtractionStatus.DONE if analysis.complete else ExtractionStatus.NEEDS_REVIEW
    ).value
    if analysis.complete:
        await enqueue_match(session, doc)
    if doc.doc_type in INDEXED_TYPES and doc.text_content:
        await enqueue_index(session, doc)


async def _refuse(session: AsyncSession, doc: Document, reason: str) -> None:
    """A file that must not stay (residents' data, D120 B5): the stored file is deleted and
    nothing read from it is kept; the row stays so the sender sees why."""
    await asyncio.to_thread(get_storage().delete, doc.storage_key)
    doc.doc_type = DocumentType.OUTRO.value
    doc.classification_source = "triagem"
    doc.extraction_source = "nenhuma"
    doc.text_content = None
    doc.extracted = {"recusado": True, "motivo": reason}
    doc.field_confidence = {}
    doc.field_provenance = {}
    doc.needs_review = False
    doc.review_reasons = []
    doc.extraction_status = ExtractionStatus.DONE.value
    await record_audit(
        session,
        action="document.refused",
        object_type="document",
        object_id=doc.id,
        condominium_id=doc.condominium_id,
        details={"motivo": "relacao_devedores"},
    )


async def _management_cnpjs(session: AsyncSession, condo: Condominium) -> frozenset[str]:
    if condo.management_company_id is None:
        return frozenset()
    company = await session.get(ManagementCompany, condo.management_company_id)
    return frozenset({company.cnpj}) if company is not None else frozenset()


async def enqueue_index(session: AsyncSession, doc: Document) -> None:
    """Passages for the chat's document search (contracts, convention, minutes)."""
    await enqueue(
        session,
        INDEX_JOB,
        {"document_id": str(doc.id)},
        condominium_id=doc.condominium_id,
        dedupe_key=None,  # re-indexing is idempotent
    )


async def enqueue_match(session: AsyncSession, doc: Document) -> None:
    """Next step of the pipeline: document -> expense -> contract (milestone 3)."""
    await enqueue(
        session,
        "document.match",
        {"document_id": str(doc.id)},
        condominium_id=doc.condominium_id,
        dedupe_key=None,  # matching is idempotent; a corrected document is matched again
        priority=True,  # seconds of work: never behind a backlog of OCR
    )


async def _import_bank_file(
    session: AsyncSession, doc: Document, condo: Condominium, data: bytes
) -> None:
    doc.doc_type = (
        DocumentType.CNAB_RETORNO if doc.mime_type == CNAB else DocumentType.EXTRATO
    ).value
    doc.classification_source = "arquivo"
    doc.extraction_source = "arquivo"
    try:
        statement = parse_bank_file(doc.original_filename, data)
        imported = await store_statement(
            session, condominium_id=condo.id, condominium_cnpj=condo.cnpj, statement=statement
        )
    except BankFileError as exc:
        doc.extracted = {"erro": str(exc)}
        doc.needs_review = True
        doc.review_reasons = [str(exc)]
        doc.extraction_status = ExtractionStatus.NEEDS_REVIEW.value
        return
    doc.extracted = {
        "lancamentos_novos": imported.created,
        "lancamentos_repetidos": imported.duplicates,
        "registros_ignorados": imported.ignored_records,
        "banco": statement.bank_code,
    }
    doc.needs_review = False
    doc.review_reasons = []
    doc.extraction_status = ExtractionStatus.DONE.value
    if imported.created:
        await enqueue(
            session,
            "bank.match",
            {"condominium_id": str(condo.id)},
            condominium_id=condo.id,
            dedupe_key=f"bank-match:{condo.id}:doc:{doc.id}",
        )
