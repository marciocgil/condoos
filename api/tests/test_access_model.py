"""Access model of migration 0011 (D73, D77; docs/data-model.md §8): CondoOS staff reach only
the condominiums they are assigned to, temporary and revoked accesses stop at the next
request, reserved roles grant nothing, the manager reviews only when the condominium allows,
and reviewing is kept apart from approving."""

import random
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.auth.rbac import REVIEW_PERMISSIONS, ROLE_PERMISSIONS, Permission
from app.core.time import local_today
from app.db.enums import PlatformRole, Role
from app.db.models import (
    AppUser,
    CondoAssignment,
    Condominium,
    Finding,
    Membership,
    PlatformRoleGrant,
)
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import (
    ADMIN_CONDOOS,
    GERENTE,
    REVISORA,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

MIRANTE, ACACIAS = "mirante-do-vale", "jardim-das-acacias"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def _scope_ids(admin_engine: AsyncEngine, email: str) -> set[uuid.UUID]:
    async with admin_engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT unnest(app_accessible_condominium_ids(id)) FROM app_user WHERE email = :e"
            ),
            {"e": email},
        )
        return {r[0] for r in rows}


async def _new_user(admin_engine: AsyncEngine, prefix: str) -> tuple[uuid.UUID, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@condoos.example.com"
    uid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(AppUser(id=uid, name=f"Pessoa {prefix}", email=email, is_active=True))
    return uid, email


@pytest.fixture
async def finding_in_review(admin_engine: AsyncEngine) -> AsyncIterator[uuid.UUID]:
    """A serious finding awaiting review in Mirante, in a month no other test looks at."""
    mirante = await condo_id(admin_engine, MIRANTE)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=mirante,
                rule_code="R01",
                severity="alta",
                title="Achado de teste do modelo de acesso",
                explanation="Indício para verificação.",
                amount_at_risk=Decimal("100.00"),
                status="aguardando_validacao",
                evidence=[],
                rule_inputs={},
                competence=date(2020, 1, 1),
                dedupe_key=f"test-access-{fid}",
            )
        )
    yield fid


# --------------------------------------------------------------------------- staff scope


async def test_reviewer_reaches_only_assigned_condominium(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    acacias = await condo_id(admin_engine, ACACIAS)
    assert await _scope_ids(admin_engine, REVISORA) == {mirante}
    async with _client() as c:
        await login(c, mailer, REVISORA)
        me = (await c.get("/me")).json()
        assert me["platform_roles"] == ["condoos_reviewer"]
        assert me["management_companies"] == []
        [condo] = me["condominiums"]
        assert condo["id"] == str(mirante) and condo["roles"] == ["condoos_reviewer"]
        assert "validate_finding" in condo["permissions"]
        assert "approve_in_condo" not in condo["permissions"]
        assert (await c.get(f"/condominiums/{mirante}/expenses")).status_code == 200
        assert (await c.get(f"/condominiums/{acacias}/expenses")).status_code == 404
        # The queue and the portfolio list only the assigned condominium.
        assert {q["condominium_id"] for q in (await c.get("/queue")).json()} <= {str(mirante)}
        rows = (await c.get("/portfolio")).json()["condominiums"]
        assert [r["id"] for r in rows] == [str(mirante)]


async def test_platform_role_without_assignment_reaches_nothing(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    uid, email = await _new_user(admin_engine, "admin-sem-atribuicao")
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            PlatformRoleGrant(
                id=uuid.uuid4(), user_id=uid, role=PlatformRole.CONDOOS_ADMIN, reason="teste"
            )
        )
    mirante = await condo_id(admin_engine, MIRANTE)
    assert await _scope_ids(admin_engine, email) == set()
    async with _client() as c:
        await login(c, mailer, email)
        assert (await c.get("/me")).json()["condominiums"] == []
        assert (await c.get(f"/condominiums/{mirante}")).status_code == 404


async def test_assignment_revoked_expired_or_role_revoked_cuts_access(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """Admin assigns a reviewer through the API; removing it, letting it expire or revoking
    the platform role each cut the open session at the next request."""
    mirante = await condo_id(admin_engine, MIRANTE)
    uid, email = await _new_user(admin_engine, "revisor")
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            PlatformRoleGrant(
                id=uuid.uuid4(), user_id=uid, role=PlatformRole.CONDOOS_REVIEWER, reason="teste"
            )
        )
    base = f"/condominiums/{mirante}"
    async with _client() as admin, _client() as person:
        await login(admin, mailer, ADMIN_CONDOOS)
        r = await admin.post(
            f"{base}/assignments",
            json={"email": email, "platform_role": "condoos_reviewer", "reason": "Piloto Mirante"},
        )
        assert r.status_code == 201, r.text
        assignment = r.json()["id"]
        listed = (await admin.get(f"{base}/assignments")).json()
        assert {a["email"] for a in listed if a["active"]} >= {email, ADMIN_CONDOOS}

        await login(person, mailer, email)
        assert (await person.get(f"{base}/expenses")).status_code == 200

        # 1. removed by the admin
        assert (await admin.delete(f"{base}/assignments/{assignment}")).status_code == 200
        assert (await person.get(f"{base}/expenses")).status_code == 404

        # 2. assigned again, then expired
        r = await admin.post(
            f"{base}/assignments",
            json={"email": email, "platform_role": "condoos_reviewer", "reason": "De volta"},
        )
        assert r.status_code == 201 and r.json()["id"] == assignment  # same row, reactivated
        assert (await person.get(f"{base}/expenses")).status_code == 200
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CondoAssignment)
                .where(CondoAssignment.id == uuid.UUID(assignment))
                .values(valid_until=datetime.now(UTC) - timedelta(minutes=1))
            )
        assert (await person.get(f"{base}/expenses")).status_code == 404

        # 3. active assignment, platform role revoked
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CondoAssignment)
                .where(CondoAssignment.id == uuid.UUID(assignment))
                .values(valid_until=None)
            )
        assert (await person.get(f"{base}/expenses")).status_code == 200
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(PlatformRoleGrant)
                .where(PlatformRoleGrant.user_id == uid)
                .values(revoked_at=datetime.now(UTC))
            )
        assert (await person.get(f"{base}/expenses")).status_code == 404


async def test_only_staff_with_the_role_can_be_assigned(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    _, email = await _new_user(admin_engine, "sem-papel")
    await login(client, mailer, ADMIN_CONDOOS)
    r = await client.post(
        f"/condominiums/{mirante}/assignments",
        json={"email": email, "platform_role": "condoos_reviewer", "reason": "Tentativa"},
    )
    assert r.status_code == 422 and "papel CondoOS" in r.json()["detail"]
    # Neither the manager nor the síndica manage CondoOS staff.
    for who in (GERENTE, SINDICA_MIRANTE):
        await login(client, mailer, who)
        assert (await client.get(f"/condominiums/{mirante}/assignments")).status_code == 403


async def test_admin_creates_direct_condominium_and_is_assigned(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from app.core.br import generate_cnpj

    await login(client, mailer, ADMIN_CONDOOS)
    slug = f"direto-{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/portfolio/condominiums",
        json={
            "condominium": {
                "name": "Residencial Contratante Direto",
                "slug": slug,
                "cnpj": generate_cnpj(random.Random()),
                "units": 40,
                "address": "Rua das Palmeiras, 100, São Paulo, SP",
                "retention_years": 5,
                "approval_limits": {"default": "3000.00", "by_category": {}},
            },
            "board": [
                {"name": "Helena Castro Viana", "position": "sindico", "term_start": "2026-01-01"}
            ],
        },
    )
    assert r.status_code == 201, r.text
    cid = uuid.UUID(r.json()["id"])
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.get(Condominium, cid)
    assert condo is not None
    assert condo.management_company_id is None and not condo.management_company_reviews
    assert condo.timezone == "America/Sao_Paulo"
    roles = {c["id"]: c["roles"] for c in (await client.get("/me")).json()["condominiums"]}
    assert roles[str(cid)] == ["condoos_admin"]
    # The management company's manager does not see it.
    await login(client, mailer, GERENTE)
    assert str(cid) not in {c["id"] for c in (await client.get("/me")).json()["condominiums"]}


# --------------------------------------------------------------------------- memberships


async def test_temporary_access_expires_and_invitation_is_accepted(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    email = f"temporaria-{uuid.uuid4().hex[:8]}@mirante.example.com"
    base = f"/condominiums/{mirante}"
    until = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    async with _client() as manager, _client() as person:
        await login(manager, mailer, GERENTE)
        r = await manager.post(
            f"{base}/members",
            json={
                "name": "Pessoa Temporária",
                "email": email,
                "role": "conselheiro",
                "expires_at": until,
            },
        )
        assert r.status_code == 201, r.text
        members = (await manager.get(f"{base}/settings")).json()["members"]
        row = next(m for m in members if m["email"] == email)
        assert row["status"] == "convidado" and row["expires_at"] is not None

        await login(person, mailer, email)
        assert (await person.get(f"{base}/expenses")).status_code == 200
        members = (await manager.get(f"{base}/settings")).json()["members"]
        assert next(m for m in members if m["email"] == email)["status"] == "ativo"

        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(Membership)
                .where(Membership.id == uuid.UUID(r.json()["id"]))
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
        assert (await person.get(f"{base}/expenses")).status_code == 404
        members = (await manager.get(f"{base}/settings")).json()["members"]
        assert email not in {m["email"] for m in members}
        # A past end date is refused.
        r2 = await manager.post(
            f"{base}/members",
            json={
                "name": "Pessoa Temporária",
                "email": email,
                "role": "conselheiro",
                "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        )
        assert r2.status_code == 422


async def test_removed_access_is_kept_as_history_and_can_be_granted_again(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    email = f"historico-{uuid.uuid4().hex[:8]}@mirante.example.com"
    base = f"/condominiums/{mirante}"
    await login(client, mailer, GERENTE)
    body = {"name": "Pessoa Histórico", "email": email, "role": "conselheiro"}
    first = (await client.post(f"{base}/members", json=body)).json()["id"]
    assert (await client.delete(f"{base}/members/{first}")).status_code == 200
    assert (await client.delete(f"{base}/members/{first}")).status_code == 404
    async with sessionmaker_for(admin_engine)() as s:
        row = await s.get(Membership, uuid.UUID(first))
    assert row is not None and row.revoked_at is not None  # kept, not deleted
    again = await client.post(f"{base}/members", json=body)
    assert again.status_code == 201 and again.json()["id"] == first


async def test_reserved_roles_grant_nothing(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    for role in (Role.ZELADOR, Role.FORNECEDOR, Role.MORADOR):
        assert ROLE_PERMISSIONS[role] == frozenset()
    mirante = await condo_id(admin_engine, MIRANTE)
    uid, email = await _new_user(admin_engine, "zelador")
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(Membership(id=uuid.uuid4(), user_id=uid, condominium_id=mirante, role="zelador"))
    async with _client() as c:
        await login(c, mailer, email)
        [condo] = (await c.get("/me")).json()["condominiums"]
        assert condo["roles"] == ["zelador"] and condo["permissions"] == []
        assert (await c.get(f"/condominiums/{mirante}/expenses")).status_code == 403
    # Staff roles never go into memberships.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Membership(id=uuid.uuid4(), user_id=uid, condominium_id=mirante, role="condoos_admin")
        )
        with pytest.raises(Exception, match="ck_membership_role_valid"):
            await s.flush()


# --------------------------------------------------------------------------- who reviews


async def test_manager_reviews_only_when_the_condominium_allows(
    mailer: MemoryMailer, admin_engine: AsyncEngine, finding_in_review: uuid.UUID
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    base = f"/condominiums/{mirante}/findings/{finding_in_review}"

    async def allow(value: bool) -> None:
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(Condominium)
                .where(Condominium.id == mirante)
                .values(management_company_reviews=value)
            )

    async with _client() as manager, _client() as reviewer:
        await login(manager, mailer, GERENTE)
        await login(reviewer, mailer, REVISORA)
        assert "validar" in (await manager.get(base)).json()["allowed_actions"]
        await allow(False)
        try:
            detail = await manager.get(base)
            assert detail.status_code == 200  # still sees it (view_pending_findings)
            assert detail.json()["allowed_actions"] == []
            r = await manager.post(f"{base}/decisions", json={"action": "validar"})
            assert r.status_code == 403
            queue = (await manager.get("/queue")).json()
            assert str(finding_in_review) not in {q["id"] for q in queue}
            assert str(finding_in_review) in {
                q["id"] for q in (await reviewer.get("/queue")).json()
            }
            r = await reviewer.post(f"{base}/decisions", json={"action": "validar"})
            assert r.status_code == 200 and r.json()["status"] == "publicado"
        finally:
            await allow(True)


async def test_review_is_kept_apart_from_approval() -> None:
    """CB-017: no role both reviews and approves in the condominium."""
    for role, perms in ROLE_PERMISSIONS.items():
        assert not (perms & REVIEW_PERMISSIONS and Permission.APPROVE_IN_CONDO in perms), role
    assert Permission.APPROVE_IN_CONDO in ROLE_PERMISSIONS[Role.SINDICO]
    assert Permission.REVIEW_OPPORTUNITY in ROLE_PERMISSIONS[Role.CONDOOS_REVIEWER]
    assert Permission.REVIEW_OPPORTUNITY not in ROLE_PERMISSIONS[Role.GERENTE]
    assert Permission.MANAGE_PLATFORM not in ROLE_PERMISSIONS[Role.GERENTE]


# --------------------------------------------------------------------------- time zone


async def test_condominium_time_zone(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    await login(client, mailer, GERENTE)
    profile = (await client.get(f"/condominiums/{mirante}/settings")).json()["profile"]
    assert profile["timezone"] == "America/Sao_Paulo"
    body = {k: profile[k] for k in ("name", "units", "address", "retention_years")}
    r = await client.put(
        f"/condominiums/{mirante}/profile", json={**body, "timezone": "Marte/Base"}
    )
    assert r.status_code == 422
    r = await client.put(
        f"/condominiums/{mirante}/profile", json={**body, "timezone": "America/Manaus"}
    )
    assert r.status_code == 200
    try:
        profile = (await client.get(f"/condominiums/{mirante}/settings")).json()["profile"]
        assert profile["timezone"] == "America/Manaus"
    finally:
        await client.put(
            f"/condominiums/{mirante}/profile", json={**body, "timezone": "America/Sao_Paulo"}
        )
    # At 23:30 in São Paulo it is already tomorrow in UTC; "today" follows the condominium.
    assert local_today("Pacific/Kiritimati") >= local_today("Pacific/Pago_Pago")
    assert local_today("Zona/Inexistente") == local_today("America/Sao_Paulo")


async def test_staff_assignment_table_is_isolated(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        rows = list(await s.scalars(select(CondoAssignment)))
    assert rows and all(r.condominium_id for r in rows)


async def test_first_admin_on_an_empty_database(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """Production starts with no one: the operator adds a person, grants the admin role and
    the person signs in seeing no condominium until creating or being assigned one."""
    from app.platform import PlatformError, add_person, grant_role

    email = f"primeiro-admin-{uuid.uuid4().hex[:6]}@condoos.example.com"
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        user = await add_person(s, email=email.upper(), name=" Primeira Admin ")
        await grant_role(s, user=user, role=PlatformRole.CONDOOS_ADMIN, reason="Implantação")
    async with sessionmaker_for(admin_engine)() as s:
        with pytest.raises(PlatformError):
            await add_person(s, email=email, name="De novo")
        with pytest.raises(PlatformError):
            await add_person(s, email="sem-arroba", name="X")
    async with _client() as c:
        await login(c, mailer, email)
        me = (await c.get("/me")).json()
        assert me["platform_roles"] == ["condoos_admin"] and me["condominiums"] == []
