"""Gate G1 (CB-003, CB-004): denied accesses are recorded, and removed access stops working
on the very next request of an already open session (SEC-10)."""

import uuid

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AppUser, AuditLog
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import CONSELHEIRO_ACACIAS, GERENTE, SINDICA_ACACIAS, condo_id, login


async def _user_id(admin_engine: AsyncEngine, email: str) -> uuid.UUID:
    async with sessionmaker_for(admin_engine)() as s:
        uid = await s.scalar(select(AppUser.id).where(AppUser.email == email))
    assert uid is not None
    return uid


async def _events(admin_engine: AsyncEngine, action: str, actor: uuid.UUID) -> list[AuditLog]:
    async with sessionmaker_for(admin_engine)() as s:
        rows = await s.scalars(
            select(AuditLog)
            .where(AuditLog.action == action, AuditLog.actor_user_id == actor)
            .order_by(AuditLog.created_at)
        )
        return list(rows)


async def test_other_condominium_is_404_and_recorded(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    ana = await _user_id(admin_engine, SINDICA_ACACIAS)
    before = len(await _events(admin_engine, "security.access_denied", ana))
    await login(client, mailer, SINDICA_ACACIAS)

    unknown = uuid.uuid4()
    assert (await client.get(f"/condominiums/{mirante}/expenses")).status_code == 404
    assert (await client.get(f"/condominiums/{unknown}/findings")).status_code == 404

    events = (await _events(admin_engine, "security.access_denied", ana))[before:]
    assert [e.details["requested_condominium_id"] for e in events] == [str(mirante), str(unknown)]
    first = events[0]
    assert first.condominium_id is None  # the requested id may not exist: kept in details only
    assert first.details["route"] == "/condominiums/{condominium_id}/expenses"
    assert first.details["method"] == "GET"
    # ids and codes only: no e-mail, name or query string in the trail
    assert SINDICA_ACACIAS not in str(first.details)
    assert set(first.details) == {"requested_condominium_id", "method", "route"}


async def test_role_without_permission_is_403_and_recorded(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    bruno = await _user_id(admin_engine, CONSELHEIRO_ACACIAS)
    before = len(await _events(admin_engine, "security.permission_denied", bruno))
    await login(client, mailer, CONSELHEIRO_ACACIAS)

    r = await client.put(f"/condominiums/{acacias}/settings", json={})
    assert r.status_code == 403

    events = (await _events(admin_engine, "security.permission_denied", bruno))[before:]
    assert len(events) == 1
    assert events[0].condominium_id == acacias
    assert events[0].details["permission"] == "configure"
    assert events[0].details["roles"] == ["conselheiro"]


async def test_removed_access_stops_an_open_session(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """SEC-10: the manager removes a login; the person's session, still valid, gets 404."""
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    email = f"revogada-{uuid.uuid4().hex[:8]}@acacias.example.com"
    transport = httpx.ASGITransport(app=create_app())
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://api.test") as manager,
        httpx.AsyncClient(transport=transport, base_url="http://api.test") as person,
    ):
        await login(manager, mailer, GERENTE)
        base = f"/condominiums/{acacias}"
        r = await manager.post(
            f"{base}/members", json={"name": "Pessoa Revogada", "email": email, "role": "sindico"}
        )
        assert r.status_code == 201, r.text
        membership_id = r.json()["id"]

        await login(person, mailer, email)
        assert (await person.get(f"{base}/expenses")).status_code == 200
        assert [c["id"] for c in (await person.get("/condominiums")).json()] == [str(acacias)]

        assert (await manager.delete(f"{base}/members/{membership_id}")).status_code == 200

        # Same cookie, same session row: access is recomputed on every request.
        assert (await person.get(f"{base}/expenses")).status_code == 404
        assert (await person.get(f"{base}/findings")).status_code == 404
        assert (await person.get("/condominiums")).json() == []

        uid = await _user_id(admin_engine, email)
        assert len(await _events(admin_engine, "security.access_denied", uid)) == 2


async def test_deactivated_user_session_is_rejected(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """SEC-10 for a deactivated person: the open session stops at the next request (401)."""
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    email = f"desativada-{uuid.uuid4().hex[:8]}@acacias.example.com"
    await login(client, mailer, GERENTE)
    r = await client.post(
        f"/condominiums/{acacias}/members",
        json={"name": "Pessoa Desativada", "email": email, "role": "conselheiro"},
    )
    assert r.status_code == 201, r.text

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as person:
        await login(person, mailer, email)
        assert (await person.get(f"/condominiums/{acacias}")).status_code == 200

        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(update(AppUser).where(AppUser.email == email).values(is_active=False))

        assert (await person.get(f"/condominiums/{acacias}")).status_code == 401
        assert (await person.get("/me")).status_code == 401
