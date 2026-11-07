"""Termination terms of a contract read from its text by rule (CB-060, D85): notice period,
automatic renewal and termination penalty, each with the excerpt it came from. Nothing is
guessed: a term the text does not state stays empty ("não disponível").

Backfill for contracts that already have a source document:
``python -m app.extraction.clauses`` (database owner role).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

WORDS = {
    "trinta": 30,
    "sessenta": 60,
    "noventa": 90,
    "quinze": 15,
    "dez": 10,
    "cento e vinte": 120,
    "cento e oitenta": 180,
}


def _fold(text: str) -> str:
    # Same length as the input, so positions map back to the original text.
    return "".join(
        unicodedata.normalize("NFKD", ch)[0] if ch.strip() else " " for ch in text
    ).lower()


def _excerpt(text: str, start: int, end: int, margin: int = 80) -> str:
    a = max(0, start - margin)
    b = min(len(text), end + margin)
    piece = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("…" if a > 0 else "") + piece + ("…" if b < len(text) else "")


@dataclass
class Clauses:
    notice_days: int | None = None
    auto_renewal: bool | None = None
    termination_penalty: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


NOTICE = re.compile(
    r"aviso previo (?:minimo )?(?:por escrito )?(?:de|com) (?:no minimo )?"
    r"(?P<num>\d{1,3})?\s*(?:\((?P<word1>[a-z ]+)\)\s*)?(?P<word2>[a-z ]+?)?\s*dias"
)
ANTECEDENCIA = re.compile(r"(?P<num>\d{1,3})\s*(?:\([a-z ]+\)\s*)?dias de antecedencia")
NO_RENEWAL = re.compile(r"(?:nao sera|nao e|vedada a) (?:renovad[oa]|prorrogad[oa]|renovacao)")
RENEWAL = re.compile(
    r"(?:renovad[oa]|prorrogad[oa]) automaticamente|renovacao automatica|prorrogacao automatica"
)
PENALTY = re.compile(
    r"multa(?: rescisoria)?(?: de| equivalente a| correspondente a) "
    r"(?P<what>.{3,120}?)(?=\.\s|\.$|;|\n|$)"
)


def read_clauses(text: str | None) -> Clauses:
    out = Clauses()
    if not text:
        return out
    folded = _fold(text)
    m = NOTICE.search(folded)
    if m is not None:
        days = int(m["num"]) if m["num"] else WORDS.get((m["word1"] or m["word2"] or "").strip())
        if days:
            out.notice_days = days
            out.evidence["notice_days"] = {"excerpt": _excerpt(text, m.start(), m.end())}
    if out.notice_days is None:
        m = ANTECEDENCIA.search(folded)
        if m is not None and "resc" in folded[max(0, m.start() - 300) : m.end() + 300]:
            out.notice_days = int(m["num"])
            out.evidence["notice_days"] = {"excerpt": _excerpt(text, m.start(), m.end())}
    m = NO_RENEWAL.search(folded)
    if m is not None:
        out.auto_renewal = False
        out.evidence["auto_renewal"] = {"excerpt": _excerpt(text, m.start(), m.end())}
    else:
        m = RENEWAL.search(folded)
        if m is not None:
            out.auto_renewal = True
            out.evidence["auto_renewal"] = {"excerpt": _excerpt(text, m.start(), m.end())}
    m = PENALTY.search(folded)
    if m is not None:
        what = text[m.start("what") : m.end("what")].strip()
        out.termination_penalty = what[:300]
        out.evidence["termination_penalty"] = {"excerpt": _excerpt(text, m.start(), m.end())}
    return out


def apply_clauses(contract: Any, text: str | None) -> bool:
    """Fill the contract's terms from the text. Values a person already set are kept.
    Returns True when something changed."""
    found = read_clauses(text)
    changed = False
    evidence = dict(contract.clause_evidence or {})
    for name in ("notice_days", "auto_renewal", "termination_penalty"):
        value = getattr(found, name)
        if value is not None and getattr(contract, name) is None:
            setattr(contract, name, value)
            evidence[name] = found.evidence[name]
            changed = True
    if changed:
        contract.clause_evidence = evidence
    return changed


async def backfill() -> int:
    """Read the terms of every contract with a source document (owner role, all tenants)."""
    from sqlalchemy import select

    from app.db.models import Contract, Document
    from app.db.session import get_admin_engine, sessionmaker_for

    changed = 0
    async with sessionmaker_for(get_admin_engine())() as session, session.begin():
        rows = await session.execute(
            select(Contract, Document.text_content).join(
                Document, Document.id == Contract.source_document_id
            )
        )
        for contract, text in rows:
            changed += apply_clauses(contract, text)
    return changed


if __name__ == "__main__":
    import asyncio

    print(f"contratos atualizados: {asyncio.run(backfill())}")
