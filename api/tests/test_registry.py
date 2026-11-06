"""D67: registration screens — condominium data, board, logins, contracts, new condominium.
Manager only; audited; other condominium = 404."""

import random
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.db.models import AuditLog, Condominium, Contract, Job
from app.db.session import sessionmaker_for
from tests.helpers import ANALISTA, GERENTE, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login


async def _actions(admin_engine: AsyncEngine, cid: uuid.UUID) -> set[str]:
    async with sessionmaker_for(admin_engine)() as s:
        return set(await s.scalars(select(AuditLog.action).where(AuditLog.condominium_id == cid)))


async def test_manager_edits_profile_board_logins_and_contracts(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    base = f"/condominiums/{mirante}"
    await login(client, mailer, GERENTE)

    settings = (await client.get(f"{base}/settings")).json()
    profile = settings["profile"]
    r = await client.put(
        f"{base}/profile",
        json={
            **{k: profile[k] for k in ("name", "address")},
            "units": profile["units"] + 1,
            "retention_years": 6,
        },
    )
    assert r.status_code == 200
    assert (
        await client.put(f"{base}/profile", json={**profile, "retention_years": 2})
    ).status_code == 422

    r = await client.post(
        f"{base}/board",
        json={
            "full_name": "Teresa Lima Prado",
            "position": "conselheiro",
            "term_start": "2026-01-01",
        },
    )
    assert r.status_code == 201
    member_id = r.json()["id"]
    bad = await client.put(
        f"{base}/board/{member_id}",
        json={
            "full_name": "Teresa Lima Prado",
            "position": "conselheiro",
            "term_start": "2026-01-01",
            "term_end": "2025-01-01",
        },
    )
    assert bad.status_code == 422
    assert (await client.delete(f"{base}/board/{member_id}")).status_code == 200

    email = f"novo.{uuid.uuid4().hex[:6]}@mirante.example.com"
    r = await client.post(
        f"{base}/members", json={"name": "Nova Pessoa", "email": email, "role": "conselheiro"}
    )
    assert r.status_code == 201
    assert (
        await client.post(
            f"{base}/members", json={"name": "Nova Pessoa", "email": email, "role": "conselheiro"}
        )
    ).status_code == 409
    members = (await client.get(f"{base}/settings")).json()["members"]
    added = next(m for m in members if m["email"] == email)
    assert added["scope"] == "condominio" and added["id"]
    company_row = next(m for m in members if m["scope"] == "administradora")
    assert company_row["id"] is None  # company-wide accesses are not removed here
    assert (await client.delete(f"{base}/members/{added['id']}")).status_code == 200

    cnpj = generate_cnpj(random.Random(uuid.uuid4().hex))
    contract = {
        "supplier_cnpj": cnpj,
        "supplier_name": "Jardins Fictícios Ltda",
        "object": "Manutenção de jardins",
        "scope_items": ["poda", "adubação"],
        "monthly_value": "1.250,00",
        "adjustment_index": "IPCA",
        "adjustment_base_month": 4,
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
    }
    assert (
        await client.post(f"{base}/contracts", json={**contract, "adjustment_index": "OUTRO"})
    ).status_code == 422
    assert (
        await client.post(f"{base}/contracts", json={**contract, "supplier_cnpj": "11111111111111"})
    ).status_code == 422
    r = await client.post(f"{base}/contracts", json=contract)
    assert r.status_code == 201, r.text
    assert r.json()["monthly_value"] == "1250.00"
    cid = r.json()["id"]
    r = await client.put(f"{base}/contracts/{cid}", json={**contract, "monthly_value": "1300.00"})
    assert r.status_code == 200 and r.json()["monthly_value"] == "1300.00"

    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(Contract, uuid.UUID(cid))
        rechecks = (
            await s.scalars(
                select(Job).where(Job.job_type == "rules.evaluate", Job.condominium_id == mirante)
            )
        ).all()
    assert stored is not None and stored.adjustment_base_month == 4
    assert rechecks
    assert {
        "condominium.updated",
        "board.added",
        "board.removed",
        "member.added",
        "member.removed",
        "contract.created",
        "contract.updated",
    } <= await _actions(admin_engine, mirante)


async def test_only_manager_registers_and_other_condo_is_404(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    for email in (ANALISTA, SINDICA_ACACIAS):
        await client.post("/auth/logout")
        await login(client, mailer, email)
        r = await client.post(
            f"/condominiums/{acacias}/board",
            json={
                "full_name": "Fulano de Tal",
                "position": "conselheiro",
                "term_start": "2026-01-01",
            },
        )
        assert r.status_code == 403
    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    r = await client.put(
        f"/condominiums/{acacias}/profile",
        json={"name": "X Y Z", "units": 1, "address": "Rua Fictícia, 1", "retention_years": 5},
    )
    assert r.status_code == 404


async def test_manager_creates_a_condominium(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    tag = uuid.uuid4().hex[:6]
    name = f"Condomínio Novo {tag} (fictício)"
    body: dict[str, Any] = {
        "condominium": {
            "name": name,
            "slug": f"novo-{tag}",
            "cnpj": generate_cnpj(random.Random(tag)),
            "units": 30,
            "address": "Rua Fictícia, 99 — Cidade Modelo/SP",
            "approval_limits": {"default": "4000.00", "by_category": {}},
        },
        "board": [
            {
                "name": "Síndico Novo",
                "position": "sindico",
                "term_start": "2026-01-01",
                "email": f"sindico.{tag}@novo.example.com",
            }
        ],
    }
    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.post("/portfolio/condominiums", json=body)).status_code == 403
    await client.post("/auth/logout")
    await login(client, mailer, GERENTE)
    r = await client.post("/portfolio/condominiums", json=body)
    assert r.status_code == 201, r.text
    assert (
        await client.post("/portfolio/condominiums", json=body)
    ).status_code == 422  # never overwrites
    new_id = r.json()["id"]
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.get(Condominium, uuid.UUID(new_id))
    assert condo is not None and condo.management_company_id is not None
    names = {c["name"] for c in (await client.get("/portfolio")).json()["condominiums"]}
    assert name in names
