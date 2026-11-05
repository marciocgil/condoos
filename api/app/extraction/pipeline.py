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

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import DocumentType, ExtractionStatus
from app.db.models import Condominium, Document
from app.extraction.confidence import assess
from app.extraction.convert import Converted, convert
from app.extraction.fields import BANK_TYPES, SPECS, TEXT_ONLY_TYPES
from app.extraction.heuristics import CERTAIN, classify_text, prefill
from app.extraction.llm_extract import classify_with_llm, extract_with_llm
from app.extraction.xml_fiscal import NotFiscalXml, parse_fiscal_xml
from app.ingestion.bank.base import BankFileError
from app.ingestion.bank.service import parse_bank_file, store_statement
from app.ingestion.filetypes import CNAB, CSV, OFX, XML
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

    @property
    def extraction_source(self) -> str:
        return "+".join(self.sources) or "nenhuma"


async def analyze(
    session: AsyncSession | None,
    *,
    data: bytes,
    mime: str,
    filename: str,
    condominium_id: uuid.UUID,
    condominium_cnpj: str,
    today: date,
) -> Analysis:
    """Classify and extract a non-bank document. No database writes except ``llm_calls``."""
    raw: dict[str, Any] = {}
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
        sources.append(xml.layout)
        page_count = 1
    else:
        converted = await asyncio.to_thread(convert, data, mime, filename)
        page_count = converted.page_count
        classification = classify_text(converted.text, today)
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
            sources.append("ia")
        except LLMUnavailable as exc:
            logger.info("extraction without model reason=%s", type(exc).__name__)

    result = assess(doc_type, raw, source_conf, condominium_cnpj=condominium_cnpj, today=today)
    base.values = result.values
    base.confidence = {k: round(v, 3) for k, v in result.confidence.items()}
    base.sources = sources
    base.reasons = list(result.reasons)
    if base.reasons and notes:
        base.reasons.append(f"Observação da IA: {notes}")
    base.complete = not result.needs_review
    return base


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
    )
    doc.doc_type = analysis.doc_type.value
    doc.classification_source = analysis.classification_source
    doc.extraction_source = analysis.extraction_source
    doc.text_content = analysis.text
    doc.page_count = analysis.page_count
    doc.extracted = analysis.values
    doc.field_confidence = analysis.confidence
    doc.needs_review = not analysis.complete
    doc.review_reasons = [] if analysis.complete else analysis.reasons
    doc.extraction_status = (
        ExtractionStatus.DONE if analysis.complete else ExtractionStatus.NEEDS_REVIEW
    ).value


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
