"""Inbound e-mail: each condominium has <slug>@<INGEST_EMAIL_DOMAIN>.

``InboundEmailProvider`` is the integration point (IMAP, SES, Mailgun... later). The MVP
ships ``FolderEmailProvider``, which reads ``.eml`` files from a folder, used locally and in
tests. Processed messages are moved to ``processed/`` (or ``rejected/``).
"""

import email
import email.policy
import logging
import shutil
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.enums import DocumentOrigin
from app.db.models import Condominium
from app.ingestion.documents import IngestOutcome, ingest_file

logger = logging.getLogger(__name__)


@dataclass
class InboundEmail:
    ref: str  # provider reference (file name, IMAP uid...)
    recipients: list[str]
    subject: str
    attachments: list[tuple[str, bytes]] = field(default_factory=list)


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
    return InboundEmail(
        ref=ref, recipients=recipients, subject=str(msg.get("Subject", "")), attachments=attachments
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


def condominium_slug(recipients: list[str]) -> str | None:
    domain = "@" + get_settings().ingest_email_domain.lower()
    for addr in recipients:
        if addr.endswith(domain):
            return addr[: -len(domain)]
    return None


async def process_inbound(session: AsyncSession, message: InboundEmail) -> list[IngestOutcome]:
    slug = condominium_slug(message.recipients)
    if slug is None:
        logger.warning("inbound email without condominium address ref=%s", message.ref)
        return []
    condo_id: uuid.UUID | None = await session.scalar(
        select(Condominium.id).where(Condominium.slug == slug)
    )
    if condo_id is None:
        logger.warning("inbound email for unknown condominium ref=%s", message.ref)
        return []
    outcomes = []
    for filename, data in message.attachments:
        outcomes.append(
            await ingest_file(
                session,
                condominium_id=condo_id,
                filename=filename,
                data=data,
                origin=DocumentOrigin.EMAIL,
                actor_user_id=None,
            )
        )
    return outcomes


async def poll_provider(
    maker: async_sessionmaker[AsyncSession], provider: InboundEmailProvider
) -> int:
    """Process every waiting message, one transaction each. A message is acknowledged
    (moved away) only after its documents are committed. Returns how many were accepted."""
    accepted = 0
    for message in provider.fetch():
        async with maker() as session, session.begin():
            outcomes = await process_inbound(session, message)
        ok = any(o.document_id is not None for o in outcomes)
        provider.ack(message, ok)
        accepted += int(ok)
    return accepted
