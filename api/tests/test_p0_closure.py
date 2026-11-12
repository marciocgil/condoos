"""Closing the P0 requirements left partial (D126): invitation expiry (FR-002), before and
after of critical changes (FR-005), relations of documents, contracts and suppliers
(FR-014), deadline alerts (FR-026) and the next action of a finding (FR-033). Positive and
negative cases; fictitious data only."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app import alerts
from app.auth.deps import roles_on_condominium
from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.enums import AlertStatus, Role
from app.db.models import (
    AppUser,
    AuditLog,
    AutomationPause,
    CaseRecord,
    Condominium,
    DeadlineAlert,
    Finding,
    Membership,
)
from app.db.session import sessionmaker_for
from app.findings.next_action import next_action
from app.main import create_app
from tests.helpers import GERENTE, SINDICA_ACACIAS, condo_id, login
from tests.test_audit import _new_condo
from tests.test_cases import _body

ACACIAS = "jardim-das-acacias"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


# --------------------------------------------------------------------------- FR-002


async def test_pending_invitation_expires_after_14_days_and_can_be_renewed(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    email = f"convite-{uuid.uuid4().hex[:6]}@teste.example.com"
    async with _client() as ana:
        await login(ana, mailer, GERENTE)  # who configures accesses
        r = await ana.post(
            f"/condominiums/{acacias}/members",
            json={"name": "Conselheira Convidada", "email": email, "role": "conselheiro"},
        )
        assert r.status_code == 200 or r.status_code == 201, r.text
        mid = uuid.UUID(r.json()["id"])
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(Membership)
                .where(Membership.id == mid)
                .values(invited_at=utcnow() - timedelta(days=15))
            )
        async with sessionmaker_for(admin_engine)() as s:
            user = await s.scalar(select(AppUser).where(AppUser.email == email))
            condo = await s.get(Condominium, acacias)
            assert user is not None and condo is not None
            assert await roles_on_condominium(s, user.id, condo) == frozenset()
        members = (await ana.get(f"/condominiums/{acacias}/settings")).json()["members"]
        assert next(m for m in members if m["email"] == email)["status"] == "convite_vencido"
        # Logging in with an expired invitation does not accept it.
        async with _client() as guest:
            await login(guest, mailer, email)
            assert (await guest.get(f"/condominiums/{acacias}/summary")).status_code == 404
        async with sessionmaker_for(admin_engine)() as s:
            assert (await s.get(Membership, mid)).accepted_at is None  # type: ignore[union-attr]
        # Sending it again renews it.
        again = await ana.post(
            f"/condominiums/{acacias}/members",
            json={"name": "Conselheira Convidada", "email": email, "role": "conselheiro"},
        )
        assert again.status_code in (200, 201), again.text
        members = (await ana.get(f"/condominiums/{acacias}/settings")).json()["members"]
        assert next(m for m in members if m["email"] == email)["status"] == "convidado"
        # FR-005: removing it records before, after and the reason.
        r = await ana.delete(f"/condominiums/{acacias}/members/{mid}?motivo=Teste encerrado")
        assert r.status_code == 200, r.text
    async with sessionmaker_for(admin_engine)() as s:
        log = await s.scalar(
            select(AuditLog)
            .where(AuditLog.action == "member.removed", AuditLog.object_id == mid)
            .order_by(AuditLog.created_at.desc())
        )
        assert log is not None
        d = log.details
        assert d["formato"] == "mudanca_v1" and d["motivo"] == "Teste encerrado"
        assert d["antes"]["revoked_at"] is None and d["depois"]["revoked_at"]
        assert "revoked_at" in d["mudou"] and d["versao_aplicacao"]
        renewed = await s.scalar(
            select(AuditLog)
            .where(AuditLog.action == "member.added", AuditLog.object_id == mid)
            .order_by(AuditLog.created_at.desc())
        )
        assert renewed is not None and renewed.details.get("invite_renewed") is True


# --------------------------------------------------------------------------- FR-005


async def test_critical_changes_keep_before_after_reason_and_version(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with _client() as diego:
        await login(diego, mailer, GERENTE)
        board = (await diego.get(f"/condominiums/{acacias}/settings")).json()["board"]
        m = board[0]
        r = await diego.put(
            f"/condominiums/{acacias}/board/{m['id']}",
            json={
                "full_name": m["full_name"],
                "position": m["position"],
                "term_start": m["term_start"],
                "term_end": "2030-12-31",
                "reason": "Mandato renovado na assembleia",
            },
        )
        assert r.status_code == 200, r.text
        settings = (await diego.get(f"/condominiums/{acacias}/settings")).json()
        original = dict(settings["approval_limits"])
        limits = dict(original)
        limits["default"] = "7777.00"
        r = await diego.put(
            f"/condominiums/{acacias}/settings",
            json={"approval_limits": limits, "reason": "Nova alçada aprovada em assembleia"},
        )
        assert r.status_code == 200, r.text
        # Shared seed: put the limits back (a new version, history kept).
        r = await diego.put(
            f"/condominiums/{acacias}/settings",
            json={"approval_limits": original, "reason": "Volta da alçada (teste)"},
        )
        assert r.status_code == 200, r.text
    async with sessionmaker_for(admin_engine)() as s:
        board_log = await s.scalar(
            select(AuditLog)
            .where(AuditLog.action == "board.updated", AuditLog.object_id == uuid.UUID(m["id"]))
            .order_by(AuditLog.created_at.desc())
        )
        assert board_log is not None
        assert board_log.details["mudou"]["term_end"]["depois"] == "2030-12-31"
        assert board_log.details["motivo"] == "Mandato renovado na assembleia"
        settings_log = await s.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == "settings.updated",
                AuditLog.object_id == acacias,
                AuditLog.details["motivo"].as_string() == "Nova alçada aprovada em assembleia",
            )
            .order_by(AuditLog.created_at.desc())
        )
        assert settings_log is not None
        d = settings_log.details
        assert d["depois"]["approval_limits"]["default"] == "7777.00"
        assert d["antes"]["approval_limits"] != d["depois"]["approval_limits"]
        assert isinstance(d["versao_configuracao"], int) and d["motivo"]


# --------------------------------------------------------------------------- FR-014


async def test_relations_of_contract_document_and_supplier(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with _client() as diego, _client() as ana:
        await login(diego, mailer, GERENTE)
        contracts = (await diego.get(f"/condominiums/{acacias}/contracts")).json()
        c = next(x for x in contracts if x.get("source_document_id") and x.get("supplier_id"))
        rel = (await diego.get(f"/condominiums/{acacias}/relations/contract/{c['id']}")).json()
        titles = {g["title"] for g in rel["groups"]}
        assert {"Documentos do contrato", "Despesas cobradas", "Fornecedor"} <= titles
        doc = (
            await diego.get(f"/condominiums/{acacias}/relations/document/{c['source_document_id']}")
        ).json()
        assert any(
            i["id"] == c["id"]
            for g in doc["groups"]
            if g["title"] == "Contratos"
            for i in g["items"]
        )
        sup = (
            await diego.get(f"/condominiums/{acacias}/relations/supplier/{c['supplier_id']}")
        ).json()
        assert any(g["title"] == "Contratos" for g in sup["groups"])
        # Another condominium's view never reveals this one's links; the síndica has no
        # access to the internal relations screen.
        other = await diego.get(f"/condominiums/{mirante}/relations/contract/{c['id']}")
        assert other.status_code == 404
        await login(ana, mailer, SINDICA_ACACIAS)
        assert (
            await ana.get(f"/condominiums/{acacias}/relations/contract/{c['id']}")
        ).status_code == 403


# --------------------------------------------------------------------------- FR-033


async def test_next_action_by_rule_with_authorisation_state(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)

        def finding(rule: str, status: str = "publicado") -> Finding:
            return Finding(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                rule_code=rule,
                severity="MEDIA",
                title="Indício de teste",
                explanation="Explicação da regra.",
                amount_at_risk=Decimal("100.00"),
                status=status,
                evidence=[{"kind": "expense", "id": str(uuid.uuid4()), "label": "Nota 12"}],
                rule_inputs={},
                competence=date(2025, 6, 1),
                dedupe_key=f"{rule}:{uuid.uuid4()}",
            )

        r02 = await next_action(s, condo, finding("R02"))
        assert r02 is not None and r02["action_type"] == "fornecedor.cobrar"
        assert r02["authorization"] == "require_approval" and r02["evidence"] == [
            {"label": "Nota 12"}
        ]
        r12 = await next_action(s, condo, finding("R12"))
        assert (
            r12 is not None and r12["authorization"] == "interna" and r12["internal"] == "aprovacao"
        )
        assert await next_action(s, condo, finding("R02", "contestado")) is None
        s.add(
            AutomationPause(
                condominium_id=condo.id,
                automation_type="action.dispatch",
                reason="Pausa de teste",
            )
        )
        await s.flush()
        paused = await next_action(s, condo, finding("R01"))
        assert paused is not None and paused["authorization"] == "pause"
        await s.rollback()


# --------------------------------------------------------------------------- FR-026


async def test_deadline_alerts_follow_the_policy_and_resolve_themselves(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        r = await ana.post(
            f"/condominiums/{acacias}/cases",
            json=_body(title=f"Prazo curto {uuid.uuid4().hex[:6]}", next_action_due_at=due),
        )
        assert r.status_code == 201, r.text
        case_id = r.json()["id"]
        listing = (await ana.get(f"/condominiums/{acacias}/alerts")).json()
        mine = [a for a in listing["alerts"] if a["target_id"] == case_id]
        assert len(mine) == 1 and mine[0]["level"] == "antes" and mine[0]["status"] == "criado"
        again = (await ana.get(f"/condominiums/{acacias}/alerts")).json()
        assert len([a for a in again["alerts"] if a["target_id"] == case_id]) == 1  # idempotent
        seen = await ana.post(f"/condominiums/{acacias}/alerts/{mine[0]['id']}/seen")
        assert seen.status_code == 200 and seen.json()["status"] == "visto"
        # Overdue: the "antes" alert resolves and a "vencido" one starts.
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CaseRecord)
                .where(CaseRecord.id == uuid.UUID(case_id))
                .values(next_action_due_at=utcnow() - timedelta(days=2))
            )
        listing = (await ana.get(f"/condominiums/{acacias}/alerts")).json()
        mine = [a for a in listing["alerts"] if a["target_id"] == case_id]
        assert [a["level"] for a in mine] == ["vencido"]
        # Done: nothing left open for it.
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            await s.execute(
                update(CaseRecord)
                .where(CaseRecord.id == uuid.UUID(case_id))
                .values(status="cancelado")
            )
        listing = (await ana.get(f"/condominiums/{acacias}/alerts")).json()
        assert not [a for a in listing["alerts"] if a["target_id"] == case_id]
    async with sessionmaker_for(admin_engine)() as s:
        rows = list(
            await s.scalars(
                select(DeadlineAlert).where(DeadlineAlert.target_id == uuid.UUID(case_id))
            )
        )
        assert {r.status for r in rows} == {AlertStatus.RESOLVIDO.value}
        assert all(r.channel == "app" and r.policy_version == alerts.POLICY_VERSION for r in rows)


async def test_farol_waiting_alert_goes_only_to_the_sindico(admin_engine: AsyncEngine) -> None:
    from app.audit import publication as pubs
    from app.db.models import AuditControlResult, AuditPublication
    from tests.test_audit_cycle2 import JUNE, _run
    from tests.test_audit_cycle3 import _user

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _run(s, condo)
        await s.execute(
            update(AuditControlResult)
            .where(AuditControlResult.condominium_id == condo.id)
            .values(review_state="REVIEWED")
        )
        pub = await pubs.submit(s, condo.id, JUNE, (await _user(s)).id)
        await s.execute(
            update(AuditPublication)
            .where(AuditPublication.id == pub.id)
            .values(submitted_at=utcnow() - timedelta(days=9))
        )
        out = await alerts.refresh(s, condo)
        assert out["criados"] == 1
        row = await s.scalar(select(DeadlineAlert).where(DeadlineAlert.target_id == pub.id))
        assert row is not None and row.audience == "sindico" and row.level == "vencido"
        from app.auth.rbac import CondoAccess
        from app.routers.alerts import _audiences

        assert "sindico" in _audiences(
            CondoAccess(uuid.uuid4(), condo.id, frozenset({Role.SINDICO}))
        )
        assert "sindico" not in _audiences(
            CondoAccess(uuid.uuid4(), condo.id, frozenset({Role.CONSELHEIRO}))
        )
        await s.rollback()
