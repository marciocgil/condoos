"""VS-01 (Plano Diretor §8; D75, D80): first tenant → first case, end to end.

Acceptance: another tenant reads nothing; unauthorized edits fail; closing without the
required evidence is blocked; history stays after closing. Plus: "sem próxima ação, sem
controle", N:N links with history, duplicates offered before creating, tasks with evidence.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AppUser, CaseRecord, Document, Finding, Job, Supplier
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

ACACIAS, MIRANTE = "jardim-das-acacias", "mirante-do-vale"
ANYWAY = "Teste automatizado: assunto distinto"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _future(days: int = 7) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def _uid(admin_engine: AsyncEngine, email: str) -> uuid.UUID:
    async with sessionmaker_for(admin_engine)() as s:
        uid = await s.scalar(select(AppUser.id).where(AppUser.email == email))
    assert uid
    return uid


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Infiltração na garagem B2",
        "description": "Mancha de umidade no teto da vaga 12.",
        "category": "manutencao",
        "severity": "alta",
        "next_action": "Vistoria do zelador",
        "next_action_due_at": _future(),
        "resolution_criterion": "Foto do teto seco e laudo do prestador",
        "create_anyway_reason": ANYWAY,
    }
    body.update(over)
    return body


async def _published_finding(
    admin_engine: AsyncEngine, slug: str, status: str = "publicado"
) -> uuid.UUID:
    cid = await condo_id(admin_engine, slug)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=cid,
                rule_code="R11",
                severity="media",
                title="Conta de água acima do padrão",
                explanation="Indício para verificação.",
                amount_at_risk=1,
                status=status,
                evidence=[],
                rule_inputs={},
                competence=date(2020, 3, 1),
                dedupe_key=f"test-case-{fid}",
            )
        )
    return fid


# --------------------------------------------------------------------------- the slice


async def test_vs01_first_case_end_to_end(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    diego = await _uid(admin_engine, GERENTE)
    base = f"/condominiums/{acacias}/cases"
    async with _client() as ana, _client() as manager:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(manager, mailer, GERENTE)

        r = await ana.post(base, json=_body())
        assert r.status_code == 201, r.text
        case = r.json()
        url = f"{base}/{case['id']}"
        assert case["number"].startswith(f"A-{datetime.now(UTC).year}-")
        assert case["status"] == "novo" and case["owner"]["name"] == "Ana Ribeiro Sampaio"
        assert [e["kind"] for e in case["events"]] == ["created"]
        assert case["allowed_transitions"] == ["em_triagem"]

        # A task for the management company, which needs evidence to be done.
        r = await ana.post(
            f"{url}/tasks",
            json={
                "title": "Vistoriar e fotografar o teto",
                "assignee_user_id": str(diego),
                "due_at": _future(3),
                "requires_evidence": True,
            },
        )
        assert r.status_code == 201, r.text
        task = r.json()["tasks"][0]

        # The manager sees it in "my cases" (internal notification) and works on the task
        # but cannot move the case it does not own.
        mine = (await manager.get(f"{base}?responsavel=me")).json()
        assert case["id"] in {c["id"] for c in mine}
        detail = (await manager.get(url)).json()
        assert detail["can_manage"] is False and detail["allowed_transitions"] == []
        assert detail["tasks"][0]["can_update"] is True
        r = await manager.post(f"{url}/transitions", json={"to": "em_triagem"})
        assert r.status_code == 403
        r = await manager.patch(f"{url}/tasks/{task['id']}", json={"status": "em_andamento"})
        assert r.status_code == 200
        r = await manager.patch(f"{url}/tasks/{task['id']}", json={"status": "concluida"})
        assert r.status_code == 422 and "evidência" in r.json()["detail"]
        up = await manager.post(
            f"{url}/evidence/upload",
            files={
                "file": ("teto-seco.jpg", b"\xff\xd8\xff\xe0fake-jpeg-evidence-1", "image/jpeg")
            },
            data={"description": "Foto do teto após o reparo"},
        )
        assert up.status_code == 201, up.text
        doc_id = next(link["target_id"] for link in up.json()["links"] if link["as_evidence"])
        r = await manager.patch(
            f"{url}/tasks/{task['id']}",
            json={"status": "concluida", "evidence_document_id": doc_id},
        )
        assert r.status_code == 200 and r.json()["tasks"][0]["status"] == "concluida"

        # The evidence is a document of the condominium, not sent to extraction.
        async with sessionmaker_for(admin_engine)() as s:
            doc = await s.get(Document, uuid.UUID(doc_id))
            jobs = await s.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.payload["document_id"].as_string() == doc_id)
            )
        assert doc is not None and not doc.needs_review and doc.extraction_status == "done"
        assert jobs == 0

        # The síndica walks the case to resolution.
        for to in ("em_triagem", "em_planejamento", "em_execucao", "aguardando_validacao"):
            r = await ana.post(f"{url}/transitions", json={"to": to})
            assert r.status_code == 200, (to, r.text)
        r = await ana.post(f"{url}/transitions", json={"to": "resolvido"})
        assert r.status_code == 422  # the reason is mandatory
        r = await ana.post(
            f"{url}/transitions", json={"to": "resolvido", "reason": "Teto seco, conforme foto."}
        )
        assert r.status_code == 200, r.text
        closed = r.json()
        assert closed["status"] == "resolvido" and closed["closed_at"] and closed["attention"] == []

        # History stays after closing; a closed case is not edited, only reopened with reason.
        kinds = [e["kind"] for e in closed["events"]]
        assert kinds[0] == "created" and kinds.count("status_changed") == 5
        assert "evidence_added" in kinds and "task_created" in kinds
        r = await ana.patch(url, json={"title": "Outro título"})
        assert r.status_code == 409
        r = await ana.post(f"{url}/transitions", json={"to": "reaberto"})
        assert r.status_code == 422
        r = await ana.post(
            f"{url}/transitions", json={"to": "reaberto", "reason": "Voltou a pingar na vaga 12."}
        )
        assert r.status_code == 200 and r.json()["closed_at"] is None
        assert len(r.json()["events"]) == len(closed["events"]) + 1


async def test_resolution_needs_evidence_and_closed_tasks(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        case = (
            await ana.post(
                base, json=_body(title="Portão da garagem falhando", category="seguranca")
            )
        ).json()
        url = f"{base}/{case['id']}"
        await ana.post(
            f"{url}/tasks",
            json={
                "title": "Chamar a assistência",
                "assignee_label": "Zelador Paulo",
                "due_at": _future(2),
            },
        )
        for to in ("em_triagem", "em_planejamento", "em_execucao", "aguardando_validacao"):
            assert (await ana.post(f"{url}/transitions", json={"to": to})).status_code == 200
        r = await ana.post(
            f"{url}/transitions", json={"to": "resolvido", "reason": "Fornecedor disse que fez."}
        )
        assert r.status_code == 409 and "tarefa" in r.json()["detail"]
        task = (await ana.get(url)).json()["tasks"][0]
        assert task["assignee_label"] == "Zelador Paulo"
        await ana.patch(f"{url}/tasks/{task['id']}", json={"status": "concluida"})
        r = await ana.post(
            f"{url}/transitions", json={"to": "resolvido", "reason": "Fornecedor disse que fez."}
        )
        assert r.status_code == 409 and "evidência" in r.json()["detail"]  # WF-04 / OPS-02
        # A failed validation goes back to execution, with a reason.
        r = await ana.post(f"{url}/transitions", json={"to": "em_execucao"})
        assert r.status_code == 422
        r = await ana.post(
            f"{url}/transitions", json={"to": "em_execucao", "reason": "Portão travou de novo."}
        )
        assert r.status_code == 200


# --------------------------------------------------------------------------- isolation, roles


async def test_other_tenant_reads_nothing(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    mirante = await condo_id(admin_engine, MIRANTE)
    async with _client() as ana, _client() as carla:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(carla, mailer, SINDICA_MIRANTE)
        case = (
            await ana.post(
                f"/condominiums/{acacias}/cases",
                json=_body(title="Vazamento no salão", category="obra"),
            )
        ).json()
        assert (await carla.get(f"/condominiums/{acacias}/cases")).status_code == 404
        assert (await carla.get(f"/condominiums/{acacias}/cases/{case['id']}")).status_code == 404
        # Its id under her own condominium: not found either (filter + RLS).
        assert (await carla.get(f"/condominiums/{mirante}/cases/{case['id']}")).status_code == 404
        r = await carla.post(
            f"/condominiums/{mirante}/cases/{case['id']}/transitions", json={"to": "em_triagem"}
        )
        assert r.status_code == 404
        assert case["id"] not in {c["id"] for c in (await carla.get("/portfolio/cases")).json()}


async def test_unauthorized_edits_fail(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    async with _client() as ana, _client() as bruno:
        await login(ana, mailer, SINDICA_ACACIAS)
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        case = (
            await ana.post(
                base, json=_body(title="Elevador social parado", category="administrativo")
            )
        ).json()
        url = f"{base}/{case['id']}"
        assert (await bruno.get(url)).status_code == 200  # the board reads cases
        assert (await bruno.post(base, json=_body())).status_code == 403
        assert (await bruno.patch(url, json={"title": "Mudado"})).status_code == 403
        assert (
            await bruno.post(f"{url}/transitions", json={"to": "em_triagem"})
        ).status_code == 403
        r = await bruno.post(
            f"{url}/tasks", json={"title": "Algo", "assignee_label": "X", "due_at": _future()}
        )
        assert r.status_code == 403
        # The council comments (it already comments findings).
        r = await bruno.post(f"{url}/comments", json={"body": "Acompanhar com a empresa."})
        assert r.status_code == 201 and r.json()["events"][-1]["kind"] == "comment"
        # An owner must be someone who can act on cases here.
        bruno_id = await _uid(admin_engine, CONSELHEIRO_ACACIAS)
        r = await ana.patch(
            url, json={"owner_user_id": str(bruno_id), "reason": "Troca de responsável"}
        )
        assert r.status_code == 422


# --------------------------------------------------------------------------- next action


async def test_no_next_action_no_control(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        bad = _body()
        del bad["next_action"]
        assert (await ana.post(base, json=bad)).status_code == 422
        r = await ana.post(
            base, json=_body(next_action_due_at=(datetime.now(UTC) - timedelta(days=1)).isoformat())
        )
        assert r.status_code == 422
        # A date alone means the end of that day in the condominium's time zone.
        day = (date.today() + timedelta(days=5)).isoformat()
        r = await ana.post(
            base,
            json=_body(title="Lâmpadas queimadas", category="atendimento", next_action_due_at=day),
        )
        assert r.status_code == 201, r.text
        case = r.json()
        assert case["next_action_due_at"].startswith(day)
        url = f"{base}/{case['id']}"
        # Changing the due date needs a reason.
        r = await ana.patch(url, json={"next_action_due_at": _future(9)})
        assert r.status_code == 422
        r = await ana.patch(
            url, json={"next_action_due_at": _future(9), "reason": "Fornecedor pediu mais prazo"}
        )
        assert r.status_code == 200 and r.json()["events"][-1]["kind"] == "due_changed"
        # Overdue shows as attention in the queue.
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CaseRecord)
                .where(CaseRecord.id == uuid.UUID(case["id"]))
                .values(next_action_due_at=datetime.now(UTC) - timedelta(hours=1))
            )
        rows = {c["id"]: c for c in (await ana.get(base)).json()}
        assert rows[case["id"]]["attention"] == ["atrasado"]
        # Suspension needs a reason and a future date; then no due date is required.
        await ana.post(f"{url}/transitions", json={"to": "em_triagem"})
        r = await ana.post(
            f"{url}/transitions",
            json={"to": "suspenso_justificadamente", "reason": "Aguardando assembleia"},
        )
        assert r.status_code == 422
        until = (date.today() + timedelta(days=30)).isoformat()
        r = await ana.post(
            f"{url}/transitions",
            json={
                "to": "suspenso_justificadamente",
                "reason": "Aguardando assembleia",
                "suspended_until": until,
            },
        )
        assert r.status_code == 200 and r.json()["suspended_until"] == until
        assert r.json()["attention"] == []


async def test_database_enforces_owner_next_action_and_due(admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            CaseRecord(
                id=uuid.uuid4(),
                condominium_id=acacias,
                number="A-1999-9999",
                title="Sem dono",
                description="",
                category="outro",
                origin="human_request",
                severity="baixa",
                status="em_triagem",
                resolution_criterion="Qualquer",
                requires_evidence=False,
            )
        )
        with pytest.raises(Exception, match="next_action_required"):
            await s.flush()


# --------------------------------------------------------------------------- links


async def test_case_from_finding_links_n_to_n_with_history(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    fid = await _published_finding(admin_engine, ACACIAS)
    base = f"/condominiums/{acacias}/cases"
    link = {"target_type": "finding", "target_id": str(fid)}
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        r = await ana.post(
            base,
            json=_body(
                title="Investigar consumo de água",
                category="financeiro",
                origin="finding",
                links=[],
            ),
        )
        assert r.status_code == 422  # origin finding needs the finding
        first = (
            await ana.post(
                base,
                json=_body(
                    title="Investigar consumo de água",
                    category="financeiro",
                    origin="finding",
                    links=[link],
                ),
            )
        ).json()
        assert first["origin"] == "finding" and first["links"][0]["target_type"] == "finding"

        # Same finding in a second case: offered as duplicate first, then a reason is required.
        r = await ana.post(
            base,
            json=_body(
                title="Renegociar com a concessionária",
                category="contrato",
                links=[link],
                create_anyway_reason=None,
            ),
        )
        assert r.status_code == 409 and r.json()["candidates"][0]["id"] == first["id"]
        r = await ana.post(
            base,
            json=_body(title="Renegociar com a concessionária", category="contrato", links=[link]),
        )
        assert r.status_code == 422 and first["number"] in r.json()["detail"]["message"]
        second = (
            await ana.post(
                base,
                json=_body(
                    title="Renegociar com a concessionária",
                    category="contrato",
                    links=[{**link, "reason": "Mesmo achado sustenta a renegociação"}],
                ),
            )
        ).json()

        cases = (await ana.get(f"/condominiums/{acacias}/findings/{fid}/cases")).json()
        assert {c["id"] for c in cases} == {first["id"], second["id"]}
        async with sessionmaker_for(admin_engine)() as s:
            assert (await s.get(Finding, fid)).status == "publicado"  # type: ignore[union-attr]

        # Case ↔ case, visible from both sides; unlinking keeps the history.
        r = await ana.post(
            f"{base}/{second['id']}/links", json={"target_type": "case", "target_id": first["id"]}
        )
        assert r.status_code == 201
        cited = (await ana.get(f"{base}/{first['id']}")).json()["cited_by"]
        assert [c["id"] for c in cited] == [second["id"]]
        link_id = next(x["id"] for x in r.json()["links"] if x["target_type"] == "case")
        url = f"{base}/{second['id']}/links/{link_id}/unlink"
        assert (await ana.post(url, json={"reason": ""})).status_code == 422
        r = await ana.post(url, json={"reason": "Vínculo feito por engano"})
        undone = next(x for x in r.json()["links"] if x["id"] == link_id)
        assert undone["active"] is False and undone["unlinked_at"]
        assert r.json()["events"][-1]["kind"] == "unlinked"
        assert (await ana.get(f"{base}/{first['id']}")).json()["cited_by"] == []
        # Linking itself or a record of another condominium: refused.
        r = await ana.post(
            f"{base}/{second['id']}/links", json={"target_type": "case", "target_id": second["id"]}
        )
        assert r.status_code == 422


async def test_links_respect_tenant_and_visibility(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    other_finding = await _published_finding(admin_engine, MIRANTE)
    in_review = await _published_finding(admin_engine, ACACIAS, status="aguardando_validacao")
    async with sessionmaker_for(admin_engine)() as s:
        # A supplier only Mirante uses (no contract or expense in Acácias).
        from app.db.models import Contract, Expense

        used_in_acacias = (
            select(Contract.supplier_id)
            .where(Contract.condominium_id == acacias)
            .union(
                select(Expense.supplier_id).where(
                    Expense.condominium_id == acacias, Expense.supplier_id.is_not(None)
                )
            )
        )
        foreign_supplier = await s.scalar(
            select(Supplier.id).where(Supplier.id.not_in(used_in_acacias)).limit(1)
        )
    base = f"/condominiums/{acacias}/cases"
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        for target in (
            {"target_type": "finding", "target_id": str(other_finding)},
            {"target_type": "finding", "target_id": str(in_review)},  # not visible to the board
            {"target_type": "document", "target_id": str(uuid.uuid4())},
            {"target_type": "supplier", "target_id": str(foreign_supplier)},
        ):
            r = await ana.post(
                base,
                json=_body(title="Assunto com vínculo inválido", category="outro", links=[target]),
            )
            assert r.status_code == 404, target
        r = await ana.post(
            base,
            json=_body(
                title="Oportunidade",
                category="outro",
                links=[{"target_type": "opportunity", "target_id": str(uuid.uuid4())}],
            ),
        )
        assert r.status_code == 422


# --------------------------------------------------------------------------- duplicates


async def test_duplicates_are_offered_before_creating(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, MIRANTE)
    base = f"/condominiums/{mirante}/cases"
    async with _client() as carla:
        await login(carla, mailer, SINDICA_MIRANTE)
        first = await carla.post(
            base,
            json=_body(title="Bomba d'água ruidosa", category="obra", create_anyway_reason=None),
        )
        assert first.status_code == 201, first.text
        async with sessionmaker_for(admin_engine)() as s:
            before = await s.scalar(
                select(func.count())
                .select_from(CaseRecord)
                .where(CaseRecord.condominium_id == mirante)
            )
        r = await carla.post(
            base,
            json=_body(
                title="Barulho na casa de bombas", category="obra", create_anyway_reason=None
            ),
        )
        assert r.status_code == 409
        assert [c["number"] for c in r.json()["candidates"]] == [first.json()["number"]]
        async with sessionmaker_for(admin_engine)() as s:
            after = await s.scalar(
                select(func.count())
                .select_from(CaseRecord)
                .where(CaseRecord.condominium_id == mirante)
            )
        assert after == before  # nothing written
        r = await carla.post(
            base,
            json=_body(
                title="Barulho na casa de bombas", category="obra", create_anyway_reason="ok"
            ),
        )
        assert r.status_code == 409  # a real reason is needed
        r = await carla.post(
            base,
            json=_body(
                title="Barulho na casa de bombas",
                category="obra",
                create_anyway_reason="É a bomba do bloco B, outra",
            ),
        )
        assert r.status_code == 201
        assert r.json()["events"][0]["reason"] == "É a bomba do bloco B, outra"
