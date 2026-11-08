"""D103 (LB-053): the CondoOS sends the document request by e-mail, the one thing the system
sends out — only after the síndico approves that exact version, checked again at dispatch,
with a link made at sending time (its token never stored), "accepted by the server" never
"delivered", the address masked afterwards, limits, pause and retries."""

import hashlib
import uuid
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.actions import dispatch_job
from app.auth.mailer import MemoryMailer
from app.db.models import ActionRequest, DelegationEvent, OutboxEvent
from app.db.session import sessionmaker_for
from tests.helpers import ADMIN_CONDOOS, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login

TO = "contabilidade@escritorio-ficticio.example.com"


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "recipient_name": f"Escritório Contábil {uuid.uuid4().hex[:6]} (fictício)",
        "recipient_role": "contador",
        "items": [{"label": "Balancete de outubro"}],
        "scope": "Documentos para a prestação de contas.",
        "due_date": (date.today() + timedelta(days=5)).isoformat(),
    }
    body.update(over)
    return body


async def _new_request(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    r = await client.post(base, json=_body())
    assert r.status_code == 201, r.text
    return dict(r.json())


async def _prepare(client: httpx.AsyncClient, base: str, rid: str, **over: Any) -> httpx.Response:
    body = {"to": TO, "note": "Obrigado!", "idempotency_key": f"mail-{uuid.uuid4()}"} | over
    return await client.post(f"{base}/{rid}/email", json=body)


async def _approve(client: httpx.AsyncClient, acacias: uuid.UUID, pending: dict[str, Any]) -> int:
    r = await client.post(
        f"/condominiums/{acacias}/actions/{pending['id']}/decisions",
        json={"action": "aprovar", "payload_hash": pending["payload_hash"]},
    )
    return r.status_code


async def _outbox(engine: AsyncEngine, action_id: str) -> OutboxEvent:
    async with sessionmaker_for(engine)() as s:
        event = await s.scalar(
            select(OutboxEvent).where(OutboxEvent.action_request_id == uuid.UUID(action_id))
        )
        assert event is not None
        return event


async def _dispatch(worker_engine: AsyncEngine, key: str) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await dispatch_job(s, {"idempotency_key": key})


async def _kinds(engine: AsyncEngine, rid: str) -> list[str]:
    async with sessionmaker_for(engine)() as s:
        rows = await s.scalars(
            select(DelegationEvent.kind)
            .where(DelegationEvent.request_id == uuid.UUID(rid))
            .order_by(DelegationEvent.created_at)
        )
        return list(rows)


async def test_sindico_approves_the_exact_email_and_the_condoos_sends_it(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/delegations"
    await login(client, mailer, SINDICA_ACACIAS)
    req = await _new_request(client, base)
    old = (await client.post(f"{base}/{req['id']}/link", json={})).json()["url"]
    old_token = old.rsplit("/", 1)[1]

    r = await _prepare(client, base, req["id"])
    assert r.status_code == 200, r.text
    pending = r.json()["email"]["pending"]
    assert pending["to"] == TO and pending["can_approve"] is True
    assert pending["reply_to"] == SINDICA_ACACIAS
    assert pending["from_name"].startswith("CondoOS em nome do")
    assert "{link}" in pending["body"] and "Recado do síndico: Obrigado!" in pending["body"]
    mailer.sent.clear()

    # Approving another version is refused; the generic adjust cannot change the e-mail.
    wrong = dict(pending, payload_hash="0" * 64)
    assert await _approve(client, acacias, wrong) == 409
    assert await _approve(client, acacias, pending) == 200
    assert mailer.sent == []  # approved, not sent yet: the dispatcher sends
    assert "email_aprovado" in await _kinds(admin_engine, req["id"])

    event = await _outbox(admin_engine, pending["id"])
    await _dispatch(worker_engine, event.idempotency_key)
    assert len(mailer.sent) == 1
    sent = mailer.sent[0]
    assert (sent.to, sent.reply_to) == (TO, SINDICA_ACACIAS)
    assert "{link}" not in sent.body and "/enviar/" in sent.body
    new_token = sent.body.split("/enviar/", 1)[1].split()[0]

    await client.post("/auth/logout")
    assert (await client.get(f"/public/delegations/{new_token}")).status_code == 200
    assert (await client.get(f"/public/delegations/{old_token}")).status_code == 404

    async with sessionmaker_for(admin_engine)() as s:
        action = await s.get(ActionRequest, uuid.UUID(pending["id"]))
        assert action is not None and action.status == "executada"
        stored = action.payload["email"]
        assert stored["to"] == "c***@escritorio-ficticio.example.com"
        assert stored["to_sha256"] == hashlib.sha256(TO.encode()).hexdigest()
        assert new_token not in str(action.payload)  # the token is never stored
        assert "não confirma a entrega" in (action.execution_note or "")
    receipt = (await _outbox(admin_engine, pending["id"])).receipt
    assert receipt is not None and receipt["message_id"] and receipt["accepted_at"]

    await login(client, mailer, SINDICA_ACACIAS)
    detail = (await client.get(f"{base}/{req['id']}")).json()
    assert detail["shared_at"] is not None and detail["email"]["pending"] is None
    assert detail["email"]["history"][0]["status"] == "executada"
    assert detail["email"]["history"][0]["to"].startswith("c***@")
    assert "email_enviado" in await _kinds(admin_engine, req["id"])
    # One e-mail per request per day.
    again = await _prepare(client, base, req["id"])
    assert again.status_code == 409 and "24 horas" in again.json()["detail"]


async def test_team_prepares_only_the_sindico_approves(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/delegations"
    await login(client, mailer, SINDICA_ACACIAS)
    req = await _new_request(client, base)  # authorised by the síndica

    await login(client, mailer, ADMIN_CONDOOS)
    r = await _prepare(client, base, req["id"])
    assert r.status_code == 200, r.text
    pending = r.json()["email"]["pending"]
    assert pending["can_approve"] is False
    assert pending["reply_to"] == SINDICA_ACACIAS  # replies go to the síndica
    assert await _approve(client, acacias, pending) == 403
    assert (await _prepare(client, base, req["id"])).status_code == 409  # one at a time

    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"{base}/{req['id']}")).status_code == 404
    await login(client, mailer, SINDICA_ACACIAS)
    assert await _approve(client, acacias, pending) == 200


async def test_rules_around_the_email(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/delegations"
    await login(client, mailer, ADMIN_CONDOOS)
    draft = await _new_request(client, base)  # a draft: the síndico has not authorised
    assert (await _prepare(client, base, draft["id"])).status_code == 409

    await login(client, mailer, SINDICA_ACACIAS)
    req = await _new_request(client, base)
    for bad in ("sem-arroba", "a@b.com, c@d.com", "x <y@z.com>"):
        assert (await _prepare(client, base, req["id"], to=bad)).status_code == 422
    assert (await _prepare(client, base, req["id"], note="x" * 501)).status_code == 422

    # The generic action form cannot create this type, nor carry an e-mail.
    generic = {
        "action_type": "pedido_documento.enviar_email",
        "title": "Tentativa pelo formulário genérico",
        "cost_cap": "0",
        "idempotency_key": f"gen-{uuid.uuid4()}",
        "payload": {
            "effect": "Enviar um e-mail qualquer pelo CondoOS.",
            "reason": "Testar se o formulário genérico deixa.",
            "executor": "CondoOS",
        },
    }
    r = await client.post(f"/condominiums/{acacias}/actions", json=generic)
    assert r.status_code == 422


async def test_pause_failure_and_closed_request_send_nothing(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/delegations"
    await login(client, mailer, SINDICA_ACACIAS)

    # Paused after the approval: the e-mail waits.
    req = await _new_request(client, base)
    pending = (await _prepare(client, base, req["id"])).json()["email"]["pending"]
    assert await _approve(client, acacias, pending) == 200
    pauses = f"/condominiums/{acacias}/automation-pauses"
    r = await client.post(
        pauses,
        json={"automation_type": "pedido_documento.enviar_email", "reason": "Teste da pausa"},
    )
    assert r.status_code == 201, r.text
    mailer.sent.clear()
    event = await _outbox(admin_engine, pending["id"])
    with pytest.raises(RuntimeError):
        await _dispatch(worker_engine, event.idempotency_key)
    assert mailer.sent == []
    pause_id = next(
        p["id"]
        for p in r.json()["active"]
        if p["automation_type"] == "pedido_documento.enviar_email"
    )
    await client.post(f"{pauses}/{pause_id}/resume")

    # The server refuses three times: blocked, nothing sent, the old link untouched.
    req2 = await _new_request(client, base)
    old = (await client.post(f"{base}/{req2['id']}/link", json={})).json()["url"]
    pending2 = (await _prepare(client, base, req2["id"])).json()["email"]["pending"]
    assert await _approve(client, acacias, pending2) == 200
    event2 = await _outbox(admin_engine, pending2["id"])
    mailer.fail = True
    try:
        for _ in range(3):
            await _dispatch(worker_engine, event2.idempotency_key)
    finally:
        mailer.fail = False
    assert mailer.sent == []
    detail = (await client.get(f"{base}/{req2['id']}")).json()
    assert detail["email"]["history"][0]["status"] == "bloqueada"
    assert "recusou o envio 3 vezes" in detail["email"]["history"][0]["note"]
    assert "email_falhou" in await _kinds(admin_engine, req2["id"])
    await client.post("/auth/logout")
    assert (await client.get(f"/public/delegations/{old.rsplit('/', 1)[1]}")).status_code == 200

    # Closed after the approval: blocked at dispatch.
    await login(client, mailer, SINDICA_ACACIAS)
    req3 = await _new_request(client, base)
    pending3 = (await _prepare(client, base, req3["id"])).json()["email"]["pending"]
    assert await _approve(client, acacias, pending3) == 200
    assert (await client.post(f"{base}/{req3['id']}/close")).status_code == 200
    mailer.sent.clear()  # the login above sent a magic link
    await _dispatch(worker_engine, (await _outbox(admin_engine, pending3["id"])).idempotency_key)
    assert mailer.sent == []
    async with sessionmaker_for(admin_engine)() as s:
        action = await s.get(ActionRequest, uuid.UUID(pending3["id"]))
        assert action is not None and action.status == "bloqueada"
