from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.money import parse_brl
from app.db.models import BankTransaction, Condominium
from app.db.session import sessionmaker_for
from app.ingestion.bank.base import BankFileError
from app.ingestion.bank.cnab.common import parse_cnab
from app.ingestion.bank.csv_parser import parse_csv
from app.ingestion.bank.ofx import parse_ofx
from app.ingestion.bank.service import parse_bank_file, store_statement
from tests.bankfiles import Liquidation, Payment, cnab240, cnab400, ofx_sgml

CNPJ = "11222333000181"  # fictitious, valid check digits
SUPPLIER = "45723174000110"
BANKS = ["001", "237", "341"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("-1.234,56", "-1234.56"),
        ("R$ 10,00", "10.00"),
        ("150,00 D", "-150.00"),
        ("1234.56", "1234.56"),
        ("1.234", "1234.00"),
        ("R$ 8.364.18", "8364.18"),  # OCR read the decimal comma as a dot
        ("19.277.00", "19277.00"),
    ],
)
def test_parse_brl(raw: str, expected: str) -> None:
    assert parse_brl(raw) == Decimal(expected)


@pytest.mark.parametrize("bank", BANKS)
def test_cnab240_payments(bank: str) -> None:
    data = cnab240(
        bank,
        CNPJ,
        payments=[
            Payment(
                "A",
                "PORTARIA FICTICIA LTDA",
                Decimal("18500.00"),
                date(2026, 10, 10),
                SUPPLIER,
                "PAG001",
            ),
            Payment(
                "J",
                "ENERGIA FICTICIA SA",
                Decimal("7812.34"),
                date(2026, 10, 12),
                SUPPLIER,
                "PAG002",
            ),
            Payment(
                "A",
                "REJEITADO LTDA",
                Decimal("10.00"),
                date(2026, 10, 12),
                SUPPLIER,
                "PAG003",
                occurrence="AG",
            ),
        ],
    )
    st = parse_cnab(data)
    assert st.bank_code == bank
    assert st.account_holder_document == CNPJ
    assert [(t.amount, t.posted_at) for t in st.transactions] == [
        (Decimal("-18500.00"), date(2026, 10, 10)),
        (Decimal("-7812.34"), date(2026, 10, 12)),
    ]
    transfer, boleto = st.transactions
    assert transfer.payee_document == SUPPLIER and transfer.payee_name == "PORTARIA FICTICIA LTDA"
    assert boleto.payee_document == SUPPLIER  # from segment J-52
    assert st.ignored_records == 1  # the rejected payment
    assert len({t.external_id for t in st.transactions}) == 2


@pytest.mark.parametrize("bank", BANKS)
def test_cnab240_collection(bank: str) -> None:
    data = cnab240(
        bank,
        CNPJ,
        liquidations=[
            Liquidation("000123", "UNID101", Decimal("650.00"), date(2026, 10, 10)),
            Liquidation(
                "000124", "UNID102", Decimal("650.00"), date(2026, 10, 10), occurrence="02"
            ),  # entrada confirmada: not money
        ],
    )
    st = parse_cnab(data)
    assert len(st.transactions) == 1
    t = st.transactions[0]
    assert t.amount == Decimal("650.00") and t.posted_at == date(2026, 10, 10)
    assert "UNID101" in t.description


@pytest.mark.parametrize("bank", BANKS)
def test_cnab400_collection(bank: str) -> None:
    data = cnab400(
        bank,
        CNPJ,
        [
            Liquidation("777", "UNID201", Decimal("712.40"), date(2026, 10, 11)),
            Liquidation(
                "778", "UNID202", Decimal("712.40"), date(2026, 10, 11), occurrence="09"
            ),  # baixa: not money
        ],
    )
    st = parse_cnab(data)
    assert st.bank_code == bank
    assert st.account_holder_document == CNPJ
    assert [(t.amount, t.posted_at) for t in st.transactions] == [
        (Decimal("712.40"), date(2026, 10, 11))
    ]
    assert st.ignored_records == 1


def test_unsupported_bank_is_explained() -> None:
    data = bytearray(cnab400("341", CNPJ, []))
    data[76:79] = b"104"  # header positions 77-79: bank code (Caixa, not supported yet)
    with pytest.raises(BankFileError, match="ainda não é suportado"):
        parse_cnab(bytes(data))


def test_broken_line_width_rejected() -> None:
    data = cnab400("341", CNPJ, [Liquidation("1", "A", Decimal("1"), date(2026, 1, 1))])
    with pytest.raises(BankFileError, match="tamanho"):
        parse_cnab(data.replace(b"\r\n9", b"X\r\n9"))


def test_ofx_sgml() -> None:
    data = ofx_sgml(
        [
            (date(2026, 10, 3), Decimal("-1500.00"), "F1", "PAG BOLETO VERDE VIVO"),
            (date(2026, 10, 9), Decimal("78000.00"), "F2", "RECEBIMENTO TAXAS"),
        ]
    )
    st = parse_ofx(data)
    assert [t.amount for t in st.transactions] == [Decimal("-1500.00"), Decimal("78000.00")]
    assert st.transactions[0].external_id == "ofx:F1"
    assert st.bank_code == "0341"


def test_csv_with_signed_value_and_balance_lines() -> None:
    data = (
        "Data;Histórico;Documento;Valor\n"
        "01/10/2026;SALDO ANTERIOR;;10.000,00\n"
        f"05/10/2026;PAG BOLETO PRAGA ZERO;{SUPPLIER};-650,00\n"
        "05/10/2026;TARIFA;;-12,90\n"
        "05/10/2026;TARIFA;;-12,90\n"
    ).encode("cp1252")
    st = parse_csv(data)
    assert [t.amount for t in st.transactions] == [
        Decimal("-650.00"),
        Decimal("-12.90"),
        Decimal("-12.90"),
    ]
    assert st.transactions[0].payee_document == SUPPLIER
    # Two identical lines are two transactions with different ids.
    assert st.transactions[1].external_id != st.transactions[2].external_id
    assert st.ignored_records == 1


def test_csv_with_debit_credit_columns() -> None:
    data = b'data,descricao,debito,credito\n02/10/2026,PIX ENVIADO,"1.200,00",\n03/10/2026,PIX RECEBIDO,,"300,00"\n'
    st = parse_csv(data)
    assert [t.amount for t in st.transactions] == [Decimal("-1200.00"), Decimal("300.00")]


def test_csv_unknown_columns() -> None:
    with pytest.raises(BankFileError, match="colunas"):
        parse_csv(b"a;b\n1;2\n")


def test_dispatch_by_content() -> None:
    assert parse_bank_file("x.ret", cnab400("237", CNPJ, [])).bank_code == "237"
    with pytest.raises(BankFileError):
        parse_bank_file("foto.jpg", b"\xff\xd8\xff")


async def test_store_is_idempotent_and_checks_cnpj(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.scalar(select(Condominium).where(Condominium.slug == "mirante-do-vale"))
    assert condo is not None
    data = cnab240(
        "341",
        condo.cnpj,
        payments=[
            Payment(
                "A",
                "PORTARIA FICTICIA LTDA",
                Decimal("999.99"),
                date(2026, 10, 20),
                SUPPLIER,
                "IDEMP1",
            ),
        ],
    )
    st = parse_cnab(data)
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        first = await store_statement(
            s, condominium_id=condo.id, condominium_cnpj=condo.cnpj, statement=st
        )
    async with maker() as s, s.begin():
        second = await store_statement(
            s, condominium_id=condo.id, condominium_cnpj=condo.cnpj, statement=st
        )
    assert (first.created, second.created, second.duplicates) == (1, 0, 1)
    async with maker() as s:
        count = await s.scalar(
            select(func.count())
            .select_from(BankTransaction)
            .where(
                BankTransaction.condominium_id == condo.id,
                BankTransaction.amount == Decimal("-999.99"),
            )
        )
    assert count == 1

    other = parse_cnab(
        cnab240(
            "341",
            CNPJ,
            payments=[
                Payment("A", "X", Decimal("1.00"), date(2026, 10, 20), SUPPLIER, "OTHER1"),
            ],
        )
    )
    async with maker() as s, s.begin():
        with pytest.raises(BankFileError, match="outro CNPJ"):
            await store_statement(
                s, condominium_id=condo.id, condominium_cnpj=condo.cnpj, statement=other
            )
