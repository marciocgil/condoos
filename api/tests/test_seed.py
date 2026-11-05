from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.br import is_valid_cnpj
from app.db.models import Competence, Condominium, Contract, Expense, ManagementCompany, Supplier
from app.db.session import sessionmaker_for
from app.seed.data import LAST_MONTH, MONTHS, build_seed, months
from app.seed.run import load_seed


def test_seed_is_deterministic() -> None:
    a, b = build_seed(), build_seed()
    ids_a = [getattr(o, "id", None) for phase in a.objects for o in phase]
    ids_b = [getattr(o, "id", None) for phase in b.objects for o in phase]
    assert ids_a == ids_b


def test_seed_cnpjs_are_valid_and_unique() -> None:
    seed = build_seed()
    cnpjs = [
        o.cnpj
        for phase in seed.objects
        for o in phase
        if isinstance(o, ManagementCompany | Condominium | Supplier)
    ]
    assert all(is_valid_cnpj(c) for c in cnpjs)
    assert len(cnpjs) == len(set(cnpjs))


def test_seed_covers_twelve_months() -> None:
    ms = months()
    assert len(ms) == MONTHS == 12
    assert ms[-1] == LAST_MONTH


async def test_seed_contents(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        assert (await s.scalar(select(func.count()).select_from(ManagementCompany)) or 0) >= 1
        per_condo = dict(
            (
                await s.execute(
                    select(Condominium.slug, func.count(func.distinct(Expense.competence)))
                    .join(Expense, Expense.condominium_id == Condominium.id)
                    .where(Expense.origin == "seed")  # other tests add their own expenses
                    .group_by(Condominium.slug)
                )
            ).all()
        )
        assert per_condo["jardim-das-acacias"] == 12
        assert per_condo["mirante-do-vale"] == 12
        assert (await s.scalar(select(func.count()).select_from(Competence)) or 0) >= 24
        # Only the planted R05 case has an expense after its contract ended.
        late = await s.scalar(
            select(func.count())
            .select_from(Expense)
            .join(Contract, Contract.id == Expense.contract_id)
            .where(Contract.end_date.is_not(None), Expense.competence > Contract.end_date)
        )
        planted_r05 = [e for e in build_seed().expected if e.rule_code == "R05"]
        assert late == len(planted_r05) == 1
        min_amount = await s.scalar(select(func.min(Expense.amount)))
        assert min_amount is not None and min_amount > Decimal("0")


async def test_seed_load_is_idempotent(admin_engine: AsyncEngine) -> None:
    assert await load_seed(admin_engine) is False
