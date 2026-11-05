"""Expense categories and the CNAE classes compatible with each one.

The CNAE side is a lookup in the official IBGE classification (class = first 4 digits), so
rule R07 is deterministic for mapped categories; the model is only asked about categories
that have no entry here.
"""

from app.db.models import Contract, Supplier
from app.matching.text import tokens

# category -> CNAE class prefixes (4 digits, or 2-digit division) compatible with it.
COMPATIBLE_CNAE: dict[str, tuple[str, ...]] = {
    "portaria": ("8011", "8012", "8020", "8111", "7810", "7820", "7830"),
    "limpeza": ("8121", "8122", "8129", "8111", "7810", "7820"),
    "manutencao": (
        "4321",
        "4322",
        "4329",
        "4330",
        "4399",
        "3311",
        "3312",
        "3313",
        "3314",
        "3319",
        "3321",
        "3329",
        "4120",
        "8111",
        "9529",
    ),
    "elevadores": ("4329", "3321", "3314", "2822"),
    "jardinagem": ("8130", "0161"),
    "dedetizacao": ("8122",),
    "energia": ("35",),
    "agua": ("36", "37"),
    "gas": ("35", "4682", "4784"),
    "seguro": ("65", "66"),
    "administracao": ("6822", "8211", "6920", "7020"),
    "obras": ("41", "42", "43", "7111", "7112"),
}

# Keywords that suggest a category for an expense with no contract (description / CNAE text).
KEYWORDS: dict[str, tuple[str, ...]] = {
    "portaria": ("portaria", "vigilancia", "seguranca", "porteiro"),
    "limpeza": ("limpeza", "conservacao", "faxina"),
    "elevadores": ("elevador", "elevadores"),
    "jardinagem": ("jardim", "jardinagem", "paisagismo", "poda", "grama"),
    "dedetizacao": ("dedetizacao", "desratizacao", "pragas", "imunizacao"),
    "energia": ("energia", "kwh"),
    "agua": ("agua", "esgoto", "saneamento"),
    "gas": ("gas",),
    "seguro": ("seguro", "apolice"),
    "obras": ("obra", "reforma", "pintura", "fachada", "impermeabilizacao"),
    "manutencao": ("manutencao", "reparo", "conserto", "bomba", "hidraulica", "eletrica"),
}


def cnae_compatible(category: str, cnae_codes: list[str]) -> bool | None:
    """True/False for mapped categories; None when the category has no mapping (ask the model)."""
    prefixes = COMPATIBLE_CNAE.get(category)
    if prefixes is None:
        return None
    digits = [c.replace("-", "").replace("/", "").replace(".", "") for c in cnae_codes]
    return any(d.startswith(p) for d in digits for p in prefixes)


def supplier_cnaes(supplier: Supplier) -> list[str]:
    codes = [supplier.cnae_main["code"]] if supplier.cnae_main else []
    return codes + [c["code"] for c in supplier.cnae_secondary or [] if c.get("code")]


def _by_keywords(text: str) -> str | None:
    words = tokens(text)
    for category, keys in KEYWORDS.items():
        if words & set(keys):
            return category
    return None


def category_for(contract: Contract | None, supplier: Supplier | None, text: str) -> str:
    """Category of a new expense: from its contract's object, else from the description,
    else from the supplier's CNAE, else "outros"."""
    if contract is not None:
        found = _by_keywords(contract.object)
        if found:
            return found
    found = _by_keywords(text)
    if found:
        return found
    if supplier is not None:
        for category, prefixes in COMPATIBLE_CNAE.items():
            if any(
                c.replace("-", "").replace("/", "").startswith(prefixes)
                for c in supplier_cnaes(supplier)
            ):
                return category
    return "outros"


CATEGORY_LABEL: dict[str, str] = {
    "portaria": "portaria",
    "limpeza": "limpeza",
    "manutencao": "manutenção",
    "elevadores": "elevadores",
    "jardinagem": "jardinagem",
    "energia": "energia elétrica",
    "agua": "água e esgoto",
    "gas": "gás",
    "seguro": "seguro",
    "administracao": "administração",
    "dedetizacao": "dedetização",
    "obras": "obras",
    "outros": "outros",
}


def category_label(category: str) -> str:
    return CATEGORY_LABEL.get(category, category)
