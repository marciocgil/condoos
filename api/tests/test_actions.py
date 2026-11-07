"""VS-05 (Plano Diretor §8; D83): action request with approval and frozen scope, minimal
policy engine and kill switch. Nothing is ever sent outside the system.

Acceptance: deny by default; the síndico approves exactly the version seen (SEC-04); an
expired approval blocks the execution and goes back for approval (SEC-05); a rejected action
never reaches the dispatcher (WF-06); the outbox never duplicates; the kill switch stops the
worker (SEC-08 of the Plano); other condominium = 404; every step is append only.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.actions import DISPATCH_JOB, dispatch_job
from app.auth.mailer import MemoryMailer
from app.core.jobs import enqueue, run_one
from app.db.enums import JobStatus, PolicyDecision
from app.db.models import (
    ActionDecision,
    ActionRequest,
    AuditLog,
    CaseEvent,
    Condominium,
    Job,
    OutboxEvent,
)
from app.db.session import sessionmaker_for
from app.main import create_app
from app.policy import evaluate, job_paused
from tests.helpers import (
    ADMIN_CONDOOS,
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

ACACIAS = "jardim-das-acacias"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "action_type": "visita.agendar",
        "title": "Visita técnica à bomba de recalque",
        "cost_cap": "350.00",
        "idempotency_key": f"test-{uuid.uuid4()}",
        "payload": {
            "effect": "Agendar uma visita técnica para diagnosticar a bomba de recalque 2.",
            "reason": "A bomba desarma desde segunda; sem ela a caixa superior esvazia.",
            "executor": "Hidráulica do fornecedor de manutenção",
            "due_date": "2026-11-20",
            "risks": "Pode exigir troca de peça, que precisa de nova aprovação.",
        },
    }
    body.update(over)
    return body


async def _outbox(admin_engine: AsyncEngine, action_id: str) -> list[OutboxEvent]:
    async with sessionmaker_for(admin_engine)() as s:
        return list(
            await s.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.action_request_id == uuid.UUID(action_id))
                .order_by(OutboxEvent.created_at)
            )
        )


async def _dispatch(worker_engine: AsyncEngine, key: str) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await dispatch_job(s, {"idempotency_key": key})


async def _kinds(admin_engine: AsyncEngine, action_id: str) -> list[str]:
    async with sessionmaker_for(admin_engine)() as s:
        rows = await s.scalars(
            select(ActionDecision.kind)
            .where(ActionDecision.action_request_id == uuid.UUID(action_id))
            .order_by(ActionDecision.created_at, ActionDecision.id)
        )
        return list(rows)


# --------------------------------------------------------------------------- the policy


async def test_policy_is_deny_by_default(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        condo = Condominium(id=uuid.uuid4(), approval_limits={"default": "1000.00"})
        no_limit = Condominium(id=uuid.uuid4(), approval_limits={})

        async def decide(c: Condominium, kind: str, cost: str) -> PolicyDecision:
            return (await evaluate(s, c, action_type=kind, cost_cap=Decimal(cost))).decision

        assert await decide(condo, "porta.abrir", "0") == PolicyDecision.DENY  # unknown
        for never in (
            "pagamento.aprovar",
            "contrato.contratar",
            "multa.aplicar",
            "dados_bancarios.alterar",
        ):
            assert await decide(condo, never, "0") == PolicyDecision.DENY
        assert await decide(condo, "orcamento.solicitar", "0") == PolicyDecision.REQUIRE_APPROVAL
        assert await decide(condo, "orcamento.solicitar", "1") == PolicyDecision.DENY
        assert await decide(condo, "visita.agendar", "1000") == PolicyDecision.REQUIRE_APPROVAL
        assert await decide(condo, "visita.agendar", "1000.01") == PolicyDecision.DENY
        assert await decide(condo, "visita.agendar", "-1") == PolicyDecision.DENY
        assert await decide(no_limit, "visita.agendar", "10") == PolicyDecision.REQUIRE_REVIEW
        assert await decide(no_limit, "fornecedor.cobrar", "0") == PolicyDecision.REQUIRE_APPROVAL
        # No version of this policy ever answers ALLOW: nothing runs without a person.
        assert await decide(condo, "fornecedor.cobrar", "0") != PolicyDecision.ALLOW


# --------------------------------------------------------------------------- the slice


async def test_vs05_request_approve_dispatch_execute(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana, _client() as fabio, _client() as bruno, _client() as diego:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(fabio, mailer, ADMIN_CONDOOS)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        await login(diego, mailer, GERENTE)

        case = await ana.post(
            f"/condominiums/{acacias}/cases",
            json={
                "title": "Bomba de recalque desarmando",
                "description": "A bomba 2 desarma a cada poucas horas.",
                "category": "manutencao",
                "severity": "alta",
                "next_action": "Pedir visita técnica",
                "next_action_due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
                "resolution_criterion": "Bomba funcionando por 7 dias seguidos",
                "create_anyway_reason": "Teste automatizado: assunto distinto",
            },
        )
        assert case.status_code == 201, case.text
        case_id = case.json()["id"]

        body = _body(case_id=case_id)
        for who in (bruno, diego):  # read-only for actions
            assert (await who.post(base, json=_body())).status_code == 403
        r = await fabio.post(base, json=body)
        assert r.status_code == 201, r.text
        action = r.json()
        url = f"{base}/{action['id']}"
        assert action["status"] == "aguardando_aprovacao"
        assert action["policy_decision"] == "require_approval" and action["policy_version"] == 1
        assert action["level"] == "L4" and Decimal(action["approval_limit"]) == Decimal("8000")
        assert action["case_number"] == case.json()["number"]
        # Same idempotency key: the same request, not a second one.
        again = await fabio.post(base, json=body)
        assert again.status_code == 200 and again.json()["id"] == action["id"]

        # Everyone who sees the condominium sees it; only the síndica decides.
        assert (await bruno.get(url)).json()["allowed_actions"] == []
        assert set((await ana.get(url)).json()["allowed_actions"]) == {
            "aprovar",
            "pedir_ajustes",
            "recusar",
            "ajustar",
            "cancelar",
        }
        r = await fabio.post(
            f"{url}/decisions", json={"action": "aprovar", "payload_hash": action["payload_hash"]}
        )
        assert r.status_code == 403
        # SEC-04: approving a version other than the current one is refused.
        r = await ana.post(f"{url}/decisions", json={"action": "aprovar", "payload_hash": "x"})
        assert r.status_code == 409
        r = await ana.post(
            f"{url}/decisions",
            json={"action": "aprovar", "payload_hash": action["payload_hash"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "enfileirada" and r.json()["approval_expires_at"]

        # The dispatcher runs twice for the same approval: one dispatch, nothing sent.
        (event,) = await _outbox(admin_engine, action["id"])
        await _dispatch(worker_engine, event.idempotency_key)
        await _dispatch(worker_engine, event.idempotency_key)
        (event,) = await _outbox(admin_engine, action["id"])
        assert event.status == "despachado" and event.attempts == 1
        got = (await ana.get(url)).json()
        assert got["status"] == "aguardando_execucao_manual"
        assert got["allowed_actions"] == ["registrar_execucao", "cancelar"]
        assert "nada foi enviado" in got["history"][-1]["comment"]

        # SEC-04: the supplier charges more than approved → blocked, back for a new approval.
        r = await fabio.post(
            f"{url}/execution", json={"note": "Visita feita em 12/11.", "final_cost": "420.00"}
        )
        assert r.status_code == 409
        assert "supera o teto aprovado" in r.json()["detail"]["message"]
        got = (await ana.get(url)).json()
        assert got["status"] == "aguardando_aprovacao" and Decimal(got["cost_cap"]) == 420
        assert got["payload_hash"] != action["payload_hash"]
        (old,) = await _outbox(admin_engine, action["id"])
        assert old.status == "despachado"  # history kept

        r = await ana.post(
            f"{url}/decisions",
            json={"action": "aprovar", "payload_hash": got["payload_hash"], "comment": "Ok."},
        )
        assert r.status_code == 200
        events = await _outbox(admin_engine, action["id"])
        assert len(events) == 2 and events[-1].status == "pendente"
        await _dispatch(worker_engine, events[-1].idempotency_key)
        r = await fabio.post(
            f"{url}/execution", json={"note": "Visita feita em 12/11.", "final_cost": "420.00"}
        )
        assert r.status_code == 200 and r.json()["status"] == "executada"
        assert r.json()["executed_by"] == "Fábio Nogueira Lins"

    assert await _kinds(admin_engine, action["id"]) == [
        "solicitar",
        "aprovar",
        "despachar",
        "invalidar",
        "aprovar",
        "despachar",
        "executar",
    ]
    async with sessionmaker_for(admin_engine)() as s:
        timeline = list(
            await s.scalars(
                select(CaseEvent.to_value).where(
                    CaseEvent.case_id == uuid.UUID(case_id), CaseEvent.kind == "acao"
                )
            )
        )
        audited = await s.scalar(
            select(AuditLog.id).where(
                AuditLog.object_id == uuid.UUID(action["id"]),
                AuditLog.action == "action.executar",
            )
        )
    assert "executada" in timeline and audited is not None


async def test_rejected_action_is_never_dispatched(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    """WF-06."""
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        r = await ana.post(base, json=_body(action_type="fornecedor.cobrar", cost_cap="0"))
        assert r.status_code == 201, r.text
        action = r.json()
        url = f"{base}/{action['id']}"
        r = await ana.post(f"{url}/decisions", json={"action": "recusar"})
        assert r.status_code == 422  # a reason is required
        r = await ana.post(
            f"{url}/decisions", json={"action": "recusar", "comment": "Já cobramos por telefone."}
        )
        assert r.json()["status"] == "recusada" and r.json()["allowed_actions"] == []
        r = await ana.post(
            f"{url}/decisions",
            json={"action": "aprovar", "payload_hash": action["payload_hash"]},
        )
        assert r.status_code == 409
    assert await _outbox(admin_engine, action["id"]) == []


async def test_expired_approval_blocks_the_execution(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    """SEC-05: the approval is checked again at the moment of the action."""
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        action = (await ana.post(base, json=_body())).json()
        url = f"{base}/{action['id']}"
        await ana.post(
            f"{url}/decisions", json={"action": "aprovar", "payload_hash": action["payload_hash"]}
        )
        (event,) = await _outbox(admin_engine, action["id"])
        await _dispatch(worker_engine, event.idempotency_key)
        async with admin_engine.begin() as conn:
            await conn.execute(
                update(ActionRequest)
                .where(ActionRequest.id == uuid.UUID(action["id"]))
                .values(approval_expires_at=datetime.now(UTC) - timedelta(minutes=1))
            )
        r = await ana.post(f"{url}/execution", json={"note": "Feito.", "final_cost": "100"})
        assert r.status_code == 409 and "venceu" in r.json()["detail"]["message"]
        got = (await ana.get(url)).json()
        assert got["status"] == "aguardando_aprovacao" and got["approval_expires_at"] is None
    assert (await _kinds(admin_engine, action["id"]))[-1] == "expirar"


async def test_change_after_approval_voids_it(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        body = _body()
        action = (await ana.post(base, json=body)).json()
        url = f"{base}/{action['id']}"
        await ana.post(
            f"{url}/decisions", json={"action": "aprovar", "payload_hash": action["payload_hash"]}
        )
        changed = {
            "title": body["title"],
            "payload": {**body["payload"], "executor": "Outra empresa de hidráulica"},
            "cost_cap": body["cost_cap"],
        }
        r = await ana.patch(url, json=changed)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "aguardando_aprovacao"
        assert "anulada" in r.json()["history"][-1]["comment"]
        (event,) = await _outbox(admin_engine, action["id"])
        assert event.status == "cancelado"
        await _dispatch(worker_engine, event.idempotency_key)  # no-op
        assert (await ana.get(url)).json()["status"] == "aguardando_aprovacao"
        # Above the síndica's limit: denied, nothing changes.
        r = await ana.patch(url, json={**changed, "cost_cap": "9000.00"})
        assert r.status_code == 422 and "alçada" in r.json()["detail"]


async def test_tampered_payload_is_blocked_at_dispatch(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        action = (await ana.post(base, json=_body())).json()
        await ana.post(
            f"{base}/{action['id']}/decisions",
            json={"action": "aprovar", "payload_hash": action["payload_hash"]},
        )
        async with admin_engine.begin() as conn:  # changed behind the application's back
            await conn.execute(
                update(ActionRequest)
                .where(ActionRequest.id == uuid.UUID(action["id"]))
                .values(cost_cap=Decimal("7999.00"))
            )
        (event,) = await _outbox(admin_engine, action["id"])
        await _dispatch(worker_engine, event.idempotency_key)
        assert (await ana.get(f"{base}/{action['id']}")).json()["status"] == "bloqueada"
        (event,) = await _outbox(admin_engine, action["id"])
        assert event.status == "bloqueado"


async def test_denied_by_policy_is_recorded_without_a_request(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        body = _body(action_type="pagamento.aprovar")
        r = await ana.post(base, json=body)
        assert r.status_code == 422
        assert r.json()["detail"]["policy_decision"] == "deny"
        r = await ana.post(base, json=_body(cost_cap="9000.00"))
        assert r.status_code == 422 and "conselho" in r.json()["detail"]["message"]
    async with sessionmaker_for(admin_engine)() as s:
        created = await s.scalar(
            select(ActionRequest.id).where(ActionRequest.idempotency_key == body["idempotency_key"])
        )
        denied = list(
            await s.scalars(
                select(AuditLog.details).where(
                    AuditLog.action == "action.denied_by_policy",
                    AuditLog.condominium_id == acacias,
                )
            )
        )
    assert created is None
    assert {"pagamento.aprovar", "visita.agendar"} <= {d["action_type"] for d in denied}


async def test_kill_switch_stops_requests_and_the_worker(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    pauses = f"/condominiums/{acacias}/automation-pauses"
    async with _client() as ana, _client() as bruno, _client() as diego:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        await login(diego, mailer, GERENTE)
        action = (await ana.post(base, json=_body())).json()
        await ana.post(
            f"{base}/{action['id']}/decisions",
            json={"action": "aprovar", "payload_hash": action["payload_hash"]},
        )

        for who in (bruno, diego):
            r = await who.post(pauses, json={"automation_type": "*", "reason": "Teste de pausa"})
            assert r.status_code == 403
        r = await ana.post(pauses, json={"automation_type": "x", "reason": "Teste de pausa"})
        assert r.status_code == 422
        r = await ana.post(
            pauses, json={"automation_type": "*", "reason": "Fornecedor reclamou de cobrança"}
        )
        assert r.status_code == 201, r.text
        pause_id = r.json()["active"][0]["id"]
        assert r.json()["active"][0]["label"] == "Todas as automações"
        r = await ana.post(pauses, json={"automation_type": "*", "reason": "De novo"})
        assert r.status_code == 409

        # New requests are refused while paused.
        r = await ana.post(base, json=_body())
        assert r.status_code == 409 and r.json()["detail"]["policy_decision"] == "pause"

        # The worker does not run the approved action's dispatch while paused.
        async with admin_engine.begin() as conn:
            await conn.execute(update(Job).values(status=JobStatus.DONE.value))
        (event,) = await _outbox(admin_engine, action["id"])
        async with sessionmaker_for(worker_engine)() as s, s.begin():
            assert await job_paused(s, DISPATCH_JOB, acacias)
            assert not await job_paused(s, "rules.evaluate", acacias)  # not pausable
            job_id = await enqueue(
                s,
                DISPATCH_JOB,
                {"idempotency_key": event.idempotency_key},
                condominium_id=acacias,
            )
        assert await run_one(
            sessionmaker_for(worker_engine), {DISPATCH_JOB: dispatch_job}, job_paused
        )
        async with sessionmaker_for(admin_engine)() as s:
            job = await s.get(Job, job_id)
            assert job is not None
            assert (
                job.status == "queued" and job.attempts == 0 and "pausado" in (job.last_error or "")
            )
        assert (await ana.get(f"{base}/{action['id']}")).json()["status"] == "enfileirada"

        # Resumed: the same job runs and the action goes to manual execution.
        r = await ana.post(f"{pauses}/{pause_id}/resume")
        assert r.status_code == 200 and r.json()["active"] == []
        assert r.json()["history"][0]["resumed_by"] == "Ana Ribeiro Sampaio"
        async with admin_engine.begin() as conn:
            await conn.execute(
                update(Job).where(Job.id == job_id).values(run_after=datetime.now(UTC))
            )
        assert await run_one(
            sessionmaker_for(worker_engine), {DISPATCH_JOB: dispatch_job}, job_paused
        )
        got = (await ana.get(f"{base}/{action['id']}")).json()
        assert got["status"] == "aguardando_execucao_manual"


async def test_other_condominium_actions_are_404(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/actions"
    async with _client() as ana, _client() as carla:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(carla, mailer, SINDICA_MIRANTE)
        action = (await ana.post(base, json=_body())).json()
        assert (await carla.get(f"{base}/{action['id']}")).status_code == 404
        mirante = (await carla.get("/me")).json()["condominiums"][0]["id"]
        r = await carla.get(f"/condominiums/{mirante}/actions/{action['id']}")
        assert r.status_code == 404
        assert action["id"] not in {a["id"] for a in (await carla.get("/portfolio/actions")).json()}
        assert action["id"] in {a["id"] for a in (await ana.get("/portfolio/actions")).json()}


async def test_action_rows_are_isolated_by_rls(app_engine: AsyncEngine) -> None:
    async with AsyncSession(app_engine) as s:
        for model in (ActionRequest, ActionDecision, OutboxEvent):
            assert list(await s.scalars(select(model.id))) == []


@pytest.mark.parametrize("kind", ["pagamento.aprovar", "contrato.contratar"])
def test_denied_types_are_not_offered(kind: str) -> None:
    from app.policy import REQUESTABLE_TYPES

    assert kind not in REQUESTABLE_TYPES
