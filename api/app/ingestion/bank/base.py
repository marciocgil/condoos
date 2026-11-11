"""Common types for bank statement parsers (OFX, CSV, CNAB)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.db.enums import BankTransactionOrigin


class BankFileError(ValueError):
    """The file could not be read; the message is shown to the user (pt-BR)."""


@dataclass(frozen=True)
class ParsedTransaction:
    posted_at: date
    amount: Decimal  # negative = debit
    description: str
    external_id: str  # stable id inside the source, used for idempotent ingestion
    origin: BankTransactionOrigin
    payee_name: str | None = None
    payee_document: str | None = None  # CNPJ/CPF digits


@dataclass
class ParsedStatement:
    transactions: list[ParsedTransaction]
    # CNPJ of the account holder declared by the file, when the format carries it.
    account_holder_document: str | None = None
    bank_code: str | None = None
    ignored_records: int = 0
    notes: list[str] = field(default_factory=list)
    # D122: the account and the balances exactly as the file states them (None = not stated;
    # a missing balance is never derived nor taken as zero).
    branch: str | None = None
    account_number: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    opening_balance: Decimal | None = None
    opening_date: date | None = None
    closing_balance: Decimal | None = None
    closing_date: date | None = None
    balance_source: str | None = None
