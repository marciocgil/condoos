"""Demonstration data for CondoOS Audit (D122): one fictitious account of Jardim das
Acácias and one statement per month of the seed, with the balances a bank would declare.
Synthetic: the bank code 999 does not exist; the balances start at a round fictitious
value and follow the seed's own transactions."""

import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.models import BankAccount, BankStatement, BankTransaction, Condominium

OPENING = Decimal("50000.00")


async def seed_audit(session: AsyncSession) -> None:
    condo = await session.scalar(
        select(Condominium).where(Condominium.slug == "jardim-das-acacias")
    )
    if condo is None:
        return
    exists = await session.scalar(
        select(BankAccount.id).where(BankAccount.condominium_id == condo.id)
    )
    if exists is not None:
        return
    account = BankAccount(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        bank_code="999",
        branch="0001",
        number="12345-6",
        label="Banco fictício 999 · ag. 0001 · conta 12345-6 (seed)",
    )
    session.add(account)
    await session.flush()
    lines = list(
        await session.scalars(
            select(BankTransaction)
            .where(BankTransaction.condominium_id == condo.id)
            .order_by(BankTransaction.posted_at)
        )
    )
    if not lines:
        return
    month = lines[0].posted_at.replace(day=1)
    balance = OPENING
    while month <= lines[-1].posted_at:
        end = add_months(month, 1) - timedelta(days=1)
        mine = [t for t in lines if month <= t.posted_at <= end]
        closing = balance + sum((t.amount for t in mine), Decimal("0"))
        st = BankStatement(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            bank_account_id=account.id,
            document_id=None,
            period_start=month,
            period_end=end,
            opening_balance=balance,
            opening_date=month,
            closing_balance=closing,
            closing_date=end,
            balance_source="seed (fictício)",
            transactions=len(mine),
            format="ofx",
        )
        session.add(st)
        await session.flush()
        for t in mine:
            t.bank_account_id, t.statement_id = account.id, st.id
        balance, month = closing, add_months(month, 1)
    await session.flush()
