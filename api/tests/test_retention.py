"""Milestone 6 (LGPD): fiscal files older than the retention period are purged; governing
documents, contracts in force and accounting records stay."""

import random
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.br import generate_cnpj
from app.core.retention import purge_condominium
from app.db.models import AuditLog, Condominium, Contract, Document, Expense
from app.db.session import sessionmaker_for
from app.onboarding import onboard
from app.storage.base import get_storage
from tests.test_matching import _doc
from tests.test_onboarding import _spec

TODAY = date(2032, 6, 15)  # retention 5 years → cutoff 2027-06-01


async def test_retention_purges_only_old_fiscal_files(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
    storage = get_storage()

    def doc(kind: str, extracted: dict[str, Any]) -> Document:
        d = _doc(condo, kind, extracted, storage_key=f"cond/{condo.id}/{uuid.uuid4()}")
        storage.put(d.storage_key, b"x", "application/pdf")
        return d

    old_note = doc("nfse", {"data_emissao": "2026-10-02"})
    recent_note = doc("nfse", {"data_emissao": "2028-01-10"})
    old_minutes = doc("ata", {})
    old_contract_file = doc("contrato", {})
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add_all([old_note, recent_note, old_minutes, old_contract_file])
        await s.flush()
        supplier_cnpj = generate_cnpj(random.Random(str(condo.id)))
        from app.enrichment.suppliers import get_or_create_supplier

        supplier = await get_or_create_supplier(s, supplier_cnpj, "Fornecedor Fictício Ltda")
        s.add(
            Contract(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                supplier_id=supplier.id,
                object="Portaria",
                scope_items=[],
                monthly_value=1000,
                adjustment_index="IPCA",
                adjustment_base_month=1,
                start_date=date(2025, 1, 1),
                end_date=None,  # in force: its file stays
                source_document_id=old_contract_file.id,
            )
        )
        expense = Expense(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=supplier.id,
            document_id=old_note.id,
            competence=date(2026, 10, 1),
            issue_date=date(2026, 10, 2),
            amount=1000,
            category="portaria",
            description="Portaria",
        )
        s.add(expense)

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        c = await s.get(Condominium, condo.id)
        assert c is not None
        assert await purge_condominium(s, c, TODAY) == 1

    async with sessionmaker_for(admin_engine)() as s:
        left = set(await s.scalars(select(Document.id).where(Document.condominium_id == condo.id)))
        kept_expense = await s.get(Expense, expense.id)
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.action == "retention.purged", AuditLog.object_id == condo.id
            )
        )
    assert left == {recent_note.id, old_minutes.id, old_contract_file.id}
    assert kept_expense is not None and kept_expense.document_id is None  # record stays
    assert old_note.storage_key not in getattr(storage, "objects", {})
    assert audit is not None and audit.details["documents"] == 1
