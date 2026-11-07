"""LF3-b (ADR-L05, LB-030, LB-035, LB-036; D95): data conflicts as objects.

Acceptance: a contract whose registered value differs from what its own document says (as a
fact) opens one issue, idempotently; doubtful values, equal values and end dates changed by
an amendment open none; contradictory amendments and an amendment before the contract
starts open one each. A person resolves with the prevailing version and a reason (the value
is applied to the contract) or dismisses; nothing is deleted; the system closes an issue the
data no longer shows. While open: C2 is partial, the first-value card marks the field as
"conflitante", and the policy denies actions tied to the contract. Who resolves: síndico,
the manager only when the management company reviews, and the CondoOS team.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.auth.rbac import CondoAccess, Permission
from app.data_issues import AUTO_REASON, scan
from app.db.enums import PolicyDecision, Role
from app.db.models import (
    AuditLog,
    Condominium,
    Contract,
    ContractAmendment,
    DataIssue,
    Document,
)
from app.db.session import sessionmaker_for, set_tenant_scope
from app.launch.first_value import build as build_first_value
from app.policy import evaluate
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_MIRANTE, condo_id, login
from tests.test_launch import (
    _cap,
    _client,
    _contract,
    _contract_doc,
    _new_condo,
    _supplier,
    _view,
)

FACT = {"valor_mensal": 0.97, "data_inicio": 0.97, "data_fim": 0.97}


async def _read(
    admin_engine: AsyncEngine, did: uuid.UUID, values: dict[str, Any], conf: dict[str, float]
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        doc = await s.get(Document, did)
        assert doc is not None
        doc.extracted = values
        doc.field_confidence = conf
        doc.field_provenance = {
            "valor_mensal": {"source": "texto", "page": 1, "excerpt": "R$ 4.500,00 mensais"}
        }


async def _scan(admin_engine: AsyncEngine, cid: uuid.UUID) -> list[DataIssue]:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        return await scan(s, cid)


async def _issues(admin_engine: AsyncEngine, cid: uuid.UUID) -> list[DataIssue]:
    async with sessionmaker_for(admin_engine)() as s:
        return list(await s.scalars(select(DataIssue).where(DataIssue.condominium_id == cid)))


async def _conflicted(admin_engine: AsyncEngine) -> tuple[Condominium, str, uuid.UUID, uuid.UUID]:
    """A contract registered at R$ 4.000,00 whose own document says R$ 4.500,00."""
    condo, email = await _new_condo(admin_engine)
    did = await _contract_doc(admin_engine, condo.id)
    kid = await _contract(admin_engine, condo.id, did)  # 4000.00, from 2025-01-01
    await _read(admin_engine, did, {"valor_mensal": "4500.00", "data_inicio": "2025-01-01"}, FACT)
    return condo, email, did, kid


# --------------------------------------------------------------------------- detection


async def test_contract_and_its_document_disagree(admin_engine: AsyncEngine) -> None:
    condo, _, _, kid = await _conflicted(admin_engine)
    opened = await _scan(admin_engine, condo.id)
    assert len(opened) == 1
    issue = opened[0]
    assert (issue.subject_id, issue.field_name, issue.capability) == (kid, "monthly_value", "C2")
    assert [s["value"] for s in issue.sources] == ["4000.00", "4500.00"]
    assert issue.sources[1]["excerpt"] == "R$ 4.500,00 mensais"
    assert len(await _scan(admin_engine, condo.id)) == 1  # idempotent
    assert len(await _issues(admin_engine, condo.id)) == 1
    c2 = _cap(await _view(admin_engine, condo.id), "C2")
    assert c2["state"] == "analise_parcial"
    assert [r["key"] for r in c2["requirements"] if not r["met"]] == ["sem_conflito_aberto"]


async def test_no_conflict_without_a_fact_or_with_an_amendment(admin_engine: AsyncEngine) -> None:
    condo, _ = await _new_condo(admin_engine)
    did = await _contract_doc(admin_engine, condo.id)
    kid = await _contract(admin_engine, condo.id, did)
    # A doubtful value (below 0.9) is not a fact: no conflict.
    await _read(admin_engine, did, {"valor_mensal": "4500.00"}, {"valor_mensal": 0.6})
    assert await _scan(admin_engine, condo.id) == []
    # The same value: no conflict.
    await _read(admin_engine, did, {"valor_mensal": "4000.00"}, FACT)
    assert await _scan(admin_engine, condo.id) == []
    # A different end date that an amendment explains (D66): no conflict.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        contract = await s.get(Contract, kid)
        assert contract is not None
        contract.end_date = date(2027, 12, 31)
        s.add(
            ContractAmendment(
                condominium_id=condo.id,
                contract_id=kid,
                effective_date=date(2026, 1, 1),
                end_date=date(2027, 12, 31),
                scope_items=[],
            )
        )
    await _read(admin_engine, did, {"valor_mensal": "4000.00", "data_fim": "2026-12-31"}, FACT)
    assert await _scan(admin_engine, condo.id) == []


async def test_contradictory_amendments_and_amendment_before_start(
    admin_engine: AsyncEngine,
) -> None:
    condo, _ = await _new_condo(admin_engine)
    kid = await _contract(admin_engine, condo.id, None)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        for value in ("4200.00", "4300.00"):
            s.add(
                ContractAmendment(
                    condominium_id=condo.id,
                    contract_id=kid,
                    effective_date=date(2026, 1, 1),
                    monthly_value=Decimal(value),
                    scope_items=[],
                )
            )
        s.add(
            ContractAmendment(
                condominium_id=condo.id,
                contract_id=kid,
                effective_date=date(2024, 6, 1),  # before the contract starts (2025-01-01)
                scope_items=[],
            )
        )
    fields = sorted(i.field_name or "" for i in await _scan(admin_engine, condo.id))
    assert fields == ["amendment", "start_date"]


# --------------------------------------------------------------------------- resolution


async def test_sindico_resolves_with_the_prevailing_version(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email, _, kid = await _conflicted(admin_engine)
    [issue] = await _scan(admin_engine, condo.id)
    base = f"/condominiums/{condo.id}/data-issues"
    async with _client() as c:
        await login(c, mailer, email)
        listed = (await c.get(base)).json()
        assert [i["id"] for i in listed] == [str(issue.id)] and listed[0]["can_resolve"]
        r = await c.post(f"{base}/{issue.id}/resolve", json={"prevailing": 1, "reason": "curto"})
        assert r.status_code == 422  # a reason is required
        r = await c.post(f"{base}/{issue.id}/resolve", json={"prevailing": 5, "reason": "x" * 20})
        assert r.status_code == 422
        r = await c.post(
            f"{base}/{issue.id}/resolve",
            json={"prevailing": 1, "reason": "O documento assinado é o que vale."},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "resolvido"
        assert r.json()["resolution"]["applied"] == {"field": "monthly_value", "before": "4000.00"}
        again = await c.post(f"{base}/{issue.id}/dismiss", json={"reason": "x" * 20})
        assert again.status_code == 422  # already handled
        assert (await c.get(base)).json() == []
    async with sessionmaker_for(admin_engine)() as s:
        contract = await s.get(Contract, kid)
        assert contract is not None and contract.monthly_value == Decimal("4500.00")
        actions = (
            await s.scalars(
                select(AuditLog.action)
                .where(AuditLog.object_id == issue.id)
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert actions == ["data_issue.detected", "data_issue.resolved"]
    assert await _scan(admin_engine, condo.id) == []  # the data agree now
    assert len(await _issues(admin_engine, condo.id)) == 1  # nothing deleted, nothing new
    assert _cap(await _view(admin_engine, condo.id), "C2")["state"] == "supervisionada"


async def test_keeping_the_registered_value_holds(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email, _, kid = await _conflicted(admin_engine)
    [issue] = await _scan(admin_engine, condo.id)
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(
            f"/condominiums/{condo.id}/data-issues/{issue.id}/dismiss",
            json={"reason": "Valor do documento é de uma proposta antiga."},
        )
        assert r.status_code == 200 and r.json()["status"] == "descartado"
    assert await _scan(admin_engine, condo.id) == []  # the same values: not reopened
    async with sessionmaker_for(admin_engine)() as s:
        contract = await s.get(Contract, kid)
        assert contract is not None and contract.monthly_value == Decimal("4000.00")


async def test_system_closes_what_the_data_no_longer_show(admin_engine: AsyncEngine) -> None:
    condo, _, _, kid = await _conflicted(admin_engine)
    [issue] = await _scan(admin_engine, condo.id)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        contract = await s.get(Contract, kid)
        assert contract is not None
        contract.monthly_value = Decimal("4500.00")  # fixed by the contract form
    assert await _scan(admin_engine, condo.id) == []
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(DataIssue, issue.id)
    assert stored is not None and stored.status == "resolvido"
    assert stored.resolution == {"auto": True, "prevailing": None, "reason": AUTO_REASON}
    assert stored.resolved_by_user_id is None


# --------------------------------------------------------------------------- who and where


def test_who_may_resolve() -> None:
    def perms(role: Role, company_reviews: bool = False) -> frozenset[Permission]:
        return CondoAccess(
            uuid.uuid4(), uuid.uuid4(), frozenset({role}), company_reviews
        ).permissions

    for role in (Role.SINDICO, Role.CONDOOS_ADMIN, Role.CONDOOS_REVIEWER):
        assert Permission.RESOLVE_DATA_ISSUE in perms(role)
    assert Permission.RESOLVE_DATA_ISSUE not in perms(Role.GERENTE)  # company does not review
    assert Permission.RESOLVE_DATA_ISSUE in perms(Role.GERENTE, company_reviews=True)
    for role in (Role.CONSELHEIRO, Role.SUBSINDICO, Role.ANALISTA):
        assert Permission.RESOLVE_DATA_ISSUE not in perms(role, company_reviews=True)


async def test_conselheiro_sees_but_cannot_resolve_and_other_condo_is_404(
    mailer: MemoryMailer, admin_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    issue_id = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        kid = await s.scalar(select(Contract.id).where(Contract.condominium_id == acacias))
        assert kid is not None
        s.add(
            DataIssue(
                id=issue_id,
                condominium_id=acacias,
                kind="conflito_documentos",
                status="descartado",  # closed: does not change the seed's capabilities
                capability="C2",
                subject_type="contract",
                subject_id=kid,
                field_name="monthly_value",
                title="Teste de acesso",
                sources=[{"label": "A", "value": "1"}, {"label": "B", "value": "2"}],
                dedupe_key=f"test:{issue_id}",
                detected_at=date(2026, 11, 1),
            )
        )
    url = f"/condominiums/{acacias}/data-issues"
    body = {"reason": "Motivo suficiente para o teste."}
    async with _client() as c:
        await login(c, mailer, CONSELHEIRO_ACACIAS)
        listed = (await c.get(f"{url}?state=todos")).json()
        mine = next(i for i in listed if i["id"] == str(issue_id))
        assert mine["can_resolve"] is False
        assert (await c.post(f"{url}/{issue_id}/dismiss", json=body)).status_code == 403
    async with _client() as c:
        await login(c, mailer, SINDICA_MIRANTE)
        assert (await c.get(url)).status_code == 404
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [mirante])
        assert await s.get(DataIssue, issue_id) is None  # RLS


# --------------------------------------------------------------------------- policy and card


async def test_policy_denies_actions_on_a_contract_in_conflict(admin_engine: AsyncEngine) -> None:
    condo, _, _, kid = await _conflicted(admin_engine)
    [issue] = await _scan(admin_engine, condo.id)
    async with sessionmaker_for(admin_engine)() as s:
        found = await s.get(Condominium, condo.id)
        assert found is not None
        stored: Condominium = found

        async def decide(ids: list[uuid.UUID]) -> PolicyDecision:
            return (
                await evaluate(
                    s,
                    stored,
                    action_type="fornecedor.cobrar",
                    cost_cap=Decimal("0"),
                    contract_ids=ids,
                )
            ).decision

        assert await decide([kid]) == PolicyDecision.DENY
        assert await decide([]) == PolicyDecision.REQUIRE_APPROVAL
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        stored_issue = await s.get(DataIssue, issue.id)
        assert stored_issue is not None
        stored_issue.status = "descartado"
    async with sessionmaker_for(admin_engine)() as s:
        again = await s.get(Condominium, condo.id)
        assert again is not None
        result = await evaluate(
            s, again, action_type="fornecedor.cobrar", cost_cap=Decimal("0"), contract_ids=[kid]
        )
    assert result.decision == PolicyDecision.REQUIRE_APPROVAL


async def test_action_request_about_the_supplier_is_refused(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email, _, _ = await _conflicted(admin_engine)
    await _scan(admin_engine, condo.id)
    supplier = await _supplier(admin_engine)  # the contract's supplier in these helpers
    body = {
        "action_type": "fornecedor.cobrar",
        "title": "Cobrar a portaria",
        "cost_cap": "0",
        "idempotency_key": f"di-{uuid.uuid4()}",
        "payload": {
            "effect": "Cobrar do fornecedor a diferença do mês de outubro.",
            "reason": "O valor cobrado passou do previsto no contrato.",
            "executor": "Síndica",
            "supplier_id": str(supplier),
        },
    }
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(f"/condominiums/{condo.id}/actions", json=body)
    assert r.status_code == 422, r.text
    assert "conflito de dados" in r.json()["detail"]["message"]


def test_first_value_marks_conflicting_and_inferred_fields() -> None:
    doc = Document(
        id=uuid.uuid4(),
        condominium_id=uuid.uuid4(),
        doc_type="contrato",
        original_filename="contrato.pdf",
        extraction_status="done",
        extracted={"valor_mensal": "4500.00", "objeto": "Portaria", "data_inicio": "2025-01-01"},
        field_confidence={"valor_mensal": 0.97, "objeto": 0.97, "data_inicio": 0.97},
        field_provenance={
            "valor_mensal": {"source": "texto", "excerpt": "R$ 4.500,00"},
            "objeto": {"source": "ia"},  # confident, but no excerpt shows it
            "data_inicio": {"source": "xml"},
        },
        text_content="CONTRATO",
        reviewed_at=None,
    )
    plain = {f.name: f.state for f in build_first_value(doc).fields}
    assert plain["valor_mensal"] == "lido"
    assert plain["objeto"] == "inferido"
    assert plain["data_inicio"] == "lido"  # a fiscal XML needs no excerpt
    card = build_first_value(doc, {"valor_mensal": "Portaria: valor mensal difere"})
    assert {f.name: f.state for f in card.fields}["valor_mensal"] == "conflitante"
    assert card.status == "lido_parcial" and "não batem" in card.message
    assert card.next_step == {
        "key": "resolver_conflito",
        "title": "Escolha a versão certa em Conflitos de dados",
    }


async def test_first_value_route_shows_the_conflict(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email, did, _ = await _conflicted(admin_engine)
    await _scan(admin_engine, condo.id)
    async with _client() as c:
        await login(c, mailer, email)
        card = (await c.get(f"/condominiums/{condo.id}/launch/first-value/{did}")).json()
    by = {f["name"]: f["state"] for f in card["fields"]}
    assert by["valor_mensal"] == "conflitante"


async def test_contract_document_match_scans(
    admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    """The pipeline looks for conflicts whenever a contract document is matched."""
    from app.matching.documents import match_document_job

    condo, _, did, _ = await _conflicted(admin_engine)
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await match_document_job(s, {"document_id": str(did)})
    assert len(await _issues(admin_engine, condo.id)) == 1
