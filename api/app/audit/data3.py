"""What the cycle-3 controls read (D124): contracts in force with their amendments and the
index table, approvals and acceptances, the formal approval of the accounts, funds and their
backing accounts, the budget and its notes, and the compliance obligations.

Loaded once per run, like the rest of ``AuditData``; values stay ``Decimal``.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.models import (
    AccountsApproval,
    Approval,
    BoardMember,
    Budget,
    BudgetLine,
    BudgetNote,
    Condominium,
    Contract,
    ContractAmendment,
    Expense,
    Fund,
    FundAccount,
    FundBalance,
)


@dataclass
class Cycle3:
    contracts: list[Contract] = field(default_factory=list)
    amendments: dict[uuid.UUID, list[ContractAmendment]] = field(default_factory=dict)
    index_table: dict[str, dict[date, Decimal]] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    limits_version: int | None = None
    rule_params: dict[str, Any] = field(default_factory=dict)
    approvals: dict[uuid.UUID, list[Approval]] = field(default_factory=dict)
    contract_expenses: dict[uuid.UUID, list[Expense]] = field(default_factory=dict)
    accounts_approvals: list[AccountsApproval] = field(default_factory=list)
    board: list[BoardMember] = field(default_factory=list)
    funds: list[Fund] = field(default_factory=list)
    fund_accounts: dict[uuid.UUID, set[uuid.UUID]] = field(default_factory=dict)
    fund_balances: dict[uuid.UUID, FundBalance] = field(default_factory=dict)
    previous_fund_balances: dict[uuid.UUID, FundBalance] = field(default_factory=dict)
    budget: Budget | None = None
    budget_lines: list[BudgetLine] = field(default_factory=list)
    budget_notes: list[BudgetNote] = field(default_factory=list)
    year_expenses: list[Expense] = field(default_factory=list)
    obligations: list[Any] = field(default_factory=list)  # compliance Row at the month end


async def load_cycle3(
    session: AsyncSession,
    condo: Condominium,
    first: date,
    last: date,
    today: date,
    expense_ids: list[uuid.UUID],
) -> Cycle3:
    from app.compliance import rows_for
    from app.condo_settings import settings_at
    from app.enrichment.indices import load_index_table
    from app.rules.contracts import amendments_by_contract

    out = Cycle3()
    out.contracts = list(
        await session.scalars(
            select(Contract)
            .where(Contract.condominium_id == condo.id, Contract.start_date <= last)
            .order_by(Contract.start_date, Contract.id)
        )
    )
    ids = [c.id for c in out.contracts]
    out.amendments = await amendments_by_contract(session, ids)
    out.index_table = await load_index_table(session)
    out.limits, out.rule_params, out.limits_version = await settings_at(session, condo, last)
    approvals: dict[uuid.UUID, list[Approval]] = defaultdict(list)
    for a in await session.scalars(
        select(Approval)
        .where(
            Approval.condominium_id == condo.id,
            Approval.expense_id.in_(expense_ids or [uuid.uuid4()]),
        )
        .order_by(Approval.approved_at, Approval.id)
    ):
        approvals[a.expense_id].append(a)
    out.approvals = dict(approvals)
    by_contract: dict[uuid.UUID, list[Expense]] = defaultdict(list)
    for e in await session.scalars(
        select(Expense)
        .where(
            Expense.condominium_id == condo.id,
            Expense.contract_id.in_(ids or [uuid.uuid4()]),
            Expense.competence <= first,
        )
        .order_by(Expense.competence, Expense.issue_date, Expense.id)
    ):
        assert e.contract_id is not None
        by_contract[e.contract_id].append(e)
    out.contract_expenses = dict(by_contract)

    out.accounts_approvals = list(
        await session.scalars(
            select(AccountsApproval)
            .where(
                AccountsApproval.condominium_id == condo.id,
                AccountsApproval.period_start <= first,
                AccountsApproval.period_end >= first,
            )
            .order_by(AccountsApproval.approved_on, AccountsApproval.created_at)
        )
    )
    out.board = list(
        await session.scalars(select(BoardMember).where(BoardMember.condominium_id == condo.id))
    )

    out.funds = list(
        await session.scalars(
            select(Fund).where(Fund.condominium_id == condo.id).order_by(Fund.name)
        )
    )
    accounts: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for fa in await session.scalars(
        select(FundAccount).where(FundAccount.condominium_id == condo.id)
    ):
        accounts[fa.fund_id].add(fa.bank_account_id)
    out.fund_accounts = dict(accounts)
    previous = add_months(first, -1)
    for fb in await session.scalars(
        select(FundBalance).where(
            FundBalance.condominium_id == condo.id,
            FundBalance.competence.in_([first, previous]),
        )
    ):
        target = out.fund_balances if fb.competence == first else out.previous_fund_balances
        target[fb.fund_id] = fb

    out.budget = await session.scalar(
        select(Budget)
        .where(Budget.condominium_id == condo.id, Budget.year == first.year)
        .order_by(Budget.version.desc())
        .limit(1)
    )
    if out.budget is not None:
        out.budget_lines = list(
            await session.scalars(select(BudgetLine).where(BudgetLine.budget_id == out.budget.id))
        )
    out.budget_notes = list(
        await session.scalars(
            select(BudgetNote)
            .where(BudgetNote.condominium_id == condo.id, BudgetNote.competence == first)
            .order_by(BudgetNote.created_at)
        )
    )
    out.year_expenses = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condo.id,
                Expense.competence.between(date(first.year, 1, 1), first),
            )
        )
    )

    out.obligations = await rows_for(session, condo.id, min(last, today))
    return out
