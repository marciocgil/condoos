"""Brazilian document helpers (CNPJ, CPF). Own implementation, covered by tests."""

import random
import re

_NON_DIGITS = re.compile(r"\D")
_CNPJ_W1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_W2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def only_digits(value: str) -> str:
    return _NON_DIGITS.sub("", value)


def _mod11(digits: str, weights: tuple[int, ...]) -> int:
    rest = sum(int(d) * w for d, w in zip(digits, weights, strict=True)) % 11
    return 0 if rest < 2 else 11 - rest


def cnpj_check_digits(base12: str) -> str:
    d1 = _mod11(base12, _CNPJ_W1)
    d2 = _mod11(base12 + str(d1), _CNPJ_W2)
    return f"{d1}{d2}"


def is_valid_cnpj(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    return digits[12:] == cnpj_check_digits(digits[:12])


def generate_cnpj(rng: random.Random, branch: str = "0001") -> str:
    """A CNPJ with valid check digits. Used only for fictitious seed/test data."""
    base = "".join(str(rng.randint(0, 9)) for _ in range(8)) + branch
    return base + cnpj_check_digits(base)


def format_cnpj(value: str) -> str:
    d = only_digits(value)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else value


def _cpf_digit(digits: str) -> int:
    weight = len(digits) + 1
    rest = sum(int(d) * (weight - i) for i, d in enumerate(digits)) % 11
    return 0 if rest < 2 else 11 - rest


def is_valid_cpf(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    d1 = _cpf_digit(digits[:9])
    d2 = _cpf_digit(digits[:9] + str(d1))
    return digits[9:] == f"{d1}{d2}"


def mask_cpf(value: str) -> str:
    """Mask a CPF as ***.456.789-** (keeps only the middle six digits).

    Already-masked inputs from the Receita (e.g. "***456789**") are normalised to the same
    format. Anything that is not 11 characters becomes fully masked.
    """
    raw = re.sub(r"[.\-\s]", "", value)
    if len(raw) != 11:
        return "***.***.***-**"
    middle = raw[3:9]
    if not middle.isdigit():
        return "***.***.***-**"
    return f"***.{middle[:3]}.{middle[3:]}-**"
