"""CondoOS Launch, LF2-a (D89): milestones from facts, readiness per capability, the
first-value card of a contract, next steps by goal, and the API with its permissions."""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.core.money import brl
from app.core.time import utcnow
from app.db.enums import PolicyDecision
from app.db.models import (
    AuditLog,
    BankTransaction,
    Competence,
    Condominium,
    Contract,
    Document,
    Expense,
    Membership,
)
from app.db.session import sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.launch.first_value import first_value
from app.launch.journey import milestones
from app.launch.readiness import Readiness, readiness
from app.launch.state import portfolio_row
from app.launch.steps import next_steps
from app.onboarding import onboard
from app.policy import evaluate as policy_evaluate
from tests.helpers import (
    ADMIN_CONDOOS,
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)
from tests.test_onboarding import _spec

CONTRACT_TEXT = (
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE PORTARIA\n"
    "CONTRATADA: Portaria Fictícia Ltda\n"
    "Valor mensal de R$ 12.480,00, reajustado anualmente pelo IPCA.\n"
    "Vigência a partir de 01/02/2026."
)
EXTRACTED: dict[str, Any] = {
    "cnpj_contratada": "",  # filled per test
    "razao_social_contratada": "Portaria Fictícia Ltda",
    "objeto": "Portaria 24 horas",
    "itens_escopo": ["portaria"],
    "valor_mensal": "12480.00",
    "indice_reajuste": "IPCA",
    "data_inicio": "2026-02-01",
}


def _document(condo: Condominium, doc_type: str, **kw: Any) -> Document:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": condo.id,
        "doc_type": doc_type,
        "storage_key": f"cond/{condo.id}/x",
        "sha256": uuid.uuid4().hex * 2,
        "original_filename": f"{doc_type}.pdf",
        "mime_type": "application/pdf",
        "origin": "upload",
        "extraction_status": "done",
        "extracted": {},
        "field_confidence": {},
        "needs_review": False,
        "review_reasons": [],
    }
    base.update(kw)
    return Document(**base)


async def _new_condo(s: AsyncSession) -> Condominium:
    return await onboard(s, _spec(management_company_name=None))


def _by_key(items: list[Any]) -> dict[str, Any]:
    return {i.key: i for i in items}


async def test_new_condominium_journey_from_facts(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        ms = _by_key(await milestones(s, condo.id))
        assert not any(m.done for m in ms.values())  # the síndico has not logged in yet
        ready = _by_key(await readiness(s, condo.id))
        assert {ready[k].state for k in ("C1", "C2", "C3")} == {"nao_configurado"}
        assert ready["C7"].state == "supervisionada"  # registered with an approval limit

        # LM1: the síndico's first login accepts the access.
        await s.execute(
            update(Membership)
            .where(Membership.condominium_id == condo.id)
            .values(accepted_at=utcnow())
        )
        ms = _by_key(await milestones(s, condo.id))
        assert ms["LM1"].done and ms["LM1"].ref and ms["LM1"].ref["kind"] == "membership"
        assert not ms["LM2"].done

        # LM2: a contract read in full, with its text.
        cnpj = generate_cnpj(random.Random(f"launch-{condo.id}"))
        doc = _document(
            condo,
            "contrato",
            text_content=CONTRACT_TEXT,
            extracted={**EXTRACTED, "cnpj_contratada": cnpj},
            field_confidence={k: 0.95 for k in EXTRACTED},
        )
        s.add(doc)
        await s.flush()
        ms = _by_key(await milestones(s, condo.id))
        assert ms["LM2"].done and ms["LM2"].ref == {"kind": "document", "id": str(doc.id)}
        ready = _by_key(await readiness(s, condo.id))
        assert ready["C1"].state == "analise_parcial"  # not indexed yet; chat in replay
        assert ready["C2"].state == "analise_parcial"  # no contract organised yet
        assert ready["C3"].state == "nao_configurado"

        supplier = await get_or_create_supplier(s, cnpj, "Portaria Fictícia Ltda")
        contract = Contract(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=supplier.id,
            object="Portaria 24 horas",
            scope_items=[],
            monthly_value=Decimal("12480.00"),
            adjustment_index="IPCA",
            start_date=date(2026, 2, 1),
            source_document_id=doc.id,
        )
        s.add(contract)
        await s.flush()
        ready = _by_key(await readiness(s, condo.id))
        assert ready["C2"].state == "supervisionada"
        assert "Envie as notas" in ready["C3"].missing[0]

        # LM3: an expense of the contract in a month that went through the rules.
        month = date(2026, 10, 1)
        s.add(
            Expense(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                supplier_id=supplier.id,
                contract_id=contract.id,
                competence=month,
                issue_date=date(2026, 10, 5),
                amount=Decimal("12480.00"),
                category="portaria",
                description="Portaria 10/2026",
                invoice_number="77",
            )
        )
        s.add(Competence(id=uuid.uuid4(), condominium_id=condo.id, month=month))
        await s.flush()
        ms = _by_key(await milestones(s, condo.id))
        assert ms["LM3"].done and ms["LM3"].ref == {"kind": "competence", "id": "2026-10"}
        assert not ms["LM4"].done and not ms["LM5"].done
        c3 = _by_key(await readiness(s, condo.id))["C3"]
        assert c3.state == "analise_parcial"
        assert c3.facts["contratos_com_cobranca"] == 1 == c3.facts["contratos_vigentes"]
        assert any("extrato" in m for m in c3.missing)

        s.add(
            BankTransaction(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                posted_at=date(2026, 10, 10),
                amount=Decimal("-12480.00"),
                description="Pagamento portaria",
                origin="ofx",
                external_id=f"launch-{condo.id}",
            )
        )
        await s.flush()
        assert _by_key(await readiness(s, condo.id))["C3"].state == "supervisionada"
        await s.rollback()


async def test_uncertain_contract_field_is_never_a_fact(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        cnpj = generate_cnpj(random.Random(f"fv-{condo.id}"))
        conf = {k: 0.95 for k in EXTRACTED} | {"valor_mensal": 0.6}
        doc = _document(
            condo,
            "contrato",
            extraction_status="needs_review",
            needs_review=True,
            text_content=CONTRACT_TEXT,
            extracted={**EXTRACTED, "cnpj_contratada": cnpj},
            field_confidence=conf,
            field_provenance={
                "valor_mensal": {"source": "texto", "page": 1, "excerpt": "R$ 12.480,00"}
            },
        )
        s.add(doc)
        await s.flush()
        card = await first_value(s, doc)
        fields = {f["name"]: f for f in card["fields"]}
        assert card["state"] == "parcial"
        assert fields["valor_mensal"]["status"] == "a_confirmar"
        # The value shown is the extracted one, formatted; nothing computed.
        assert fields["valor_mensal"]["value"] == brl(Decimal(EXTRACTED["valor_mensal"]))
        assert fields["valor_mensal"]["evidence"]["excerpt"] == "R$ 12.480,00"
        assert fields["objeto"]["status"] == "lido"
        assert fields["data_fim"]["status"] == "lido"  # no end date: indeterminate
        assert "valor mensal" in card["message"]
        assert any("não uma auditoria" in limit for limit in card["limits"])
        assert _by_key(await readiness(s, condo.id))["C2"].state == "analise_parcial"

        # Missing field: "não encontrado", never a guessed value.
        doc.extracted = {k: v for k, v in doc.extracted.items() if k != "indice_reajuste"}
        card = await first_value(s, doc)
        index = next(f for f in card["fields"] if f["name"] == "indice_reajuste")
        assert index == {
            "name": "indice_reajuste",
            "label": "Índice de reajuste",
            "status": "nao_encontrado",
            "value": None,
        }

        for status, state in (("pending", "lendo"), ("failed", "falhou")):
            doc.extraction_status = status
            assert (await first_value(s, doc))["state"] == state
        nf = _document(condo, "nfse")
        s.add(nf)
        await s.flush()
        card = await first_value(s, nf)
        assert card["state"] == "outro_tipo" and "nota fiscal" in card["message"]
        await s.rollback()


def _r(key: str, state: str, **facts: Any) -> Readiness:
    return Readiness(key, key, state, [], facts)  # type: ignore[arg-type]


def test_next_steps_follow_the_goal_and_postponement() -> None:
    today = date(2026, 11, 7)
    empty = [
        _r("C1", "nao_configurado", documentos_lidos=0),
        _r("C2", "nao_configurado"),
        _r("C3", "nao_configurado"),
    ]
    steps = next_steps("economizar", empty, 0, {}, today)
    assert [s["key"] for s in steps] == ["enviar_contrato", "enviar_convencao"]
    assert [s["primary"] for s in steps] == [True, False]
    assert len(next_steps(None, empty, 0, {}, today)) == 3  # never more than three
    assert all(s["why"] and s["unlocks"] for s in steps)
    assert next_steps("pendencias", empty, 0, {}, today)[0]["key"] == "criar_assunto"
    assert next_steps("panorama", empty, 0, {}, today)[0]["key"] == "enviar_convencao"

    later = {"enviar_contrato": "2026-11-14", "criar_assunto": "2026-11-01"}  # one expired
    keys = [s["key"] for s in next_steps(None, empty, 0, later, today)]
    assert keys == ["enviar_convencao", "criar_assunto"]

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
    keys = [s["key"] for s in next_steps("economizar", with_contract, 1, {}, today)]
    assert keys == ["enviar_extrato"]  # only what is actually missing


async def test_launch_api_permissions_and_isolation(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/launch"

    await login(client, mailer, CONSELHEIRO_ACACIAS)
    r = await client.get(base)
    assert r.status_code == 200 and r.json()["can_manage"] is False
    assert (await client.put(f"{base}/goal", json={"goal": "economizar"})).status_code == 403

    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(base)).status_code == 404  # another condominium

    await login(client, mailer, SINDICA_ACACIAS)
    body = (await client.get(base)).json()
    assert body["can_manage"] is True
    assert [m["key"] for m in body["milestones"]] == ["LM1", "LM2", "LM3", "LM4", "LM5"]
    assert body["milestones"][0]["done"] is True  # she has just logged in
    assert [r["key"] for r in body["readiness"]] == ["C1", "C2", "C3", "C7"]
    assert len(body["next_steps"]) <= 3

    r = await client.put(f"{base}/goal", json={"goal": "economizar"})
    assert r.status_code == 200
    assert (await client.get(base)).json()["goal"] == "economizar"
    assert (await client.put(f"{base}/goal", json={"goal": "tudo"})).status_code == 422
    assert (await client.post(f"{base}/postpone", json={"step": "x"})).status_code == 422
    r = await client.post(f"{base}/postpone", json={"step": "criar_assunto"})
    assert r.status_code == 200
    assert "criar_assunto" not in [s["key"] for s in (await client.get(base)).json()["next_steps"]]
    assert (await client.put(f"{base}/dismissed", json={"dismissed": True})).status_code == 200
    assert (await client.get(base)).json()["dismissed"] is True
    await client.put(f"{base}/dismissed", json={"dismissed": False})
    await client.put(f"{base}/goal", json={"goal": None})

    async with sessionmaker_for(admin_engine)() as s:
        actions = set(
            (
                await s.scalars(
                    select(AuditLog.action).where(
                        AuditLog.condominium_id == acacias, AuditLog.action.like("launch.%")
                    )
                )
            ).all()
        )
        assert {"launch.goal_selected", "launch.step_postponed", "launch.dismissed"} <= actions

    # CondoOS admin assigned to the condominium may also guide the journey.
    await login(client, mailer, ADMIN_CONDOOS)
    assert (await client.get(base)).json()["can_manage"] is True


async def test_first_value_route_is_scoped_and_recorded_once(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await s.get(Condominium, acacias)
        assert condo is not None
        doc = _document(condo, "ata", text_content="Ata da assembleia\fSegunda página")
        doc.page_count = 2
        s.add(doc)

    await login(client, mailer, SINDICA_MIRANTE)
    url = f"/condominiums/{mirante}/documents/{doc.id}/first-value"
    assert (await client.get(url)).status_code == 404  # document of another condominium

    await login(client, mailer, SINDICA_ACACIAS)
    url = f"/condominiums/{acacias}/documents/{doc.id}/first-value"
    for _ in range(2):
        r = await client.get(url)
        assert r.status_code == 200
        assert r.json()["state"] == "memoria" and "2 páginas" in r.json()["message"]
    async with sessionmaker_for(admin_engine)() as s:
        shown = (
            await s.scalars(
                select(AuditLog.id).where(
                    AuditLog.action == "launch.first_value_shown", AuditLog.object_id == doc.id
                )
            )
        ).all()
    assert len(shown) == 1


# --------------------------------------------------------------------------- LF2-b (D90)


async def test_condominium_without_limits_waits_for_them(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """LB-009: limits are optional at registration; without them actions with a cost are
    refused by the policy and C7 says what is missing."""
    await login(client, mailer, ADMIN_CONDOOS)
    r = await client.post(
        "/portfolio/condominiums",
        json={
            "condominium": {
                "name": "Residencial Sem Alçada (fictício)",
                "slug": f"sem-alcada-{uuid.uuid4().hex[:6]}",
                "cnpj": generate_cnpj(random.Random()),
                "units": 24,
                "address": "Rua Fictícia, 20 — Cidade Modelo/SP",
            },
            "board": [
                {"name": "Síndica Sem Alçada", "position": "sindico", "term_start": "2026-01-01"}
            ],
        },
    )
    assert r.status_code == 201, r.text
    cid = uuid.UUID(r.json()["id"])
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.get(Condominium, cid)
        assert condo is not None and condo.approval_limits == {}
        c7 = _by_key(await readiness(s, cid))["C7"]
        assert c7.state == "nao_configurado" and "alçada" in c7.missing[0].lower()
        paid = await policy_evaluate(
            s, condo, action_type="fornecedor.cobrar", cost_cap=Decimal("500.00")
        )
        assert paid.decision == PolicyDecision.REQUIRE_REVIEW
        free = await policy_evaluate(
            s, condo, action_type="orcamento.solicitar", cost_cap=Decimal("0")
        )
        assert free.decision == PolicyDecision.REQUIRE_APPROVAL

    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(admin_engine)() as s:
        assert _by_key(await readiness(s, acacias))["C7"].state in (
            "supervisionada",
            "analise_parcial",  # a test may have paused actions
        )


async def test_portfolio_launch_and_time_to_first_value(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """LB-012 and LB-090: the team sees each implementation and the time from the síndico's
    first login to the first reading shown; the síndica does not see the portfolio."""
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        login_at = utcnow() - timedelta(hours=3)
        await s.execute(
            update(Membership)
            .where(Membership.condominium_id == condo.id)
            .values(accepted_at=login_at)
        )
        s.add(
            AuditLog(
                action="launch.first_value_shown",
                object_type="document",
                object_id=uuid.uuid4(),
                condominium_id=condo.id,
                created_at=login_at + timedelta(hours=1, minutes=30),
            )
        )
        today = date.today()
        row = await portfolio_row(s, condo, today)
    assert row["milestones_done"] == 1 and row["next_milestone"] == "Seu condomínio ganhou memória"
    assert row["hours_to_first_value"] == 1.5
    assert row["days_idle"] == 0 and row["capabilities_total"] == 4

    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get("/portfolio/launch")).json() == []
    await login(client, mailer, ADMIN_CONDOOS)
    rows = (await client.get("/portfolio/launch")).json()
    acacias = str(await condo_id(admin_engine, "jardim-das-acacias"))
    assert acacias in {r["id"] for r in rows}
    assert all(r["milestones_total"] == 5 for r in rows)
