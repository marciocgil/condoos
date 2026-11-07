"""D93 (LF3-b): conflicts between documents — detectors (positive and negative),
idempotency, "superado", resolution by a person, effects on readiness, first-value card,
policy and findings' evidence, and the API with its permissions and isolation."""

import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.data_issues import DataIssueError, detect, discard, open_issues, reopen, resolve
from app.db.enums import PolicyDecision, Severity
from app.db.models import (
    AppUser,
    Condominium,
    Contract,
    ContractAmendment,
    DataIssue,
    DataIssueEvent,
    Document,
    Supplier,
)
from app.db.session import sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.launch.first_value import first_value
from app.launch.readiness import readiness
from app.onboarding import onboard
from app.policy import evaluate as policy_evaluate
from app.rules.base import Evidence, FindingDraft
from app.rules.engine import _conflict_evidence
from tests.helpers import (
    ADMIN_CONDOOS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)
from tests.test_onboarding import _spec

REASON = "Conferido com a administradora: vale o documento assinado."


def _doc(condo: Condominium, extracted: dict[str, Any], **kw: Any) -> Document:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": condo.id,
        "doc_type": "contrato",
        "storage_key": f"cond/{condo.id}/x",
        "sha256": uuid.uuid4().hex * 2,
        "original_filename": "contrato.pdf",
        "mime_type": "application/pdf",
        "origin": "upload",
        "extraction_status": "done",
        "extracted": extracted,
        "field_confidence": {},
        "needs_review": False,
        "review_reasons": [],
    }
    base.update(kw)
    return Document(**base)


async def _setup(s: AsyncSession) -> tuple[Condominium, Supplier, Contract, Document]:
    condo = await onboard(s, _spec(management_company_name=None))
    supplier = await get_or_create_supplier(
        s, generate_cnpj(random.Random(f"di-{condo.id}")), "Portaria Fictícia Ltda"
    )
    source = _doc(
        condo,
        {"data_inicio": "2026-01-01", "data_fim": "2026-06-30", "valor_mensal": "9000.00"},
        field_provenance={"data_fim": {"source": "texto", "page": 2, "excerpt": "até 30/06/2026"}},
    )
    s.add(source)
    await s.flush()
    contract = Contract(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        supplier_id=supplier.id,
        object="Portaria 24 horas",
        scope_items=[],
        monthly_value=Decimal("9000.00"),
        adjustment_index="IPCA",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        source_document_id=source.id,
    )
    s.add(contract)
    await s.flush()
    return condo, supplier, contract, source


def _amendment(
    condo: Condominium, contract: Contract, effective: date, value: str | None, doc: Document
) -> ContractAmendment:
    return ContractAmendment(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        contract_id=contract.id,
        document_id=doc.id,
        effective_date=effective,
        monthly_value=Decimal(value) if value else None,
        scope_items=[],
        description="Termo aditivo",
    )


async def _events(s: AsyncSession, issue_id: uuid.UUID) -> list[str]:
    return list(
        await s.scalars(
            select(DataIssueEvent.kind)
            .where(DataIssueEvent.issue_id == issue_id)
            .order_by(DataIssueEvent.created_at)
        )
    )


async def test_amendment_outside_the_term(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, supplier, contract, source = await _setup(s)
        inside = _doc(condo, {"data_inicio": "2026-05-01"})
        s.add(inside)
        await s.flush()
        s.add(_amendment(condo, contract, date(2026, 5, 1), "9500.00", inside))
        await s.flush()
        assert (await detect(s, condo.id)).opened == []  # negative: within the term

        late = _doc(
            condo,
            {"data_inicio": "2026-08-01"},
            field_provenance={"data_inicio": {"excerpt": "a partir de 01/08/2026", "page": 1}},
        )
        s.add(late)
        await s.flush()
        amendment = _amendment(condo, contract, date(2026, 8, 1), None, late)
        s.add(amendment)
        await s.flush()
        result = await detect(s, condo.id)
        assert len(result.opened) == 1
        issue = await s.get(DataIssue, result.opened[0])
        assert issue is not None
        assert issue.detector == "aditivo_fora_da_vigencia_v1" and issue.field == "data_fim"
        assert issue.supplier_id == supplier.id and issue.subject_id == contract.id
        sides = {e["label"]: e for e in issue.evidence}
        assert sides["Contrato"]["excerpt"] == "até 30/06/2026"
        assert sides["Aditivo"]["excerpt"] == "a partir de 01/08/2026"
        assert "fraude" not in (issue.title + issue.detail).lower()

        # Idempotent: detecting again changes nothing.
        assert (await detect(s, condo.id)).opened == []
        count = await s.scalar(
            select(func.count()).select_from(DataIssue).where(DataIssue.condominium_id == condo.id)
        )
        assert count == 1 and await _events(s, issue.id) == ["detectado"]

        # Effects while open: readiness, first-value card, policy, findings' evidence.
        ready = {r.key: r for r in await readiness(s, condo.id, date(2026, 11, 20))}
        assert ready["C2"].state == "analise_parcial"
        assert any("Divergência em validação" in m for m in ready["C2"].missing)
        card = await first_value(s, source)
        fields = {f["name"]: f for f in card["fields"]}
        assert fields["data_fim"]["status"] == "conflitante"
        assert card["conflicts"] and card["state"] == "parcial"
        denied = await policy_evaluate(
            s,
            condo,
            action_type="fornecedor.cobrar",
            cost_cap=Decimal("0"),
            supplier_id=supplier.id,
        )
        assert denied.decision == PolicyDecision.DENY and "divergência" in denied.reason
        draft = FindingDraft(
            rule_code="R02",
            severity=Severity.MEDIA,
            title="t",
            explanation="e",
            amount_at_risk=Decimal("1"),
            subject_key="k",
            evidence=[Evidence("contract", str(contract.id), "Contrato")],
        )
        extra = _conflict_evidence(draft, {str(contract.id): [issue]})
        assert extra and extra[0]["kind"] == "data_issue"

        # Superado: the late amendment goes away, nobody had acted -> discarded by itself.
        await s.delete(amendment)
        await s.flush()
        assert (await detect(s, condo.id)).superseded == [issue.id]
        assert issue.status == "descartado"
        assert (issue.resolution or {}).get("superado") is True
        # ...and comes back if detected again.
        s.add(_amendment(condo, contract, date(2026, 8, 1), None, late))
        await s.flush()
        assert (await detect(s, condo.id)).opened == [issue.id]
        assert issue.status == "aberto"
        assert await _events(s, issue.id) == ["detectado", "superado", "redetectado"]

        # A person resolves: a reason and one of the sides are required.
        user = await s.scalar(select(AppUser).limit(1))
        assert user is not None
        for index, reason in ((0, "curto"), (5, REASON)):
            with pytest.raises(DataIssueError):
                await resolve(s, issue, user_id=user.id, prevailing_index=index, reason=reason)
        await s.rollback()


async def test_lifecycle_by_a_person_and_policy_after(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, supplier, contract, _ = await _setup(s)
        a1 = _doc(condo, {})
        a2 = _doc(condo, {})
        s.add_all([a1, a2])
        await s.flush()
        s.add(_amendment(condo, contract, date(2026, 3, 1), "9500.00", a1))
        s.add(_amendment(condo, contract, date(2026, 3, 1), "9500.00", a2))
        await s.flush()
        assert (await detect(s, condo.id)).opened == []  # negative: same value on the same day
        second = await s.scalar(
            select(ContractAmendment).where(ContractAmendment.document_id == a2.id)
        )
        assert second is not None
        second.monthly_value = Decimal("9900.00")
        await s.flush()
        [issue_id] = (await detect(s, condo.id)).opened
        issue = await s.get(DataIssue, issue_id)
        assert issue is not None and issue.detector == "aditivos_mesmo_dia_v1"
        assert issue.amount_at_stake == Decimal("400.00")

        user = await s.scalar(select(AppUser).limit(1))
        assert user is not None
        chosen = next(i for i, e in enumerate(issue.evidence) if e["value"].startswith("R$ 9.900"))
        await resolve(s, issue, user_id=user.id, prevailing_index=chosen, reason=REASON)
        assert issue.status == "resolvido"
        assert issue.resolution is not None
        assert issue.resolution["prevailing"]["value"].startswith("R$ 9.900,00")
        allowed = await policy_evaluate(
            s,
            condo,
            action_type="fornecedor.cobrar",
            cost_cap=Decimal("0"),
            supplier_id=supplier.id,
        )
        assert allowed.decision == PolicyDecision.REQUIRE_APPROVAL
        # What a person decided stays, even if detection runs again.
        await detect(s, condo.id)
        assert issue.status == "resolvido"
        await reopen(s, issue, user_id=user.id, reason="Chegou um terceiro aditivo do mesmo dia.")
        assert issue.status == "aberto"
        await discard(s, issue, user_id=user.id, reason="São dois serviços diferentes, conferido.")
        assert issue.status == "descartado"
        # Gone from the documents now: a person acted, so it is not touched.
        assert await open_issues(s, condo.id) == []
        await s.rollback()


async def test_overlapping_contracts(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, supplier, _, source = await _setup(s)

        def other(
            obj: str, start: date, doc_id: uuid.UUID | None = None, end: date | None = None
        ) -> Contract:
            return Contract(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                supplier_id=supplier.id,
                object=obj,
                scope_items=[],
                monthly_value=Decimal("8000.00"),
                adjustment_index="IPCA",
                start_date=start,
                end_date=end,
                source_document_id=doc_id,
            )

        s.add(other("Limpeza das áreas comuns", date(2026, 3, 1)))  # different service
        s.add(other("Portaria 24 horas", date(2026, 7, 1)))  # starts after the first ends
        version = _doc(condo, {}, supersedes_id=source.id)  # a new version of the same document
        s.add(version)
        await s.flush()
        s.add(other("Portaria 24 horas", date(2026, 2, 1), version.id, date(2026, 6, 30)))
        await s.flush()
        assert (await detect(s, condo.id)).opened == []  # three negatives

        # Overlaps the original contract (R$ 9.000) and the version-chained one (R$ 8.000).
        s.add(other("Serviço de portaria 24 horas", date(2026, 4, 1), None, date(2026, 6, 30)))
        await s.flush()
        opened = (await detect(s, condo.id)).opened
        assert len(opened) == 2
        issues = [await s.get(DataIssue, i) for i in opened]
        assert all(i is not None and i.detector == "contratos_sobrepostos_v1" for i in issues)
        assert {i.amount_at_stake for i in issues if i} == {Decimal("1000.00"), None}
        assert all(i is not None and len(i.evidence) == 2 for i in issues)
        await s.rollback()


async def test_api_permissions_and_isolation(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        supplier_id = await s.scalar(
            select(Contract.supplier_id).where(Contract.condominium_id == acacias).limit(1)
        )
        contract_id = await s.scalar(
            select(Contract.id).where(Contract.condominium_id == acacias).limit(1)
        )
        assert supplier_id and contract_id
        issue = DataIssue(
            id=uuid.uuid4(),
            condominium_id=acacias,
            kind="conflito_documentos",
            status="aberto",
            subject_type="contract",
            subject_id=contract_id,
            supplier_id=supplier_id,
            title="Aditivo com data de efeito fora da vigência do contrato",
            detail="Teste.",
            evidence=[{"label": "Contrato", "value": "a"}, {"label": "Aditivo", "value": "b"}],
            capabilities=["C2", "C3"],
            detector="teste",
            dedupe_key=f"teste:{uuid.uuid4()}",
        )
        s.add(issue)
    base = f"/condominiums/{acacias}/data-issues"

    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"{base}/{issue.id}")).status_code == 404

    await login(client, mailer, SINDICA_ACACIAS)
    body = (await client.get(f"{base}/{issue.id}")).json()
    assert body["can_resolve"] is False and body["status"] == "aberto"
    r = await client.post(f"{base}/{issue.id}/resolve", json={"prevailing": 0, "reason": REASON})
    assert r.status_code == 403  # the síndico does not resolve data conflicts (D93)
    assert (await client.get("/portfolio/data-issues")).json() == []

    await login(client, mailer, GERENTE)
    listed = (await client.get("/portfolio/data-issues")).json()
    assert str(issue.id) in {i["id"] for i in listed}
    r = await client.post(f"{base}/{issue.id}/resolve", json={"prevailing": 1, "reason": "curto"})
    assert r.status_code == 422
    r = await client.post(f"{base}/{issue.id}/resolve", json={"prevailing": 1, "reason": REASON})
    assert r.status_code == 200 and r.json()["status"] == "resolvido"
    assert (
        await client.post(f"{base}/{issue.id}/resolve", json={"prevailing": 1, "reason": REASON})
    ).status_code == 409

    await login(client, mailer, ADMIN_CONDOOS)
    r = await client.post(f"{base}/{issue.id}/reopen", json={"reason": "Reaberto para conferir."})
    assert r.status_code == 200 and r.json()["status"] == "aberto"
    r = await client.post(f"{base}/{issue.id}/discard", json={"reason": "Não era divergência."})
    assert r.status_code == 200
    events = (await client.get(f"{base}/{issue.id}")).json()["events"]
    assert [e["kind"] for e in events] == ["resolvido", "reaberto", "descartado"]
    assert all(e["by_person"] for e in events)
