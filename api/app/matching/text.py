"""Text normalisation shared by matching and rules (names, descriptions)."""

import re
import unicodedata

STOPWORDS = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "para",
    "por",
    "com",
    "sem",
    "ao",
    "aos",
    "um",
    "uma",
    "ltda",
    "me",
    "epp",
    "eireli",
    "sa",
    "s/a",
    "servico",
    "servicos",
    "mensal",
    "mes",
    "referente",
    "condominio",
}


def normalize_name(name: str) -> str:
    """Lowercase, no accents, single spaces: for exact full-name comparison (rule R08)."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return " ".join(text.split())


def tokens(text: str) -> set[str]:
    words = normalize_name(text).split()
    return {w for w in words if len(w) > 2 and w not in STOPWORDS and not w.isdigit()}


def overlap(a: str, b: str) -> float:
    """Share of the shorter text's meaningful words that also appear in the other."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))
