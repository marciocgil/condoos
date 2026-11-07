"""Leftovers of VS-01 (CB-023, CB-028): queue filter by deadline and the search used to link
records from the case screen. Read only; the link itself is covered in ``test_cases.py``."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.main import create_app
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

ACACIAS = "jardim-das-acacias"
ANYWAY = "Teste automatizado: assunto distinto"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _body(title: str, due_in_days: float, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "description": "Teste da fila.",
        "category": "administrativo",
        "severity": "baixa",
        "next_action": "Ligar para o fornecedor",
        "next_action_due_at": (datetime.now(UTC) + timedelta(days=due_in_days)).isoformat(),
        "resolution_criterion": "Retorno registrado no assunto",
        "create_anyway_reason": ANYWAY,
    }
    body.update(over)
    return body


async def test_queue_filters_by_deadline_category_and_severity(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    tag = uuid.uuid4().hex[:6]
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        soon = (await ana.post(base, json=_body(f"Prazo curto {tag}", 2))).json()
        later = (await ana.post(base, json=_body(f"Prazo longo {tag}", 30, category="obra"))).json()

        def ids(rows: list[dict[str, Any]]) -> set[str]:
            return {r["id"] for r in rows}

        week = ids((await ana.get(f"{base}?prazo=7dias")).json())
        assert soon["id"] in week and later["id"] not in week
        late = ids((await ana.get(f"{base}?prazo=atrasados")).json())
        assert soon["id"] not in late and later["id"] not in late
        obra = ids((await ana.get(f"{base}?categoria=obra")).json())
        assert later["id"] in obra and soon["id"] not in obra
        assert soon["id"] in ids((await ana.get(f"{base}?criticidade=baixa")).json())
        assert soon["id"] not in ids((await ana.get(f"{base}?criticidade=critica")).json())
        r = await ana.get(f"{base}?prazo=ontem")
        assert r.status_code == 422
        # The management view accepts the same filter.
        portfolio = ids((await ana.get("/portfolio/cases?prazo=7dias")).json())
        assert soon["id"] in portfolio and later["id"] not in portfolio


async def test_link_candidates_search_and_visibility(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    tag = uuid.uuid4().hex[:6]
    async with _client() as ana, _client() as carla, _client() as bruno:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(carla, mailer, SINDICA_MIRANTE)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        first = (await ana.post(base, json=_body(f"Elevador parado {tag}", 3))).json()
        second = (await ana.post(base, json=_body(f"Elevador barulho {tag}", 3))).json()
        url = f"{base}/{second['id']}/link-candidates"

        contracts = (await ana.get(f"{url}?tipo=contract")).json()
        assert contracts and all(c["target_type"] == "contract" for c in contracts)
        contract = contracts[0]
        # Link a contract to the first case: the second case sees it is already there.
        r = await ana.post(
            f"{base}/{first['id']}/links",
            json={"target_type": "contract", "target_id": contract["target_id"]},
        )
        assert r.status_code == 201, r.text
        again = (await ana.get(f"{url}?tipo=contract")).json()
        mark = next(c for c in again if c["target_id"] == contract["target_id"])
        assert mark["in_open_cases"] == [first["number"]]

        cases = (await ana.get(f"{url}?tipo=case&q={tag}")).json()
        assert [c["target_id"] for c in cases] == [first["id"]]  # never itself
        suppliers = (await ana.get(f"{url}?tipo=supplier")).json()
        assert suppliers
        assert (await ana.get(f"{url}?tipo=expense")).json()
        assert (await ana.get(f"{url}?tipo=opportunity")).json() == []

        # The board does not get findings still under review.
        everything = (await ana.get(f"{url}?tipo=finding")).json()
        board = (await bruno.get(f"{url}?tipo=finding")).json()
        assert {f["target_id"] for f in board} <= {f["target_id"] for f in everything}

        # Another condominium: 404.
        assert (await carla.get(f"{url}?tipo=contract")).status_code == 404
