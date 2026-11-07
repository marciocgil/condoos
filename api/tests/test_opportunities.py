"""VS-03 (Plano Diretor §8; D76, D81): contract + invoice → opportunity with internal review.

Acceptance: the calculation is reproducible (FIN-01); without the CondoOS review nothing
reaches the condominium (OPT-01, FR-046); stages are separate photographs; a change after
the review needs a new review (US-011); the síndico decides only what was approved.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import Finding, SavingsRecord, Supplier
from app.db.session import sessionmaker_for
from app.main import create_app
from app.opportunities import OpportunityError, estimate_from_finding
from tests.helpers import (
    ADMIN_CONDOOS,
    GERENTE,
    REVISORA,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

MIRANTE = "mirante-do-vale"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _finding(rule: str = "R03", **inputs: str) -> Finding:
    base = (
        {"indice": "IGPM", "valor_com_indice": "5000.00", "diferenca": "420.00"}
        if rule == "R03"
        else {"valor_contratual_reajustado": "18500.00", "diferenca": "1850.00"}
    )
    base.update(inputs)
    return Finding(
        id=uuid.uuid4(),
        rule_code=rule,
        status="publicado",
        rule_inputs=base,
        evidence=[],
        competence=date(2026, 10, 1),
    )


async def _seed_finding(admin_engine: AsyncEngine, rule: str = "R03") -> uuid.UUID:
    mirante = await condo_id(admin_engine, MIRANTE)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        supplier = await s.scalar(select(Supplier.id).limit(1))
        s.add(
            Finding(
                id=fid,
                condominium_id=mirante,
                rule_code=rule,
                severity="alta",
                title="Reajuste acima do índice",
                explanation="Indício para verificação.",
                amount_at_risk=Decimal("420.00"),
                status="publicado",
                evidence=[],
                rule_inputs={
                    "indice": "IGPM",
                    "valor_com_indice": "5000.00",
                    "diferenca": "420.00",
                },
                competence=date(2020, 4, 1),
                dedupe_key=f"test-opp-{fid}",
                supplier_id=supplier,
            )
        )
    return fid


# --------------------------------------------------------------------------- the calculation


def test_potential_savings_are_reproducible() -> None:
    e, kind, title, _ = estimate_from_finding(_finding("R03"), "Elevadores Alfa")
    assert kind == "reajuste" and "Elevadores Alfa" in title
    assert e.amount == Decimal("420.00") and e.periodicity == "mensal"
    assert e.annualized == Decimal("5040.00") and e.net == Decimal("5040.00")
    assert e.baseline_amount == Decimal("5000.00") and e.method_code == "excesso_mensal_v1"
    again, *_ = estimate_from_finding(_finding("R03"), "Elevadores Alfa")
    assert again.version_hash() == e.version_hash()  # same inputs, same approved version
    r02, kind02, *_ = estimate_from_finding(_finding("R02"), "Portaria Beta")
    assert kind02 == "cobranca_inconsistente" and r02.annualized == Decimal("22200.00")
    changed, *_ = estimate_from_finding(_finding("R03", diferenca="421.00"), "Elevadores Alfa")
    assert changed.version_hash() != e.version_hash()
    with pytest.raises(OpportunityError):
        estimate_from_finding(_finding("R03", diferenca="0"), "X")
    other = _finding("R03")
    other.rule_code = "R11"
    with pytest.raises(OpportunityError):
        estimate_from_finding(other, "X")


# --------------------------------------------------------------------------- the slice


async def test_vs03_internal_review_before_the_condominium(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    fid = await _seed_finding(admin_engine)
    base = f"/condominiums/{mirante}/opportunities"
    async with _client() as rev, _client() as carla, _client() as diego, _client() as fabio:
        await login(rev, mailer, REVISORA)
        await login(carla, mailer, SINDICA_MIRANTE)
        await login(diego, mailer, GERENTE)
        await login(fabio, mailer, ADMIN_CONDOOS)

        assert (await carla.post(base, json={"finding_id": str(fid)})).status_code == 403
        r = await rev.post(base, json={"finding_id": str(fid)})
        assert r.status_code == 201, r.text
        opp = r.json()
        url = f"{base}/{opp['id']}"
        assert opp["status"] == "em_revisao_interna" and opp["presented"] is False
        assert opp["review_requirement"] == "internal_review"
        assert [s["stage"] for s in opp["stages"]] == ["potencial"]
        assert Decimal(opp["stages"][0]["annualized_amount"]) == Decimal("5040.00")
        assert set(opp["allowed_actions"]) == {"aprovar", "devolver", "rejeitar", "ajustar"}
        assert (await rev.post(base, json={"finding_id": str(fid)})).status_code == 409

        # OPT-01: before the review, it does not exist for the board nor the management company.
        for who in (carla, diego):
            assert (await who.get(url)).status_code == 404
            assert opp["id"] not in {o["id"] for o in (await who.get(base)).json()}
            got = (await who.get(f"/condominiums/{mirante}/findings/{fid}/opportunities")).json()
            assert got == []
        # The CondoOS admin sees the draft but does not review it.
        seen = (await fabio.get(url)).json()
        assert seen["allowed_actions"] == []
        r = await fabio.post(f"{url}/decisions", json={"action": "aprovar"})
        assert r.status_code == 403

        # The reviewer adjusts (new row, reason required), returns, adjusts back and approves.
        r = await rev.post(f"{url}/estimate", json={"amount": "400.00", "reason": ""})
        assert r.status_code == 422
        r = await rev.post(
            f"{url}/estimate", json={"amount": "400.00", "reason": "Descontado 1 dia de feriado"}
        )
        assert r.status_code == 200 and Decimal(r.json()["stages"][0]["amount"]) == 400
        r = await rev.post(f"{url}/decisions", json={"action": "devolver"})
        assert r.status_code == 422
        r = await rev.post(
            f"{url}/decisions", json={"action": "devolver", "comment": "Conferir o aditivo de 2025"}
        )
        assert r.json()["status"] == "devolvida"
        r = await rev.post(
            f"{url}/estimate",
            json={"amount": "420.00", "reason": "Aditivo conferido: sem mudança de valor"},
        )
        assert r.json()["status"] == "em_revisao_interna"
        r = await rev.post(f"{url}/decisions", json={"action": "aprovar"})
        assert r.status_code == 200 and r.json()["status"] == "aprovada_para_cliente"

        # Now the síndica sees it, with the validated estimate only (never the raw potential).
        mine = (await carla.get(url)).json()
        assert [s["stage"] for s in mine["stages"]] == ["estimada_validada"]
        assert mine["headline_stage"] == "estimada_validada"
        assert Decimal(mine["headline_annualized"]) == Decimal("5040.00")
        assert {h["action"] for h in mine["history"]} == {"aprovar"}  # no internal notes
        assert set(mine["allowed_actions"]) == {"condominio_aprovar", "condominio_recusar"}
        # Reviewing and approving stay apart (D77).
        r = await rev.post(f"{url}/decisions", json={"action": "condominio_aprovar"})
        assert r.status_code == 403
        r = await carla.post(f"{url}/decisions", json={"action": "aprovar"})
        assert r.status_code == 403
        r = await carla.post(f"{url}/decisions", json={"action": "condominio_aprovar"})
        assert r.status_code == 200 and r.json()["status"] == "aprovada_pelo_condominio"
        stages = [s["stage"] for s in r.json()["stages"]]
        assert stages == ["estimada_validada", "aprovada"]  # side by side, never summed

    async with sessionmaker_for(admin_engine)() as s:
        rows = list(
            await s.scalars(
                select(SavingsRecord).where(SavingsRecord.opportunity_id == uuid.UUID(opp["id"]))
            )
        )
    assert sorted(r.stage for r in rows) == [
        "aprovada",
        "estimada_validada",
        "potencial",
        "potencial",
        "potencial",
    ]


async def test_change_after_review_needs_a_new_review(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    fid = await _seed_finding(admin_engine)
    base = f"/condominiums/{mirante}/opportunities"
    async with _client() as rev, _client() as carla:
        await login(rev, mailer, REVISORA)
        await login(carla, mailer, SINDICA_MIRANTE)
        opp = (await rev.post(base, json={"finding_id": str(fid)})).json()
        url = f"{base}/{opp['id']}"
        await rev.post(f"{url}/decisions", json={"action": "aprovar"})
        assert (await carla.get(url)).status_code == 200
        # Reopening takes it out of the board's view until approved again.
        r = await rev.post(f"{url}/decisions", json={"action": "reabrir_revisao"})
        assert r.status_code == 422
        r = await rev.post(
            f"{url}/decisions", json={"action": "reabrir_revisao", "comment": "Novo aditivo chegou"}
        )
        assert r.json()["status"] == "em_revisao_interna"
        assert (await carla.get(url)).status_code == 404

        # A potential that changed behind the approval blocks the condominium's decision.
        await rev.post(f"{url}/decisions", json={"action": "aprovar"})
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            last = await s.scalar(
                select(SavingsRecord)
                .where(
                    SavingsRecord.opportunity_id == uuid.UUID(opp["id"]),
                    SavingsRecord.stage == "potencial",
                )
                .order_by(SavingsRecord.created_at.desc())
                .limit(1)
            )
            assert last is not None
            s.add(
                SavingsRecord(
                    id=uuid.uuid4(),
                    condominium_id=mirante,
                    opportunity_id=last.opportunity_id,
                    stage="potencial",
                    amount=Decimal("999.00"),
                    periodicity="mensal",
                    annualized_amount=Decimal("11988.00"),
                    one_time_cost=Decimal("0"),
                    net_amount=Decimal("11988.00"),
                    baseline_period_start=last.baseline_period_start,
                    baseline_period_end=last.baseline_period_end,
                    baseline_amount=last.baseline_amount,
                    method_code="manual",
                    assumptions=[],
                    evidence=[],
                    confidence="baixa",
                    quality_risks="",
                    version_hash="x" * 64,
                    created_at=datetime.now(UTC) + timedelta(seconds=5),
                )
            )
        r = await carla.post(f"{url}/decisions", json={"action": "condominio_aprovar"})
        assert r.status_code == 409 and "nova revisão" in r.json()["detail"]
        r = await carla.post(f"{url}/decisions", json={"action": "condominio_recusar"})
        assert r.status_code == 422  # a reason is required to decline


async def test_other_condominium_and_cases(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = await _seed_finding(admin_engine)
    base = f"/condominiums/{mirante}/opportunities"
    async with _client() as rev, _client() as carla, _client() as ana:
        await login(rev, mailer, REVISORA)
        await login(carla, mailer, SINDICA_MIRANTE)
        await login(ana, mailer, SINDICA_ACACIAS)
        opp = (await rev.post(base, json={"finding_id": str(fid)})).json()
        url = f"{base}/{opp['id']}"
        link = {"target_type": "opportunity", "target_id": opp["id"]}
        case = {
            "title": "Renegociar o reajuste dos elevadores",
            "category": "contrato",
            "origin": "opportunity",
            "next_action": "Enviar contestação à empresa",
            "next_action_due_at": (date.today() + timedelta(days=10)).isoformat(),
            "resolution_criterion": "Fatura seguinte pelo índice do contrato",
            "links": [link],
            "create_anyway_reason": "Teste automatizado",
        }
        # Before the review the síndica cannot link it; after, a case can follow it.
        r = await carla.post(f"/condominiums/{mirante}/cases", json=case)
        assert r.status_code == 404
        await rev.post(f"{url}/decisions", json={"action": "aprovar"})
        r = await carla.post(f"/condominiums/{mirante}/cases", json=case)
        assert r.status_code == 201, r.text
        assert r.json()["links"][0]["label"].startswith(opp["number"])
        # Another condominium: nothing.
        assert (await ana.get(url)).status_code == 404
        assert (
            await ana.get(f"/condominiums/{acacias}/opportunities/{opp['id']}")
        ).status_code == 404
