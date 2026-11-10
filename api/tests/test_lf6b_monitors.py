"""LF6-b (D110): daily health monitors as internal alerts, and the Centro de Evolução.

Each monitor has a positive and a negative case; the seed opens no alert; alerts for the
team are invisible to the síndico (404); alerts never make a capability partial nor refuse an
action; what a person resolved stays; what disappears by itself is "superado".
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth.mailer import MemoryMailer
from app.core.time import add_months, local_today, utcnow
from app.data_issues import open_issues
from app.data_issues.monitors import run_monitors
from app.db.enums import PlatformRole
from app.db.models import (
    ActionDecision,
    ActionRequest,
    AppUser,
    CondoAssignment,
    Condominium,
    Contract,
    ContractAmendment,
    DataIssue,
    Expense,
    Membership,
)
from app.db.session import sessionmaker_for
from app.launch.readiness import readiness
from app.onboarding import onboard
from tests.helpers import ADMIN_CONDOOS, condo_id, login
from tests.test_launch import _document
from tests.test_onboarding import _spec


async def _open(s: AsyncSession, cid: uuid.UUID) -> dict[str, DataIssue]:
    rows = await s.scalars(
        select(DataIssue).where(DataIssue.condominium_id == cid, DataIssue.status == "aberto")
    )
    return {r.dedupe_key: r for r in rows}


async def _monitor(s: AsyncSession, cid: uuid.UUID) -> dict[str, DataIssue]:
    await run_monitors(s, cid, date.today())
    return await _open(s, cid)


async def _new(s: AsyncSession) -> tuple[Condominium, Any]:
    spec = _spec(management_company_name=None)
    return await onboard(s, spec), spec


async def _supplier_id(s: AsyncSession, cid: uuid.UUID) -> uuid.UUID:
    """A supplier of the seed (already enriched, never looked up: CLAUDE.md)."""
    acacias = await s.scalar(select(Condominium).where(Condominium.slug == "jardim-das-acacias"))
    assert acacias is not None
    contract = await s.scalar(select(Contract).where(Contract.condominium_id == acacias.id))
    assert contract is not None and contract.supplier_id is not None
    return contract.supplier_id


async def test_seed_opens_no_alert(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        for slug in ("jardim-das-acacias", "mirante-do-vale"):
            cid = await condo_id(admin_engine, slug)
            await run_monitors(s, cid, local_today(None))
            alerts = [i for i in (await _open(s, cid)).values() if i.kind != "conflito_documentos"]
            assert alerts == [], [a.dedupe_key for a in alerts]
        await s.rollback()


async def test_reviewer_and_sindico_access_monitors(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, _ = await _new(s)
        found = await _monitor(s, condo.id)
        # No management company and no CondoOS reviewer: nobody reviews nor closes.
        assert "revisor_ausente_v1:condominio" in found
        assert found["revisor_ausente_v1:condominio"].audiencia == "equipe"
        # The síndica has an active access: no access alert.
        assert not any(k.startswith("sindico_sem_acesso_v1") for k in found)

        admin = await s.scalar(select(AppUser).where(AppUser.email == ADMIN_CONDOOS))
        assert admin is not None
        s.add(
            CondoAssignment(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                user_id=admin.id,
                platform_role=PlatformRole.CONDOOS_REVIEWER.value,
                reason="Teste do monitor de revisora",
            )
        )
        membership = await s.scalar(select(Membership).where(Membership.condominium_id == condo.id))
        assert membership is not None
        membership.expires_at = utcnow() + timedelta(days=3)
        await s.flush()
        found = await _monitor(s, condo.id)
        assert "revisor_ausente_v1:condominio" not in found  # superado
        assert f"sindico_sem_acesso_v1:vencendo:{membership.id}" in found
        reviewer = await s.scalar(
            select(DataIssue).where(
                DataIssue.condominium_id == condo.id,
                DataIssue.dedupe_key == "revisor_ausente_v1:condominio",
            )
        )
        assert reviewer is not None and reviewer.status == "descartado"
        assert (reviewer.resolution or {}).get("superado") is True

        membership.revoked_at = utcnow()
        await s.flush()
        found = await _monitor(s, condo.id)
        assert "sindico_sem_acesso_v1:sem_sindico" in found
        assert f"sindico_sem_acesso_v1:vencendo:{membership.id}" not in found


async def test_stale_channel_amendment_and_stalled_action(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, _ = await _new(s)
        supplier_id = await _supplier_id(s, condo.id)
        contract = Contract(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=supplier_id,
            object="Limpeza das áreas comuns",
            monthly_value=Decimal("4000.00"),
            adjustment_index="IPCA",
            billing_frequency_months=1,
            start_date=date.today() - timedelta(days=200),
        )
        s.add(contract)
        old = _document(condo, "nfse")
        s.add(old)
        await s.flush()
        old.created_at = utcnow() - timedelta(days=40)
        await s.flush()
        found = await _monitor(s, condo.id)
        assert "canal_parado_v1:condominio" in found  # positive

        # Amendment with the same terms: nothing; with a new value: an alert to check.
        same = ContractAmendment(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            contract_id=contract.id,
            effective_date=date.today(),
            monthly_value=Decimal("4000.00"),
        )
        new_value = ContractAmendment(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            contract_id=contract.id,
            effective_date=date.today() + timedelta(days=10),
            monthly_value=Decimal("4400.00"),
        )
        s.add_all([same, new_value])
        # A document arrives today: the channel is alive again.
        s.add(_document(condo, "boleto"))
        await s.flush()
        found = await _monitor(s, condo.id)
        assert "canal_parado_v1:condominio" not in found  # negative (superado)
        assert f"contrato_aditado_v1:{new_value.id}" in found
        assert f"contrato_aditado_v1:{same.id}" not in found

        # An action handed to a person 8 days ago with nothing recorded.
        req = ActionRequest(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            action_type="visita.agendar",
            title="Visita técnica",
            payload={},
            payload_hash="x" * 64,
            cost_cap=Decimal("100.00"),
            status="aguardando_execucao_manual",
            policy_decision="require_approval",
            policy_version=1,
            policy_reason="",
            idempotency_key=f"t-{uuid.uuid4()}",
        )
        s.add(req)
        await s.flush()
        s.add(
            ActionDecision(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                action_request_id=req.id,
                kind="despachar",
                payload_hash=req.payload_hash,
                from_status="enfileirada",
                to_status="aguardando_execucao_manual",
                policy_version=1,
                created_at=utcnow() - timedelta(days=8),
            )
        )
        await s.flush()
        found = await _monitor(s, condo.id)
        stalled = found[f"acao_parada_v1:{req.id}"]
        assert stalled.audiencia == "condominio"  # the síndico sees this one

        # Alerts never change readiness nor the policy (conflicts only).
        assert [i.kind for i in await open_issues(s, condo.id)] == []
        assert all(
            r.facts.get("divergencias_abertas") is None for r in await readiness(s, condo.id)
        )


async def test_visibility_and_resolution_of_alerts(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, spec = await _new(s)
        await run_monitors(s, condo.id, date.today())
        team = await s.scalar(
            select(DataIssue).where(
                DataIssue.condominium_id == condo.id, DataIssue.kind == "revisor_ausente"
            )
        )
        assert team is not None
        team_id = team.id
        admin = await s.scalar(select(AppUser).where(AppUser.email == ADMIN_CONDOOS))
        assert admin is not None
        s.add(
            CondoAssignment(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                user_id=admin.id,
                platform_role=PlatformRole.CONDOOS_ADMIN.value,
                reason="Teste de visibilidade dos alertas",
            )
        )
    base = f"/condominiums/{condo.id}/data-issues"

    # The síndica does not see the team's alert: not in the list, 404 by id.
    await login(client, mailer, spec.board[0].email)
    assert all(i["audiencia"] == "condominio" for i in (await client.get(base)).json())
    assert (await client.get(f"{base}/{team_id}")).status_code == 404

    # The CondoOS admin sees it and resolves it without choosing a side.
    await login(client, mailer, ADMIN_CONDOOS)
    listed = (await client.get(base)).json()
    assert any(i["id"] == str(team_id) and i["audiencia"] == "equipe" for i in listed)
    r = await client.post(
        f"{base}/{team_id}/resolve", json={"reason": "Revisora será atribuída amanhã."}
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolvido"
    portfolio = (await client.get(f"/portfolio/data-issues?condominium_id={condo.id}")).json()
    assert str(team_id) not in {i["id"] for i in portfolio}  # only open ones

    # A person acted: the next run does not reopen it.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await run_monitors(s, condo.id, date.today())
        again = await s.get(DataIssue, team_id)
        assert again is not None and again.status == "resolvido"


async def test_conflict_still_needs_a_side(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        cid = await condo_id(admin_engine, "jardim-das-acacias")
        issue = DataIssue(
            id=uuid.uuid4(),
            condominium_id=cid,
            kind="conflito_documentos",
            status="aberto",
            subject_type="contract",
            subject_id=uuid.uuid4(),
            title="Conflito de teste",
            detail="",
            evidence=[{"label": "A"}, {"label": "B"}],
            capabilities=[],
            detector="teste_v1",
            dedupe_key=f"teste:{uuid.uuid4()}",
        )
        s.add(issue)
    await login(client, mailer, ADMIN_CONDOOS)
    r = await client.post(
        f"/condominiums/{cid}/data-issues/{issue.id}/resolve",
        json={"reason": "Sem escolher um dos lados."},
    )
    assert r.status_code == 422


async def test_evolution_suggestions_follow_the_demand(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo, spec = await _new(s)
    await login(client, mailer, spec.board[0].email)
    url = f"/condominiums/{condo.id}/launch/evolution"
    assert (await client.get(url)).json()["items"] == []  # no demand, no suggestion

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        supplier_id = await _supplier_id(s, condo.id)
        today = date.today()
        for back in (1, 2):
            month = add_months(today.replace(day=1), -back)
            s.add(
                Expense(
                    id=uuid.uuid4(),
                    condominium_id=condo.id,
                    supplier_id=supplier_id,
                    competence=month,
                    issue_date=month,
                    amount=Decimal("900.00"),
                    category="manutencao",
                    description="Serviço mensal",
                )
            )
    body = (await client.get(url)).json()
    keys = [i["key"] for i in body["items"]]
    assert keys == ["contrato_faltando", "extrato"]
    assert all(i["observed"] and i["gain"] for i in body["items"])
    assert body["items"][0]["action"]["href"] == "enviar?passo=enviar_contrato"

    r = await client.post(f"/condominiums/{condo.id}/launch/postpone", json={"step": "evo:extrato"})
    assert r.status_code == 200
    assert [i["key"] for i in (await client.get(url)).json()["items"]] == ["contrato_faltando"]
    assert (
        await client.post(f"/condominiums/{condo.id}/launch/postpone", json={"step": "evo:x"})
    ).status_code == 422

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(Expense).where(Expense.condominium_id == condo.id).values(supplier_id=None)
        )
    assert [i["key"] for i in (await client.get(url)).json()["items"]] == []


async def test_evolution_of_another_condominium_is_404(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from tests.helpers import SINDICA_MIRANTE

    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/launch/evolution")).status_code == 404
