"""Exception queue: listing, correction (training data) and discard."""

import json
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AuditLog, Document, ExtractionCorrection
from app.db.session import sessionmaker_for
from app.extraction.pipeline import process_document
from tests.helpers import (
    ANALISTA,
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

CORPUS = Path(__file__).parent / "fixtures" / "corpus"
TRUTH = json.loads((CORPUS / "ground_truth.json").read_text(encoding="utf-8"))["documents"]


async def _upload_receipt(
    client: httpx.AsyncClient, mailer: MemoryMailer, worker_engine: AsyncEngine, acacias: uuid.UUID
) -> str:
    """Upload a receipt (goes to the queue without the model) with unique bytes."""
    await login(client, mailer, SINDICA_ACACIAS)
    data = (CORPUS / "18_recibo.pdf").read_bytes() + f"\n% {uuid.uuid4()}\n".encode()
    r = await client.post(
        f"/condominiums/{acacias}/documents",
        files=[("files", ("recibo.pdf", data, "application/pdf"))],
    )
    doc_id: str = r.json()[0]["document_id"]
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await process_document(s, {"document_id": doc_id})
    await client.post("/auth/logout")
    return doc_id


async def test_queue_correction_flow(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    doc_id = await _upload_receipt(client, mailer, worker_engine, acacias)

    # The síndica cannot correct and has no queue items.
    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get("/queue")).json() == []
    assert (
        await client.get(f"/condominiums/{acacias}/documents/{doc_id}/review")
    ).status_code == 403
    await client.post("/auth/logout")

    await login(client, mailer, ANALISTA)
    queue = (await client.get("/queue")).json()
    item = next(i for i in queue if i["id"] == doc_id)
    assert item["kind"] == "extracao" and "Jardim das Acácias" in item["condominium_name"]
    assert (await client.get("/queue/count")).json()["extracao"] >= 1

    review = (await client.get(f"/condominiums/{acacias}/documents/{doc_id}/review")).json()
    assert review["doc_type"] == "recibo" and review["reasons"]
    assert {f["name"] for f in review["fields_by_type"]["recibo"]} >= {"data", "valor"}

    truth = TRUTH["18_recibo.pdf"]["fields"]
    bad = {**truth, "documento_recebedor": "11111111111"}
    r = await client.put(
        f"/condominiums/{acacias}/documents/{doc_id}/review",
        json={"doc_type": "recibo", "values": bad},
    )
    assert r.status_code == 422
    assert "documento_recebedor" in r.json()["detail"]["fields"]

    r = await client.put(
        f"/condominiums/{acacias}/documents/{doc_id}/review",
        json={"doc_type": "recibo", "values": {**truth, "valor": "R$ 180,00"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["values"]["valor"] == "180.00" and r.json()["reviewed_at"]
    assert all(c == 1.0 for c in r.json()["confidence"].values())
    queue = (await client.get("/queue")).json()
    assert doc_id not in {i["id"] for i in queue}

    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.get(Document, uuid.UUID(doc_id))
        corrections = (
            await s.scalars(
                select(ExtractionCorrection).where(
                    ExtractionCorrection.document_id == uuid.UUID(doc_id)
                )
            )
        ).all()
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.object_id == uuid.UUID(doc_id), AuditLog.action == "document.reviewed"
            )
        )
    assert doc is not None and not doc.needs_review and doc.extraction_status == "done"
    assert corrections and audit is not None
    assert {c.field_name for c in corrections} >= {"nome_recebedor"}  # was not found automatically


async def test_tomador_of_other_condominium_is_rejected(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    doc_id = await _upload_receipt(client, mailer, worker_engine, acacias)
    await login(client, mailer, ANALISTA)
    nfse = TRUTH["24_nfse_nacional.xml"]["fields"]
    r = await client.put(
        f"/condominiums/{acacias}/documents/{doc_id}/review",
        json={"doc_type": "nfse", "values": {**nfse, "cnpj_tomador": "11222333000181"}},
    )
    assert r.status_code == 422
    assert "descarte" in r.json()["detail"]["fields"]["cnpj_tomador"]

    r = await client.post(
        f"/condominiums/{acacias}/documents/{doc_id}/review/discard",
        json={"motivo": "Documento de outro condomínio"},
    )
    assert r.status_code == 200
    assert doc_id not in {i["id"] for i in (await client.get("/queue")).json()}


async def test_review_is_tenant_scoped(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    doc_id = await _upload_receipt(client, mailer, worker_engine, acacias)
    await login(client, mailer, ANALISTA)
    # Right document, wrong condominium in the path.
    assert (
        await client.get(f"/condominiums/{mirante}/documents/{doc_id}/review")
    ).status_code == 404
    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (
        await client.get(f"/condominiums/{acacias}/documents/{doc_id}/review")
    ).status_code == 404
    await client.post("/auth/logout")
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    assert (
        await client.get(f"/condominiums/{acacias}/documents/{doc_id}/review")
    ).status_code == 403
