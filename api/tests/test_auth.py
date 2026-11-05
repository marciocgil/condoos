from datetime import timedelta

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.models import AuditLog, MagicLinkToken
from app.db.session import sessionmaker_for
from tests.helpers import SINDICA_ACACIAS, TOKEN_RE, login


async def test_unknown_email_gets_same_response_and_no_mail(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    r = await client.post("/auth/magic-link", json={"email": "ninguem@example.com"})
    assert r.status_code == 202
    assert mailer.sent == []


async def test_login_flow_sets_session_cookie(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    assert (await client.get("/me")).status_code == 401
    await login(client, mailer, SINDICA_ACACIAS.upper())  # e-mail is case-insensitive
    r = await client.get("/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == SINDICA_ACACIAS
    assert [c["slug"] for c in body["condominiums"]] == ["jardim-das-acacias"]
    assert body["condominiums"][0]["roles"] == ["sindico"]
    assert "http://web.test/auth/verify?token=" in mailer.sent[-1].body


async def test_magic_link_is_single_use(client: httpx.AsyncClient, mailer: MemoryMailer) -> None:
    await client.post("/auth/magic-link", json={"email": SINDICA_ACACIAS})
    match = TOKEN_RE.search(mailer.sent[-1].body)
    assert match
    token = match.group(1)
    assert (await client.post("/auth/verify", json={"token": token})).status_code == 200
    assert (await client.post("/auth/verify", json={"token": token})).status_code == 400


async def test_expired_magic_link_is_rejected(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    await client.post("/auth/magic-link", json={"email": SINDICA_ACACIAS})
    match = TOKEN_RE.search(mailer.sent[-1].body)
    assert match
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(MagicLinkToken)
            .where(MagicLinkToken.used_at.is_(None))
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
    r = await client.post("/auth/verify", json={"token": match.group(1)})
    assert r.status_code == 400


async def test_logout_revokes_session(client: httpx.AsyncClient, mailer: MemoryMailer) -> None:
    await login(client, mailer, SINDICA_ACACIAS)
    cookie = client.cookies.get("condoos_session")
    assert cookie
    assert (await client.post("/auth/logout")).status_code == 200
    client.cookies.set("condoos_session", cookie)  # replaying the old cookie must fail
    assert (await client.get("/me")).status_code == 401


async def test_login_is_audited(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    await login(client, mailer, SINDICA_ACACIAS)
    async with sessionmaker_for(admin_engine)() as s:
        actions = set(await s.scalars(select(AuditLog.action)))
    assert {"auth.magic_link_requested", "auth.login"} <= actions


async def test_magic_link_rate_limit(client: httpx.AsyncClient, mailer: MemoryMailer) -> None:
    for _ in range(5):
        await client.post("/auth/magic-link", json={"email": SINDICA_ACACIAS})
    assert len(mailer.sent) == 5
    await client.post("/auth/magic-link", json={"email": SINDICA_ACACIAS})
    assert len(mailer.sent) == 5
