"""CSV bank statement reader.

Banks export CSV in many shapes. Columns are recognised by header name (case and accents
ignored): a date column, a description column, and either one signed value column or
separate debit/credit columns. An optional document column (CNPJ/CPF of the payee) is used
when present. Dates are dd/mm/aaaa; values use the Brazilian format.
"""

import csv
import hashlib
import io
import unicodedata

from app.core.br import only_digits
from app.core.money import parse_brl, parse_ddmmyyyy
from app.db.enums import BankTransactionOrigin
from app.ingestion.bank.base import BankFileError, ParsedStatement, ParsedTransaction
from app.ingestion.bank.ofx import decode

DATE_COLS = ("data", "data lancamento", "data do lancamento", "data movimento", "dt lancamento")
DESC_COLS = ("descricao", "historico", "lancamento", "descricao do lancamento", "memo")
VALUE_COLS = ("valor", "valor (r$)", "valor r$", "montante")
DEBIT_COLS = ("debito", "saida", "valor debito", "debito (r$)")
CREDIT_COLS = ("credito", "entrada", "valor credito", "credito (r$)")
DOC_COLS = ("documento", "cnpj/cpf", "cpf/cnpj", "cnpj", "doc favorecido")
PAYEE_COLS = ("favorecido", "beneficiario", "nome")


def _norm(header: str) -> str:
    text = unicodedata.normalize("NFKD", header).encode("ascii", "ignore").decode()
    return " ".join(text.lower().strip().split())


def _find(headers: list[str], options: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        if h in options:
            return i
    return None


def parse_csv(data: bytes) -> ParsedStatement:
    text = decode(data).lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise BankFileError("O CSV não tem lançamentos.")

    headers = [_norm(h) for h in rows[0]]
    i_date, i_desc = _find(headers, DATE_COLS), _find(headers, DESC_COLS)
    i_value = _find(headers, VALUE_COLS)
    i_debit, i_credit = _find(headers, DEBIT_COLS), _find(headers, CREDIT_COLS)
    i_doc, i_payee = _find(headers, DOC_COLS), _find(headers, PAYEE_COLS)
    if i_date is None or i_desc is None or (i_value is None and i_debit is None):
        raise BankFileError(
            "Não reconheci as colunas do CSV. São necessárias: data, descrição e valor "
            "(ou débito e crédito)."
        )

    statement = ParsedStatement(transactions=[])
    seen: dict[str, int] = {}
    for row in rows[1:]:

        def cell(i: int | None, row: list[str] = row) -> str:
            return row[i].strip() if i is not None and i < len(row) else ""

        try:
            posted = parse_ddmmyyyy(cell(i_date))
            if i_value is not None and cell(i_value):
                amount = parse_brl(cell(i_value))
            else:
                debit, credit = cell(i_debit), cell(i_credit)
                if debit:
                    amount = -abs(parse_brl(debit))
                elif credit:
                    amount = abs(parse_brl(credit))
                else:
                    raise ValueError("sem valor")
        except (ValueError, IndexError):
            # Balance lines ("SALDO ANTERIOR") and footers have no usable date/value.
            statement.ignored_records += 1
            continue
        if posted is None:
            statement.ignored_records += 1
            continue
        description = cell(i_desc) or "SEM DESCRIÇÃO"
        if _norm(description).startswith("saldo"):
            # D122: balance lines are kept as stated: "saldo anterior" opens, the last other
            # balance line closes. Nothing is derived from the transactions.
            if _norm(description).startswith("saldo anterior"):
                if statement.opening_balance is None:
                    statement.opening_balance, statement.opening_date = amount, posted
            elif statement.closing_date is None or posted >= statement.closing_date:
                statement.closing_balance, statement.closing_date = amount, posted
            statement.balance_source = "CSV linhas de saldo"
            statement.ignored_records += 1
            continue
        doc = only_digits(cell(i_doc))
        key = f"{posted.isoformat()}|{amount}|{_norm(description)}|{doc}"
        seen[key] = seen.get(key, 0) + 1
        digest = hashlib.sha256(f"{key}#{seen[key]}".encode()).hexdigest()[:40]
        statement.transactions.append(
            ParsedTransaction(
                posted_at=posted,
                amount=amount,
                description=description[:300],
                external_id=f"csv:{digest}",
                origin=BankTransactionOrigin.CSV,
                payee_name=cell(i_payee)[:200] or None,
                payee_document=doc if len(doc) in (11, 14) else None,
            )
        )
    if not statement.transactions:
        raise BankFileError("Nenhum lançamento válido encontrado no CSV.")
    return statement
