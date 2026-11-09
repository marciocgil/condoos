"""D71: agenda — due dates with payment status, expected contract invoices on the usual day
(predicted), adjustments and contract ends; síndico and management company; no other
condominium."""

import random
import uuid
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.agenda import condominium_agenda
from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.db.models import BankTransaction, Contract, Expense
from app.db.session import sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.onboarding import onboard
from tests.helpers import GERENTE, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login
from tests.test_onboarding import _spec

TODAY = date(2026, 11, 6)


async def test_agenda_events_and_statuses(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        sup = await get_or_create_supplier(
            s, generate_cnpj(random.Random(f"ag-{condo.id}")), "Portaria Fictícia Ltda"
        )
        contract = Contract(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=sup.id,
            object="Portaria 24 horas",
            scope_items=[],
            monthly_value=Decimal("9000.00"),
            adjustment_index="INPC",
            adjustment_base_month=12,
            billing_frequency_months=1,
            start_date=date(2025, 12, 1),
            end_date=date(2026, 12, 15),
        )
        s.add(contract)
        await s.flush()

        def exp(month: int, day: int, due: date, **kw: object) -> Expense:
            fields: dict[str, object] = {
                "id": uuid.uuid4(),
                "condominium_id": condo.id,
                "supplier_id": sup.id,
                "contract_id": contract.id,
                "competence": date(2026, month, 1),
                "issue_date": date(2026, month, day),
                "due_date": due,
                "amount": Decimal("9000.00"),
                "category": "portaria",
                "description": f"Portaria {month:02d}/2026",
                "invoice_number": str(100 + month),
            }
            fields.update(kw)
            return Expense(**fields)

        history = [exp(m, 7, date(2026, m, 17)) for m in (6, 7, 8, 9)]
        paid = exp(10, 7, date(2026, 11, 3))
        overdue = exp(11, 7, date(2026, 11, 4), invoice_number=None)  # no NF yet, unpaid
        upcoming = Expense(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=sup.id,
            competence=date(2026, 11, 1),
            issue_date=date(2026, 11, 1),
            due_date=date(2026, 11, 20),
            amount=Decimal("350.00"),
            category="manutencao",
            description="Troca de lâmpadas",
        )
        s.add_all([*history, paid, overdue, upcoming])
        await s.flush()
        s.add(
            BankTransaction(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                posted_at=date(2026, 11, 3),
                amount=Decimal("-9000.00"),
                description="PAG PORTARIA",
                origin="ofx",
                external_id=f"ag-{uuid.uuid4().hex}",
                expense_id=paid.id,
            )
        )

    async with sessionmaker_for(admin_engine)() as s:
        events = await condominium_agenda(s, condo.id, date(2026, 11, 1), date(2026, 12, 31), TODAY)
    by = {(e.kind, e.date): e for e in events}
    assert by[("vencimento", date(2026, 11, 3))].status == "pago"
    assert by[("vencimento", date(2026, 11, 4))].status == "vencido"
    assert by[("vencimento", date(2026, 11, 20))].status == "a_vencer"
    # December invoice expected on the usual issue day (7), predicted; November's has no NF
    # yet but is within the issue time.
    dec = by[("nf_prevista", date(2026, 12, 7))]
    assert dec.predicted and dec.status == "prevista"
    assert dec.amount == Decimal("9000.00")  # first INPC adjustment only in Dec/2026
    assert by[("nf_prevista", date(2026, 11, 7))].status == "prevista"
    assert by[("reajuste", date(2026, 12, 1))].detail.endswith("INPC")
    assert by[("fim_contrato", date(2026, 12, 15))].status == "vence"


async def test_agenda_access(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.get(f"/condominiums/{acacias}/agenda?start=2026-10-01&end=2026-10-31")
    assert r.status_code == 200
    body = r.json()
    assert body["events"] and {e["kind"] for e in body["events"]} <= {
        "vencimento",
        "nf_prevista",
        "reajuste",
        "fim_contrato",
        "validade",  # compliance documents of the seed (D112), dates relative to today
    }
    only = await client.get(
        f"/condominiums/{acacias}/agenda?start=2026-10-01&end=2026-10-31&kind=vencimento"
    )
    assert {e["kind"] for e in only.json()["events"]} == {"vencimento"}
    too_long = await client.get(f"/condominiums/{acacias}/agenda?start=2026-01-01&end=2026-12-31")
    assert too_long.status_code == 422
    assert (await client.get("/portfolio/agenda")).json()["events"] == []  # board: no portfolio

    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/agenda")).status_code == 404

    await client.post("/auth/logout")
    await login(client, mailer, GERENTE)
    body = (
        await client.get(
            f"/portfolio/agenda?start=2026-10-01&end=2026-10-31&condominium_id={acacias}"
        )
    ).json()
    assert body["events"] and {e["condominium_id"] for e in body["events"]} == {str(acacias)}
