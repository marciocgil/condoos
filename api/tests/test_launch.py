"""CondoOS Launch LF2-a (D89): milestones derived from facts, readiness per capability, next
best steps and the stored choices of the journey.

Acceptance (``docs/condoos-planning/launch/05-backlog.md``): no milestone is done without its
fact, and nothing can mark one by hand; the seed's Jardim das Acácias has LM1-LM3 and a new
condominium only LM1; readiness states follow binary requirements; at most three steps, one
primary, in the goal's order, hiding what was put off; the conselheiro cannot change the
journey (403), another condominium is 404 and recorded.
"""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

import app.launch.readiness as readiness_mod
from app.auth.mailer import MemoryMailer
from app.config import get_settings
from app.core.br import generate_cnpj
from app.core.time import local_today, utcnow
from app.db.enums import PlatformRole
from app.db.models import (
    ActionRequest,
    AppUser,
    AuditLog,
    Competence,
    CondoAssignment,
    Condominium,
    Contract,
    Document,
    DocumentChunk,
    Expense,
    ExtractionCorrection,
    LaunchState,
    LlmCall,
    Membership,
    Supplier,
)
from app.db.session import sessionmaker_for, set_tenant_scope
from app.extraction.pipeline import process_document
from app.launch import overview
from app.launch.first_value import build as build_first_value
from app.launch.journey import milestones
from app.launch.metrics import implementation
from app.launch.readiness import readiness
from app.launch.steps import CATALOGUE, choose
from app.main import create_app
from app.onboarding import OnboardingIn, onboard
from app.routers import launch as launch_router
from tests.helpers import (
    ADMIN_CONDOOS,
    CONSELHEIRO_ACACIAS,
    GERENTE,
    REVISORA,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

ACACIAS = "jardim-das-acacias"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _done(view: dict[str, Any]) -> set[str]:
    return {m["key"] for m in view["milestones"] if m["done"]}


def _cap(view: dict[str, Any], capability: str) -> dict[str, Any]:
    return next(r for r in view["readiness"] if r["capability"] == capability)


async def _new_condo(admin_engine: AsyncEngine, with_limit: bool = True) -> tuple[Condominium, str]:
    tag = uuid.uuid4().hex[:8]
    email = f"sindica.{tag}@launch.example.com"
    spec = OnboardingIn.model_validate(
        {
            "management_company_name": "Atlântida Gestão Condominial Ltda (fictícia)",
            "condominium": {
                "name": f"Condomínio Bosque {tag} (fictício)",
                "slug": f"bosque-{tag}",
                "cnpj": generate_cnpj(random.Random(tag)),
                "units": 24,
                "address": "Rua Fictícia, 20 — Cidade Modelo/SP",
                "approval_limits": {"default": "5.000,00"} if with_limit else None,
            },
            "board": [
                {
                    "name": "Síndica Bosque",
                    "position": "sindico",
                    "term_start": "2026-01-01",
                    "email": email,
                }
            ],
        }
    )
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, spec)
    return condo, email


async def _view(admin_engine: AsyncEngine, cid: uuid.UUID) -> dict[str, Any]:
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.get(Condominium, cid)
        assert condo is not None
        return await overview(s, condo)


async def _supplier(admin_engine: AsyncEngine) -> uuid.UUID:
    async with sessionmaker_for(admin_engine)() as s:
        sid = await s.scalar(select(Supplier.id).limit(1))
    assert sid is not None
    return sid


async def _contract_doc(
    admin_engine: AsyncEngine, cid: uuid.UUID, *, needs_review: bool = False, chunk: bool = True
) -> uuid.UUID:
    did = uuid.uuid4()
    text = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE PORTARIA. Valor mensal R$ 4.000,00."
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Document(
                id=did,
                condominium_id=cid,
                doc_type="contrato",
                storage_key=f"cond/{cid}/{did}.txt",
                sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                original_filename="contrato-portaria.txt",
                mime_type="text/plain",
                origin="upload",
                extraction_status="needs_review" if needs_review else "done",
                needs_review=needs_review,
                field_confidence={"valor_mensal": 0.5} if needs_review else {},
                text_content=text,
            )
        )
        if chunk:
            await s.flush()
            s.add(DocumentChunk(condominium_id=cid, document_id=did, chunk_index=0, text=text))
    return did


async def _contract(
    admin_engine: AsyncEngine, cid: uuid.UUID, source: uuid.UUID | None, index: str = "IPCA"
) -> uuid.UUID:
    sid = await _supplier(admin_engine)
    kid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Contract(
                id=kid,
                condominium_id=cid,
                supplier_id=sid,
                object="Portaria",
                scope_items=["portaria 24h"],
                monthly_value=Decimal("4000.00"),
                adjustment_index=index,
                start_date=date(2025, 1, 1),
                source_document_id=source,
            )
        )
    return kid


async def _invoice(
    admin_engine: AsyncEngine, cid: uuid.UUID, contract: uuid.UUID, month: date, competence: bool
) -> None:
    sid = await _supplier(admin_engine)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Expense(
                condominium_id=cid,
                supplier_id=sid,
                contract_id=contract,
                competence=month,
                issue_date=month,
                amount=Decimal("4000.00"),
                category="portaria",
                description="Portaria do mês",
            )
        )
        if competence:
            s.add(Competence(condominium_id=cid, month=month))


# --------------------------------------------------------------------------- milestones


async def test_seed_condominium_has_lm1_to_lm3_with_their_facts(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    await login(client, mailer, SINDICA_ACACIAS)  # the síndico's first access (LM1)
    r = await client.get(f"/condominiums/{acacias}/launch")
    assert r.status_code == 200, r.text
    view = r.json()
    assert {"LM1", "LM2", "LM3"} <= _done(view)
    for m in view["milestones"]:
        if m["done"]:  # a done milestone always names its record and when
            assert m["fact"]["type"] and uuid.UUID(m["fact"]["id"])
            assert m["missing"] == []
        else:
            assert m["fact"] is None and m["missing"]
    lm3 = next(m for m in view["milestones"] if m["key"] == "LM3")
    assert lm3["details"]["contratos_esperados"] >= lm3["details"]["contratos_com_fatura"] > 0


async def test_new_condominium_has_only_lm1_after_the_first_access(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email = await _new_condo(admin_engine)
    assert _done(await _view(admin_engine, condo.id)) == set()  # invited, never logged in
    async with _client() as c:
        await login(c, mailer, email)
        view = (await c.get(f"/condominiums/{condo.id}/launch")).json()
    assert _done(view) == {"LM1"}
    states = {r["capability"]: r["state"] for r in view["readiness"]}
    assert states == {
        "C1": "nao_configurado",
        "C2": "nao_configurado",
        "C3": "nao_configurado",
        "C7": "supervisionada",  # limit set at onboarding, síndica logged in
    }
    assert view["steps"][0]["key"] == "enviar_contrato" and view["steps"][0]["primary"]


async def test_each_milestone_needs_its_fact(admin_engine: AsyncEngine) -> None:
    condo, _ = await _new_condo(admin_engine)
    cid = condo.id

    # LM2: a read contract without passages is not memory yet; with them it is.
    did = await _contract_doc(admin_engine, cid, chunk=False)
    assert "LM2" not in _done(await _view(admin_engine, cid))
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(DocumentChunk(condominium_id=cid, document_id=did, chunk_index=0, text="x"))
    assert "LM2" in _done(await _view(admin_engine, cid))

    # LM3: an invoice matched to a contract counts only once its month was evaluated.
    kid = await _contract(admin_engine, cid, did)
    month = date(2026, 9, 1)
    await _invoice(admin_engine, cid, kid, month, competence=False)
    assert "LM3" not in _done(await _view(admin_engine, cid))
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(Competence(condominium_id=cid, month=month))
    view = await _view(admin_engine, cid)
    lm3 = next(m for m in view["milestones"] if m["key"] == "LM3")
    assert lm3["done"] and lm3["details"]["mes"] == "2026-09"

    # LM4: the channel exists (management company with access), the reviewer does not.
    lm4 = next(m for m in view["milestones"] if m["key"] == "LM4")
    assert not lm4["done"] and lm4["missing"] == ["Nenhum revisor CondoOS atribuído."]
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        reviewer = await s.scalar(select(AppUser.id).where(AppUser.email == REVISORA))
        assert reviewer is not None
        s.add(
            CondoAssignment(
                condominium_id=cid,
                user_id=reviewer,
                platform_role=PlatformRole.CONDOOS_REVIEWER.value,
                reason="Teste do Launch",
                revoked_at=utcnow(),  # revoked: does not count
            )
        )
    assert "LM4" not in _done(await _view(admin_engine, cid))
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        a = await s.scalar(select(CondoAssignment).where(CondoAssignment.condominium_id == cid))
        assert a is not None
        a.revoked_at = None
    assert "LM4" in _done(await _view(admin_engine, cid))

    # LM5: an approved action counts only when a person recorded its execution.
    aid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            ActionRequest(
                id=aid,
                condominium_id=cid,
                action_type="orcamento.solicitar",
                title="Pedir orçamento",
                payload={},
                payload_hash="0" * 64,
                cost_cap=Decimal("0"),
                policy_decision="require_approval",
                policy_version=1,
                policy_reason="Exige aprovação do síndico.",
                status="aguardando_execucao_manual",
                idempotency_key=f"launch-{aid}",
            )
        )
    assert "LM5" not in _done(await _view(admin_engine, cid))
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        req = await s.get(ActionRequest, aid)
        assert req is not None
        req.status, req.executed_at = "executada", utcnow()
    assert _done(await _view(admin_engine, cid)) == {"LM2", "LM3", "LM4", "LM5"}


def test_no_route_marks_a_milestone() -> None:
    routes = {
        (method, r.path)
        for r in launch_router.router.routes
        if isinstance(r, APIRoute)
        for method in r.methods or set()
    }
    base = "/condominiums/{condominium_id}/launch"
    assert routes == {
        ("GET", base),
        ("PUT", f"{base}/goal"),
        ("POST", f"{base}/postpone"),
        ("POST", f"{base}/dismiss"),
        ("GET", f"{base}/first-value/{{document_id}}"),
        ("POST", f"{base}/first-value/{{document_id}}/shown"),
    }


# --------------------------------------------------------------------------- readiness


async def test_contract_with_field_to_confirm_is_partial(admin_engine: AsyncEngine) -> None:
    condo, _ = await _new_condo(admin_engine)
    await _contract_doc(admin_engine, condo.id, needs_review=True)
    view = await _view(admin_engine, condo.id)
    c2 = _cap(view, "C2")
    assert c2["state"] == "analise_parcial"
    unmet = {r["key"] for r in c2["requirements"] if not r["met"]}
    assert unmet == {"contrato_cadastrado", "sem_campo_a_confirmar"}
    assert _cap(view, "C3")["state"] == "nao_configurado"
    assert view["steps"][0]["key"] == "confirmar_contrato"


async def test_contract_without_invoice_then_with_invoice(admin_engine: AsyncEngine) -> None:
    condo, _ = await _new_condo(admin_engine)
    did = await _contract_doc(admin_engine, condo.id)
    kid = await _contract(admin_engine, condo.id, did)
    other = await _contract(admin_engine, condo.id, None, index="FIXO")  # typed, no document
    month = date(2026, 10, 1)
    await _invoice(admin_engine, condo.id, kid, month, competence=True)

    view = await _view(admin_engine, condo.id)
    c2, c3 = _cap(view, "C2"), _cap(view, "C3")
    assert c2["state"] == "analise_parcial"
    assert [r["key"] for r in c2["requirements"] if not r["met"]] == ["contratos_com_documento"]
    assert c3["state"] == "analise_parcial"
    assert c3["coverage"] == {
        "mes": "2026-10",
        "contratos_com_fatura": 1,
        "contratos_esperados": 2,
    }
    keys = [s["key"] for s in view["steps"]]
    assert keys == ["enviar_faturas", "enviar_documento_contrato"]

    # The typed contract gets its document and its invoice: everything is supervised.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        contract = await s.get(Contract, other)
        assert contract is not None
        contract.source_document_id = await _contract_doc(admin_engine, condo.id)
    await _invoice(admin_engine, condo.id, other, month, competence=False)
    view = await _view(admin_engine, condo.id)
    assert _cap(view, "C2")["state"] == "supervisionada"
    assert _cap(view, "C3")["state"] == "supervisionada"
    assert view["steps"] == []  # no goal: only contract steps, and none is missing


async def test_documents_capability_depends_on_the_assistant(
    admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    condo, _ = await _new_condo(admin_engine)
    await _contract_doc(admin_engine, condo.id)
    async with sessionmaker_for(admin_engine)() as s:
        c1 = (await readiness(s, condo))[0]
        assert c1.state == "analise_parcial"  # no API key in tests: the chat is unavailable
        assert [r.key for r in c1.missing] == ["assistente_disponivel"]
        monkeypatch.setattr(readiness_mod, "assistant_available", lambda: True)
        assert (await readiness(s, condo))[0].state == "supervisionada"


# --------------------------------------------------------------------------- steps


def test_steps_follow_the_goal_and_skip_what_was_put_off() -> None:
    pending = set(CATALOGUE)
    today = date(2026, 11, 7)
    assert [s.key for s in choose(pending, None, {}, today)] == [
        "enviar_contrato",
        "confirmar_contrato",
        "enviar_faturas",
    ]
    assert [s.key for s in choose(pending, "panorama", {}, today)][:2] == [
        "enviar_convencao",
        "enviar_ata",
    ]
    assert choose(pending, "pendencias", {}, today)[0].key == "criar_assunto"
    later = {"criar_assunto": (today + timedelta(days=3)).isoformat()}
    assert choose(pending, "pendencias", later, today)[0].key == "enviar_ata"
    past = {"criar_assunto": (today - timedelta(days=1)).isoformat()}
    assert choose(pending, "pendencias", past, today)[0].key == "criar_assunto"
    assert len(choose(pending, "panorama", {}, today)) == 3
    assert choose(set(), "economizar", {}, today) == []


# --------------------------------------------------------------------------- API and access


async def test_sindico_sets_goal_and_postpones_a_step(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email = await _new_condo(admin_engine)
    base = f"/condominiums/{condo.id}/launch"
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.put(f"{base}/goal", json={"goal": "panorama"})
        assert r.status_code == 200, r.text
        view = r.json()
        assert view["goal"] == "panorama" and view["goal_answered"]
        assert view["steps"][0]["key"] == "enviar_convencao"

        r = await c.post(f"{base}/postpone", json={"step": "enviar_convencao"})
        assert r.status_code == 200, r.text
        assert "enviar_convencao" not in [s["key"] for s in r.json()["steps"]]

        assert (await c.put(f"{base}/goal", json={"goal": "outro"})).status_code == 422
        too_far = (local_today(condo.timezone) + timedelta(days=200)).isoformat()
        r = await c.post(f"{base}/postpone", json={"step": "enviar_ata", "until": too_far})
        assert r.status_code == 422
        assert (await c.post(f"{base}/postpone", json={"step": "x"})).status_code == 422

        r = await c.put(f"{base}/goal", json={"goal": None})  # "Prefiro decidir depois"
        assert r.json()["goal"] is None and r.json()["goal_answered"]

        assert (await c.post(f"{base}/dismiss", json={"dismissed": True})).json()["dismissed"]

    async with sessionmaker_for(admin_engine)() as s:
        rows = (
            await s.scalars(select(LaunchState).where(LaunchState.condominium_id == condo.id))
        ).all()
        assert len(rows) == 1 and rows[0].dismissed_at is not None
        actions = (
            await s.scalars(
                select(AuditLog.action)
                .where(AuditLog.condominium_id == condo.id, AuditLog.action.like("launch.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert actions == [
        "launch.goal_selected",
        "launch.step_postponed",
        "launch.goal_selected",
        "launch.card_dismissed",
    ]


async def test_conselheiro_reads_but_cannot_change(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with _client() as c:
        await login(c, mailer, CONSELHEIRO_ACACIAS)
        assert (await c.get(f"/condominiums/{acacias}/launch")).status_code == 200
        r = await c.put(f"/condominiums/{acacias}/launch/goal", json={"goal": "economizar"})
        assert r.status_code == 403


async def test_condoos_admin_may_change_the_journey(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with _client() as c:
        await login(c, mailer, ADMIN_CONDOOS)
        r = await c.post(f"/condominiums/{acacias}/launch/dismiss", json={"dismissed": False})
        assert r.status_code == 200, r.text


async def test_other_condominium_is_404_and_recorded(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with sessionmaker_for(admin_engine)() as s:
        carla = await s.scalar(select(AppUser.id).where(AppUser.email == SINDICA_MIRANTE))
    async with _client() as c:
        await login(c, mailer, SINDICA_MIRANTE)
        assert (await c.get(f"/condominiums/{acacias}/launch")).status_code == 404
        r = await c.put(f"/condominiums/{acacias}/launch/goal", json={"goal": "panorama"})
        assert r.status_code == 404
    async with sessionmaker_for(admin_engine)() as s:
        events = (
            await s.scalars(
                select(AuditLog).where(
                    AuditLog.action == "security.access_denied",
                    AuditLog.actor_user_id == carla,
                )
            )
        ).all()
    routes = [e.details.get("route", "") for e in events]
    assert any(r.endswith("/launch") for r in routes)
    assert any(r.endswith("/launch/goal") for r in routes)


async def test_launch_state_is_isolated_by_rls(
    admin_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    condo, _ = await _new_condo(admin_engine)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(LaunchState(condominium_id=condo.id, goal="economizar", postponed={}))
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [mirante])
        assert (
            await s.scalar(select(LaunchState).where(LaunchState.condominium_id == condo.id))
        ) is None
        assert await milestones(s, condo) is not None  # reads nothing of the other tenant
        view = await overview(s, condo)
        assert view["goal"] is None


# --------------------------------------------------------------------------- first value (LF2-b)

NOTICE_TEXT = "CONTRATO DE PORTARIA. A rescisão exige aviso prévio de 30 (trinta) dias por escrito."


def _doc(**over: Any) -> Document:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": uuid.uuid4(),
        "doc_type": "contrato",
        "original_filename": "contrato.pdf",
        "extraction_status": "done",
        "extracted": {},
        "field_confidence": {},
        "field_provenance": {},
        "text_content": NOTICE_TEXT,
        "reviewed_at": None,
    }
    base.update(over)
    return Document(**base)


FULL = {
    "razao_social_contratada": "Portaria Modelo Ltda",
    "cnpj_contratada": "11222333000181",
    "cnpj_contratante": "11444777000161",
    "objeto": "Portaria 24 horas",
    "itens_escopo": ["portaria"],
    "valor_mensal": "12480.00",
    "indice_reajuste": "IPCA",
    "data_inicio": "2025-01-01",
}


def test_first_value_shows_only_what_was_read() -> None:
    conf = {k: 0.97 for k in FULL}
    prov = {"valor_mensal": {"source": "texto", "page": 1, "excerpt": "R$ 12.480,00 mensais"}}
    card = build_first_value(_doc(extracted=FULL, field_confidence=conf, field_provenance=prov))
    assert card.status == "lido" and card.next_step and card.next_step["key"] == "enviar_faturas"
    by = {f.name: f for f in card.fields}
    assert by["valor_mensal"].state == "lido"
    assert by["valor_mensal"].excerpt == "R$ 12.480,00 mensais"
    assert by["data_fim"].state == "nao_encontrado" and by["data_fim"].value is None
    assert by["aviso_previo_dias"].value == 30 and by["aviso_previo_dias"].source == "regra"
    assert card.limits  # what this reading does not cover is always said
    # nothing outside ``extracted`` (and the clause rule over the same text) appears
    for f in card.fields:
        if f.value is not None:
            assert f.value == (30 if f.name == "aviso_previo_dias" else FULL[f.name]), f.name


def test_first_value_never_shows_a_doubtful_field_as_fact() -> None:
    conf = {k: 0.97 for k in FULL} | {"valor_mensal": 0.6}
    card = build_first_value(_doc(extracted=FULL, field_confidence=conf, needs_review=True))
    assert card.status == "lido_parcial"
    by = {f.name: f for f in card.fields}
    assert by["valor_mensal"].state == "a_confirmar"
    assert "valor mensal" in card.message
    # once a person confirms the document, the same value is a fact
    confirmed = build_first_value(_doc(extracted=FULL, field_confidence=conf, reviewed_at=utcnow()))
    assert {f.name: f for f in confirmed.fields}["valor_mensal"].state == "lido"


def test_first_value_for_other_documents_and_failures() -> None:
    assert build_first_value(_doc(extraction_status="pending")).status == "lendo"
    failed = build_first_value(_doc(extraction_status="failed"))
    assert failed.status == "falhou" and "Não consegui ler" in failed.message
    unreadable = build_first_value(_doc(doc_type="outro", text_content=None, needs_review=True))
    assert unreadable.status == "nao_identificado"
    other = build_first_value(_doc(doc_type="outro"))  # readable text of another kind
    assert other.status == "nao_contrato"
    nf = build_first_value(_doc(doc_type="nfse"))
    assert nf.status == "nao_contrato" and "nota fiscal" in nf.message and nf.fields == []


async def test_first_value_route_records_the_event_once(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email = await _new_condo(admin_engine)
    did = await _contract_doc(admin_engine, condo.id, needs_review=True)
    base = f"/condominiums/{condo.id}/launch/first-value/{did}"
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.get(base)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "lido_parcial"
        assert (await c.post(f"{base}/shown")).json() == {"recorded": True}
        assert (await c.post(f"{base}/shown")).json() == {"recorded": False}
        missing = f"/condominiums/{condo.id}/launch/first-value/{uuid.uuid4()}"
        assert (await c.get(missing)).status_code == 404
        view = (await c.get(f"/condominiums/{condo.id}/launch")).json()
    assert view["done_for_you"] == []  # the contract is still to confirm: nothing read yet
    async with _client() as c:  # another condominium's document is not found
        await login(c, mailer, SINDICA_MIRANTE)
        assert (await c.get(base)).status_code == 404


async def test_done_for_you_counts_facts_only(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    items = {i["key"]: i for i in (await _view(admin_engine, acacias))["done_for_you"]}
    assert items["documentos_lidos"]["count"] > 0
    assert items["contratos_organizados"]["label"].endswith("contratos organizados")
    assert all(i["count"] > 0 for i in items.values())


# --------------------------------------------------------------------------- upload edges (LB-022)


async def test_upload_edges_leave_no_phantom_document(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    condo, email = await _new_condo(admin_engine)
    docs = f"/condominiums/{condo.id}/documents"
    corrupt = b"%PDF-1.7\n" + b"\x00garbage, not a real PDF\x00" * 40
    limit = get_settings().max_upload_mb * 1024 * 1024
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(
            docs,
            files=[
                ("files", ("vazio.pdf", b"", "application/pdf")),
                ("files", ("grande.pdf", b"%PDF" + b"0" * limit, "application/pdf")),
                ("files", ("planilha.xlsx", b"PK\x03\x04xl/", "application/zip")),
                ("files", ("contrato.pdf", corrupt, "application/pdf")),
            ],
        )
        assert r.status_code == 201, r.text
        out = r.json()
        assert out[0]["error"] == "Arquivo vazio."
        assert out[1]["error"] == f"Arquivo maior que {get_settings().max_upload_mb} MB."
        assert "Tipo de arquivo não aceito" in out[2]["error"]
        assert all(o["document_id"] is None for o in out[:3])
        corrupt_id = out[3]["document_id"]
        assert corrupt_id and out[3]["error"] is None

        # The same file again: the existing document, not a second one.
        again = await c.post(docs, files=[("files", ("copia.pdf", corrupt, "application/pdf"))])
        assert again.json()[0] == {
            "filename": "copia.pdf",
            "document_id": corrupt_id,
            "duplicate": True,
            "error": None,
        }

    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await process_document(s, {"document_id": corrupt_id})
    async with _client() as c:
        await login(c, mailer, email)
        card = (await c.get(f"/condominiums/{condo.id}/launch/first-value/{corrupt_id}")).json()
    assert card["status"] == "nao_identificado"  # never "parece outro tipo" for unreadable
    assert "PDF original" in card["message"]
    assert card["fields"] == []  # nothing invented from an unreadable file
    async with sessionmaker_for(admin_engine)() as s:
        stored = (
            await s.scalars(select(Document.id).where(Document.condominium_id == condo.id))
        ).all()
    assert [str(d) for d in stored] == [corrupt_id]  # only the file that was accepted


# --------------------------------------------------------------------------- instrumentation


async def test_implementation_metrics_come_from_records(admin_engine: AsyncEngine) -> None:
    condo, email = await _new_condo(admin_engine)
    start = utcnow() - timedelta(days=10)
    did = await _contract_doc(admin_engine, condo.id, needs_review=True)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        user = await s.scalar(select(AppUser).where(AppUser.email == email))
        assert user is not None
        m = await s.scalar(select(Membership).where(Membership.user_id == user.id))
        assert m is not None
        m.accepted_at = start
        for action, at in (
            ("launch.first_value_shown", start + timedelta(hours=3)),
            ("launch.step_postponed", start + timedelta(hours=4)),
            ("launch.step_postponed", start + timedelta(days=6)),
        ):
            s.add(
                AuditLog(
                    action=action,
                    object_type="launch_state",
                    actor_user_id=user.id,
                    condominium_id=condo.id,
                    created_at=at,
                )
            )
        for name in ("valor_mensal", "data_inicio"):
            s.add(
                ExtractionCorrection(
                    condominium_id=condo.id,
                    document_id=did,
                    user_id=user.id,
                    doc_type="contrato",
                    field_name=name,
                )
            )
        s.add(
            LlmCall(
                purpose="extract",
                model="modelo-teste",
                cost_usd=Decimal("0.0120"),
                condominium_id=condo.id,
            )
        )
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(Condominium, condo.id)
        assert stored is not None
        row = (await implementation(s, stored)).as_dict(now=start + timedelta(days=9))
    assert row["in_progress"] and row["milestones_done"] == 1
    assert row["next_milestone"] == "Seu condomínio ganhou memória"
    assert row["hours_to_first_value"] == 3.0
    assert row["postponed_steps"] == 2
    assert row["days_without_activity"] == 3  # the latest person's event was on day 6
    assert row["review_queue"] == 1
    assert row["documents"] == 1
    assert row["corrections_per_document"] == 2.0
    assert row["llm_cost_per_document_usd"] == "0.0120"
    assert row["readiness"] == {
        "C1": "nao_configurado",  # the only document still waits for review
        "C2": "analise_parcial",
        "C3": "nao_configurado",
        "C7": "supervisionada",
    }
    assert email not in str(row)  # ids and counts only


async def test_implementations_are_for_the_condoos_team_only(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with _client() as c:
        await login(c, mailer, ADMIN_CONDOOS)
        rows = (await c.get("/portfolio/launch")).json()
        assert {r["name"] for r in rows} >= {
            "Condomínio Residencial Jardim das Acácias",
            "Condomínio Edifício Mirante do Vale",
        }
        assert all(set(r["readiness"]) == {"C1", "C2", "C3", "C7"} for r in rows)
    for email in (GERENTE, SINDICA_ACACIAS):  # management company and board: not theirs
        async with _client() as c:
            await login(c, mailer, email)
            assert (await c.get("/portfolio/launch")).json() == []


# --------------------------------------------------------------------------- C7 (LF2-d)


async def test_condominium_without_limit_gets_no_action_until_it_is_set(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """LB-009 (D89, D93): the CondoOS admin may create a condominium without the síndico's
    limit. C7 is then "nao_configurado" and the policy denies any action request, with the
    reason, until the limit is set; nothing else of the journey depends on it."""
    condo, email = await _new_condo(admin_engine, with_limit=False)
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(Condominium, condo.id)
        assert stored is not None and stored.approval_limits == {}
    body = {
        "action_type": "orcamento.solicitar",
        "title": "Pedir orçamento de manutenção",
        "cost_cap": "0",
        "payload": {
            "effect": "Pedir um orçamento sem compromisso ao fornecedor do elevador.",
            "reason": "Comparar o preço atual com o mercado antes da renovação.",
            "executor": "Síndica",
        },
        "idempotency_key": f"launch-{uuid.uuid4()}",
    }
    async with _client() as c:
        await login(c, mailer, email)
        view = (await c.get(f"/condominiums/{condo.id}/launch")).json()
        c7 = _cap(view, "C7")
        assert c7["state"] == "nao_configurado"
        assert [r["key"] for r in c7["requirements"] if not r["met"]] == ["alcada_configurada"]
        r = await c.post(f"/condominiums/{condo.id}/actions", json=body)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["policy_decision"] == "deny"
        assert "alçada" in r.json()["detail"]["message"]

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        stored = await s.get(Condominium, condo.id)
        assert stored is not None
        stored.approval_limits = {"default": "3000.00"}
    async with _client() as c:
        await login(c, mailer, email)
        assert (
            _cap((await c.get(f"/condominiums/{condo.id}/launch")).json(), "C7")["state"]
            == "supervisionada"
        )
        body["idempotency_key"] = f"launch-{uuid.uuid4()}"
        r = await c.post(f"/condominiums/{condo.id}/actions", json=body)
        assert r.status_code == 201, r.text
