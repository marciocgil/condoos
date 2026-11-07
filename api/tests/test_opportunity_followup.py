"""CB-063 (D76): after the condominium approves, "contratada" needs the agreement document and
"realizada" is measured by code from later invoices; stages stay side by side, never summed.
Nothing here moves money or sends anything."""

import uuid
from datetime import date
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.models import Document, Expense, Opportunity
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import REVISORA, SINDICA_MIRANTE, login
from tests.test_opportunities import MIRANTE, _seed_finding

PDF = b"%PDF-1.4\n% acordo de reajuste " + uuid.uuid4().bytes + b"\n%%EOF\n"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def _invoices(
    admin_engine: AsyncEngine, opp_id: str, amounts: list[str], *, with_document: bool = True
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        opp = await s.get(Opportunity, uuid.UUID(opp_id))
        assert opp is not None
        for i, amount in enumerate(amounts):
            doc_id = None
            if with_document:
                doc_id = uuid.uuid4()
                s.add(
                    Document(
                        id=doc_id,
                        condominium_id=opp.condominium_id,
                        doc_type="nfse",
                        storage_key=f"cond/{opp.condominium_id}/test/{doc_id}.pdf",
                        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
                        original_filename=f"nf-{i}.pdf",
                        mime_type="application/pdf",
                        origin="upload",
                    )
                )
                await s.flush()
            s.add(
                Expense(
                    id=uuid.uuid4(),
                    condominium_id=opp.condominium_id,
                    supplier_id=opp.supplier_id,
                    document_id=doc_id,
                    competence=date(2026, 11 + i, 1) if i < 2 else date(2027, i - 1, 1),
                    issue_date=utcnow().date(),
                    amount=Decimal(amount),
                    category="manutencao",
                    description="Manutenção mensal após o acordo",
                )
            )


async def test_contracted_needs_the_agreement_and_realized_is_measured(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    from tests.helpers import condo_id

    mirante = await condo_id(admin_engine, MIRANTE)
    fid = await _seed_finding(admin_engine)
    base = f"/condominiums/{mirante}/opportunities"
    async with _client() as rev, _client() as carla:
        await login(rev, mailer, REVISORA)
        await login(carla, mailer, SINDICA_MIRANTE)
        opp = (await rev.post(base, json={"finding_id": str(fid)})).json()
        url = f"{base}/{opp['id']}"
        files = {"file": ("acordo.pdf", PDF, "application/pdf")}

        # Not before the condominium approves.
        r = await carla.post(f"{url}/contracted", data={"agreed_amount": "4600"}, files=files)
        assert r.status_code in (403, 404)
        await rev.post(f"{url}/decisions", json={"action": "aprovar"})
        assert (await carla.get(url)).json()["follow_up_actions"] == []
        await carla.post(f"{url}/decisions", json={"action": "condominio_aprovar"})
        assert (await carla.get(url)).json()["follow_up_actions"] == ["registrar_contratacao"]

        # The agreed value must be below the baseline (R$ 5.000,00).
        r = await carla.post(f"{url}/contracted", data={"agreed_amount": "5000"}, files=files)
        assert r.status_code == 422
        r = await carla.post(
            f"{url}/contracted",
            data={"agreed_amount": "4580.00", "one_time_cost": "120.00", "comment": "Aditivo 3"},
            files=files,
        )
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["status"] == "em_execucao"
        contracted = next(s for s in got["stages"] if s["stage"] == "contratada")
        assert Decimal(contracted["amount"]) == Decimal("420.00")
        assert Decimal(contracted["net_amount"]) == Decimal("4920.00")  # 420×12 − 120
        assert contracted["method_code"] == "acordo_v1"
        assert [h["action"] for h in got["history"]][-1] == "contratada"
        # The board measures nothing; the síndica does not measure either.
        assert got["follow_up_actions"] == []
        assert (await carla.post(f"{url}/measurement")).status_code == 403

        # No invoice after the agreement yet; invoices without the fiscal document do not count.
        assert (await rev.post(f"{url}/measurement")).status_code == 409
        await _invoices(admin_engine, opp["id"], ["4000.00"], with_document=False)
        assert (await rev.post(f"{url}/measurement")).status_code == 409
        await _invoices(admin_engine, opp["id"], ["4580.00", "4620.00"])
        r = await rev.post(f"{url}/measurement")
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["status"] == "resultado_medido"
        realized = next(s for s in got["stages"] if s["stage"] == "realizada")
        assert Decimal(realized["amount"]) == Decimal("400.00")  # mean of 420 and 380
        assert Decimal(realized["one_time_cost"]) == Decimal("120.00")
        assert realized["method_code"] == "medicao_faturas_v1"
        assert realized["confidence"] == "media"  # fewer than 3 invoices
        # Side by side, each with its own name: never a total across stages.
        stages = [s["stage"] for s in (await carla.get(url)).json()["stages"]]
        assert stages == ["estimada_validada", "aprovada", "contratada", "realizada"]

    async with sessionmaker_for(admin_engine)() as s:
        agreement = await s.scalar(
            select(Document).where(
                Document.condominium_id == mirante, Document.original_filename == "acordo.pdf"
            )
        )
    assert agreement is not None  # stored as evidence of the agreement
