import uuid
from email.message import EmailMessage
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AuditLog, Document, Job
from app.db.session import sessionmaker_for
from app.ingestion.email import FolderEmailProvider, parse_eml, poll_provider
from app.ingestion.filetypes import sniff
from app.storage.base import MemoryStorage, get_storage
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _unique_pdf() -> bytes:
    return PDF + f"% {uuid.uuid4()}\n".encode()


async def test_upload_stores_file_and_enqueues_processing(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    data = _unique_pdf()
    r = await client.post(
        f"/condominiums/{acacias}/documents",
        files=[("files", ("nota 1.pdf", data, "application/pdf"))],
    )
    assert r.status_code == 201, r.text
    [result] = r.json()
    assert result["error"] is None and not result["duplicate"]
    doc_id = uuid.UUID(result["document_id"])

    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.get(Document, doc_id)
        assert doc is not None
        job = await s.scalar(select(Job).where(Job.dedupe_key == f"doc:{doc_id}:process"))
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.object_id == doc_id, AuditLog.action == "document.uploaded"
            )
        )
    assert doc.mime_type == "application/pdf" and doc.origin == "upload"
    assert doc.storage_key.startswith(f"cond/{acacias}/")
    storage = get_storage()
    assert isinstance(storage, MemoryStorage) and storage.get(doc.storage_key) == data
    assert job is not None and audit is not None

    # Same bytes again: no new document, no new job.
    again = (
        await client.post(
            f"/condominiums/{acacias}/documents",
            files=[("files", ("copia.pdf", data, "application/pdf"))],
        )
    ).json()
    assert again[0]["duplicate"] and again[0]["document_id"] == str(doc_id)

    detail = (await client.get(f"/condominiums/{acacias}/documents/{doc_id}")).json()
    assert detail["file_url"].startswith("memory://cond/")


async def test_upload_rejects_unsupported_files(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(
        f"/condominiums/{acacias}/documents",
        files=[
            ("files", ("virus.exe", b"MZ\x90\x00", "application/octet-stream")),
            ("files", ("foto.heic", b"\x00\x00\x00\x18ftypheic", "image/heic")),
            ("files", ("vazio.pdf", b"", "application/pdf")),
        ],
    )
    errors = [x["error"] for x in r.json()]
    assert "Tipo de arquivo não aceito" in errors[0]
    assert "HEIC" in errors[1]
    assert errors[2] == "Arquivo vazio."


async def test_conselheiro_cannot_upload(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    r = await client.post(
        f"/condominiums/{acacias}/documents",
        files=[("files", ("a.pdf", _unique_pdf(), "application/pdf"))],
    )
    assert r.status_code == 403


async def test_documents_are_isolated(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(
        f"/condominiums/{acacias}/documents",
        files=[("files", ("a.pdf", _unique_pdf(), "application/pdf"))],
    )
    doc_id = r.json()[0]["document_id"]
    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    assert (await client.get(f"/condominiums/{acacias}/documents/{doc_id}")).status_code == 404
    assert (await client.get(f"/condominiums/{mirante}/documents/{doc_id}")).status_code == 404


def test_sniff() -> None:
    assert sniff("x", b"%PDF-1.7") == "application/pdf"
    assert sniff("x", b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff("x", b'<?xml version="1.0"?><nfeProc/>') == "application/xml"
    assert sniff("extrato.csv", b"data;valor\n") == "text/csv"


def _eml(to: str, attachments: list[tuple[str, bytes, str]]) -> bytes:
    msg = EmailMessage()
    msg["From"] = "financeiro@fornecedor.example.com"
    msg["To"] = to
    msg["Subject"] = "Nota fiscal de outubro"
    msg.set_content("Segue a nota.")
    for name, data, mime in attachments:
        main, sub = mime.split("/")
        msg.add_attachment(data, maintype=main, subtype=sub, filename=name)
    return msg.as_bytes()


async def test_folder_email_provider(tmp_path: Path, worker_engine: AsyncEngine) -> None:
    good = _eml(
        "mirante-do-vale@ingest.condoos.local",
        [("nf.pdf", _unique_pdf(), "application/pdf")],
    )
    unknown = _eml(
        "nao-existe@ingest.condoos.local", [("nf.pdf", _unique_pdf(), "application/pdf")]
    )
    (tmp_path / "1.eml").write_bytes(good)
    (tmp_path / "2.eml").write_bytes(unknown)
    parsed = parse_eml(good, "1.eml")
    assert parsed.recipients == ["mirante-do-vale@ingest.condoos.local"]
    assert [a[0] for a in parsed.attachments] == ["nf.pdf"]

    before = await _count_email_docs(worker_engine)
    accepted = await poll_provider(sessionmaker_for(worker_engine), FolderEmailProvider(tmp_path))
    assert accepted == 1
    assert await _count_email_docs(worker_engine) == before + 1
    assert (tmp_path / "processed" / "1.eml").exists()
    assert (tmp_path / "rejected" / "2.eml").exists()
    assert not list(tmp_path.glob("*.eml"))


async def _count_email_docs(engine: AsyncEngine) -> int:
    async with sessionmaker_for(engine)() as s:
        return int(
            await s.scalar(
                select(func.count()).select_from(Document).where(Document.origin == "email")
            )
            or 0
        )
