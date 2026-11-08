"""Classification and field extraction with Claude (structured output, per-field confidence).

What is sent to the API is the minimum needed (spec §12): the document text when it has a
usable text layer; the file itself (PDF or image) only when there is no usable text.
"""

import uuid
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.enums import DocumentType
from app.extraction.convert import Converted
from app.extraction.fields import specs_for
from app.ingestion.filetypes import IMAGE_TYPES, PDF
from app.llm.client import ImageInput, LLMRequest, PdfInput, call_structured
from app.llm.prompts import load_prompt

PROMPT_FILES = {
    DocumentType.NFSE: "extract_nfse",
    DocumentType.NFE: "extract_nfe",
    DocumentType.BOLETO: "extract_boleto",
    DocumentType.RECIBO: "extract_recibo",
    DocumentType.CONTRATO: "extract_contrato",
}


class TextField(BaseModel):
    value: str | None
    confidence: float = Field(ge=0, le=1)


class ListField(BaseModel):
    value: list[str]
    confidence: float = Field(ge=0, le=1)


ClassifiableType = Literal[
    "nfse",
    "nfe",
    "boleto",
    "recibo",
    "extrato",
    "contrato",
    "convencao",
    "ata",
    "regimento",
    "apolice",
    "balancete",
    "laudo",
    "plano_manutencao",
    "outro",
]


class ClassificationOut(BaseModel):
    doc_type: ClassifiableType
    confidence: float = Field(ge=0, le=1)
    motivo: str


@lru_cache
def output_model(doc_type: DocumentType) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for spec in specs_for(doc_type):
        fields[spec.name] = (ListField if spec.kind == "list" else TextField, ...)
    fields["observacoes"] = (str, ...)
    return create_model(f"Extracao_{doc_type.value}", **fields)


def _inputs(
    converted: Converted, data: bytes, mime: str
) -> tuple[str, list[ImageInput | PdfInput]]:
    limit = get_settings().llm_max_text_chars
    if converted.quality == "good" and len(converted.text) <= limit:
        return f"Texto do documento:\n<documento>\n{converted.text}\n</documento>", []
    if mime == PDF:
        return "O documento está em anexo (PDF).", [PdfInput(data)]
    if mime in IMAGE_TYPES:
        return "O documento está em anexo (foto ou imagem).", [ImageInput(mime, data)]
    return f"Texto do documento:\n<documento>\n{converted.text[:limit]}\n</documento>", []


async def classify_with_llm(
    session: AsyncSession | None,
    *,
    converted: Converted,
    data: bytes,
    mime: str,
    condominium_id: uuid.UUID | None,
) -> ClassificationOut:
    user_text, attachments = _inputs(converted, data, mime)
    result = await call_structured(
        session,
        LLMRequest(
            purpose="document.classify",
            role="fast",
            system=load_prompt("classify_document"),
            user_text=user_text,
            attachments=attachments,
            output_model=ClassificationOut,
            condominium_id=condominium_id,
            max_tokens=2000,
            effort="low",
        ),
    )
    return result.output


async def extract_with_llm(
    session: AsyncSession | None,
    *,
    doc_type: DocumentType,
    converted: Converted,
    data: bytes,
    mime: str,
    condominium_id: uuid.UUID | None,
) -> tuple[dict[str, Any], dict[str, float], str]:
    """Returns (raw values, model confidence per field, model notes)."""
    model = output_model(doc_type)
    user_text, attachments = _inputs(converted, data, mime)
    system = load_prompt("extract_common") + "\n\n" + load_prompt(PROMPT_FILES[doc_type])
    result = await call_structured(
        session,
        LLMRequest(
            purpose=f"document.extract.{doc_type.value}",
            role="extraction",
            system=system,
            user_text=user_text,
            attachments=attachments,
            output_model=model,
            condominium_id=condominium_id,
            max_tokens=8000,
            effort="medium",
        ),
    )
    out = result.output
    values: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    for spec in specs_for(doc_type):
        item = getattr(out, spec.name)
        values[spec.name] = item.value
        confidence[spec.name] = float(item.confidence)
    return values, confidence, str(getattr(out, "observacoes", "") or "")
