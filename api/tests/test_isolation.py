"""Multi-tenant isolation: between condominiums and between management companies.

Two layers are tested: the API (explicit filters + membership checks) and the database
(Row-Level Security applied to the application role).
"""

import random
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.db.models import (
    AppUser,
    Condominium,
    Expense,
    ManagementCompany,
    Membership,
)
from app.db.session import sessionmaker_for, set_tenant_scope
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

CONDO_ENDPOINTS = ["", "/expenses", "/contracts", "/findings", "/competences"]


async def test_sindica_sees_only_her_condominium(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, SINDICA_ACACIAS)

    listed = (await client.get("/condominiums")).json()
    assert [c["id"] for c in listed] == [str(acacias)]

    for suffix in CONDO_ENDPOINTS:
        own = await client.get(f"/condominiums/{acacias}{suffix}")
        assert own.status_code == 200, suffix
        other = await client.get(f"/condominiums/{mirante}{suffix}")
        assert other.status_code == 404, suffix  # 404, not 403: existence is not revealed

    expenses = (await client.get(f"/condominiums/{acacias}/expenses")).json()
    assert expenses
    async with sessionmaker_for(admin_engine)() as s:
        mirante_ids = {
            str(i)
            for i in await s.scalars(select(Expense.id).where(Expense.condominium_id == mirante))
        }
    assert not mirante_ids & {e["id"] for e in expenses}


async def test_unknown_condominium_is_404(client: httpx.AsyncClient, mailer: MemoryMailer) -> None:
    await login(client, mailer, SINDICA_MIRANTE)
    r = await client.get(f"/condominiums/{uuid.uuid4()}/expenses")
    assert r.status_code == 404


async def test_gerente_sees_whole_portfolio(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    await login(client, mailer, GERENTE)
    slugs = {c["slug"] for c in (await client.get("/condominiums")).json()}
    assert {"jardim-das-acacias", "mirante-do-vale"} <= slugs
    me = (await client.get("/me")).json()
    assert me["management_companies"][0]["roles"] == ["gerente"]


@pytest.fixture
async def other_company(admin_engine: AsyncEngine) -> dict[str, uuid.UUID]:
    """A second, unrelated management company with its own condominium and manager."""
    rng = random.Random()
    suffix = uuid.uuid4().hex[:8]
    company = ManagementCompany(
        id=uuid.uuid4(), name="Outra Administradora (fictícia)", cnpj=generate_cnpj(rng)
    )
    condo = Condominium(
        id=uuid.uuid4(),
        management_company_id=company.id,
        name="Condomínio Outro",
        slug=f"outro-{suffix}",
        cnpj=generate_cnpj(rng),
        units=10,
        address="Rua Inexistente, 1",
        approval_limits={},
        rule_params={},
        expense_categories=[],
        retention_years=5,
    )
    user = AppUser(
        id=uuid.uuid4(), name="Gerente Outra", email=f"gerente-{suffix}@outra.example.com"
    )
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(company)
        await s.flush()
        s.add_all([condo, user])
        await s.flush()
        s.add(Membership(user_id=user.id, management_company_id=company.id, role="gerente"))
        s.add(
            Expense(
                condominium_id=condo.id,
                competence=date(2026, 10, 1),
                issue_date=date(2026, 10, 2),
                amount=Decimal("123.45"),
                category="limpeza",
                description="Despesa de outra administradora",
            )
        )
    return {"company": company.id, "condo": condo.id}


async def test_isolation_between_management_companies(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    other_company: dict[str, uuid.UUID],
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, GERENTE)
    assert (await client.get(f"/condominiums/{other_company['condo']}")).status_code == 404
    listed = {c["id"] for c in (await client.get("/condominiums")).json()}
    assert str(other_company["condo"]) not in listed

    async with sessionmaker_for(admin_engine)() as s:
        email = await s.scalar(
            select(AppUser.email)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(Membership.management_company_id == other_company["company"])
        )
    assert email
    await client.post("/auth/logout")
    await login(client, mailer, email)
    assert (await client.get(f"/condominiums/{acacias}/expenses")).status_code == 404
    only = [c["id"] for c in (await client.get("/condominiums")).json()]
    assert only == [str(other_company["condo"])]


# ----------------------------------------------------------------- database layer (RLS)


async def test_rls_without_scope_returns_nothing(app_engine: AsyncEngine) -> None:
    async with sessionmaker_for(app_engine)() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(Expense)) == 0
        assert await s.scalar(select(func.count()).select_from(Condominium)) == 0


async def test_rls_filters_queries_without_where_clause(
    app_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [acacias])
        # Deliberately no WHERE: the database must still restrict the rows.
        condo_ids = set(await s.scalars(select(Expense.condominium_id).distinct()))
    assert condo_ids == {acacias}


async def test_rls_blocks_writes_into_another_condominium(
    app_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    with pytest.raises((DBAPIError, ProgrammingError)):
        async with sessionmaker_for(app_engine)() as s, s.begin():
            await set_tenant_scope(s, [acacias])
            s.add(
                Expense(
                    condominium_id=mirante,
                    competence=date(2026, 10, 1),
                    issue_date=date(2026, 10, 1),
                    amount=Decimal("1.00"),
                    category="limpeza",
                    description="tentativa indevida",
                )
            )
            await s.flush()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE decision SET comment = 'x'",
        "DELETE FROM decision",
        "DELETE FROM audit_log",
        "UPDATE review_policy SET reason = 'x'",
        "DELETE FROM review_policy",
        "UPDATE case_event SET reason = 'x'",
        "DELETE FROM case_event",
        "UPDATE savings_record SET amount = 0",
        "DELETE FROM savings_record",
        "UPDATE opportunity_review SET comment = 'x'",
        "DELETE FROM opportunity_review",
    ],
)
async def test_append_only_tables(app_engine: AsyncEngine, statement: str) -> None:
    with pytest.raises((DBAPIError, ProgrammingError), match="permission denied"):
        async with app_engine.begin() as conn:
            await conn.execute(text(statement))


async def test_conselheiro_is_read_only_in_permissions(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    perms = (await client.get("/me")).json()["condominiums"][0]["permissions"]
    assert "decide_finding" not in perms
    assert "comment_finding" in perms


async def test_every_tenant_table_has_rls(admin_engine: AsyncEngine) -> None:
    from app.db.models import RLS_TABLES

    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT c.relname FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid "
                "WHERE c.relrowsecurity AND p.polname = 'tenant_isolation'"
            )
        )
        protected = {r[0] for r in rows}
    assert set(RLS_TABLES) <= protected, set(RLS_TABLES) - protected
