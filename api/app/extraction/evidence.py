"""Confidence by evidence (D120, A1) and CNPJ search in the text (A3).

A field read below 0.9 is raised to "confirmed" (0.95) only with a proof checked by code:
- the value is written in the document text (structured kinds, or a long enough text);
- the legal name matches the Receita record for the counterparty CNPJ (both fields);
- the condominium CNPJ field is exactly the registered CNPJ.
Without proof the model's confidence stands. A field a validation already flagged (a note)
is never raised, and a value the model itself doubted (below ``WRITTEN_FLOOR``) needs more
than being written somewhere: several amounts or dates in one contract are common.
"""

import re
import unicodedata
from typing import Any

from app.core.br import is_valid_cnpj, only_digits
from app.extraction.fields import Kind
from app.extraction.provenance import forms
from app.matching.text import normalize_name

CONFIRMED = 0.95
# The model's minimum confidence for "written in the text" to count as proof.
WRITTEN_FLOOR = 0.6
MIN_TEXT_LEN = 8
MIN_ITEM_LEN = 4

WRITTEN = "escrito no documento"
RECEITA = "razão social confere com a Receita"
OWN = "CNPJ do condomínio confere com o cadastro"

# Counterparty CNPJ and legal-name fields per document type.
NAME_PAIRS = {
    "cnpj_contratada": "razao_social_contratada",
    "cnpj_prestador": "razao_social_prestador",
    "cnpj_emitente": "razao_social_emitente",
    "cnpj_beneficiario": "nome_beneficiario",
}

# How a tracked index is written; FIXO/NENHUM/OUTRO are never proven by the text alone.
INDEX_NAMES = {"IPCA": ("IPCA",), "IGPM": ("IGP-M", "IGPM"), "INPC": ("INPC",)}
_LEGAL_SUFFIXES = {"ltda", "me", "epp", "eireli", "sa", "s", "a", "cia", "companhia"}
_CNPJ_IN_TEXT = re.compile(r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(text.split())


def same_legal_name(a: str | None, b: str | None) -> bool:
    """Same company name, ignoring accents, punctuation and the legal suffix (LTDA, S.A.)."""
    if not a or not b:
        return False
    wa = [w for w in normalize_name(a).split() if w not in _LEGAL_SUFFIXES]
    wb = [w for w in normalize_name(b).split() if w not in _LEGAL_SUFFIXES]
    return bool(wa) and wa == wb


def written(plain_text: str, kind: Kind, value: Any) -> bool:
    """``plain_text`` already passed through ``_plain``."""
    if kind == "int":
        return False  # a month number alone proves little
    if kind == "index":
        return any(_plain(n) in plain_text for n in INDEX_NAMES.get(str(value), ()))
    if kind == "list":
        items = [str(v) for v in value] if isinstance(value, list) else []
        # Scope items are short ("poda", "limpeza"): every one must be written.
        return bool(items) and all(
            len(i.strip()) >= MIN_ITEM_LEN and _plain(i) in plain_text for i in items
        )
    candidates = forms(kind, value)
    if kind == "text":
        candidates = [c for c in candidates if len(c) >= MIN_TEXT_LEN]
    return any(_plain(c) in plain_text for c in candidates)


def plain(text: str | None) -> str:
    return _plain(text) if text else ""


def apply(
    *,
    values: dict[str, Any],
    conf: dict[str, float],
    notes: dict[str, str],
    kinds: dict[str, Kind],
    text: str | None,
    registry_names: dict[str, str],
    condominium_cnpj: str,
    own_fields: set[str],
    inferred: dict[str, str],
) -> dict[str, str]:
    """Raise fields with proof to ``CONFIRMED``. Returns field -> the proof used."""
    proofs: dict[str, str] = {}

    def raise_(name: str, proof: str, floor: float = 0.0) -> None:
        if name in notes or name in inferred or values.get(name) is None:
            return
        current = conf.get(name, 0.0)
        if current >= CONFIRMED or current < floor:
            return
        conf[name] = CONFIRMED
        proofs.setdefault(name, proof)

    for name in own_fields:
        if values.get(name) == condominium_cnpj:
            raise_(name, OWN)
    for cnpj_field, name_field in NAME_PAIRS.items():
        cnpj = values.get(cnpj_field)
        if cnpj and same_legal_name(registry_names.get(cnpj), values.get(name_field)):
            raise_(cnpj_field, RECEITA)
            raise_(name_field, RECEITA)
    body = plain(text)
    if body:
        for name, kind in kinds.items():
            if values.get(name) is not None and written(body, kind, values[name]):
                raise_(name, WRITTEN, WRITTEN_FLOOR)
    return proofs


def cnpjs_in_text(text: str | None) -> list[str]:
    """Valid CNPJs written in the text, in order of appearance, without repeats."""
    if not text:
        return []
    seen: list[str] = []
    for match in _CNPJ_IN_TEXT.finditer(text):
        digits = only_digits(match.group(1))
        if len(digits) == 14 and is_valid_cnpj(digits) and digits not in seen:
            seen.append(digits)
    return seen


def lone_counterparty(text: str | None, exclude: set[str]) -> str | None:
    """The only valid CNPJ in the text other than the excluded ones (condominium, management
    company, the other party), or None when there are zero or several."""
    rest = [c for c in cnpjs_in_text(text) if c not in exclude]
    return rest[0] if len(rest) == 1 else None
