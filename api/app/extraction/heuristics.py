"""Deterministic reading of document text: type classification and field pre-fill.

Classification by strong signals (spec §5.2): 44-digit access key, valid linha digitável,
CNAB header (handled earlier by file type) and fixed titles. Field pre-fill from free text
uses labels and patterns; it is a starting point, so its confidence stays below the review
threshold unless a deterministic check confirms it (valid boleto code, single valid CNPJ).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.br import is_valid_cnpj, only_digits
from app.db.enums import DocumentType
from app.extraction import boleto

TEXT_CONFIDENCE = 0.75  # value read from free text by a label: needs a human look
CHECKED_CONFIDENCE = 0.95  # value confirmed by a deterministic check
CERTAIN = 1.0  # value from check-digit-validated codes or fiscal XML


def fold(text: str) -> str:
    """Lowercase without accents, single spaces."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


_CHAVE = re.compile(r"(?<!\d)(\d{4}(?:\s?\d{4}){10})(?!\d)")
# A CNPJ is accepted when formatted (12.345.678/0001-90) or right after a "CNPJ" label.
# Bare 14-digit runs are not enough: boleto codes contain such runs, and 1 in 100 of them
# passes the check digits by chance.
_CNPJ_FORMATTED = re.compile(r"(?<!\d)(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})(?!\d)")
_CNPJ_LABELED = re.compile(r"CNPJ[^\d\n]{0,25}(\d{14})(?!\d)", re.I)
_MONEY = r"R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})"
_DATE = r"(\d{2}/\d{2}/\d{4})"


@dataclass
class Classification:
    doc_type: DocumentType | None
    confidence: float
    signals: list[str] = field(default_factory=list)


def classify_text(text: str, reference: date) -> Classification:
    t = fold(text)
    if not t:
        return Classification(None, 0.0)
    signals: list[str] = []
    if "danfe" in t or ("nota fiscal eletronica" in t and _CHAVE.search(text)):
        signals.append("DANFE/chave de acesso")
        return Classification(DocumentType.NFE, 0.95, signals)
    if any(
        k in t
        for k in (
            "nfs-e",
            "nota fiscal de servico",
            "nota fiscal eletronica de servico",
            "nota fiscal de servicos",
        )
    ):
        signals.append("título de NFS-e")
        return Classification(DocumentType.NFSE, 0.95, signals)
    if boleto.find_in_text(text, reference) is not None:
        signals.append("linha digitável válida")
        return Classification(DocumentType.BOLETO, 0.97, signals)
    if t.startswith("recibo") or " recibo " in t[:200] or "recebi de" in t or "recebemos de" in t:
        signals.append("título de recibo")
        return Classification(DocumentType.RECIBO, 0.9, signals)
    if "contrato de prestacao de servico" in t or ("contratante" in t and "contratada" in t):
        signals.append("contrato de prestação de serviços")
        return Classification(DocumentType.CONTRATO, 0.92, signals)
    if "convencao de condominio" in t or "convencao do condominio" in t:
        signals.append("convenção")
        return Classification(DocumentType.CONVENCAO, 0.92, signals)
    if "ata da assembleia" in t or "ata de assembleia" in t:
        signals.append("ata de assembleia")
        return Classification(DocumentType.ATA, 0.92, signals)
    return Classification(None, 0.0)


def valid_cnpjs(text: str) -> list[str]:
    seen: list[str] = []
    matches = sorted(
        [*_CNPJ_FORMATTED.finditer(text), *_CNPJ_LABELED.finditer(text)], key=lambda m: m.start()
    )
    for m in matches:
        digits = only_digits(m.group(1))
        if len(digits) == 14 and is_valid_cnpj(digits) and digits not in seen:
            seen.append(digits)
    return seen


def _fold_same_length(text: str) -> str:
    """Lowercase, accents removed, one output char per input char (positions preserved)."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
        out.append(base[0].lower() if base else " ")
    return "".join(out)


def _after_label(text: str, labels: list[str], pattern: str, size: int = 160) -> str | None:
    """Value matching ``pattern`` right after the first label found (labels in folded form)."""
    folded = _fold_same_length(text)
    for label in labels:
        idx = folded.find(label)
        while idx >= 0:
            window = text[idx + len(label) : idx + len(label) + size]
            m = re.match(r"[\s:.-]*" + pattern, window)
            if m:
                return m.group(1)
            idx = folded.find(label, idx + 1)
    return None


@dataclass
class Prefill:
    values: dict[str, Any] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)

    def put(self, name: str, value: Any, conf: float) -> None:
        if value is None or value == "" or value == []:
            return
        if conf >= self.confidence.get(name, 0.0):
            self.values[name] = value
            self.confidence[name] = conf


def _other_cnpj(text: str, condo_cnpj: str, pf: Prefill, name: str) -> None:
    others = [c for c in valid_cnpjs(text) if c != condo_cnpj]
    if len(others) == 1:
        pf.put(name, others[0], CHECKED_CONFIDENCE)
    elif others:
        pf.put(name, others[0], 0.5)


def prefill(doc_type: DocumentType, text: str, condo_cnpj: str, reference: date) -> Prefill:
    pf = Prefill()
    if not text.strip():
        return pf
    has_condo = condo_cnpj in valid_cnpjs(text)

    if doc_type == DocumentType.BOLETO:
        code = boleto.find_in_text(text, reference)
        if code is not None:
            pf.put("linha_digitavel", code.digits, CERTAIN)
            if code.amount is not None:
                pf.put("valor", str(code.amount), CERTAIN)
            if code.due_date is not None:
                pf.put("vencimento", code.due_date.isoformat(), CERTAIN)
        _other_cnpj(text, condo_cnpj, pf, "cnpj_beneficiario")
        if has_condo:
            pf.put("cnpj_pagador", condo_cnpj, CHECKED_CONFIDENCE)
        name = _after_label(
            text, ["beneficiario", "cedente"], r"(?:Benefici[aá]rio|Cedente)\s*:?\s*([^\n\r]{3,80})"
        )
        pf.put("nome_beneficiario", name and name.strip(" :"), TEXT_CONFIDENCE)
        pf.put("vencimento", _after_label(text, ["vencimento"], _DATE), TEXT_CONFIDENCE)
        pf.put(
            "valor",
            _after_label(text, ["valor do documento", "valor cobrado", "valor"], _MONEY),
            TEXT_CONFIDENCE,
        )
        pf.put(
            "numero_documento",
            _after_label(
                text,
                ["numero do documento", "no do documento", "n do documento", "nosso numero"],
                r"(\d[\w/-]{0,20})",
            ),
            TEXT_CONFIDENCE,
        )

    elif doc_type == DocumentType.NFSE:
        _other_cnpj(text, condo_cnpj, pf, "cnpj_prestador")
        if has_condo:
            pf.put("cnpj_tomador", condo_cnpj, CHECKED_CONFIDENCE)
        pf.put(
            "numero",
            _after_label(
                text, ["numero da nota", "numero da nfs-e", "numero:", "nº da nota"], r"(\d{1,15})"
            ),
            TEXT_CONFIDENCE,
        )
        pf.put(
            "data_emissao",
            _after_label(text, ["data e hora de emissao", "data de emissao", "emissao"], _DATE),
            TEXT_CONFIDENCE,
        )
        pf.put(
            "competencia", _after_label(text, ["competencia"], r"(\d{2}/\d{4})"), TEXT_CONFIDENCE
        )
        pf.put(
            "valor_servicos",
            _after_label(
                text, ["valor total dos servicos", "valor dos servicos", "valor do servico"], _MONEY
            ),
            TEXT_CONFIDENCE,
        )
        pf.put("valor_liquido", _after_label(text, ["valor liquido"], _MONEY), TEXT_CONFIDENCE)
        for key, labels in {
            "retencao_iss": ["iss retido", "valor do iss retido"],
            "retencao_inss": ["inss"],
            "retencao_ir": ["irrf", "ir retido", "imposto de renda"],
            "retencao_pis": ["pis"],
            "retencao_cofins": ["cofins"],
            "retencao_csll": ["csll"],
        }.items():
            pf.put(key, _after_label(text, labels, _MONEY), TEXT_CONFIDENCE)
        desc = _after_label(
            text,
            ["discriminacao dos servicos", "discriminacao", "descricao do servico"],
            r":?\s*([^\n\r]{5,300})",
        )
        pf.put("discriminacao", desc and desc.strip(" :"), TEXT_CONFIDENCE)
        name = _after_label(
            text,
            ["razao social", "prestador de servicos", "prestador"],
            r"(?:Raz[aã]o Social|Nome)\s*:?\s*([^\n\r]{3,120})",
        )
        pf.put("razao_social_prestador", name and name.strip(" :"), TEXT_CONFIDENCE)

    elif doc_type == DocumentType.NFE:
        chave = _CHAVE.search(text)
        if chave:
            pf.put("chave_acesso", only_digits(chave.group(1)), TEXT_CONFIDENCE)
        _other_cnpj(text, condo_cnpj, pf, "cnpj_emitente")
        if has_condo:
            pf.put("cnpj_destinatario", condo_cnpj, CHECKED_CONFIDENCE)
        pf.put("numero", _after_label(text, ["nº", "numero"], r"(\d{1,9})"), TEXT_CONFIDENCE)
        pf.put(
            "data_emissao",
            _after_label(text, ["data da emissao", "data de emissao"], _DATE),
            TEXT_CONFIDENCE,
        )
        pf.put("valor_total", _after_label(text, ["valor total da nota"], _MONEY), TEXT_CONFIDENCE)

    elif doc_type == DocumentType.RECIBO:
        pf.put(
            "valor",
            _after_label(text, ["valor", "quantia", "importancia"], _MONEY),
            TEXT_CONFIDENCE,
        )
        pf.put("data", _after_label(text, ["data", ","], _DATE), TEXT_CONFIDENCE)
        desc = _after_label(
            text,
            ["referente a", "referente ao", "referente"],
            r"(?:[Rr]eferente\s*(?:a|ao|à)?)\s*:?\s*([^\n\r]{3,200})",
        )
        pf.put("descricao", desc and desc.strip(" :."), TEXT_CONFIDENCE)
        docs = [c for c in valid_cnpjs(text) if c != condo_cnpj]
        if docs:
            pf.put("documento_recebedor", docs[0], TEXT_CONFIDENCE)

    elif doc_type == DocumentType.CONTRATO:
        _other_cnpj(text, condo_cnpj, pf, "cnpj_contratada")
        if has_condo:
            pf.put("cnpj_contratante", condo_cnpj, CHECKED_CONFIDENCE)
        pf.put(
            "valor_mensal",
            _after_label(text, ["valor mensal", "mensalidade", "pagara mensalmente"], _MONEY),
            TEXT_CONFIDENCE,
        )
        for idx in ("IPCA", "IGP-M", "INPC"):
            if idx.lower() in fold(text):
                pf.put("indice_reajuste", idx, TEXT_CONFIDENCE)
                break
    return pf
