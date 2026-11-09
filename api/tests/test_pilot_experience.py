"""Pilot experience slice (D108, LB-080..LB-086): guided progress, documents in review, the
síndico's month, a "Hoje" without contradictions and the chat button only when it answers."""

from datetime import date

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.enums import FindingStatus
from app.db.models import Finding, Membership
from app.db.session import sessionmaker_for
from app.launch.state import in_review
from app.launch.steps import progress
from app.onboarding import onboard
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)
from tests.test_launch import _document, _r
from tests.test_onboarding import _spec


def test_progress_counts_the_goal_steps_from_the_data() -> None:
    empty = [
        _r("C1", "nao_configurado", documentos_lidos=0),
        _r("C2", "nao_configurado"),
        _r("C3", "nao_configurado"),
    ]
    # "economizar" has five steps; with nothing sent none is done, even the ones that do not
    # apply yet (invoices before a contract).
    assert progress("economizar", empty, 0) == {"done": 0, "total": 5}
    assert progress(None, empty, 0)["total"] == 5
    with_contract = [
        _r("C1", "supervisionada", documentos_lidos=1),
        _r("C2", "supervisionada"),
        _r(
            "C3",
            "analise_parcial",
            mes="2026-10",
            contratos_vigentes=2,
            contratos_com_cobranca=2,
            movimentos_bancarios=0,
        ),
    ]
    # Contract, invoices and convention done; bank statement missing; C8 unknown.
    assert progress("economizar", with_contract, 1) == {"done": 3, "total": 5}
    with_contract.append(_r("C8", "supervisionada", esperados=2, recebidos=2))
    assert progress("economizar", with_contract, 1) == {"done": 4, "total": 5}


async def test_documents_in_review_are_listed_with_since(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec(management_company_name=None))
        assert (await in_review(s, condo.id))["total"] == 0
        waiting = _document(condo, "contrato", extraction_status="needs_review", needs_review=True)
        reading = _document(condo, "nfse", extraction_status="pending")
        reviewed = _document(
            condo,
            "contrato",
            extraction_status="needs_review",
            needs_review=True,
            reviewed_at=utcnow(),
        )
        done = _document(condo, "ata")
        s.add_all([waiting, reading, reviewed, done])
        await s.flush()
        out = await in_review(s, condo.id)
        assert out["total"] == 2
        assert out["by_type"] == {"contrato": 1, "nfse": 1}
        states = {i["id"]: i["state"] for i in out["items"]}
        assert states == {str(waiting.id): "em_conferencia", str(reading.id): "lendo"}
        assert all(i["since"] for i in out["items"])


async def test_month_routine_after_lm3_only_and_by_role(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    url = f"/condominiums/{acacias}/launch/month"
    async with sessionmaker_for(admin_engine)() as s:
        waiting = await s.scalar(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.condominium_id == acacias,
                Finding.status == FindingStatus.PUBLICADO.value,
            )
        )
    await login(client, mailer, SINDICA_ACACIAS)
    body = (await client.get(url)).json()
    assert body["active"] is True and len(body["items"]) <= 3
    items = {i["key"]: i for i in body["items"]}
    if waiting:
        assert items["decisoes"]["detail"].startswith(f"{waiting} ")
        assert items["decisoes"]["actions"][0]["href"].startswith("achados/")
    else:
        assert "decisoes" not in items
    # The board member cannot decide findings: no decisions item for him.
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    assert "decisoes" not in {i["key"] for i in (await client.get(url)).json()["items"]}
    # Another condominium's síndica gets 404.
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(url)).status_code == 404

    # A condominium still implementing (no LM3) has no month routine yet.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        spec = _spec(management_company_name=None)
        condo = await onboard(s, spec)
        email = spec.board[0].email
    assert email
    await login(client, mailer, email)
    body = (await client.get(f"/condominiums/{condo.id}/launch/month")).json()
    assert body == {"active": False, "month": body["month"], "items": []}
    launch = (await client.get(f"/condominiums/{condo.id}/launch")).json()
    assert launch["progress"]["total"] >= 1 and launch["in_review"]["total"] == 0


async def test_new_condominium_briefing_is_starting_not_late(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        spec = _spec(management_company_name=None)
        condo = await onboard(s, spec)
        await s.execute(
            update(Membership)
            .where(Membership.condominium_id == condo.id)
            .values(accepted_at=utcnow())
        )
    assert spec.board[0].email
    await login(client, mailer, spec.board[0].email)
    b = (await client.post(f"/condominiums/{condo.id}/briefing/refresh")).json()
    sources = {p["source"]: p for p in b["partial_sources"]}
    assert sources["documentos"]["not_started"] is True
    assert sources["documentos"]["reason"].startswith("Ainda não recebemos documentos")
    assert sources["extrato"]["not_started"] is True
    # Nothing late, nothing pending: no "parciais" warning and no "(ões)" or zero counts.
    assert "parciais" not in b["headline"]
    assert "(ões)" not in b["headline"] and "(s)" not in b["headline"]
    assert " 0 " not in b["headline"]
    assert b["headline"].endswith("nada pendente com você hoje.")


async def test_summary_names_later_months_waiting(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    body = (await client.get(f"/condominiums/{acacias}/summary")).json()
    shown = date.fromisoformat(body["competence"])
    async with sessionmaker_for(admin_engine)() as s:
        rows = (
            await s.execute(
                select(Finding.competence, func.count())
                .where(
                    Finding.condominium_id == acacias,
                    Finding.competence > shown,
                    Finding.status == FindingStatus.PUBLICADO.value,
                )
                .group_by(Finding.competence)
            )
        ).all()
    expected = {c.isoformat(): n for c, n in rows}
    assert {w["competence"]: w["waiting"] for w in body["later_waiting"]} == expected
    # The latest month has nothing after it.
    latest = max([shown, *[date.fromisoformat(k) for k in expected]])
    later = (await client.get(f"/condominiums/{acacias}/summary?competence={latest:%Y-%m}")).json()[
        "later_waiting"
    ]
    assert later == []


async def test_chat_status_follows_the_model_and_the_condominium(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    # The test suite never calls the model: the chat cannot answer, so no button.
    assert (await client.get(f"/condominiums/{acacias}/chat/status")).json() == {"available": False}
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/chat/status")).status_code == 404
