"""Parsing of Brazilian money and date formats."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")
_BRL = re.compile(
    r"^\s*(?P<sign>[-+])?\s*(?:R\$\s*)?(?P<num>[\d.]*\d(?:,\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?P<dc>[DC])?\s*$",
    re.I,
)


def parse_brl(value: str) -> Decimal:
    """'1.234,56' / '-1.234,56' / 'R$ 10,00' / '1234.56' / '150,00 D' -> Decimal.

    A trailing 'D' (débito) makes the value negative; 'C' keeps it positive.
    """
    m = _BRL.match(value)
    if not m:
        raise ValueError(f"valor monetário inválido: {value!r}")
    num = m.group("num")
    if "," in num:
        num = num.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d{2}", num):
        # "8.364.18": OCR often reads the decimal comma as a dot; the last 2 digits are cents.
        head, cents_part = num.rsplit(".", 1)
        num = head.replace(".", "") + "." + cents_part
    elif num.count(".") > 1 or re.search(r"\.\d{3}$", num):
        num = num.replace(".", "")  # thousands separators only
    try:
        amount = Decimal(num)
    except InvalidOperation as exc:
        raise ValueError(f"valor monetário inválido: {value!r}") from exc
    negative = m.group("sign") == "-" or (m.group("dc") or "").upper() == "D"
    return (-amount if negative else amount).quantize(CENT)


def cents(field: str) -> Decimal:
    """Fixed-width numeric field with two implied decimals ('000000012345' -> 123.45)."""
    digits = field.strip() or "0"
    if not digits.isdigit():
        raise ValueError(f"campo numérico inválido: {field!r}")
    return (Decimal(int(digits)) / 100).quantize(CENT)


def parse_ddmmyyyy(value: str) -> date | None:
    v = value.strip()
    if not v or set(v) <= {"0"}:
        return None
    if "/" in v:
        d, m, y = v.split("/")
    else:
        d, m, y = v[:2], v[2:4], v[4:]
    year = int(y)
    if year < 100:
        year += 2000
    return date(year, int(m), int(d))


def brl(value: Decimal) -> str:
    """Decimal('1234.5') -> 'R$ 1.234,50'."""
    q = Decimal(value).quantize(CENT)
    sign = "-" if q < 0 else ""
    text = f"{abs(q):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sign}R$ {text}"


def pct(value: Decimal) -> str:
    """Decimal('4.5612') -> '4,56%'."""
    return f"{Decimal(value).quantize(CENT)}".replace(".", ",") + "%"
