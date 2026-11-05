"""Boleto "linha digitável": parsing and check-digit validation (FEBRABAN).

- Bank boletos: 47 digits. Value and due date come from the code itself; when every check
  digit matches, these two fields are certain (confidence 1.0) and need no review.
- Collection slips of utilities (arrecadação, start with 8): 48 digits. Value comes from the
  code when the value identifier is 6 or 8; there is no due date in the code.

Due-date factor: days since 07/10/1997, restarted at 1000 on 22/02/2025 (FEBRABAN). Both
cycles are computed and the date closest to the reference date wins.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

BASE_OLD = date(1997, 10, 7)
BASE_NEW = date(2025, 2, 22)  # factor 1000 in the new cycle

_CANDIDATE = re.compile(r"(?<![\d])(?:\d[\d.\s-]{44,62}\d)(?![\d])")


@dataclass(frozen=True)
class Boleto:
    digits: str  # the linha digitável, digits only
    barcode: str  # 44 digits
    kind: str  # "bancario" | "arrecadacao"
    amount: Decimal | None
    due_date: date | None
    bank_code: str | None


def mod10(number: str) -> int:
    total = 0
    weight = 2
    for ch in reversed(number):
        prod = int(ch) * weight
        total += prod // 10 + prod % 10
        weight = 1 if weight == 2 else 2
    return (10 - total % 10) % 10


def _mod11_weights(number: str) -> int:
    total = 0
    weight = 2
    for ch in reversed(number):
        total += int(ch) * weight
        weight = 2 if weight == 9 else weight + 1
    return total


def mod11_bancario(number: str) -> int:
    dv = 11 - _mod11_weights(number) % 11
    return 1 if dv in (0, 10, 11) else dv


def mod11_arrecadacao(number: str) -> int:
    rest = _mod11_weights(number) % 11
    return 0 if rest in (0, 1) else 11 - rest


def due_date_from_factor(factor: int, reference: date) -> date | None:
    if factor == 0:
        return None
    candidates = [BASE_OLD + timedelta(days=factor)]
    if factor >= 1000:
        candidates.append(BASE_NEW + timedelta(days=factor - 1000))
    return min(candidates, key=lambda d: abs((d - reference).days))


def parse_bancario(digits: str, reference: date) -> Boleto | None:
    if len(digits) != 47:
        return None
    f1, f2, f3 = digits[0:10], digits[10:21], digits[21:32]
    for f in (f1, f2, f3):
        if mod10(f[:-1]) != int(f[-1]):
            return None
    barcode = digits[0:4] + digits[32] + digits[33:47] + f1[4:9] + f2[:10] + f3[:10]
    if mod11_bancario(barcode[:4] + barcode[5:]) != int(barcode[4]):
        return None
    factor = int(digits[33:37])
    amount = Decimal(int(digits[37:47])) / 100
    return Boleto(
        digits=digits,
        barcode=barcode,
        kind="bancario",
        amount=amount.quantize(Decimal("0.01")) if amount > 0 else None,
        due_date=due_date_from_factor(factor, reference),
        bank_code=digits[0:3],
    )


def parse_arrecadacao(digits: str) -> Boleto | None:
    if len(digits) != 48 or digits[0] != "8":
        return None
    blocks = [digits[i : i + 12] for i in range(0, 48, 12)]
    value_id = digits[2]
    if value_id not in "6789":
        return None
    check = mod10 if value_id in "67" else mod11_arrecadacao
    for block in blocks:
        if check(block[:11]) != int(block[11]):
            return None
    barcode = "".join(b[:11] for b in blocks)
    if check(barcode[:3] + barcode[4:]) != int(barcode[3]):
        return None
    amount = None
    if value_id in "68":
        amount = (Decimal(int(barcode[4:15])) / 100).quantize(Decimal("0.01"))
    return Boleto(
        digits=digits,
        barcode=barcode,
        kind="arrecadacao",
        amount=amount,
        due_date=None,
        bank_code=None,
    )


def parse_linha_digitavel(raw: str, reference: date) -> Boleto | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 47:
        return parse_bancario(digits, reference)
    if len(digits) == 48:
        return parse_arrecadacao(digits)
    return None


def find_in_text(text: str, reference: date) -> Boleto | None:
    """First valid linha digitável in free text (only valid check digits count)."""
    for match in _CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        for size in (47, 48):
            for start in range(0, max(1, len(digits) - size + 1)):
                parsed = parse_linha_digitavel(digits[start : start + size], reference)
                if parsed is not None:
                    return parsed
    return None


def build_bancario(bank: str, amount: Decimal, due: date, free_field: str) -> str:
    """Build a valid 47-digit linha digitável (used for fictitious test documents)."""
    assert len(bank) == 3 and len(free_field) == 25
    factor = (due - BASE_NEW).days + 1000
    assert 1000 <= factor <= 9999
    value = str(int(amount * 100)).zfill(10)
    without_dv = bank + "9" + f"{factor:04d}" + value + free_field
    dv = mod11_bancario(without_dv)
    f1 = bank + "9" + free_field[0:5]
    f2 = free_field[5:15]
    f3 = free_field[15:25]
    return (
        f1
        + str(mod10(f1))
        + f2
        + str(mod10(f2))
        + f3
        + str(mod10(f3))
        + str(dv)
        + f"{factor:04d}"
        + value
    )


def format_bancario(digits: str) -> str:
    d = digits
    return f"{d[0:5]}.{d[5:10]} {d[10:15]}.{d[15:21]} {d[21:26]}.{d[26:32]} {d[32]} {d[33:47]}"


def build_arrecadacao(segment: str, amount: Decimal, company: str, free: str) -> str:
    """Build a valid 48-digit arrecadação code with value id 6 (mod 10)."""
    value = str(int(amount * 100)).zfill(11)
    body = "8" + segment + "6" + value + company + free  # 43 digits without the general DV
    assert len(body) == 43, len(body)
    barcode = body[:3] + str(mod10(body)) + body[3:]
    blocks = [barcode[i : i + 11] for i in range(0, 44, 11)]
    return "".join(b + str(mod10(b)) for b in blocks)
