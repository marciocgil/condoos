"""Review proportional to risk (migration 0012, D74; docs/data-model.md §8): a versioned
policy decides what is reviewed; the default reproduces the behaviour before D74; findings
can wait for evidence; economy recommendations are CondoOS-only."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.enums import ReviewRequirement
from app.db.models import Condominium, Finding, ReviewPolicy
from app.db.session import sessionmaker_for
from app.main import create_app
from app.review import PLATFORM_DEFAULT_V1, Policy, current_policy, evaluate, parse_rules
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
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


def _default() -> Policy:
    return Policy(version=1, rules=parse_rules(PLATFORM_DEFAULT_V1), condominium_specific=False)


async def _finding(
    admin_engine: AsyncEngine, requirement: str = "qualified_review", amount: str = "321.00"
) -> uuid.UUID:
    mirante = await condo_id(admin_engine, MIRANTE)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=mirante,
                rule_code="R02",
                severity="alta",
                title="Achado de teste da política de revisão",
                explanation="Indício para verificação.",
                amount_at_risk=Decimal(amount),
                status="aguardando_validacao",
                evidence=[],
                rule_inputs={},
                competence=date(2020, 2, 1),
                dedupe_key=f"test-review-{fid}",
                review_requirement=requirement,
                review_policy_version=1,
            )
        )
    return fid


# --------------------------------------------------------------------------- the policy


def test_default_policy_reproduces_previous_behaviour() -> None:
    policy = _default()
    alta = evaluate(policy, "finding", rule_code="R01", severity="alta", amount=Decimal("1"))
    assert alta.requirement == ReviewRequirement.QUALIFIED_REVIEW
    assert {r.value for r in alta.reviewers} == {"condoos_reviewer", "gerente"}
    for severity in ("media", "baixa"):
        out = evaluate(policy, "finding", rule_code="R11", severity=severity, amount=Decimal("9"))
        assert out.requirement == ReviewRequirement.NONE
    economy = evaluate(policy, "opportunity", amount=Decimal("12000"))
    assert economy.requirement == ReviewRequirement.INTERNAL_REVIEW
    assert {r.value for r in economy.reviewers} == {"condoos_reviewer"}


def test_rules_are_typed_and_need_a_catch_all() -> None:
    rules: list[dict[str, Any]] = [
        {
            "object": "finding",
            "match": {"min_amount": "5000"},
            "requirement": "qualified_review",
            "reviewers": ["condoos_reviewer"],
        },
        {"object": "finding", "match": {"ai_assisted": True}, "requirement": "pending_evidence"},
        {"object": "finding", "requirement": "none"},
    ]
    policy = Policy(version=2, rules=parse_rules(rules), condominium_specific=True)
    big = evaluate(policy, "finding", severity="baixa", amount=Decimal("5000"))
    assert big.requirement == ReviewRequirement.QUALIFIED_REVIEW and big.version == 2
    ai = evaluate(policy, "finding", severity="baixa", amount=Decimal("10"), ai_assisted=True)
    assert ai.requirement == ReviewRequirement.PENDING_EVIDENCE
    assert evaluate(policy, "finding", amount=Decimal("10")).requirement == ReviewRequirement.NONE
    # No rule for opportunities in this policy: the conservative answer is a CondoOS review.
    assert evaluate(policy, "opportunity").requirement == ReviewRequirement.QUALIFIED_REVIEW
    with pytest.raises(ValueError, match="última regra"):
        parse_rules(rules[:2])
    with pytest.raises(ValueError):  # unknown fields or expression strings are refused
        parse_rules([{"object": "finding", "match": {"expr": "amount > 1"}, "requirement": "none"}])


async def test_condominium_version_overrides_default_from_valid_from(
    admin_engine: AsyncEngine,
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    stricter = [
        {"object": "finding", "requirement": "qualified_review", "reviewers": ["condoos_reviewer"]}
    ]
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add_all(
            [
                ReviewPolicy(
                    id=uuid.uuid4(),
                    condominium_id=mirante,
                    version=2,
                    valid_from=datetime.now(UTC) - timedelta(days=1),
                    rules=stricter,
                    reason="teste",
                ),
                ReviewPolicy(
                    id=uuid.uuid4(),
                    condominium_id=mirante,
                    version=3,
                    valid_from=datetime.now(UTC) + timedelta(days=30),
                    rules=[],
                    reason="teste futuro",
                ),
            ]
        )
    try:
        async with sessionmaker_for(admin_engine)() as s:
            own = await current_policy(s, mirante)
            other = await current_policy(s, acacias)
        assert own.version == 2 and own.condominium_specific  # v3 is not in force yet
        assert evaluate(own, "finding", severity="baixa").requirement == "qualified_review"
        assert other.version == 1 and not other.condominium_specific
    finally:
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(delete(ReviewPolicy).where(ReviewPolicy.condominium_id == mirante))


# --------------------------------------------------------------------------- the API


async def test_board_reads_the_policy_and_sindica_configures_it(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    url = f"/condominiums/{acacias}/review-policy"
    async with _client() as c:
        await login(c, mailer, CONSELHEIRO_ACACIAS)
        body = (await c.get(url)).json()
        assert body["version"] == 1 and body["management_company_reviews"] is True
        assert body["can_configure"] is False
        assert (await c.put(url, json={"management_company_reviews": False})).status_code == 403

        await login(c, mailer, GERENTE)  # the management company does not decide it
        assert (await c.put(url, json={"management_company_reviews": False})).status_code == 403

        await login(c, mailer, SINDICA_ACACIAS)
        assert (await c.get(url)).json()["can_configure"] is True
        r = await c.put(url, json={"management_company_reviews": False})
        assert r.status_code == 200 and r.json()["management_company_reviews"] is False
        try:
            async with _client() as m:
                await login(m, mailer, GERENTE)
                me = (await m.get("/me")).json()
                perms = next(x for x in me["condominiums"] if x["id"] == str(acacias))
                assert "validate_finding" not in perms["permissions"]
        finally:
            r = await c.put(url, json={"management_company_reviews": True})
            assert r.json()["management_company_reviews"] is True


async def test_no_management_company_means_no_company_review(admin_engine: AsyncEngine) -> None:
    from app.review import REVIEWER_ROLES

    assert set(REVIEWER_ROLES) == {"condoos_reviewer", "gerente"}
    async with sessionmaker_for(admin_engine)() as s:
        direct = list(
            await s.scalars(select(Condominium).where(Condominium.management_company_id.is_(None)))
        )
    assert all(not c.management_company_reviews for c in direct)


@pytest.fixture
async def in_review(admin_engine: AsyncEngine) -> AsyncIterator[uuid.UUID]:
    yield await _finding(admin_engine)


async def test_reviewer_asks_for_evidence_then_validates(
    mailer: MemoryMailer, admin_engine: AsyncEngine, in_review: uuid.UUID
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    base = f"/condominiums/{mirante}/findings/{in_review}"
    async with _client() as reviewer, _client() as sindica:
        await login(reviewer, mailer, REVISORA)
        await login(sindica, mailer, SINDICA_MIRANTE)
        assert set((await reviewer.get(base)).json()["allowed_actions"]) == {
            "validar",
            "descartar",
            "solicitar_evidencia",
        }
        r = await reviewer.post(f"{base}/decisions", json={"action": "solicitar_evidencia"})
        assert r.status_code == 422  # the reason is mandatory
        r = await reviewer.post(
            f"{base}/decisions",
            json={"action": "solicitar_evidencia", "comment": "Falta a nota do mês anterior."},
        )
        assert r.status_code == 200 and r.json()["status"] == "pendente_evidencia"

        # Not visible to the board, not at risk, but in the reviewer's queue.
        assert (await sindica.get(base)).status_code == 404
        queue = {q["id"]: q for q in (await reviewer.get("/queue")).json()}
        assert queue[str(in_review)]["title"].startswith("Evidência pendente:")
        summary = (await reviewer.get(f"/condominiums/{mirante}/summary?competence=2020-02")).json()
        assert Decimal(summary["amount_at_risk"]) == 0

        assert set((await reviewer.get(base)).json()["allowed_actions"]) == {"validar", "descartar"}
        r = await reviewer.post(f"{base}/decisions", json={"action": "validar"})
        assert r.json()["status"] == "publicado"
        detail = (await sindica.get(base)).json()
        assert detail["validated_by_condoos"] and not detail["validated_by_management"]


async def test_internal_review_is_condoos_only(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    fid = await _finding(admin_engine, requirement="internal_review")
    mirante = await condo_id(admin_engine, MIRANTE)
    base = f"/condominiums/{mirante}/findings/{fid}"
    async with _client() as manager, _client() as reviewer:
        await login(manager, mailer, GERENTE)
        await login(reviewer, mailer, REVISORA)
        assert (await manager.get(base)).json()["allowed_actions"] == []
        r = await manager.post(f"{base}/decisions", json={"action": "validar"})
        assert r.status_code == 403
        r = await reviewer.post(f"{base}/decisions", json={"action": "validar"})
        assert r.status_code == 200


async def test_pending_evidence_blocks_closing_the_month(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from app.reports.data import pending_for_month

    fid = await _finding(admin_engine)
    mirante = await condo_id(admin_engine, MIRANTE)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(Finding).where(Finding.id == fid).values(status="pendente_evidencia")
        )
    async with sessionmaker_for(admin_engine)() as s:
        pending = await pending_for_month(s, mirante, date(2020, 2, 1))
    assert pending["achados_graves"] >= 1
