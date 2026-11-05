"""Shared helpers and the bank registry for CNAB return files.

Positions in this package are 1-indexed and inclusive, exactly as printed in the bank
manuals, so each field can be checked against the manual by eye.

Adding a bank: write a parser function and register it with ``@register(layout, bank_code)``.
"""

from collections.abc import Callable

from app.ingestion.bank.base import BankFileError, ParsedStatement

CnabParser = Callable[[list[str]], ParsedStatement]

_REGISTRY: dict[tuple[int, str], CnabParser] = {}

BANK_NAMES = {"001": "Banco do Brasil", "237": "Bradesco", "341": "Itaú"}


def field(line: str, start: int, end: int) -> str:
    """Characters ``start``..``end`` (1-indexed, inclusive)."""
    return line[start - 1 : end]


def register(layout: int, bank_code: str) -> Callable[[CnabParser], CnabParser]:
    def deco(fn: CnabParser) -> CnabParser:
        _REGISTRY[(layout, bank_code)] = fn
        return fn

    return deco


def split_lines(data: bytes) -> list[str]:
    text = data.decode("latin-1")
    return [ln.rstrip("\r") for ln in text.split("\n") if ln.strip("\r\n \x1a")]


def detect(lines: list[str]) -> tuple[int, str] | None:
    """Return (layout, bank code) or None when the file is not a CNAB return."""
    if not lines:
        return None
    first = lines[0]
    if len(first) == 240 and field(first, 8, 8) == "0":
        return 240, field(first, 1, 3)
    if len(first) == 400 and first[0] == "0" and field(first, 2, 2) == "2":
        return 400, field(first, 77, 79)
    return None


def looks_like_cnab(data: bytes) -> bool:
    return detect(split_lines(data[:2000])) is not None


def parse_cnab(data: bytes) -> ParsedStatement:
    ensure_registered()
    lines = split_lines(data)
    found = detect(lines)
    if found is None:
        raise BankFileError("O arquivo não é um retorno CNAB 240 ou 400 reconhecido.")
    layout, bank = found
    widths = {len(ln) for ln in lines}
    if widths != {layout}:
        raise BankFileError(f"Linhas com tamanho diferente de {layout} posições no arquivo CNAB.")
    parser = _REGISTRY.get((layout, bank))
    if parser is None:
        supported = ", ".join(f"{BANK_NAMES.get(b, b)} ({lay})" for lay, b in sorted(_REGISTRY))
        raise BankFileError(
            f"Retorno CNAB {layout} do banco {bank} ainda não é suportado. Suportados: {supported}."
        )
    statement = parser(lines)
    statement.bank_code = bank
    return statement


def _load_parsers() -> None:
    # Import for registration side effects.
    from app.ingestion.bank.cnab import cnab240, cnab400  # noqa: F401


_load_parsers_done = False


def ensure_registered() -> None:
    global _load_parsers_done
    if not _load_parsers_done:
        _load_parsers()
        _load_parsers_done = True
