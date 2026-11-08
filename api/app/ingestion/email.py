"""Inbound e-mail (D101): each condominium has <slug>-<token>@<INGEST_EMAIL_DOMAIN>.

Providers implement ``InboundEmailProvider`` (``fetch`` and ``ack``):

- ``FolderEmailProvider`` reads ``.eml`` files from a folder (local and tests);
- ``S3EmailProvider`` reads what Amazon SES (São Paulo) stored in a bucket.

Handled messages move to ``processed/`` or ``rejected/``. Every message leaves one
``inbound_message`` row (sender's domain and counts only) for the channel's health; the same
message twice is processed once. Nothing is ever sent back to the sender.
"""

import email
import email.policy
import hashlib
import logging
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.enums import DocumentOrigin, InboundMessageStatus
from app.db.models import Condominium, InboundMessage
from app.ingestion.documents import IngestOutcome, ingest_file

logger = logging.getLogger(__name__)

PAUSE_TYPE = "email.inbound"


@dataclass
class InboundEmail:
    ref: str  # provider reference (file name, object key...)
    recipients: list[str]
    subject: str
    attachments: list[tuple[str, bytes]] = field(default_factory=list)
    message_hash: str = ""  # SHA-256 of the Message-ID (or of the raw message)
    sender_domain: str | None = None


class InboundEmailProvider(Protocol):
    def fetch(self) -> Iterator[InboundEmail]: ...
    def ack(self, message: InboundEmail, ok: bool) -> None: ...


def parse_eml(raw: bytes, ref: str) -> InboundEmail:
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(msg, EmailMessage)
    recipients = [
        addr.lower()
        for _, addr in getaddresses(
            msg.get_all("To", []) + msg.get_all("Cc", []) + msg.get_all("Delivered-To", [])
        )
        if addr
    ]
    attachments: list[tuple[str, bytes]] = []
    for part in msg.iter_attachments():
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes) and payload:
            attachments.append((part.get_filename() or "anexo", payload))
    message_id = str(msg.get("Message-ID", "")).strip()
    digest = hashlib.sha256(message_id.encode() if message_id else raw).hexdigest()
    senders = [a for _, a in getaddresses(msg.get_all("From", [])) if "@" in a]
    return InboundEmail(
        ref=ref,
        recipients=recipients,
        subject=str(msg.get("Subject", "")),
        attachments=attachments,
        message_hash=digest,
        sender_domain=senders[0].rsplit("@", 1)[1].lower()[:255] if senders else None,
    )


class FolderEmailProvider:
    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def fetch(self) -> Iterator[InboundEmail]:
        for path in sorted(self.folder.glob("*.eml")):
            yield parse_eml(path.read_bytes(), ref=path.name)

    def ack(self, message: InboundEmail, ok: bool) -> None:
        target = self.folder / ("processed" if ok else "rejected")
        target.mkdir(exist_ok=True)
        shutil.move(str(self.folder / message.ref), str(target / message.ref))


class S3EmailProvider:
    """Messages Amazon SES stored under ``prefix`` (receipt rule "deliver to S3"). Handled
    ones move to ``processed/`` or ``rejected/`` in the same bucket; a lifecycle rule on the
    bucket deletes them after 30 days (docs/deploy.md)."""

    def __init__(self, client: Any, bucket: str, prefix: str = "inbound/") -> None:
        self.client = client
        self.bucket = bucket
        self.prefix = prefix

    def fetch(self) -> Iterator[InboundEmail]:
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Prefix": self.prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = self.client.list_objects_v2(**kwargs)
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                raw = self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
                yield parse_eml(raw, ref=key)
            if not page.get("IsTruncated"):
                return
            token = page.get("NextContinuationToken")

    def ack(self, message: InboundEmail, ok: bool) -> None:
        ref = message.ref
        name = ref[len(self.prefix) :] if ref.startswith(self.prefix) else ref
        target = f"{'processed' if ok else 'rejected'}/{name}"
        self.client.copy_object(
            Bucket=self.bucket, Key=target, CopySource={"Bucket": self.bucket, "Key": ref}
        )
        self.client.delete_object(Bucket=self.bucket, Key=ref)


def provider_from_settings() -> InboundEmailProvider | None:
    s = get_settings()
    kind = s.inbound_email_provider
    if kind == "none" and s.inbound_email_dir:
        kind = "folder"
    if kind == "folder" and s.inbound_email_dir:
        return FolderEmailProvider(s.inbound_email_dir)
    if kind == "s3" and s.inbound_email_s3_bucket:
        import boto3
        from botocore.config import Config

        key = s.inbound_email_s3_access_key_id or s.s3_access_key_id
        secret = s.inbound_email_s3_secret_access_key or s.s3_secret_access_key
        client = boto3.client(
            "s3",
            endpoint_url=s.inbound_email_s3_endpoint_url,
            region_name=s.inbound_email_s3_region,
            aws_access_key_id=key.get_secret_value(),
            aws_secret_access_key=secret.get_secret_value(),
            config=Config(signature_version="s3v4"),
        )
        return S3EmailProvider(client, s.inbound_email_s3_bucket, s.inbound_email_s3_prefix)
    return None


# --------------------------------------------------------------------------- addresses


def inbound_address(condo: Condominium) -> str:
    return f"{condo.slug}-{condo.inbound_token}@{get_settings().ingest_email_domain.lower()}"


def _accept_slug_address() -> bool:
    s = get_settings()
    if s.inbound_accept_slug_address is not None:
        return s.inbound_accept_slug_address
    return s.environment != "production"


async def find_condominium(session: AsyncSession, recipients: list[str]) -> Condominium | None:
    """The condominium of the first recipient at our domain: <slug>-<token> must match both
    parts (an old token stops working once changed); <slug> alone only where allowed."""
    domain = "@" + get_settings().ingest_email_domain.lower()
    for addr in recipients:
        if not addr.endswith(domain):
            continue
        local = addr[: -len(domain)].split("+", 1)[0]
        slug, _, token = local.rpartition("-")
        if slug and token:
            condo = await session.scalar(
                select(Condominium).where(
                    Condominium.inbound_token == token, Condominium.slug == slug
                )
            )
            if condo is not None:
                return condo
        if _accept_slug_address():
            condo = await session.scalar(select(Condominium).where(Condominium.slug == local))
            if condo is not None:
                return condo
    return None


# --------------------------------------------------------------------------- processing


@dataclass
class Handled:
    status: str | None  # None: paused, the message stays where it is
    outcomes: list[IngestOutcome] = field(default_factory=list)


def _log(
    message: InboundEmail,
    condo_id: uuid.UUID | None,
    status: InboundMessageStatus,
    outcomes: list[IngestOutcome] | None = None,
    reasons: list[str] | None = None,
) -> InboundMessage:
    outcomes = outcomes or []
    errors = [o.error for o in outcomes if o.error]
    return InboundMessage(
        id=uuid.uuid4(),
        condominium_id=condo_id,
        message_hash=message.message_hash,
        sender_domain=message.sender_domain,
        status=status.value,
        attachments=len(message.attachments),
        documents=sum(1 for o in outcomes if o.document_id and not o.duplicate),
        duplicates=sum(1 for o in outcomes if o.duplicate),
        refused=len(errors),
        reasons=sorted(set((reasons or []) + errors))[:10],
    )


async def process_inbound(session: AsyncSession, message: InboundEmail) -> Handled:
    from app.policy import active_pause

    if message.message_hash and await session.scalar(
        select(InboundMessage.id).where(InboundMessage.message_hash == message.message_hash)
    ):
        return Handled(InboundMessageStatus.PROCESSADA.value)  # already handled once
    condo = await find_condominium(session, message.recipients)
    if condo is None:
        logger.warning("inbound email for no condominium ref=%s", message.ref)
        session.add(
            _log(message, None, InboundMessageStatus.RECUSADA, reasons=["Endereço desconhecido."])
        )
        return Handled(InboundMessageStatus.RECUSADA.value)
    if await active_pause(session, condo.id, PAUSE_TYPE):
        return Handled(None)
    if not message.attachments:
        session.add(
            _log(message, condo.id, InboundMessageStatus.RECUSADA, reasons=["E-mail sem anexo."])
        )
        return Handled(InboundMessageStatus.RECUSADA.value)
    outcomes = []
    for filename, data in message.attachments:
        outcomes.append(
            await ingest_file(
                session,
                condominium_id=condo.id,
                filename=filename,
                data=data,
                origin=DocumentOrigin.EMAIL,
                actor_user_id=None,
            )
        )
    accepted = any(o.document_id is not None for o in outcomes)
    status = InboundMessageStatus.PROCESSADA if accepted else InboundMessageStatus.RECUSADA
    session.add(_log(message, condo.id, status, outcomes))
    return Handled(status.value, outcomes)


async def _record_failure(maker: async_sessionmaker[AsyncSession], message: InboundEmail) -> None:
    async with maker() as session, session.begin():
        if await session.scalar(
            select(InboundMessage.id).where(InboundMessage.message_hash == message.message_hash)
        ):
            return
        condo = await find_condominium(session, message.recipients)
        session.add(
            _log(
                message,
                condo.id if condo else None,
                InboundMessageStatus.FALHOU,
                reasons=["Falha ao processar a mensagem."],
            )
        )


async def poll_provider(
    maker: async_sessionmaker[AsyncSession], provider: InboundEmailProvider
) -> int:
    """Process every waiting message, one transaction each. A message is acknowledged
    (moved away) only after its documents and its log row are committed; a paused
    condominium's messages stay where they are. Returns how many were accepted."""
    accepted = 0
    for message in provider.fetch():
        try:
            async with maker() as session, session.begin():
                handled = await process_inbound(session, message)
        except Exception:
            logger.exception("inbound email failed ref=%s", message.ref)
            await _record_failure(maker, message)
            provider.ack(message, False)
            continue
        if handled.status is None:
            continue
        ok = handled.status == InboundMessageStatus.PROCESSADA.value
        provider.ack(message, ok)
        accepted += int(ok)
    return accepted
