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
# OCR and typing variants: spaces around separators, missing dots, "." for "-" (check digits
# still have to match, so noise does not become a CNPJ).
_CNPJ_LOOSE = re.compile(
    r"(?<![\d.])(\d{2}\s?[.,]?\s?\d{3}\s?[.,]?\s?\d{3}\s?/\s?\d{4}\s?[-–.]?\s?\d{2})(?![\d])"
)
_LONG_DATE = re.compile(
    r"(\d{1,2})\s*(?:º|o)?\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})",
    re.I,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "janeiro",
            "fevereiro",
            "marco",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ],
        start=1,
    )
}
_CNPJ_LABELED = re.compile(r"CNPJ[^\d\n]{0,25}(\d{14})(?!\d)", re.I)
_MONEY = r"R?\$?\s*(\d{1,3}(?:\.\d{3})*,\d{2})"
_DATE = r"(\d{2}/\d{2}/\d{4})"


@dataclass
class Classification:
    doc_type: DocumentType | None
    confidence: float
    signals: list[str] = field(default_factory=list)
    # Set when the document must not enter the CondoOS at all (D120, B5): the reason.
    refused: str | None = None


REFUSED_DEBTORS = (
    "Relação de devedores tem nomes e unidades de moradores e não entra no piloto. "
    "O arquivo foi apagado; se precisar, envie só o total da inadimplência."
)


_UNIT_ROW = re.compile(r"\b(?:apto|apartamento|unidade|unid|casa|sala|lote)\.?\s*n?o?\s*\d{1,4}\b")


def _lists_units(folded: str) -> bool:
    """A list of residents' units (one row per unit): at least five unit references."""
    return len(_UNIT_ROW.findall(folded)) >= 5


def classify_text(text: str, reference: date) -> Classification:
    t = fold(text)
    if not t:
        return Classification(None, 0.0)
    signals: list[str] = []
    head = t[:1200]  # titles live at the top; payment clauses mention "nota fiscal" too
    clauses = t.count("clausula")
    if (
        ("contrato" in head or "termo aditivo" in head or "aditivo" in head)
        and "contratante" in t
        and "contratada" in t
    ) or (clauses >= 3 and "contratante" in t):
        signals.append("contrato: partes e cláusulas")
        return Classification(DocumentType.CONTRATO, 0.93, signals)
    if "danfe" in t or ("nota fiscal eletronica" in t and _CHAVE.search(text)):
        signals.append("DANFE/chave de acesso")
        return Classification(DocumentType.NFE, 0.95, signals)
    if any(
        k in head
        for k in (
            "nfs-e",
            "nota fiscal de servico",
            "nota fiscal eletronica de servico",
            "nota fiscal de servicos",
        )
    ):
        signals.append("título de NFS-e")
        return Classification(DocumentType.NFSE, 0.95, signals)
    # D120: checked before the boleto, because a payment receipt and a tax slip also carry a
    # bar code. The debtor list is refused: it holds residents' names and units (B5).
    top = t[:400]
    debtor_title = any(
        k in top
        for k in ("relacao de devedores", "relacao de inadimplentes", "lista de inadimplentes")
    )
    if debtor_title or ("inadimpl" in top and "balancete" not in top and _lists_units(t)):
        signals.append("relação de devedores")
        return Classification(None, 0.0, signals, refused=REFUSED_DEBTORS)
    if any(
        k in top
        for k in (
            "comprovante de pagamento",
            "comprovante de transferencia",
            "comprovante de pix",
            "comprovante pix",
            "comprovante de transacao",
        )
    ) or ("comprovante" in top and "autenticacao" in t):
        signals.append("título de comprovante de pagamento")
        return Classification(DocumentType.COMPROVANTE, 0.92, signals)
    if any(
        k in top
        for k in (
            "documento de arrecadacao de receitas federais",
            "darf",
            "guia da previdencia social",
            "dctfweb",
            "guia do fgts",
            "guia de recolhimento do fgts",
            "fgts digital",
            "guia de recolhimento do iss",
            "documento de arrecadacao municipal",
        )
    ):
        signals.append("título de guia de tributo")
        return Classification(DocumentType.GUIA_TRIBUTO, 0.92, signals)
    if boleto.find_in_text(text, reference) is not None:
        signals.append("linha digitável válida")
        return Classification(DocumentType.BOLETO, 0.97, signals)
    if t.startswith("recibo") or " recibo " in t[:200] or "recebi de" in t or "recebemos de" in t:
        signals.append("título de recibo")
        return Classification(DocumentType.RECIBO, 0.9, signals)
    # Governing and technical documents by their title (LB-020): checked before the loose
    # "contratante/contratada" rule, since a maintenance plan or a report may name the parties.
    top = t[:300]
    if any(
        k in top
        for k in (
            "relatorio da administradora",
            "relatorio de gestao",
            "relatorio mensal de gestao",
            "relatorio da administracao",
        )
    ):
        signals.append("título de relatório da administradora")
        return Classification(DocumentType.RELATORIO_ADM, 0.9, signals)
    if any(
        k in top
        for k in (
            "informe de rendimentos",
            "extrato de rendimento",
            "extrato de investimento",
            "extrato de aplicacao",
        )
    ):
        signals.append("título de extrato de rendimento")
        return Classification(DocumentType.EXTRATO_RENDIMENTO, 0.9, signals)
    if "regimento interno" in top:
        signals.append("título de regimento interno")
        return Classification(DocumentType.REGIMENTO, 0.92, signals)
    if "apolice" in top and ("segurado" in t or "seguradora" in t):
        signals.append("apólice com seguradora/segurado")
        return Classification(DocumentType.APOLICE, 0.92, signals)
    if "balancete" in top or "demonstrativo de receitas e despesas" in top:
        signals.append("título de balancete")
        return Classification(DocumentType.BALANCETE, 0.9, signals)
    if "plano de manutencao" in top or "pmoc" in top:
        signals.append("título de plano de manutenção")
        return Classification(DocumentType.PLANO_MANUTENCAO, 0.9, signals)
    if "laudo" in top or "relatorio de vistoria" in top or "relatorio de inspecao" in top:
        signals.append("título de laudo ou vistoria")
        return Classification(DocumentType.LAUDO, 0.9, signals)
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
        [
            *_CNPJ_FORMATTED.finditer(text),
            *_CNPJ_LABELED.finditer(text),
            *_CNPJ_LOOSE.finditer(text),
        ],
        key=lambda m: m.start(),
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


def _cnpj_after_party(text: str, condo_cnpj: str, party: str) -> str | None:
    """The CNPJ in the description of a party ("CONTRATADA: X, inscrita no CNPJ sob o nº ...").
    Several CNPJs in a contract (witnesses, guarantors) make "the other one" ambiguous."""
    folded = _fold_same_length(text)
    for m in re.finditer(party, folded):
        window = text[m.start() : m.start() + 400]
        for c in valid_cnpjs(window):
            if c != condo_cnpj:
                return c
    return None


def signature_date(text: str) -> str | None:
    """The last long-form date ("São Paulo, 10 de março de 2025"): usually the signature."""
    found = None
    for m in _LONG_DATE.finditer(text):
        month = _MONTHS.get(fold(m.group(2)))
        try:
            found = date(int(m.group(3)), month or 0, int(m.group(1))).isoformat()
        except ValueError:
            continue
    return found


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
        contracted = _cnpj_after_party(text, condo_cnpj, "contratada")
        if contracted:
            pf.put("cnpj_contratada", contracted, CHECKED_CONFIDENCE)
        else:
            _other_cnpj(text, condo_cnpj, pf, "cnpj_contratada")
        signed = signature_date(text)
        if signed:
            pf.put("data_assinatura", signed, TEXT_CONFIDENCE)
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
