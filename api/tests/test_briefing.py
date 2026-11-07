"""VS-04 (Plano Diretor §8; D82): the day's briefing from data.

Acceptance: it never claims what did not happen; it never mixes condominiums; when a source
fails, it says the briefing is partial. Also: versioned with its period, in the
condominium's time zone, read receipt, and each person sees only what they may see.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.briefing import Builder, purge
from app.core.time import local_today
from app.db.models import (
    AppUser,
    Briefing,
    CaseRecord,
    Condominium,
    Document,
    Finding,
    Opportunity,
)
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    condo_id,
    login,
)

ACACIAS, MIRANTE = "jardim-das-acacias", "mirante-do-vale"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _section(b: dict[str, Any], key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = next(s for s in b["sections"] if s["key"] == key)["items"]
    return items


def _refs(b: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (i["ref"]["type"], i["ref"]["id"]) for s in b["sections"] for i in s["items"] if i["ref"]
    }


async def _finding(admin_engine: AsyncEngine, slug: str, status: str, title: str) -> uuid.UUID:
    cid = await condo_id(admin_engine, slug)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=cid,
                rule_code="R01",
                severity="alta",
                title=title,
                explanation="Indício para verificação.",
                amount_at_risk=Decimal("99999.00"),
                status=status,
                evidence=[],
                rule_inputs={},
                competence=date(2020, 5, 1),
                dedupe_key=f"test-brief-{fid}",
            )
        )
    return fid


async def test_briefing_is_versioned_with_period_and_read_receipt(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    url = f"/condominiums/{acacias}/briefing"
    async with _client() as ana, _client() as bruno:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        first = (await ana.get(url)).json()
        again = (await ana.get(url)).json()
        assert again["id"] == first["id"]  # the same briefing all day until refreshed
        async with sessionmaker_for(admin_engine)() as s:
            condo = await s.get(Condominium, acacias)
        assert condo is not None
        assert first["local_date"] == local_today(condo.timezone).isoformat()
        assert first["timezone"] == "America/Sao_Paulo"
        assert [x["key"] for x in first["sections"]] == [
            "riscos",
            "decisoes",
            "andamento",
            "concluido",
            "agenda",
            "oportunidades",
            "dados",
        ]
        assert first["headline"].startswith(("Bom dia", "Boa tarde", "Boa noite"))
        # A section that fails is reported as partial instead of breaking the briefing; in
        # normal use only stale data may be partial, never a failing section (that would
        # hide a bug behind the safety net).
        assert {p["source"] for p in first["partial_sources"]} <= {"documentos", "extrato"}

        second = (await ana.post(f"{url}/refresh")).json()
        assert second["version"] == first["version"] + 1
        # The new period starts where the previous briefing ended.
        assert second["period_start"] == first["generated_at"]
        assert (await ana.get(url)).json()["id"] == second["id"]

        assert second["read_at"] is None
        r = await bruno.post(f"{url}/{second['id']}/read")  # someone else's briefing
        assert r.status_code == 404
        r = await ana.post(f"{url}/{second['id']}/read")
        assert r.status_code == 200
        assert (await ana.get(url)).json()["read_at"] is not None


async def test_briefing_lists_what_needs_the_person(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    published = await _finding(admin_engine, ACACIAS, "publicado", "Pagamento em dobro (briefing)")
    in_review = await _finding(
        admin_engine, ACACIAS, "aguardando_validacao", "Em revisão (briefing)"
    )
    base = f"/condominiums/{acacias}"
    async with _client() as ana, _client() as bruno, _client() as diego:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        await login(diego, mailer, GERENTE)
        # A case of Ana's whose next action is overdue.
        case = (
            await ana.post(
                f"{base}/cases",
                json={
                    "title": "Portão da garagem (briefing)",
                    "category": "seguranca",
                    "next_action": "Chamar a assistência",
                    "next_action_due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    "resolution_criterion": "Portão abrindo normalmente",
                    "create_anyway_reason": "Teste automatizado do briefing",
                },
            )
        ).json()
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CaseRecord)
                .where(CaseRecord.id == uuid.UUID(case["id"]))
                .values(next_action_due_at=datetime.now(UTC) - timedelta(hours=2))
            )

        b = (await ana.post(f"{base}/briefing/refresh")).json()
        risks = _section(b, "riscos")
        assert ("case", case["id"]) in {
            (i["ref"]["type"], i["ref"]["id"]) for i in risks if i["ref"]
        }
        assert ("finding", str(published)) in _refs(b)
        decide = {i["ref"]["id"] for i in _section(b, "decisoes") if i["ref"]}
        assert str(published) in decide  # the síndica decides findings
        assert str(in_review) not in str(b)  # under review: not for the board
        mine = {i["ref"]["id"] for i in _section(b, "andamento") if i["ref"]}
        assert case["id"] in mine

        council = (await bruno.post(f"{base}/briefing/refresh")).json()
        assert str(published) not in {
            i["ref"]["id"] for i in _section(council, "decisoes") if i["ref"]
        }
        assert str(in_review) not in str(council)

        manager = (await diego.post(f"{base}/briefing/refresh")).json()
        assert str(in_review) in {i["ref"]["id"] for i in _section(manager, "decisoes") if i["ref"]}


async def test_done_lists_only_recorded_events(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        await ana.post(f"{base}/briefing/refresh")  # opens a new period from now
        body = {
            "next_action": "Conferir",
            "resolution_criterion": "Conferido pelo síndico",
            "next_action_due_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "requires_evidence": False,
            "create_anyway_reason": "Teste automatizado do briefing",
        }
        resolved = (
            await ana.post(
                f"{base}/cases",
                json={**body, "title": "Resolvido (briefing)", "category": "atendimento"},
            )
        ).json()
        still_open = (
            await ana.post(
                f"{base}/cases",
                json={**body, "title": "Só aberto (briefing)", "category": "administrativo"},
            )
        ).json()
        url = f"{base}/cases/{resolved['id']}"
        for to in ("em_triagem", "em_planejamento", "em_execucao", "aguardando_validacao"):
            await ana.post(f"{url}/transitions", json={"to": to})
        r = await ana.post(
            f"{url}/transitions", json={"to": "resolvido", "reason": "Conferido no local."}
        )
        assert r.status_code == 200
        b = (await ana.post(f"{base}/briefing/refresh")).json()
        done = _section(b, "concluido")
        refs = {i["ref"]["id"] for i in done if i["ref"]}
        assert resolved["id"] in refs
        assert still_open["id"] not in refs  # opened is not done
        assert any("Resolvido por Ana" in i["detail"] for i in done)


async def test_condominiums_never_mix(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    mirante = await condo_id(admin_engine, MIRANTE)
    await _finding(admin_engine, MIRANTE, "publicado", "Só de Mirante (briefing)")
    async with _client() as ana, _client() as diego:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(diego, mailer, GERENTE)
        b = (await ana.post(f"/condominiums/{acacias}/briefing/refresh")).json()
        assert "Só de Mirante" not in str(b)
        assert (await ana.get(f"/condominiums/{mirante}/briefing")).status_code == 404
        # The manager gets one briefing per condominium; every ref belongs to its own.
        many = (await diego.get("/portfolio/briefing")).json()
        assert {x["condominium_id"] for x in many} >= {str(acacias), str(mirante)}
        owners: dict[str, type[Finding] | type[CaseRecord] | type[Opportunity]] = {
            "finding": Finding,
            "case": CaseRecord,
            "opportunity": Opportunity,
        }
        async with sessionmaker_for(admin_engine)() as s:
            for brief in many:
                for kind, rid in _refs(brief):
                    model = owners[kind]
                    row = await s.get(model, uuid.UUID(rid))
                    assert row is not None
                    assert str(getattr(row, "condominium_id", "")) == brief["condominium_id"]


async def test_failed_source_makes_the_briefing_partial(
    mailer: MemoryMailer, admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)

    async def broken(self: Builder) -> list[dict[str, Any]]:
        raise RuntimeError("agenda indisponível")

    monkeypatch.setattr(Builder, "agenda", broken)
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        r = await ana.post(f"/condominiums/{acacias}/briefing/refresh")
        assert r.status_code == 200
        b = r.json()
    assert "agenda" in {p["source"] for p in b["partial_sources"]}
    assert "parciais" in b["headline"]
    assert _section(b, "agenda") == []
    # The other sources still came out (the failure did not abort the transaction).
    assert _section(b, "dados")


async def test_stale_data_is_reported(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    """The test seed has no uploaded documents: the briefing says documents are stale."""
    acacias = await condo_id(admin_engine, ACACIAS)
    async with sessionmaker_for(admin_engine)() as s:
        uploads = await s.scalar(
            select(Document.id)
            .where(
                Document.condominium_id == acacias,
                Document.origin.in_(["upload", "email"]),
                Document.created_at > datetime.now(UTC) - timedelta(days=35),
            )
            .limit(1)
        )
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        b = (await ana.post(f"/condominiums/{acacias}/briefing/refresh")).json()
    titles = {i["title"] for i in _section(b, "dados")}
    assert titles == {"Documentos", "Extrato bancário", "Cobertura do mês"}  # LB-037
    coverage = next(i for i in _section(b, "dados") if i["title"] == "Cobertura do mês")
    assert "completo" not in coverage["detail"].lower()
    if uploads is None:
        assert "documentos" in {p["source"] for p in b["partial_sources"]}


async def test_retention_keeps_90_days(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        uid = await s.scalar(select(AppUser.id).where(AppUser.email == SINDICA_ACACIAS))
        assert uid
        today = date.today()
        old, recent = uuid.uuid4(), uuid.uuid4()
        for bid, day in ((old, today - timedelta(days=91)), (recent, today - timedelta(days=89))):
            s.add(
                Briefing(
                    id=bid,
                    condominium_id=acacias,
                    user_id=uid,
                    local_date=day,
                    version=1,
                    timezone="America/Sao_Paulo",
                    period_start=datetime.now(UTC),
                    period_end=datetime.now(UTC),
                    content={},
                    partial_sources=[],
                    generated_at=datetime.now(UTC),
                )
            )
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await purge(s, date.today())
    async with sessionmaker_for(admin_engine)() as s:
        assert await s.get(Briefing, old) is None
        assert await s.get(Briefing, recent) is not None
