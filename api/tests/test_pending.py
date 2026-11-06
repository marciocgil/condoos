"""D70: pending items cockpit — contracts in force without the month's invoice, and one-off
services without an approval document."""

import random
import uuid
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.db.models import Approval, Contract, Expense
from app.db.session import sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.onboarding import onboard
from app.pending import billing_expected, month_pending
from tests.helpers import GERENTE, SINDICA_ACACIAS, login
from tests.test_onboarding import _spec

SEP = date(2026, 9, 1)
TODAY = date(2026, 11, 5)  # September is past the grace period, October is not


def _contract(condo_id: uuid.UUID, supplier_id: uuid.UUID, obj: str, every: int = 1) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        condominium_id=condo_id,
        supplier_id=supplier_id,
        object=obj,
        scope_items=[],
        monthly_value=Decimal("1000.00"),
        adjustment_index="NENHUM",
        adjustment_base_month=None,
        billing_frequency_months=every,
        start_date=date(2026, 1, 1),
        end_date=None,
    )


def _expense(condo_id: uuid.UUID, supplier_id: uuid.UUID | None, **kw: object) -> Expense:
    base: dict[str, object] = {
        "id": uuid.uuid4(),
        "condominium_id": condo_id,
        "supplier_id": supplier_id,
        "competence": SEP,
        "issue_date": date(2026, 9, 5),
        "amount": Decimal("1000.00"),
        "category": "manutencao",
        "description": "Serviço",
    }
    base.update(kw)
    return Expense(**base)


def test_billing_frequency() -> None:
    c = _contract(uuid.uuid4(), uuid.uuid4(), "Dedetização trimestral", every=3)
    assert [m for m in range(1, 13) if billing_expected(c, date(2026, m, 1))] == [1, 4, 7, 10]
    c.billing_frequency_months = 0
    assert not billing_expected(c, date(2026, 4, 1))  # on demand: no fixed billing


async def test_month_pending_statuses(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        sup = await get_or_create_supplier(
            s, generate_cnpj(random.Random(str(condo.id))), "Fornecedor Fictício Ltda"
        )
        invoiced = _contract(condo.id, sup.id, "Portaria")
        charged = _contract(condo.id, sup.id, "Limpeza")
        missing = _contract(condo.id, sup.id, "Jardinagem")
        quarterly = _contract(condo.id, sup.id, "Dedetização", every=3)  # not due in Sep
        s.add_all([invoiced, charged, missing, quarterly])
        await s.flush()
        loose = _expense(condo.id, sup.id, description="Troca de bomba", amount=Decimal("2500"))
        backed = _expense(condo.id, sup.id, description="Pintura do hall")
        utility = _expense(condo.id, sup.id, category="energia", description="Conta de luz")
        s.add_all(
            [
                _expense(condo.id, sup.id, contract_id=invoiced.id, invoice_number="881"),
                _expense(condo.id, sup.id, contract_id=charged.id),  # boleto, no invoice
                loose,
                backed,
                utility,
            ]
        )
        await s.flush()
        s.add(
            Approval(
                condominium_id=condo.id,
                expense_id=backed.id,
                approved_by="Conselho consultivo",
                approved_at=date(2026, 9, 1),
            )
        )

    async with sessionmaker_for(admin_engine)() as s:
        result = await month_pending(s, condo.id, SEP, TODAY)
        october = await month_pending(s, condo.id, date(2026, 10, 1), TODAY)
    status = {c.object: c.status for c in result.contracts}
    assert status == {"Portaria": "faturado", "Limpeza": "sem_nf", "Jardinagem": "sem_faturamento"}
    pending = {o.description: o.pending for o in result.one_off}
    assert pending == {"Troca de bomba": True, "Pintura do hall": False}  # utility not listed
    assert result.open_count == 3
    assert {c.status for c in october.contracts} == {"aguardando"}  # within issue time

    await login(client, mailer, GERENTE)
    body = (await client.get(f"/portfolio/pending?month=2026-09&condominium_id={condo.id}")).json()
    assert len(body["months"]) == 6 and body["month"] == "2026-09-01"
    [row] = body["condominiums"]
    assert row["open_count"] == 3
    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get("/portfolio/pending")).json()["condominiums"] == []
