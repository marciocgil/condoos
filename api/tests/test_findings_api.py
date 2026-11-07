"""Milestone 4 API: finding detail and decisions by role, comments, trail, summary,
portfolio and settings."""

import random
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.db.models import AuditLog, Decision, Finding, ManagementCompany
from app.db.session import sessionmaker_for
from app.onboarding import OnboardingIn, onboard
from tests.helpers import (
    ANALISTA,
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

OCT = date(2026, 10, 1)


async def _finding(
    admin_engine: AsyncEngine,
    status: str,
    severity: str = "media",
    amount: str = "1000.00",
    competence: date = OCT,
) -> uuid.UUID:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=acacias,
                rule_code="R02",
                severity=severity,
                title="Valor acima do contrato",
                explanation="Divergência de R$ 1.000,00.",
                amount_at_risk=Decimal(amount),
                status=status,
                evidence=[
                    {
                        "kind": "contract",
                        "id": str(uuid.uuid4()),
                        "label": "Contrato",
                        "excerpt": "",
                    }
                ],
                rule_inputs={"diferenca": amount, "categoria": "portaria"},
                competence=competence,
                dedupe_key=f"test-{fid}",
            )
        )
    return fid


async def _switch(client: httpx.AsyncClient, mailer: MemoryMailer, email: str) -> None:
    await client.post("/auth/logout")
    await login(client, mailer, email)


async def test_sindico_confirms_and_contests(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = await _finding(admin_engine, "publicado")
    base = f"/condominiums/{acacias}/findings/{fid}"
    await login(client, mailer, SINDICA_ACACIAS)

    detail = (await client.get(base)).json()
    assert set(detail["allowed_actions"]) == {"confirmar", "contestar", "ignorar"}
    assert detail["category_label"] == "portaria" and not detail["validated_by_management"]

    r = await client.post(f"{base}/decisions", json={"action": "confirmar"})
    assert r.status_code == 200 and r.json()["status"] == "confirmado"
    assert r.json()["decisions"][0]["user_name"] == "Ana Ribeiro Sampaio"

    r = await client.post(f"{base}/decisions", json={"action": "contestar", "comment": "  "})
    assert r.status_code == 422
    r = await client.post(
        f"{base}/decisions",
        json={"action": "contestar", "comment": "O valor inclui hora extra aprovada."},
    )
    assert r.status_code == 200 and r.json()["status"] == "contestado"
    r = await client.post(f"{base}/decisions", json={"action": "validar"})
    assert r.status_code == 403

    async with sessionmaker_for(admin_engine)() as s:
        rows = (await s.scalars(select(Decision).where(Decision.finding_id == fid))).all()
        audits = (await s.scalars(select(AuditLog).where(AuditLog.object_id == fid))).all()
    assert [d.action for d in sorted(rows, key=lambda d: d.decided_at)] == [
        "confirmar",
        "contestar",
    ]
    assert len(audits) == 2

    trail = (await client.get(f"/condominiums/{acacias}/decisions")).json()
    assert {t["action"] for t in trail if t["finding_id"] == str(fid)} == {"confirmar", "contestar"}


async def test_manager_validates_and_discards_serious_findings(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    to_validate = await _finding(admin_engine, "aguardando_validacao", "alta")
    to_discard = await _finding(admin_engine, "aguardando_validacao", "alta")

    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get(f"/condominiums/{acacias}/findings/{to_validate}")).status_code == 404

    await _switch(client, mailer, GERENTE)
    base = f"/condominiums/{acacias}/findings"
    assert (await client.get(f"{base}/{to_validate}")).json()["allowed_actions"] == [
        "validar",
        "descartar",
        "solicitar_evidencia",  # D74: inconclusive findings wait for evidence
    ]
    r = await client.post(f"{base}/{to_validate}/decisions", json={"action": "validar"})
    assert r.json()["status"] == "publicado"
    assert (
        await client.post(f"{base}/{to_discard}/decisions", json={"action": "descartar"})
    ).status_code == 422
    r = await client.post(
        f"{base}/{to_discard}/decisions",
        json={"action": "descartar", "comment": "Sócio homônimo, sem vínculo."},
    )
    assert r.json()["status"] == "descartado"
    r = await client.post(f"{base}/{to_discard}/decisions", json={"action": "reabrir"})
    assert r.json()["status"] == "aguardando_validacao"
    queue = {i["id"] for i in (await client.get("/queue")).json() if i["kind"] == "achado_grave"}
    assert str(to_discard) in queue and str(to_validate) not in queue

    await _switch(client, mailer, SINDICA_ACACIAS)
    detail = (await client.get(f"{base}/{to_validate}")).json()
    assert detail["validated_by_management"] is True
    assert (await client.get(f"{base}/{to_discard}")).status_code == 404


async def test_conselheiro_comments_but_cannot_decide(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = await _finding(admin_engine, "publicado")
    base = f"/condominiums/{acacias}/findings/{fid}"
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    detail = (await client.get(base)).json()
    assert detail["allowed_actions"] == [] and detail["can_comment"]
    assert (await client.post(f"{base}/decisions", json={"action": "confirmar"})).status_code == 403
    r = await client.post(f"{base}/comments", json={"body": "Vamos levar à assembleia."})
    assert r.status_code == 201 and r.json()["comments"][-1]["user_name"] == "Bruno Tavares Molina"


async def test_findings_are_isolated_between_condominiums(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    fid = await _finding(admin_engine, "publicado")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/findings/{fid}")).status_code == 404
    assert (await client.get(f"/condominiums/{mirante}/findings/{fid}")).status_code == 404
    r = await client.post(
        f"/condominiums/{mirante}/findings/{fid}/decisions", json={"action": "ignorar"}
    )
    assert r.status_code == 404


async def test_summary_filters_and_ignored_not_at_risk(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    month = date(2026, 3, 1)  # a month without other test findings
    await _finding(admin_engine, "publicado", "media", "300.00", month)
    await _finding(admin_engine, "ignorado", "baixa", "200.00", month)
    await _finding(admin_engine, "aguardando_validacao", "alta", "900.00", month)
    await login(client, mailer, SINDICA_ACACIAS)
    s = (await client.get(f"/condominiums/{acacias}/summary?competence=2026-03")).json()
    assert s["findings"] == 2 and Decimal(s["amount_at_risk"]) == Decimal("300.00")
    assert s["by_severity"] == {"alta": 0, "media": 1, "baixa": 1}
    default = (await client.get(f"/condominiums/{acacias}/summary")).json()
    assert default["competence"] == "2026-09-01"  # most recent closed month
    listed = (
        await client.get(f"/condominiums/{acacias}/findings?competence=2026-03&severity=baixa")
    ).json()
    assert [f["severity"] for f in listed] == ["baixa"]
    by_cat = (
        await client.get(f"/condominiums/{acacias}/findings?competence=2026-03&category=agua")
    ).json()
    assert by_cat == []


async def test_portfolio_views(client: httpx.AsyncClient, mailer: MemoryMailer) -> None:
    await login(client, mailer, GERENTE)
    p = (await client.get("/portfolio")).json()
    assert {c["name"] for c in p["condominiums"]} >= {
        "Condomínio Residencial Jardim das Acácias",
        "Condomínio Edifício Mirante do Vale",
    }
    sups = (await client.get("/portfolio/suppliers")).json()
    shared = next(s for s in sups if s["name"].startswith("Vigilare"))
    assert len(shared["condominiums"]) == 2  # same supplier serving two condominiums
    contracts = (await client.get("/portfolio/contracts")).json()
    assert any(c["object"] == "Portaria 24 horas" for c in contracts)
    await _switch(client, mailer, SINDICA_ACACIAS)
    assert (await client.get("/portfolio")).json()["condominiums"] == []


@pytest.mark.parametrize("email", [ANALISTA, SINDICA_ACACIAS])
async def test_only_manager_configures(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine, email: str
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, email)
    assert (await client.get(f"/condominiums/{acacias}/settings")).status_code == 403


async def test_manager_updates_settings_with_audit(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, GERENTE)
    url = f"/condominiums/{mirante}/settings"
    current = (await client.get(url)).json()
    assert {r["code"] for r in current["rules"]} == {f"R{n:02d}" for n in range(1, 13)}
    assert any(m["role"] == "sindico" for m in current["members"])
    bad = await client.put(url, json={"rule_params": {"R01": {"tolerance_pct": "abc"}}})
    assert bad.status_code == 422
    bad = await client.put(url, json={"rule_params": {"R99": {}}})
    assert bad.status_code == 422
    r = await client.put(
        url,
        json={
            "approval_limits": {"default": "6000", "by_category": {"obras": "3500,00"}},
            "rule_params": {"R01": {"tolerance_pct": 2}},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["approval_limits"] == {"default": "6000.00", "by_category": {"obras": "3500.00"}}
    assert next(x for x in body["rules"] if x["code"] == "R01")["overrides"] == {"tolerance_pct": 2}
    async with sessionmaker_for(admin_engine)() as s:
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.action == "settings.updated", AuditLog.object_id == mirante
            )
        )
    assert audit is not None and audit.details["fields"] == ["approval_limits", "rule_params"]
    # restore
    await client.put(
        url,
        json={
            "approval_limits": {"default": "5000", "by_category": {"obras": "3000"}},
            "rule_params": {},
        },
    )


async def test_portfolio_report_flags(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """The portfolio tells the screen who may close the month and whether it exists."""
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        company = await s.scalar(
            select(ManagementCompany).where(ManagementCompany.name.like("Atlântida%"))
        )
        assert company is not None
        tag = uuid.uuid4().hex[:8]
        fresh = await onboard(
            s,
            OnboardingIn.model_validate(
                {
                    "management_company_name": company.name,
                    "condominium": {
                        "name": f"Condomínio Novo {tag} (fictício)",
                        "slug": f"novo-{tag}",
                        "cnpj": generate_cnpj(random.Random(tag)),
                        "units": 12,
                        "address": "Rua Fictícia, 20 — Cidade Modelo/SP",
                        "approval_limits": {"default": "5.000,00"},
                    },
                    "board": [
                        {
                            "name": "Síndico Novo",
                            "position": "sindico",
                            "term_start": "2026-01-01",
                        }
                    ],
                }
            ),
        )
    acacias = await condo_id(admin_engine, "jardim-das-acacias")

    await login(client, mailer, GERENTE)
    rows = {r["id"]: r for r in (await client.get("/portfolio")).json()["condominiums"]}
    assert rows[str(acacias)]["can_close"] and rows[str(acacias)]["has_competence"]
    assert rows[str(fresh.id)]["can_close"] and not rows[str(fresh.id)]["has_competence"]

    await _switch(client, mailer, ANALISTA)
    rows = {r["id"]: r for r in (await client.get("/portfolio")).json()["condominiums"]}
    assert rows[str(acacias)]["has_competence"] and not rows[str(acacias)]["can_close"]
    assert not any(r["can_close"] for r in rows.values())
