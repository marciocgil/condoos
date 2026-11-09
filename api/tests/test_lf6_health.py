"""LF6-a (D109): change of síndico, capability history and rollback, gate LG6.

A new condominium (so the seed's síndica is untouched) goes through: síndica A enters,
approves two actions, leaves; her approvals go back to approval, C7 waits for the next
síndico, the history records the regression; síndica B enters, C7 comes back, B approves.
An approval whose approver's access expired is caught at dispatch and by the daily check.
"""

import random
import uuid
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.actions import APPROVER_GONE, dispatch_job
from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.core.time import utcnow
from app.db.models import ActionRequest, AuditLog, Job, Membership, OutboxEvent
from app.db.session import sessionmaker_for
from app.launch.health import (
    CAPABILITY_EVENT,
    HEALTH_JOB,
    health_job,
    record_capability_changes,
)
from tests.helpers import ADMIN_CONDOOS, login
from tests.test_actions import _body, _client, _kinds, _outbox


async def _c7(client: httpx.AsyncClient, cid: str) -> dict[str, Any]:
    body = (await client.get(f"/condominiums/{cid}/launch")).json()
    return next(r for r in body["readiness"] if r["key"] == "C7")


async def _record(admin_engine: AsyncEngine, cid: str, reason: str) -> list[dict[str, Any]]:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        return await record_capability_changes(s, uuid.UUID(cid), reason=reason)


async def _membership(admin_engine: AsyncEngine, cid: str, email: str) -> Membership:
    async with sessionmaker_for(admin_engine)() as s:
        from app.db.models import AppUser

        m = await s.scalar(
            select(Membership)
            .join(AppUser, AppUser.id == Membership.user_id)
            .where(Membership.condominium_id == uuid.UUID(cid), AppUser.email == email)
        )
        assert m is not None
        return m


async def _approve(who: httpx.AsyncClient, url: str) -> dict[str, Any]:
    got = (await who.get(url)).json()
    r = await who.post(
        f"{url}/decisions", json={"action": "aprovar", "payload_hash": got["payload_hash"]}
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


async def test_change_of_sindico_voids_approvals_and_c7_rolls_back_and_forth(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    tag = uuid.uuid4().hex[:8]
    a_email = f"sindica.a.{tag}@troca.example.com"
    b_email = f"sindico.b.{tag}@troca.example.com"
    async with _client() as fabio, _client() as a, _client() as b:
        await login(fabio, mailer, ADMIN_CONDOOS)
        r = await fabio.post(
            "/portfolio/condominiums",
            json={
                "condominium": {
                    "name": f"Residencial Troca {tag} (fictício)",
                    "slug": f"troca-{tag}",
                    "cnpj": generate_cnpj(random.Random(tag)),
                    "units": 30,
                    "address": "Rua Fictícia da Troca, 5 — Cidade Modelo/SP",
                    "approval_limits": {"default": "5000.00", "by_category": {}},
                },
                "board": [
                    {
                        "name": "Síndica A",
                        "position": "sindico",
                        "term_start": "2025-01-01",
                        "email": a_email,
                    }
                ],
            },
        )
        assert r.status_code == 201, r.text
        cid = r.json()["id"]

        # Before anyone enters, C7 waits for the síndico; the first check is the baseline.
        c7 = await _c7(fabio, cid)
        assert c7["state"] == "analise_parcial"
        assert any("Nenhum síndico" in m for m in c7["missing"])
        first = await _record(admin_engine, cid, "diaria")
        assert {c["key"] for c in first} >= {"C1", "C7"} and all(c["from"] is None for c in first)
        assert await _record(admin_engine, cid, "diaria") == []  # idempotent

        await login(a, mailer, a_email)  # A enters: C7 works
        assert (await _c7(a, cid))["state"] == "supervisionada"
        (change,) = await _record(admin_engine, cid, "diaria")
        assert (change["key"], change["from"], change["to"]) == (
            "C7",
            "analise_parcial",
            "supervisionada",
        )

        # Two actions approved by A: one still queued, one handed to a person.
        base = f"/condominiums/{cid}/actions"
        urls = []
        for _ in range(2):
            created = await fabio.post(base, json=_body())
            assert created.status_code == 201, created.text
            urls.append(f"{base}/{created.json()['id']}")
            await _approve(a, urls[-1])
        handed_id = urls[1].rsplit("/", 1)[1]
        (event,) = await _outbox(admin_engine, handed_id)
        async with sessionmaker_for(worker_engine)() as s, s.begin():
            await dispatch_job(s, {"idempotency_key": event.idempotency_key})
        assert (await a.get(urls[1])).json()["status"] == "aguardando_execucao_manual"

        # A leaves (her access is revoked, never deleted).
        ma = await _membership(admin_engine, cid, a_email)
        r = await fabio.delete(f"/condominiums/{cid}/members/{ma.id}")
        assert r.status_code == 200, r.text
        assert "2 ações aprovadas por essa pessoa voltaram para aprovação" in r.json()["message"]
        for url in urls:
            got = (await fabio.get(url)).json()
            assert got["status"] == "aguardando_aprovacao"
            assert got["history"][-1]["comment"] == APPROVER_GONE
            assert (await _kinds(admin_engine, url.rsplit("/", 1)[1]))[-1] == "invalidar"
        queued_id = urls[0].rsplit("/", 1)[1]
        assert {e.status for e in await _outbox(admin_engine, queued_id)} == {"cancelado"}
        # Residual access denied: A's open session no longer reaches the condominium.
        assert (await a.get(f"/condominiums/{cid}")).status_code == 404
        # C7 rolled back, and the history says when and why.
        c7 = await _c7(fabio, cid)
        assert c7["state"] == "analise_parcial"
        hist = (await fabio.get(f"/condominiums/{cid}/launch/history")).json()
        assert hist[0]["key"] == "C7" and hist[0]["to"] == "analise_parcial"
        assert hist[0]["reason"] == "Troca de síndico"

        # B becomes síndico and enters: C7 is back; B approves the version B sees.
        r = await fabio.post(
            f"/condominiums/{cid}/members",
            json={"name": "Síndico B", "email": b_email, "role": "sindico"},
        )
        assert r.status_code == 201, r.text
        await login(b, mailer, b_email)
        assert (await _c7(b, cid))["state"] == "supervisionada"
        # B's first login queued a check of this condominium; the worker records C7 back.
        async with sessionmaker_for(admin_engine)() as s:
            job = await s.scalar(
                select(Job).where(Job.job_type == HEALTH_JOB, Job.condominium_id == uuid.UUID(cid))
            )
            assert job is not None and job.payload["reason"] == "acesso"
        async with sessionmaker_for(worker_engine)() as s, s.begin():
            await health_job(s, job.payload)
        hist = (await fabio.get(f"/condominiums/{cid}/launch/history")).json()
        assert (hist[0]["key"], hist[0]["to"], hist[0]["reason"]) == (
            "C7",
            "supervisionada",
            "Mudança de acesso",
        )
        approved = await _approve(b, urls[0])
        assert approved["status"] == "enfileirada"

        # B's access expires before the dispatch: the dispatcher sends it back for approval.
        mb = await _membership(admin_engine, cid, b_email)
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(Membership)
                .where(Membership.id == mb.id)
                .values(expires_at=utcnow() - timedelta(minutes=1))
            )
        pending = [e for e in await _outbox(admin_engine, queued_id) if e.status == "pendente"]
        (event,) = pending
        async with sessionmaker_for(worker_engine)() as s, s.begin():
            await dispatch_job(s, {"idempotency_key": event.idempotency_key})
        async with sessionmaker_for(admin_engine)() as s:
            req = await s.get(ActionRequest, uuid.UUID(queued_id))
            assert req is not None and req.status == "aguardando_aprovacao"
            assert req.approved_by_user_id is None
            ev = await s.get(OutboxEvent, event.id)
            assert ev is not None and ev.status == "bloqueado" and ev.last_error == APPROVER_GONE


async def test_daily_check_records_history_once_and_isolated(
    admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await health_job(s, {})
    async with sessionmaker_for(admin_engine)() as s:
        before = len(
            list(await s.scalars(select(AuditLog.id).where(AuditLog.action == CAPABILITY_EVENT)))
        )
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await health_job(s, {})  # nothing changed since: nothing new
    async with sessionmaker_for(admin_engine)() as s:
        rows = list(await s.scalars(select(AuditLog).where(AuditLog.action == CAPABILITY_EVENT)))
        assert len(rows) == before
        assert all(r.condominium_id is not None and r.details.get("key") for r in rows)


async def test_history_of_another_condominium_is_404(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from tests.helpers import SINDICA_MIRANTE, condo_id

    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/launch/history")).status_code == 404
