import random

import pytest

from app.core.br import (
    format_cnpj,
    generate_cnpj,
    is_valid_cnpj,
    is_valid_cpf,
    mask_cpf,
)


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-81", "11222333000181"])
def test_valid_cnpj(cnpj: str) -> None:
    assert is_valid_cnpj(cnpj)


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-82", "00000000000000", "123", ""])
def test_invalid_cnpj(cnpj: str) -> None:
    assert not is_valid_cnpj(cnpj)


def test_generated_cnpjs_are_valid() -> None:
    rng = random.Random(1)
    for _ in range(500):
        assert is_valid_cnpj(generate_cnpj(rng))


def test_format_cnpj() -> None:
    assert format_cnpj("11222333000181") == "11.222.333/0001-81"


def test_cpf_validation() -> None:
    assert is_valid_cpf("529.982.247-25")
    assert not is_valid_cpf("529.982.247-24")
    assert not is_valid_cpf("111.111.111-11")


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("123.456.789-09", "***.456.789-**"),
        ("12345678909", "***.456.789-**"),
        ("***456789**", "***.456.789-**"),
        ("bad", "***.***.***-**"),
    ],
)
def test_mask_cpf(raw: str, masked: str) -> None:
    assert mask_cpf(raw) == masked
