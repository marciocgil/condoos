"""Where each extracted value came from (CB-030, ADR-P04; D85).

For every field: the source ("xml", "texto", "ia" or "pessoa"), and, when the document has
text, the page and an excerpt around the value. A value the text does not show keeps only its
source (the excerpt is never invented); a field without value is "nao_disponivel".
"""

import re
from datetime import date
from decimal import Decimal
from typing import Any

from app.extraction.fields import SPECS, Kind

NOT_AVAILABLE = "nao_disponivel"


def _money_forms(value: str) -> list[str]:
    amount = Decimal(value)
    whole, cents = f"{amount:,.2f}".split(".")
    br = f"{whole.replace(',', '.')},{cents}"
    return [br, br.replace(".", ""), f"{amount:.2f}"]


def _cnpj_forms(digits: str) -> list[str]:
    if len(digits) == 14:
        return [f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}", digits]
    if len(digits) == 11:
        return [f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}", digits]
    return [digits]


def forms(kind: Kind, value: Any) -> list[str]:
    """Ways a normalised value may be written in a Brazilian document."""
    if value in (None, "", []):
        return []
    try:
        if kind in ("cnpj", "doc"):
            return _cnpj_forms(str(value))
        if kind == "money":
            return _money_forms(str(value))
        if kind == "date":
            d = date.fromisoformat(str(value))
            return [f"{d:%d/%m/%Y}", f"{d:%d.%m.%Y}", d.isoformat()]
        if kind == "month":
            year, month = str(value).split("-")
            return [f"{month}/{year}", f"{month}/{year[2:]}"]
    except (ValueError, ArithmeticError):
        return []
    if kind == "list":
        return [str(value[0])] if isinstance(value, list) and value else []
    text = str(value).strip()
    return [text] if len(text) >= 3 else []


def locate(text: str, kind: Kind, value: Any, margin: int = 60) -> dict[str, Any] | None:
    lowered = text.lower()
    for form in forms(kind, value):
        pos = lowered.find(form.lower())
        if pos < 0:
            continue
        end = pos + len(form)
        a, b = max(0, pos - margin), min(len(text), end + margin)
        excerpt = re.sub(r"\s+", " ", text[a:b]).strip()
        return {
            "page": text.count("\f", 0, pos) + 1,
            "excerpt": ("…" if a else "") + excerpt + ("…" if b < len(text) else ""),
        }
    return None


INFERRED = "inferido"


def build(
    doc_type: Any,
    values: dict[str, Any],
    sources: dict[str, str],
    text: str | None,
    inferred: dict[str, str] | None = None,
) -> dict[str, Any]:
    """``inferred``: fields a rule filled (field -> the rule, LB-036): their source is
    "inferido", with the rule, and never an excerpt — the text does not say it."""
    out: dict[str, Any] = {}
    for spec in SPECS.get(doc_type, []):
        value = values.get(spec.name)
        if value in (None, "", []):
            out[spec.name] = {"source": NOT_AVAILABLE}
            continue
        if inferred and spec.name in inferred:
            out[spec.name] = {"source": INFERRED, "rule": inferred[spec.name]}
            continue
        item: dict[str, Any] = {"source": sources.get(spec.name, "texto")}
        if text and item["source"] != "xml":
            found = locate(text, spec.kind, value)
            if found:
                item.update(found)
        out[spec.name] = item
    return out


def confirmed(
    previous: dict[str, Any],
    old_values: dict[str, Any],
    values: dict[str, Any],
    user_id: str,
    at: str,
) -> dict[str, Any]:
    """After a person's review every field is "confirmado" by that person. The page and
    excerpt stay when the person kept the extracted value."""
    out: dict[str, Any] = {}
    for name, value in values.items():
        before = previous.get(name) or {}
        item: dict[str, Any] = {
            "source": "pessoa" if value not in (None, "", []) else NOT_AVAILABLE,
            "status": "confirmado",
            "confirmed_by": user_id,
            "confirmed_at": at,
            "extracted_from": before.get("source"),
        }
        if before.get("excerpt") and old_values.get(name) == value:
            item["page"] = before.get("page")
            item["excerpt"] = before["excerpt"]
        out[name] = item
    return out
