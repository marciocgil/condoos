"""CB-031 (FR-015, DOC-02; D85): a new file of the same logical document becomes a new
version; the previous one is kept, leaves the search and stops being the contract's source."""

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.chat.search import search
from app.db.models import Contract, Document, DocumentChunk
from app.db.session import sessionmaker_for
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


async def test_new_version_keeps_the_old_one_and_takes_its_place(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with sessionmaker_for(admin_engine)() as s:
        contract = await s.scalar(
            select(Contract)
            .where(Contract.condominium_id == acacias, Contract.source_document_id.is_not(None))
            .limit(1)
        )
        assert contract is not None
        old = await s.get(Document, contract.source_document_id)
        assert old is not None
        chunks = await s.scalar(
            select(DocumentChunk.id).where(DocumentChunk.document_id == old.id).limit(1)
        )
    assert chunks is not None  # the seed contract is searchable before
    base = f"/condominiums/{acacias}/documents"
    data = PDF + f"% versão nova {uuid.uuid4()}\n".encode()

    await login(client, mailer, CONSELHEIRO_ACACIAS)
    r = await client.post(
        f"{base}/{old.id}/versions", files={"file": ("contrato-v2.pdf", data, "application/pdf")}
    )
    assert r.status_code == 403

    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(
        f"{base}/{old.id}/versions", files={"file": ("contrato-v2.pdf", data, "application/pdf")}
    )
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["version"] == old.version + 1 and new["supersedes_id"] == str(old.id)
    assert new["doc_type"] == "contrato"

    detail = (await client.get(f"{base}/{old.id}")).json()
    assert detail["superseded_by_id"] == new["id"]  # preserved, with a pointer to the new one
    # Only one newer version per document; the same bytes are not a new version.
    again = await client.post(
        f"{base}/{old.id}/versions", files={"file": ("x.pdf", data + b"1", "application/pdf")}
    )
    assert again.status_code == 409
    dup = await client.post(
        f"{base}/{new['id']}/versions", files={"file": ("x.pdf", data, "application/pdf")}
    )
    assert dup.status_code == 409

    async with sessionmaker_for(admin_engine)() as s:
        moved = await s.get(Contract, contract.id)
        assert moved is not None and moved.source_document_id == uuid.UUID(new["id"])
        left = await s.scalar(
            select(DocumentChunk.id).where(DocumentChunk.document_id == old.id).limit(1)
        )
        found = await search(s, acacias, "rescisão aviso prévio multa", limit=20)
    assert left is None
    assert old.id not in {p.document_id for p in found}

    await login(client, mailer, SINDICA_MIRANTE)
    r = await client.post(
        f"{base}/{new['id']}/versions",
        files={"file": ("y.pdf", data + b"2", "application/pdf")},
    )
    assert r.status_code == 404
