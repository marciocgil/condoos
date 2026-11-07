"""Milestone 6: internal pilot metrics, computed from decisions, documents and llm_calls."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AppUser, Decision, Finding, LlmCall
from app.db.session import sessionmaker_for
from app.metrics import compute
from app.onboarding import onboard
from tests.helpers import GERENTE, SINDICA_ACACIAS, login
from tests.test_matching import _doc
from tests.test_onboarding import _spec

OCT = date(2026, 10, 1)
T0 = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


async def test_metrics_definitions(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        user = AppUser(id=uuid.uuid4(), name="Pessoa", email=f"{uuid.uuid4().hex}@m.example.com")
        s.add(user)

        def finding(severity: str, status: str) -> Finding:
            fid = uuid.uuid4()
            return Finding(
                id=fid,
                condominium_id=condo.id,
                rule_code="R02",
                severity=severity,
                title="t",
                explanation="e",
                amount_at_risk=Decimal("10"),
                status=status,
                evidence=[],
                rule_inputs={},
                competence=OCT,
                dedupe_key=f"m-{fid}",
                created_at=T0,
            )

        confirmed = finding("media", "confirmado")
        contested = finding("media", "contestado")  # confirmed first, then contested
        untouched = finding("baixa", "publicado")
        serious = finding("alta", "confirmado")  # validated at T0+2h, confirmed at T0+3h
        s.add_all([confirmed, contested, untouched, serious])
        await s.flush()

        def decision(f: Finding, action: str, hours: float) -> Decision:
            return Decision(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                finding_id=f.id,
                user_id=user.id,
                action=action,
                decided_at=T0 + timedelta(hours=hours),
            )

        s.add_all(
            [
                decision(confirmed, "confirmar", 4),
                decision(contested, "confirmar", 10),
                decision(contested, "contestar", 20),
                decision(serious, "validar", 2),
                decision(serious, "confirmar", 3),
            ]
        )
        auto = _doc(condo, "nfse", {}, created_at=T0)
        corrected = _doc(condo, "boleto", {}, created_at=T0, reviewed_at=T0)
        pending = _doc(
            condo, "recibo", {}, created_at=T0, needs_review=True, extraction_status="needs_review"
        )
        seeded = _doc(condo, "nfse", {}, created_at=T0, origin="seed")
        bank = _doc(condo, "extrato", {}, created_at=T0)
        s.add_all([auto, corrected, pending, seeded, bank])
        s.add_all(
            [
                LlmCall(
                    purpose="extract",
                    model="m",
                    cost_usd=Decimal("0.12"),
                    condominium_id=condo.id,
                    created_at=T0,
                ),
                LlmCall(
                    purpose="chat",
                    model="m",
                    cost_usd=Decimal("0.03"),
                    condominium_id=condo.id,
                    created_at=T0,
                ),
            ]
        )

    async with sessionmaker_for(admin_engine)() as s:
        buckets = await compute(s, [condo.id], OCT, OCT)
    summary = buckets[condo.id][OCT].summary()
    assert summary["findings_reviewed"] == 3 and summary["findings_confirmed"] == 2
    assert summary["precision"] == round(2 / 3, 4)
    assert summary["docs_processed"] == 3 and summary["docs_automatic"] == 1
    # review times: 4 h, 10 h (first decision), 1 h (after validation) → median 4 h
    assert summary["review_count"] == 3 and summary["review_hours_median"] == 4.0
    assert summary["llm_cost_usd"] == "0.1500" and summary["llm_calls"] == 2


async def test_metrics_endpoint_is_for_the_management_company(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    await login(client, mailer, GERENTE)
    body = (await client.get("/portfolio/metrics?months=3")).json()
    assert len(body["months"]) == 3 and len(body["by_month"]) == 3
    assert {c["name"] for c in body["condominiums"]} >= {
        "Condomínio Residencial Jardim das Acácias",
        "Condomínio Edifício Mirante do Vale",
    }
    assert {"precision", "automatic_rate", "review_hours_median", "llm_cost_usd"} <= set(
        body["totals"]
    )
    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get("/portfolio/metrics")).json()["condominiums"] == []


async def test_portfolio_views_filter_by_condominium(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from tests.helpers import condo_id

    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, GERENTE)
    m = (await client.get(f"/portfolio/metrics?months=3&condominium_id={mirante}")).json()
    assert [c["name"] for c in m["condominiums"]] == ["Condomínio Edifício Mirante do Vale"]
    sups = (await client.get(f"/portfolio/suppliers?condominium_id={mirante}")).json()
    assert sups and all(s["condominiums"] == ["Condomínio Edifício Mirante do Vale"] for s in sups)
    other = uuid.uuid4()
    assert (await client.get(f"/portfolio/suppliers?condominium_id={other}")).json() == []


async def test_pilot_baseline_indicators(admin_engine: AsyncEngine) -> None:
    """CB-070: counts from the product's own records, per condominium and month."""
    from app.core.time import utcnow
    from app.db.models import AuditLog, Membership, UserSession

    now = utcnow()
    month = date(now.year, now.month, 1)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        other = uuid.uuid4()
        user = AppUser(id=uuid.uuid4(), name="Síndica", email=f"{uuid.uuid4().hex}@m.example.com")
        s.add(user)
        await s.flush()
        s.add(Membership(id=uuid.uuid4(), user_id=user.id, condominium_id=condo.id, role="sindico"))
        for _ in range(2):
            s.add(
                UserSession(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    token_hash=uuid.uuid4().hex + uuid.uuid4().hex,
                    expires_at=now + timedelta(days=1),
                )
            )
        s.add(
            AuditLog(
                action="security.access_denied",
                object_type="condominium",
                actor_user_id=user.id,
                details={"requested_condominium_id": str(condo.id)},
            )
        )
        s.add(  # aimed at another condominium: not counted here
            AuditLog(
                action="security.access_denied",
                object_type="condominium",
                details={"requested_condominium_id": str(other)},
            )
        )
        s.add(
            AuditLog(
                action="action.denied_by_policy",
                object_type="condominium",
                object_id=condo.id,
                condominium_id=condo.id,
                details={"action_type": "pagamento.aprovar"},
            )
        )
    async with sessionmaker_for(admin_engine)() as s:
        out = await compute(s, [condo.id], month, month)
    b = out[condo.id][month].summary()
    assert b["cross_tenant_attempts"] == 1
    assert b["denied_by_policy"] == 1
    assert b["board_sessions"] == 2
    assert b["savings_validated_annual"] == "0.00"
    assert b["savings_realized_annual"] == "0.00"
