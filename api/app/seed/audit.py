"""Demonstration data for CondoOS Audit (D122): one fictitious account of Jardim das
Acácias and one statement per month of the seed, with the balances a bank would declare.
Synthetic: the bank code 999 does not exist; the balances start at a round fictitious
value and follow the seed's own transactions."""

import hashlib
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.models import (
    BankAccount,
    BankStatement,
    BankTransaction,
    Condominium,
    ReceivableTitle,
    Unit,
)

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


async def seed_units(session: AsyncSession) -> None:
    """Cycle 2 demo (D123): 24 fictitious units of Jardim das Acácias and, for each month of
    the seed, titles whose payments add up to each collection credit of the statement (as a
    bank batch). Unit codes only: no names."""

    condo = await session.scalar(
        select(Condominium).where(Condominium.slug == "jardim-das-acacias")
    )
    if condo is None:
        return
    if await session.scalar(select(Unit.id).where(Unit.condominium_id == condo.id)) is not None:
        return
    units = [
        Unit(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            code=f"Apto {floor}{n:02d}",
            fraction=Decimal("0.04166667"),
        )
        for floor in range(1, 7)
        for n in range(1, 5)
    ]
    session.add_all(units)
    await session.flush()
    credits = list(
        await session.scalars(
            select(BankTransaction)
            .where(
                BankTransaction.condominium_id == condo.id,
                BankTransaction.amount > 0,
                BankTransaction.description.ilike("%taxas condomin%"),
            )
            .order_by(BankTransaction.posted_at)
        )
    )
    by_month: dict[date, list[BankTransaction]] = {}
    for c in credits:
        by_month.setdefault(c.posted_at.replace(day=1), []).append(c)
    for month, items in by_month.items():
        paying = units[:-2]  # the last two units stay open each month
        chunks = [paying[i :: len(items)] for i in range(len(items))]
        for credit, group in zip(items, chunks, strict=False):
            share = (credit.amount / len(group)).quantize(Decimal("0.01"))
            for i, unit in enumerate(group):
                amount = share if i < len(group) - 1 else credit.amount - share * (len(group) - 1)
                session.add(_title(condo.id, unit.id, month, amount, credit.posted_at))
        for unit in units[-2:]:
            session.add(_title(condo.id, unit.id, month, Decimal("3200.00"), None))
    await session.flush()


def _title(
    condo_id: uuid.UUID, unit_id: uuid.UUID, month: object, amount: Decimal, paid: object
) -> object:
    from datetime import date as _date

    assert isinstance(month, _date)
    due = month.replace(day=10)
    key = hashlib.sha256(f"seed|{unit_id}|{month}|{amount}".encode()).hexdigest()
    return ReceivableTitle(
        id=uuid.uuid4(),
        condominium_id=condo_id,
        unit_id=unit_id,
        competence=month,
        kind="ordinaria",
        amount=amount,
        due_date=due,
        status="pago" if paid else "aberto",
        paid_at=paid,
        paid_amount=amount if paid else None,
        import_key=key,
    )


async def seed_governance(session: AsyncSession) -> None:
    """Cycle 3 (D124) demo for Jardim das Acácias: the reserve fund growing 1% of the month's
    expenses, with no backing account named yet (BAN-08 shows that a positive balance is not
    segregated backing), and a budget per year from the seed's own averages, approved
    without the minutes linked (GOV-01 shows the reservation). Fictitious values."""
    from collections import defaultdict

    from app.db.models import Budget, BudgetLine, Expense, Fund, FundBalance

    condo = await session.scalar(
        select(Condominium).where(Condominium.slug == "jardim-das-acacias")
    )
    if condo is None:
        return
    if await session.scalar(select(Fund.id).where(Fund.condominium_id == condo.id)):
        return
    expenses = list(
        await session.scalars(select(Expense).where(Expense.condominium_id == condo.id))
    )
    if not expenses:
        return
    by_month: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    by_year_cat: dict[tuple[int, str], list[Decimal]] = defaultdict(list)
    months_of_year: dict[int, set[date]] = defaultdict(set)
    for e in expenses:
        by_month[e.competence] += e.amount
        by_year_cat[(e.competence.year, e.category)].append(e.amount)
        months_of_year[e.competence.year].add(e.competence)
    fund = Fund(id=uuid.uuid4(), condominium_id=condo.id, name="Fundo de reserva", kind="reserva")
    session.add(fund)
    await session.flush()
    balance = Decimal("20000.00")
    for month in sorted(by_month):
        inflow = (by_month[month] / 100).quantize(Decimal("0.01"))
        session.add(
            FundBalance(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                fund_id=fund.id,
                competence=month,
                opening=balance,
                inflows=inflow,
                outflows=Decimal("0.00"),
                yield_amount=Decimal("0.00"),
                closing=balance + inflow,
            )
        )
        balance += inflow
    for year, months in months_of_year.items():
        budget = Budget(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            year=year,
            version=1,
            approved_on=date(year - 1, 12, 10),
            file_sha256=hashlib.sha256(f"seed-{year}".encode()).hexdigest(),
        )
        session.add(budget)
        await session.flush()
        for (y, category), values in by_year_cat.items():
            if y != year:
                continue
            monthly = (sum(values, Decimal("0")) / len(months)).quantize(Decimal("1"))
            for m in range(1, 13):
                session.add(
                    BudgetLine(
                        id=uuid.uuid4(),
                        condominium_id=condo.id,
                        budget_id=budget.id,
                        category=category,
                        month=date(year, m, 1),
                        amount=monthly,
                    )
                )
    await session.flush()


async def seed_adhesion(session: AsyncSession) -> None:
    """D128: Jardim das Acácias has its (fictitious) adhesion term registered, so it is "apto a
    operar"; Mirante do Vale stays in implantation (no term, no bank statement) as the
    example of "Continuar uma implantação"."""
    from datetime import UTC, datetime

    from app.db.models import AdhesionTerm, Document
    from app.implantation import TERM_VERSION

    condo = await session.scalar(
        select(Condominium).where(Condominium.slug == "jardim-das-acacias")
    )
    if condo is None:
        return
    if await session.scalar(select(AdhesionTerm.id).where(AdhesionTerm.condominium_id == condo.id)):
        return
    doc = Document(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        doc_type="outro",
        storage_key=f"cond/{condo.id}/seed/termo-de-adesao-ficticio.pdf",
        sha256=hashlib.sha256(b"termo-de-adesao-ficticio").hexdigest(),
        original_filename="termo-de-adesao-ficticio.pdf",
        mime_type="application/pdf",
        origin="upload",
        extraction_status="done",
        extracted={},
        field_confidence={},
        needs_review=False,
        review_reasons=[],
    )
    session.add(doc)
    await session.flush()
    session.add(
        AdhesionTerm(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            version=TERM_VERSION,
            document_id=doc.id,
            accepted_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        )
    )
    await session.flush()
