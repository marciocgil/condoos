"""R12 approvals: the management company records the board's approval of an expense above
the limit; the month is re-evaluated and the untouched R12 finding is superseded."""

import uuid
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AuditLog, Expense, Finding, Job
from app.db.session import sessionmaker_for
from app.onboarding import onboard
from app.rules.engine import evaluate
from tests.helpers import ANALISTA, CONSELHEIRO_ACACIAS, condo_id, login
from tests.test_onboarding import _spec

MONTH = date(2026, 9, 1)
REF = date(2026, 11, 5)


async def test_recording_an_approval_supersedes_r12(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())  # limits: default 6000, obras 3000
        expense = Expense(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            competence=MONTH,
            issue_date=date(2026, 9, 10),
            amount=Decimal("4200.00"),
            category="obras",
            description="Reparo da fachada",
        )
        s.add(expense)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await evaluate(s, condo.id, MONTH, REF)
    async with sessionmaker_for(admin_engine)() as s:
        finding = await s.scalar(select(Finding).where(Finding.dedupe_key == f"R12:{expense.id}"))
    assert finding is not None and finding.status == "publicado"

    await login(client, mailer, ANALISTA)
    detail = (await client.get(f"/condominiums/{condo.id}/findings/{finding.id}")).json()
    assert detail["approval_expense_id"] == str(expense.id) and detail["can_record_approval"]

    url = f"/condominiums/{condo.id}/expenses/{expense.id}/approvals"
    future = await client.post(url, json={"approved_by": "Conselho", "approved_at": "2099-01-01"})
    assert future.status_code == 422
    r = await client.post(
        url,
        json={
            "approved_by": "Conselho consultivo",
            "approved_at": "2026-09-08",
            "notes": "Ata da reunião do conselho de 08/09/2026.",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["approved_by"] == "Conselho consultivo"
    listed = (await client.get(f"/condominiums/{condo.id}/approvals")).json()
    assert [a["expense_id"] for a in listed] == [str(expense.id)]

    async with sessionmaker_for(admin_engine)() as s:
        job = await s.scalar(
            select(Job).where(Job.job_type == "rules.evaluate", Job.condominium_id == condo.id)
        )
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.action == "approval.recorded", AuditLog.object_id == expense.id
            )
        )
    assert job is not None and audit is not None
    async with sessionmaker_for(admin_engine)() as s, s.begin():  # what the worker does
        await evaluate(s, condo.id, MONTH, REF)
    async with sessionmaker_for(admin_engine)() as s:
        again = await s.get(Finding, finding.id)
    assert again is not None and again.status == "superado"
    detail = (await client.get(f"/condominiums/{condo.id}/findings/{finding.id}")).json()
    assert detail["approvals"][0]["approved_at"] == "2026-09-08"


async def test_board_cannot_record_approvals(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(admin_engine)() as s:
        expense_id = await s.scalar(
            select(Expense.id).where(Expense.condominium_id == acacias).limit(1)
        )
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    r = await client.post(
        f"/condominiums/{acacias}/expenses/{expense_id}/approvals",
        json={"approved_by": "Eu mesmo", "approved_at": "2026-09-08"},
    )
    assert r.status_code == 403
