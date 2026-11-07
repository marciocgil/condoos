"""Field specifications per document type, and value normalisation.

``document.extracted`` always stores normalised JSON values:
- cnpj/cpf: digits only · date: "AAAA-MM-DD" · month: "AAAA-MM" · money: "1234.56"
- text: trimmed string · list: list of strings · int: integer · index: IPCA/IGPM/INPC/FIXO/NENHUM
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.core.br import only_digits
from app.core.money import parse_brl
from app.db.enums import AdjustmentIndex, DocumentType

Kind = Literal["cnpj", "doc", "date", "month", "money", "text", "list", "int", "index"]

REVIEW_THRESHOLD = 0.9


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: Kind
    required: bool
    label: str  # pt-BR label for the correction screen


RETENCOES = ("iss", "inss", "ir", "pis", "cofins", "csll")

SPECS: dict[DocumentType, list[FieldSpec]] = {
    DocumentType.NFSE: [
        FieldSpec("numero", "text", True, "Número da nota"),
        FieldSpec("data_emissao", "date", True, "Data de emissão"),
        FieldSpec("competencia", "month", False, "Competência"),
        FieldSpec("cnpj_prestador", "cnpj", True, "CNPJ do prestador"),
        FieldSpec("razao_social_prestador", "text", True, "Razão social do prestador"),
        FieldSpec("cnpj_tomador", "cnpj", True, "CNPJ do tomador"),
        FieldSpec("valor_servicos", "money", True, "Valor dos serviços"),
        FieldSpec("valor_liquido", "money", True, "Valor líquido"),
        *[FieldSpec(f"retencao_{r}", "money", False, f"Retenção {r.upper()}") for r in RETENCOES],
        FieldSpec("discriminacao", "text", True, "Discriminação dos serviços"),
    ],
    DocumentType.NFE: [
        FieldSpec("chave_acesso", "text", False, "Chave de acesso"),
        FieldSpec("numero", "text", True, "Número da nota"),
        FieldSpec("data_emissao", "date", True, "Data de emissão"),
        FieldSpec("cnpj_emitente", "cnpj", True, "CNPJ do emitente"),
        FieldSpec("razao_social_emitente", "text", True, "Razão social do emitente"),
        FieldSpec("cnpj_destinatario", "cnpj", True, "CNPJ do destinatário"),
        FieldSpec("valor_total", "money", True, "Valor total"),
        FieldSpec("itens", "list", False, "Itens"),
    ],
    DocumentType.BOLETO: [
        FieldSpec("linha_digitavel", "text", False, "Linha digitável"),
        FieldSpec("valor", "money", True, "Valor"),
        FieldSpec("vencimento", "date", True, "Vencimento"),
        FieldSpec("cnpj_beneficiario", "cnpj", True, "CNPJ do beneficiário"),
        FieldSpec("nome_beneficiario", "text", False, "Beneficiário"),
        FieldSpec("cnpj_pagador", "cnpj", False, "CNPJ do pagador"),
        FieldSpec("numero_documento", "text", False, "Número do documento"),
    ],
    DocumentType.RECIBO: [
        FieldSpec("data", "date", True, "Data"),
        FieldSpec("valor", "money", True, "Valor"),
        FieldSpec("nome_recebedor", "text", True, "Quem recebeu"),
        FieldSpec("documento_recebedor", "doc", False, "CPF/CNPJ de quem recebeu"),
        FieldSpec("descricao", "text", True, "Referente a"),
    ],
    DocumentType.CONTRATO: [
        FieldSpec("cnpj_contratada", "cnpj", True, "CNPJ da contratada"),
        FieldSpec("razao_social_contratada", "text", True, "Razão social da contratada"),
        FieldSpec("cnpj_contratante", "cnpj", True, "CNPJ do contratante"),
        FieldSpec("objeto", "text", True, "Objeto"),
        FieldSpec("itens_escopo", "list", True, "Itens do escopo"),
        FieldSpec("valor_mensal", "money", True, "Valor mensal"),
        FieldSpec("indice_reajuste", "index", True, "Índice de reajuste"),
        FieldSpec("indice_reajuste_outro", "text", False, "Qual índice (se Outro)"),
        FieldSpec("mes_base_reajuste", "int", False, "Mês do reajuste (padrão: mês do início)"),
        FieldSpec("data_inicio", "date", True, "Início da vigência"),
        FieldSpec("data_assinatura", "date", False, "Data da assinatura"),
        FieldSpec("data_fim", "date", False, "Fim da vigência (em branco: indeterminado)"),
    ],
}

# Types whose content is kept as text only in this milestone (chat search in milestone 5).
TEXT_ONLY_TYPES = {
    DocumentType.CONVENCAO,
    DocumentType.ATA,
    DocumentType.APOLICE,
    DocumentType.BALANCETE,
    DocumentType.REGIMENTO,
    DocumentType.LAUDO,
    DocumentType.PLANO_MANUTENCAO,
}
BANK_TYPES = {DocumentType.EXTRATO, DocumentType.CNAB_RETORNO}


def specs_for(doc_type: DocumentType) -> list[FieldSpec]:
    return SPECS.get(doc_type, [])


def required_fields(doc_type: DocumentType) -> list[str]:
    return [f.name for f in specs_for(doc_type) if f.required]


class InvalidValue(ValueError):
    pass


_DATE_BR = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$")
_DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_MONTH = re.compile(r"^(?:(\d{4})-(\d{1,2})|(\d{1,2})/(\d{4}))$")


def normalize(kind: Kind, value: Any) -> Any:
    """Normalise a raw value (from XML, text or the model). Raises InvalidValue."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if kind in ("cnpj", "doc"):
        digits = only_digits(str(value))
        if kind == "cnpj" and len(digits) != 14:
            raise InvalidValue("CNPJ deve ter 14 dígitos")
        if kind == "doc" and len(digits) not in (11, 14):
            raise InvalidValue("CPF/CNPJ inválido")
        return digits
    if kind == "date":
        return _to_date(str(value)).isoformat()
    if kind == "month":
        m = _MONTH.match(str(value).strip())
        if not m:
            d = _to_date(str(value))
            return f"{d.year:04d}-{d.month:02d}"
        year, month = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        if not 1 <= int(month) <= 12:
            raise InvalidValue("mês inválido")
        return f"{int(year):04d}-{int(month):02d}"
    if kind == "money":
        if isinstance(value, int | float | Decimal):
            amount = Decimal(str(value))
        else:
            try:
                amount = parse_brl(str(value))
            except ValueError as exc:
                raise InvalidValue(str(exc)) from exc
        return str(amount.quantize(Decimal("0.01")))
    if kind == "int":
        try:
            return int(str(value).strip())
        except ValueError as exc:
            raise InvalidValue("número inteiro inválido") from exc
    if kind == "index":
        key = str(value).strip().upper().replace("-", "").replace(" ", "")
        aliases = {
            "IGPM": "IGPM",
            "IGP": "IGPM",
            "IPCA": "IPCA",
            "INPC": "INPC",
            "FIXO": "FIXO",
            "SEMREAJUSTE": "NENHUM",
            "NENHUM": "NENHUM",
            "OUTRO": "OUTRO",
        }
        # Any other index (IGP-DI, IPC-Fipe, collective agreement...) is OUTRO; the text is
        # kept in indice_reajuste_outro by the contract step (D68).
        return AdjustmentIndex(aliases.get(key, "OUTRO")).value
    if kind == "list":
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        return [p.strip() for p in re.split(r"[;\n]", str(value)) if p.strip()]
    return " ".join(str(value).split())


def _to_date(raw: str) -> date:
    raw = raw.strip()
    try:
        if m := _DATE_ISO.match(raw):
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m := _DATE_BR.match(raw):
            year = int(m.group(3))
            year += 2000 if year < 100 else 0
            return date(year, int(m.group(2)), int(m.group(1)))
    except ValueError as exc:
        raise InvalidValue("data inválida") from exc
    raise InvalidValue("data inválida")


def as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None
