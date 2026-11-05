"""Outgoing e-mail. SMTP in docker (Mailpit locally), in-memory in tests."""

import logging
from dataclasses import dataclass, field
from email.message import EmailMessage
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


class Mailer(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class SmtpMailer:
    async def send(self, message: OutgoingEmail) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = s.mail_from
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.body)
        await aiosmtplib.send(
            msg,
            hostname=s.smtp_host,
            port=s.smtp_port,
            username=s.smtp_user,
            password=s.smtp_password.get_secret_value() if s.smtp_password else None,
        )


class ConsoleMailer:
    """Development only: prints the message body to stdout instead of sending it."""

    async def send(self, message: OutgoingEmail) -> None:
        if get_settings().environment != "development":
            raise RuntimeError("ConsoleMailer is only allowed in development")
        print(f"[mailer] {message.subject}\n{message.body}", flush=True)


@dataclass
class MemoryMailer:
    sent: list[OutgoingEmail] = field(default_factory=list)

    async def send(self, message: OutgoingEmail) -> None:
        self.sent.append(message)


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
