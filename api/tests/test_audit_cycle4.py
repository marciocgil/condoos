"""CondoOS Audit, cycle 4 (D125): reprocessing by event, SLA and escalation, history and
trend, export, links with Operate and Optimize, cost and performance bounds and the rollback
of an agent's prompt as runs see it. Synthetic data only."""

import time
import uuid
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.audit import agents as ag
from app.audit import publication as pubs
from app.audit.events import (
    REPROCESS_JOB,
    reprocess_job,
    request_reprocess,
    sla_for_condo,
    sla_level,
)
from app.audit.run import MAX_LLM_LINES, run_audit
from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.models import (
    AgentPromptVersion,
    AuditAgentRun,
    AuditControlResult,
    AuditIssue,
    AuditIssueEvent,
    AuditPublication,
    AuditRun,
    AutomationPause,
    Job,
    Opportunity,
)
from app.db.session import sessionmaker_for
from app.policy import PAUSABLE_JOBS, job_paused
from tests.helpers import GERENTE, REVISORA, SINDICA_MIRANTE, condo_id, login
from tests.test_audit import _import, _new_condo, ofx
from tests.test_audit_cycle2 import JUNE, TODAY, _expense, _run, _supplier
from tests.test_audit_cycle3 import _contract, _linked, _user

JULY = date(2025, 7, 1)


async def _jobs(s: Any, condo_id_: uuid.UUID) -> list[Job]:
    return list(
        await s.scalars(
            select(Job).where(Job.job_type == REPROCESS_JOB, Job.condominium_id == condo_id_)
        )
    )


# --------------------------------------------------------------------------- reprocessing


async def test_events_reprocess_only_months_a_person_audited(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        assert await request_reprocess(s, condo.id, JUNE, "teste") == []  # never audited
        await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        assert await request_reprocess(s, condo.id, JUNE, "teste") == ["2025-06"]
        assert await request_reprocess(s, condo.id, JUNE, "teste") == []  # collapsed (5 min)
        jobs = await _jobs(s, condo.id)
        assert len(jobs) == 1 and jobs[0].run_after > utcnow()  # waits a minute
        # The month after depends on this one (continuity): reprocessed too, when audited.
        await run_audit(s, condo, JULY, today=date(2025, 8, 20), user_id=None)
        await s.execute(update(Job).where(Job.condominium_id == condo.id).values(dedupe_key=None))
        assert await request_reprocess(s, condo.id, JUNE, "teste") == ["2025-06", "2025-07"]
        await s.rollback()


async def test_reprocess_job_replaces_only_what_the_event_changed(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        before = await _run(s, condo)
        assert before["DOC-02"].status == "PENDENTE"
        await reprocess_job(s, {"condominium_id": str(condo.id), "competence": "2025-06"})
        last = await s.scalar(
            select(AuditRun)
            .where(AuditRun.condominium_id == condo.id)
            .order_by(AuditRun.number.desc())
        )
        assert last is not None and last.trigger == "evento"
        assert last.summary["novos_resultados"] == 0 and last.summary["reutilizados"] == 25
        s.add(_expense(condo, "300.00", "manutencao", description="Reparo"))
        await s.flush()
        await reprocess_job(s, {"condominium_id": str(condo.id), "competence": "2025-06"})
        last = await s.scalar(
            select(AuditRun)
            .where(AuditRun.condominium_id == condo.id)
            .order_by(AuditRun.number.desc())
        )
        assert last is not None and 0 < last.summary["novos_resultados"] < 25
        await s.rollback()


async def test_rules_job_and_pause_cover_the_reprocess(admin_engine: AsyncEngine) -> None:
    from app.rules.engine import evaluate_job

    assert REPROCESS_JOB in PAUSABLE_JOBS
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        await evaluate_job(s, {"condominium_id": str(condo.id), "competence": "2025-06"})
        assert [j.payload["reason"] for j in await _jobs(s, condo.id)] == ["regras"]
        user = await _user(s)
        s.add(
            AutomationPause(
                condominium_id=condo.id,
                automation_type=REPROCESS_JOB,
                reason="Revisão em andamento",
                paused_by_user_id=user.id,
            )
        )
        await s.flush()
        assert await job_paused(s, REPROCESS_JOB, condo.id)
        await s.rollback()


# --------------------------------------------------------------------------- SLA


async def test_sla_escalates_once_and_again_after_reopening(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        issue = AuditIssue(
            condominium_id=condo.id,
            control_id="DOC-01",
            subject_key="x",
            title="Envie o extrato do mês",
            status="aberta",
            first_competence=date(2026, 6, 1),
            last_competence=date(2026, 6, 1),
        )
        s.add(issue)
        await s.flush()
        assert sla_level(issue, date(2026, 8, 1)) == "atencao"  # created today: not escalated yet
        issue.created_at = utcnow() - timedelta(days=40)
        await s.flush()
        assert sla_level(issue, date(2026, 6, 1)) == "em_dia"
        assert sla_level(issue, date(2026, 7, 1)) == "atencao"
        assert sla_level(issue, date(2026, 8, 1)) == "escalada"
        first = await sla_for_condo(s, condo)  # today (11/2026): open since 06/2026
        again = await sla_for_condo(s, condo)
        assert first["escaladas"] == 1 and again["escaladas"] == 0
        await s.flush()
        s.add(
            AuditIssueEvent(
                condominium_id=condo.id,
                issue_id=issue.id,
                kind="reaberta",
                competence=date(2026, 10, 1),
                detail={},
                created_at=utcnow() + timedelta(seconds=5),
            )
        )
        await s.flush()
        assert (await sla_for_condo(s, condo))["escaladas"] == 1
        await s.rollback()


async def test_farol_waiting_more_than_seven_days_is_overdue(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _run(s, condo)
        await s.execute(
            update(AuditControlResult)
            .where(AuditControlResult.condominium_id == condo.id)
            .values(review_state="REVIEWED")
        )
        pub = await pubs.submit(s, condo.id, JUNE, (await _user(s)).id)
        assert (await sla_for_condo(s, condo))["envios_atrasados"] == 0
        await s.execute(
            update(AuditPublication)
            .where(AuditPublication.id == pub.id)
            .values(submitted_at=utcnow() - timedelta(days=9))
        )
        assert (await sla_for_condo(s, condo))["envios_atrasados"] == 1
        await s.rollback()


# --------------------------------------------------------------------------- cost and performance


async def test_one_run_is_bounded_in_model_calls_and_time(
    admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A month with 120 unidentified lines: one A4 call with at most MAX_LLM_LINES lines and
    one A9 call; nothing else calls the model. The run stays well under the time budget."""
    calls: list[tuple[str, int]] = []

    async def fake_call(session: Any, req: Any) -> Any:
        from app.llm.client import LLMResult

        calls.append((req.purpose, req.user_text.count("id=")))
        if req.purpose == "audit.A4.classify":
            return LLMResult(req.output_model(sugestoes=[], observacoes=""), "fake", True)
        return LLMResult(req.output_model(questionamentos=[]), "fake", True)

    monkeypatch.setattr("app.llm.client.call_structured", fake_call)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        lines = [
            (f"202506{1 + i % 28:02d}", f"-{10 + i}.00", f"DEBITO DIVERSO {i}") for i in range(120)
        ]
        await _import(
            s, condo, ofx(lines, start="20250601", end="20250630", closing="1000.00"), "x.ofx"
        )
        started = time.perf_counter()
        await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        elapsed = time.perf_counter() - started
        assert [p for p, _ in calls] == ["audit.A4.classify", "audit.A9.review"]
        assert calls[0][1] <= MAX_LLM_LINES
        assert elapsed < 20, elapsed
        calls.clear()
        again = await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        assert again.summary["reutilizados"] == 25  # nothing changed: nothing rewritten
        await s.rollback()


async def test_rolled_back_prompt_is_the_one_the_next_run_uses(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await ag.ensure_initial_versions(s)
        author, approver = await _user(s, "autor"), await _user(s, "aprovador")
        v1 = await s.scalar(
            select(AgentPromptVersion).where(
                AgentPromptVersion.agent_id == "A9", AgentPromptVersion.status == "ACTIVE"
            )
        )
        assert v1 is not None
        v2 = await ag.create_draft(
            s, "A9", v1.text + " Seja breve em cada pergunta.", "Mais curto", author.id
        )
        await ag.run_tests(s, v2, author.id)
        await ag.submit(s, v2, author.id)
        await ag.approve(s, v2, approver.id, "Testado e revisado.")
        condo = await _new_condo(s)

        async def used() -> uuid.UUID | None:
            run = await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
            a9 = await s.scalar(
                select(AuditAgentRun).where(
                    AuditAgentRun.run_id == run.id, AuditAgentRun.agent_id == "A9"
                )
            )
            assert a9 is not None
            return a9.prompt_version_id

        assert await used() == v2.id
        await ag.rollback(s, v1, approver.id, "Volta para a versão inicial.")
        assert await used() == v1.id
        await s.rollback()


# --------------------------------------------------------------------------- links


async def test_links_show_cases_and_contract_candidates_for_optimize(
    admin_engine: AsyncEngine,
) -> None:
    from app.auth.rbac import CondoAccess
    from app.db.enums import Role
    from app.routers.audit4 import VISIBLE_TO_CONDO, links

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Limpeza Fictícia Ltda")
        c = _contract(condo, sup)
        s.add(c)
        await s.flush()
        s.add(_linked(condo, c, "1100.00", "Limpeza junho"))
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-01"].status == "DIVERGENTE"
        assert any(
            e.get("tipo") == "contrato" and e["id"] == str(c.id) for e in r["CON-01"].evidence_refs
        )
        s.add(
            Opportunity(
                condominium_id=condo.id,
                number="O-2025-0001",
                title="Renegociar limpeza",
                opportunity_type="renegociacao",
                status="identificada",
                contract_id=c.id,
                supplier_id=sup.id,
                recommendation="—",
                operational_impact="—",
                legal_contractual_risk="baixo",
                implementation_readiness="pronta",
                review_requirement="interna",
                review_policy_version=1,
            )
        )
        await s.flush()
        assert "identificada" not in VISIBLE_TO_CONDO  # drafts never reach the condominium
        staff = CondoAccess(uuid.uuid4(), condo.id, frozenset({Role.CONDOOS_REVIEWER}))
        manager = CondoAccess(uuid.uuid4(), condo.id, frozenset({Role.GERENTE}))
        seen = await links(condo.id, staff, s, "2025-06")
        assert [o["number"] for o in seen["optimize"]["opportunities"]] == ["O-2025-0001"]
        hidden = await links(condo.id, manager, s, "2025-06")
        assert hidden["optimize"]["opportunities"] == []
        assert [x["contract_id"] for x in hidden["optimize"]["candidates"]] == [str(c.id)]
        await s.rollback()


# --------------------------------------------------------------------------- API


async def test_api_history_export_links_and_operations(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, REVISORA)
    for month in ("2024-02", "2024-03"):
        assert (
            await client.post(f"/condominiums/{mirante}/audit/runs", json={"competencia": month})
        ).status_code == 200
    hist = (await client.get(f"/condominiums/{mirante}/audit/history?ate=2024-03&meses=3")).json()
    assert [m["competencia"] for m in hist["months"]] == ["2024-01", "2024-02", "2024-03"]
    assert not hist["months"][0]["auditado"] and hist["months"][2]["auditado"]
    assert len(hist["controls"]) == 25 and len(hist["controls"][0]["statuses"]) == 3
    assert set(hist["trend"]) >= {"validados", "divergentes", "pendentes"}
    pdf = await client.get(f"/condominiums/{mirante}/audit/export.pdf?competencia=2024-03")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    xlsx = await client.get(f"/condominiums/{mirante}/audit/export.xlsx?competencia=2024-03")
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert (
        await client.get(f"/condominiums/{mirante}/audit/export.pdf?competencia=2019-01")
    ).status_code == 404
    links = (await client.get(f"/condominiums/{mirante}/audit/links?competencia=2024-03")).json()
    assert set(links) == {"competencia", "operate", "operate_total", "optimize"}
    ops = (await client.get(f"/condominiums/{mirante}/audit/operations")).json()
    assert {r["trigger"] for r in ops["runs"]} >= {"manual"} and ops["reprocess_paused"] is False
    issues = (await client.get(f"/condominiums/{mirante}/audit/issues")).json()
    assert all("sla" in i and "sla_label" in i for i in issues)
    client.cookies.clear()
    await login(client, mailer, SINDICA_MIRANTE)
    assert (
        await client.get(f"/condominiums/{mirante}/audit/export.pdf?competencia=2024-03")
    ).status_code == 403  # internal farol: never the síndico's
    assert (await client.get(f"/condominiums/{mirante}/audit/history")).status_code == 403
    client.cookies.clear()
    await login(client, mailer, GERENTE)
    assert (await client.get(f"/condominiums/{mirante}/audit/history")).status_code == 200


async def test_sindico_exports_only_the_farol_he_approved(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, REVISORA)
    await client.post(f"/condominiums/{mirante}/audit/runs", json={"competencia": "2024-04"})
    farol = (await client.get(f"/condominiums/{mirante}/audit/farol?competencia=2024-04")).json()
    for c in farol["controls"]:
        if c.get("review_state") == "NEEDS_HUMAN_REVIEW":
            await client.post(
                f"/condominiums/{mirante}/audit/results/{c['result_id']}/review",
                json={"decision": "confirmar", "reason": "Conferido na revisão interna."},
            )
    pub = (
        await client.post(
            f"/condominiums/{mirante}/audit/publications", json={"competencia": "2024-04"}
        )
    ).json()
    client.cookies.clear()
    await login(client, mailer, SINDICA_MIRANTE)
    url = f"/condominiums/{mirante}/audit/publications/{pub['id']}/export.pdf"
    assert (await client.get(url)).status_code == 404  # not approved yet
    await client.post(
        f"/condominiums/{mirante}/audit/publications/{pub['id']}/decision",
        json={"approve": True, "sha256": pub["sha256"]},
    )
    done = await client.get(url)
    assert done.status_code == 200 and done.content.startswith(b"%PDF")
