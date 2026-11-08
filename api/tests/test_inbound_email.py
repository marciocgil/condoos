"""D101 (LF5, LB-050/051): real inbound e-mail through Amazon SES stored in S3 (here a fake
bucket), the address with a random part, the channel's health, the pause, and that nothing
leaks between condominiums or is processed twice."""

import uuid
from collections.abc import Iterator
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.models import AutomationPause, Condominium, Document, InboundMessage
from app.db.session import sessionmaker_for
from app.ingestion import email as inbound
from app.ingestion.email import S3EmailProvider, inbound_address, poll_provider
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login

CORPUS = Path(__file__).parent / "fixtures" / "corpus"


class FakeS3:
    """The four calls the provider makes, on a dict."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def list_objects_v2(self, Bucket: str, Prefix: str, **_: Any) -> dict[str, Any]:  # noqa: N803
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803
        return {"Body": BytesIO(self.objects[Key])}

    def copy_object(self, Bucket: str, Key: str, CopySource: dict[str, str]) -> None:  # noqa: N803
        self.objects[Key] = self.objects[CopySource["Key"]]

    def delete_object(self, Bucket: str, Key: str) -> None:  # noqa: N803
        del self.objects[Key]


def _pdf() -> bytes:
    return (CORPUS / "17_recibo.pdf").read_bytes() + f"\n% {uuid.uuid4()}\n".encode()


def _eml(to: str, *files: tuple[str, bytes], message_id: str | None = None) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Financeiro <financeiro@fornecedor.example.com>"
    msg["To"] = to
    msg["Subject"] = "Nota fiscal de outubro"
    msg["Message-ID"] = message_id or f"<{uuid.uuid4()}@fornecedor.example.com>"
    msg.set_content("Segue a nota.")
    for name, data in files:
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=name)
    return msg.as_bytes()


@pytest.fixture
def bucket() -> Iterator[tuple[FakeS3, S3EmailProvider]]:
    s3 = FakeS3()
    yield s3, S3EmailProvider(s3, "condoos-inbound", "inbound/")


async def _condo(engine: AsyncEngine, slug: str) -> Condominium:
    async with sessionmaker_for(engine)() as s:
        condo = await s.scalar(select(Condominium).where(Condominium.slug == slug))
        assert condo is not None
        return condo


async def _log(engine: AsyncEngine, message_hash_of: bytes) -> InboundMessage | None:
    parsed = inbound.parse_eml(message_hash_of, "x")
    async with sessionmaker_for(engine)() as s:
        return await s.scalar(
            select(InboundMessage).where(InboundMessage.message_hash == parsed.message_hash)
        )


async def _email_docs(engine: AsyncEngine, cid: uuid.UUID) -> int:
    async with sessionmaker_for(engine)() as s:
        return int(
            await s.scalar(
                select(func.count())
                .select_from(Document)
                .where(Document.condominium_id == cid, Document.origin == "email")
            )
            or 0
        )


async def test_ses_message_becomes_a_document_once(
    bucket: tuple[FakeS3, S3EmailProvider], worker_engine: AsyncEngine
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    address = inbound_address(acacias)
    assert address.startswith(f"jardim-das-acacias-{acacias.inbound_token}@")
    raw = _eml(address, ("nf.pdf", _pdf()))
    s3.objects["inbound/msg-1"] = raw
    before = await _email_docs(worker_engine, acacias.id)

    maker = sessionmaker_for(worker_engine)
    assert await poll_provider(maker, provider) == 1
    assert "processed/msg-1" in s3.objects and "inbound/msg-1" not in s3.objects
    assert await _email_docs(worker_engine, acacias.id) == before + 1
    row = await _log(worker_engine, raw)
    assert row is not None and row.status == "processada" and row.condominium_id == acacias.id
    assert (row.documents, row.attachments, row.sender_domain) == (1, 1, "fornecedor.example.com")

    # SES may deliver the same message twice: processed once.
    s3.objects["inbound/msg-1-again"] = raw
    assert await poll_provider(maker, provider) == 1
    assert "processed/msg-1-again" in s3.objects
    assert await _email_docs(worker_engine, acacias.id) == before + 1


async def test_unknown_address_empty_and_refused_messages(
    bucket: tuple[FakeS3, S3EmailProvider], worker_engine: AsyncEngine
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    mirante = await _condo(worker_engine, "mirante-do-vale")
    address = inbound_address(acacias)
    domain = address.split("@")[1]
    active = (
        (CORPUS / "17_recibo.pdf")
        .read_bytes()
        .replace(b"%%EOF", b"9 0 obj << /S /JavaScript /JS (x) >> endobj\n%%EOF")
    )
    unknown = _eml(f"nao-existe-abc12345@{domain}", ("nf.pdf", _pdf()))
    # Acácias' slug with Mirante's token: never lands in either.
    crossed = _eml(f"jardim-das-acacias-{mirante.inbound_token}@{domain}", ("nf.pdf", _pdf()))
    empty = _eml(address)
    refused = _eml(address, ("ativo.pdf", active))
    for i, raw in enumerate((unknown, crossed, empty, refused)):
        s3.objects[f"inbound/{i}"] = raw
    before_a = await _email_docs(worker_engine, acacias.id)
    before_m = await _email_docs(worker_engine, mirante.id)

    assert await poll_provider(sessionmaker_for(worker_engine), provider) == 0
    assert sorted(k for k in s3.objects) == [f"rejected/{i}" for i in range(4)]
    assert await _email_docs(worker_engine, acacias.id) == before_a
    assert await _email_docs(worker_engine, mirante.id) == before_m
    for raw, condo, reason in (
        (unknown, None, "Endereço desconhecido."),
        (crossed, None, "Endereço desconhecido."),
        (empty, acacias.id, "E-mail sem anexo."),
    ):
        row = await _log(worker_engine, raw)
        assert row is not None and row.status == "recusada"
        assert row.condominium_id == condo and row.reasons == [reason]
    row = await _log(worker_engine, refused)
    assert row is not None and row.status == "recusada" and row.refused == 1
    assert "conteúdo ativo" in row.reasons[0]


async def test_slug_only_address_is_refused_where_not_allowed(
    bucket: tuple[FakeS3, S3EmailProvider],
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    domain = inbound_address(acacias).split("@")[1]
    monkeypatch.setattr(inbound, "_accept_slug_address", lambda: False)
    s3.objects["inbound/slug"] = _eml(f"jardim-das-acacias@{domain}", ("nf.pdf", _pdf()))
    assert await poll_provider(sessionmaker_for(worker_engine), provider) == 0
    assert "rejected/slug" in s3.objects


async def test_paused_channel_keeps_the_message_waiting(
    bucket: tuple[FakeS3, S3EmailProvider], worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    raw = _eml(inbound_address(acacias), ("nf.pdf", _pdf()))
    s3.objects["inbound/paused"] = raw
    pause_id = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            AutomationPause(
                id=pause_id,
                condominium_id=acacias.id,
                automation_type="email.inbound",
                reason="Teste da pausa do e-mail",
            )
        )
    maker = sessionmaker_for(worker_engine)
    assert await poll_provider(maker, provider) == 0
    assert list(s3.objects) == ["inbound/paused"]  # nothing lost, nothing logged
    assert await _log(worker_engine, raw) is None
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(AutomationPause)
            .where(AutomationPause.id == pause_id)
            .values(resumed_at=utcnow())
        )
    assert await poll_provider(maker, provider) == 1


async def test_failure_is_logged_and_the_message_set_aside(
    bucket: tuple[FakeS3, S3EmailProvider],
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    raw = _eml(inbound_address(acacias), ("nf.pdf", _pdf()))
    s3.objects["inbound/boom"] = raw

    async def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("storage down")

    monkeypatch.setattr(inbound, "ingest_file", boom)
    assert await poll_provider(sessionmaker_for(worker_engine), provider) == 0
    assert "rejected/boom" in s3.objects
    row = await _log(worker_engine, raw)
    assert row is not None and row.status == "falhou" and row.condominium_id == acacias.id


async def test_channel_health_and_changing_the_address(
    bucket: tuple[FakeS3, S3EmailProvider],
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    s3, provider = bucket
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    path = f"/condominiums/{acacias}/inbound"

    await login(client, mailer, SINDICA_ACACIAS)
    health = (await client.get(path)).json()
    old = health["address"]
    assert health["can_change"] is True and health["paused"] is False
    s3.objects["inbound/h1"] = _eml(old, ("nf.pdf", _pdf()))
    await poll_provider(sessionmaker_for(worker_engine), provider)
    health = (await client.get(path)).json()
    assert health["days_since_last_message"] == 0
    assert health["last_30_days"]["documents"] >= 1
    last = health["recent"][0]
    assert last["status"] == "processada" and last["sender_domain"] == "fornecedor.example.com"
    assert set(last) == {
        "received_at",
        "sender_domain",
        "status",
        "attachments",
        "documents",
        "duplicates",
        "refused",
        "reasons",
    }  # no subject, body or full sender address

    changed = (await client.post(f"{path}/change-address")).json()
    assert changed["address"] != old
    s3.objects["inbound/old"] = _eml(old, ("nf.pdf", _pdf()))
    s3.objects["inbound/new"] = _eml(changed["address"], ("nf.pdf", _pdf()))
    assert await poll_provider(sessionmaker_for(worker_engine), provider) == 1
    assert "rejected/old" in s3.objects and "processed/new" in s3.objects

    await login(client, mailer, CONSELHEIRO_ACACIAS)
    assert (await client.get(path)).json()["can_change"] is False
    assert (await client.post(f"{path}/change-address")).status_code == 403
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(path)).status_code == 404


async def test_ses_virus_verdict_refuses_and_spam_is_noted(
    bucket: tuple[FakeS3, S3EmailProvider], worker_engine: AsyncEngine
) -> None:
    s3, provider = bucket
    acacias = await _condo(worker_engine, "jardim-das-acacias")
    address = inbound_address(acacias)

    def with_verdicts(virus: str, spam: str) -> bytes:
        raw = _eml(address, ("nf.pdf", _pdf()))
        head = f"X-SES-Virus-Verdict: {virus}\r\nX-SES-Spam-Verdict: {spam}\r\n".encode()
        return head + raw

    virus = with_verdicts("FAIL", "PASS")
    spam = with_verdicts("PASS", "FAIL")
    s3.objects["inbound/virus"] = virus
    s3.objects["inbound/spam"] = spam
    before = await _email_docs(worker_engine, acacias.id)
    assert await poll_provider(sessionmaker_for(worker_engine), provider) == 1
    assert "rejected/virus" in s3.objects and "processed/spam" in s3.objects
    assert await _email_docs(worker_engine, acacias.id) == before + 1  # only the spam one
    row = await _log(worker_engine, virus)
    assert row is not None and row.status == "recusada" and row.documents == 0
    assert row.reasons == [inbound.VIRUS_REASON]
    row = await _log(worker_engine, spam)
    assert row is not None and row.status == "processada"
    assert row.reasons == [inbound.SPAM_NOTE]
