"""Per-field confidence: min(source confidence, deterministic validations) (spec §5.3).

Source confidence is 1.0 for fiscal XML and check-digit-validated codes, the model's own
estimate for LLM output, and a fixed low value for text heuristics. Validations can only
lower it. Any required field below 0.9 sends the document to the exception queue.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.core.br import format_cnpj, is_valid_cnpj, is_valid_cpf
from app.db.enums import DocumentType
from app.extraction.fields import (
    REVIEW_THRESHOLD,
    InvalidValue,
    as_decimal,
    normalize,
    required_fields,
    specs_for,
)

# Fields that must be the condominium's CNPJ, and fields that must not be.
OWN_CNPJ = {"cnpj_tomador", "cnpj_destinatario", "cnpj_pagador", "cnpj_contratante"}
COUNTERPARTY_CNPJ = {"cnpj_prestador", "cnpj_emitente", "cnpj_beneficiario", "cnpj_contratada"}
ISSUE_DATES = {"data_emissao", "data"}


@dataclass
class Assessment:
    values: dict[str, Any]
    confidence: dict[str, float]
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return bool(self.reasons)


def _cap(conf: dict[str, float], name: str, value: float) -> None:
    conf[name] = min(conf.get(name, 0.0), value)


def assess(
    doc_type: DocumentType,
    raw_values: dict[str, Any],
    source_confidence: dict[str, float],
    *,
    condominium_cnpj: str,
    today: date,
) -> Assessment:
    labels = {s.name: s.label for s in specs_for(doc_type)}
    values: dict[str, Any] = {}
    conf: dict[str, float] = {}
    notes: dict[str, str] = {}

    for spec in specs_for(doc_type):
        raw = raw_values.get(spec.name)
        try:
            value = normalize(spec.kind, raw)
        except InvalidValue as exc:
            values[spec.name] = None
            conf[spec.name] = 0.0
            notes[spec.name] = f"{spec.label}: {exc}"
            continue
        values[spec.name] = value
        conf[spec.name] = float(source_confidence.get(spec.name, 0.0)) if value is not None else 0.0

        if value is None:
            continue
        if spec.kind == "cnpj" and not is_valid_cnpj(value):
            _cap(conf, spec.name, 0.1)
            notes[spec.name] = f"{spec.label} com dígito verificador inválido"
        if spec.kind == "doc" and not (is_valid_cnpj(value) or is_valid_cpf(value)):
            _cap(conf, spec.name, 0.1)
            notes[spec.name] = f"{spec.label} com dígito verificador inválido"
        if spec.name in OWN_CNPJ and value != condominium_cnpj:
            _cap(conf, spec.name, 0.3)
            notes[spec.name] = f"{spec.label} ({format_cnpj(value)}) não é o CNPJ do condomínio"
        if spec.name in COUNTERPARTY_CNPJ and value == condominium_cnpj:
            _cap(conf, spec.name, 0.3)
            notes[spec.name] = f"{spec.label} é o próprio condomínio"
        if spec.kind == "date":
            d = date.fromisoformat(value)
            if spec.name in ISSUE_DATES and not (
                today - timedelta(days=3 * 365) <= d <= today + timedelta(days=5)
            ):
                _cap(conf, spec.name, 0.3)
                notes[spec.name] = f"{spec.label} fora do período esperado"
            elif not (today - timedelta(days=10 * 365) <= d <= today + timedelta(days=10 * 365)):
                _cap(conf, spec.name, 0.3)
                notes[spec.name] = f"{spec.label} implausível"
        if spec.kind == "money":
            amount = Decimal(value)
            if amount < 0 or (spec.required and amount == 0):
                _cap(conf, spec.name, 0.3)
                notes[spec.name] = f"{spec.label} inválido"

    if doc_type == DocumentType.NFSE:
        _check_nfse_totals(values, conf, notes)
    if doc_type == DocumentType.CONTRATO:
        start, end = values.get("data_inicio"), values.get("data_fim")
        if start and end and end < start:
            for name in ("data_inicio", "data_fim"):
                _cap(conf, name, 0.3)
            notes["data_fim"] = "Fim da vigência antes do início"

    reasons: list[str] = []
    for name in required_fields(doc_type):
        if values.get(name) is None:
            reasons.append(notes.get(name) or f"{labels[name]}: não encontrado")
        elif conf.get(name, 0.0) < REVIEW_THRESHOLD:
            reasons.append(notes.get(name) or f"{labels[name]}: baixa confiança")
    # Problems on optional fields that were filled are also shown (but alone do not block).
    for name, note in notes.items():
        if (
            name not in required_fields(doc_type)
            and values.get(name) is not None
            and note not in reasons
            and reasons
        ):
            reasons.append(note)
    if not reasons:
        # Automatic document: keep only trusted values. A low-confidence optional field is
        # dropped rather than stored as if it were reliable. (In a document that goes to the
        # queue, it stays as a suggestion for the analyst.)
        for spec in specs_for(doc_type):
            if not spec.required and conf.get(spec.name, 0.0) < REVIEW_THRESHOLD:
                values[spec.name] = None
                conf[spec.name] = 0.0
    return Assessment(values=values, confidence=conf, reasons=reasons)


def _check_nfse_totals(
    values: dict[str, Any], conf: dict[str, float], notes: dict[str, str]
) -> None:
    gross = as_decimal(values.get("valor_servicos"))
    net = as_decimal(values.get("valor_liquido"))
    if gross is None or net is None:
        return
    withheld = sum(
        (as_decimal(values.get(f"retencao_{r}")) or Decimal("0"))
        for r in ("iss", "inss", "ir", "pis", "cofins", "csll")
    )
    if abs(gross - withheld - net) > Decimal("0.02"):
        for name in ("valor_servicos", "valor_liquido"):
            _cap(conf, name, 0.6)
        notes["valor_liquido"] = (
            "Valor líquido não confere com valor dos serviços menos as retenções"
        )
    if net > gross:
        _cap(conf, "valor_liquido", 0.3)
        notes["valor_liquido"] = "Valor líquido maior que o valor dos serviços"
