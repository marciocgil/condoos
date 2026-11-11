"""Turn a bank file (OFX, CSV, CNAB) into bank_transaction rows. Idempotent."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BankAccount, BankStatement, BankTransaction
from app.ingestion.bank.base import BankFileError, ParsedStatement
from app.ingestion.bank.cnab.common import looks_like_cnab, parse_cnab
from app.ingestion.bank.csv_parser import parse_csv
from app.ingestion.bank.ofx import looks_like_ofx, parse_ofx


@dataclass(frozen=True)
class BankImportResult:
    created: int
    duplicates: int
    ignored_records: int


def parse_bank_file(filename: str, data: bytes) -> ParsedStatement:
    if looks_like_cnab(data):
        return parse_cnab(data)
    if looks_like_ofx(data):
        return parse_ofx(data)
    if filename.lower().endswith((".csv", ".txt")):
        return parse_csv(data)
    raise BankFileError("Formato de extrato não reconhecido. Envie OFX, CSV ou retorno CNAB.")


async def store_statement(
    session: AsyncSession,
    *,
    condominium_id: uuid.UUID,
    condominium_cnpj: str,
    statement: ParsedStatement,
    document_id: uuid.UUID | None = None,
    file_format: str = "arquivo",
) -> BankImportResult:
    holder = statement.account_holder_document
    if holder and holder != condominium_cnpj:
        raise BankFileError(
            "O arquivo bancário é de outro CNPJ, não do condomínio selecionado. Nada foi importado."
        )
    account_id = await _account(session, condominium_id, statement)
    statement_id = await _statement(
        session, condominium_id, statement, account_id, document_id, file_format
    )
    created = 0
    for trn in statement.transactions:
        new_id = await session.scalar(
            insert(BankTransaction)
            .values(
                id=uuid.uuid4(),
                condominium_id=condominium_id,
                bank_account_id=account_id,
                statement_id=statement_id,
                posted_at=trn.posted_at,
                amount=trn.amount,
                payee_name=trn.payee_name,
                payee_document=trn.payee_document,
                description=trn.description,
                origin=trn.origin.value,
                external_id=trn.external_id,
            )
            .on_conflict_do_nothing(index_elements=["condominium_id", "external_id"])
            .returning(BankTransaction.id)
        )
        if new_id is not None:
            created += 1
    if statement_id is not None:
        # Lines imported before (same external id) also get the account and the statement.
        await session.execute(
            update(BankTransaction)
            .where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.external_id.in_([t.external_id for t in statement.transactions]),
                BankTransaction.statement_id.is_(None),
            )
            .values(bank_account_id=account_id, statement_id=statement_id)
        )
    return BankImportResult(
        created=created,
        duplicates=len(statement.transactions) - created,
        ignored_records=statement.ignored_records,
    )


async def _account(
    session: AsyncSession, condominium_id: uuid.UUID, statement: ParsedStatement
) -> uuid.UUID | None:
    """The account the file names (bank, branch, number), created on first sight (D122).
    A file that does not name its account (most CSVs) links to no account."""
    if not (statement.bank_code and statement.account_number):
        return None
    branch = (statement.branch or "").strip()
    number = statement.account_number.strip()
    found = await session.scalar(
        select(BankAccount.id).where(
            BankAccount.condominium_id == condominium_id,
            BankAccount.bank_code == statement.bank_code,
            BankAccount.branch == branch,
            BankAccount.number == number,
        )
    )
    if found is not None:
        return found
    account = BankAccount(
        id=uuid.uuid4(),
        condominium_id=condominium_id,
        bank_code=statement.bank_code,
        branch=branch,
        number=number,
        label=f"Banco {statement.bank_code} · ag. {branch or '—'} · conta {number}",
    )
    session.add(account)
    await session.flush()
    return account.id


async def _statement(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    statement: ParsedStatement,
    account_id: uuid.UUID | None,
    document_id: uuid.UUID | None,
    file_format: str,
) -> uuid.UUID | None:
    if document_id is None:
        return None
    existing = await session.scalar(
        select(BankStatement).where(
            BankStatement.condominium_id == condominium_id,
            BankStatement.document_id == document_id,
        )
    )
    dates = [t.posted_at for t in statement.transactions]
    values = {
        "bank_account_id": account_id,
        "period_start": statement.period_start or (min(dates) if dates else None),
        "period_end": statement.period_end or (max(dates) if dates else None),
        "opening_balance": statement.opening_balance,
        "opening_date": statement.opening_date,
        "closing_balance": statement.closing_balance,
        "closing_date": statement.closing_date,
        "balance_source": statement.balance_source,
        "transactions": len(statement.transactions),
        "format": file_format[:10],
    }
    if existing is not None:
        for key, value in values.items():
            setattr(existing, key, value)
        return existing.id
    row = BankStatement(
        id=uuid.uuid4(), condominium_id=condominium_id, document_id=document_id, **values
    )
    session.add(row)
    await session.flush()
    return row.id
