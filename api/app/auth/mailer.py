"""Outgoing e-mail. SMTP in docker (Mailpit locally), in-memory in tests."""

import logging
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from functools import lru_cache
from typing import Protocol

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    body: str
    reply_to: str | None = None
    # Display name in front of the configured sender address (e.g. "CondoOS em nome do ...").
    from_name: str | None = None


class Mailer(Protocol):
    async def send(self, message: OutgoingEmail) -> str:
        """Send; return the Message-ID. Raises when the server refuses."""
        ...


def _message_id() -> str:
    return make_msgid(domain=parseaddr(get_settings().mail_from)[1].rpartition("@")[2] or None)


class SmtpMailer:
    async def send(self, message: OutgoingEmail) -> str:
        s = get_settings()
        msg = EmailMessage()
        sender = parseaddr(s.mail_from)
        msg["From"] = formataddr((message.from_name or sender[0], sender[1]))
        msg["To"] = message.to
        if message.reply_to:
            msg["Reply-To"] = message.reply_to
        msg["Subject"] = message.subject
        msg["Message-ID"] = message_id = _message_id()
        msg.set_content(message.body)
        await aiosmtplib.send(
            msg,
            hostname=s.smtp_host,
            port=s.smtp_port,
            username=s.smtp_user,
            password=s.smtp_password.get_secret_value() if s.smtp_password else None,
        )
        return message_id


class ConsoleMailer:
    """Development only: prints the message body to stdout instead of sending it."""

    async def send(self, message: OutgoingEmail) -> str:
        if get_settings().environment != "development":
            raise RuntimeError("ConsoleMailer is only allowed in development")
        print(f"[mailer] {message.subject}\n{message.body}", flush=True)
        return _message_id()


@dataclass
class MemoryMailer:
    sent: list[OutgoingEmail] = field(default_factory=list)

    fail: bool = False  # tests: the server refuses

    async def send(self, message: OutgoingEmail) -> str:
        if self.fail:
            raise ConnectionError("servidor de e-mail recusou")
        self.sent.append(message)
        return _message_id()


_memory = MemoryMailer()


@lru_cache
def _smtp() -> SmtpMailer:
    return SmtpMailer()


def get_mailer() -> Mailer:
    kind = get_settings().mailer
    if kind == "smtp":
        return _smtp()
    if kind == "memory":
        return _memory
    return ConsoleMailer()
