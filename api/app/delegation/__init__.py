"""Delegated requests for documents (LF4, F02, ADR-L04, ADR-L06; D97).

The síndico (or whoever manages cases) drafts a request: who, what is expected, until when.
Only the síndico authorizes it, which creates a send-only link valid for 7 days and a ready
text. **Nothing is sent by the system** (Q-L02): the síndico shares the link through their
own channel and may declare it shared. Whoever holds the link can only send files to that
request's condominium — never read anything. Files sent this way:

- are limited to PDF, photos and fiscal XML (no bank files: a third party never feeds the
  bank reconciliation) and to 30 per link and 20 per hour (ADR-L06; no antivirus in the
  product, ClamAV is GPL);
- always go to a person before use: they never match or become a contract alone.

Revoking or concluding invalidates the link immediately; a new link revokes the previous.
Every step goes to ``audit_log`` with ids only.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess
from app.config import get_settings
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import DELEGATION_OPEN, DelegationStatus, DocumentOrigin
from app.db.models import (
    AuditLog,
    Condominium,
    DelegationRequest,
    DelegationUploadToken,
    Document,
)
from app.ingestion.documents import ingest_file
from app.ingestion.filetypes import JPEG, PDF, PNG, WEBP, XML, UnsupportedFile, sniff

LINK_VALID_DAYS = 7
MAX_FILES_PER_LINK = 30
MAX_FILES_PER_HOUR = 20
LINK_TYPES = {PDF, JPEG, PNG, WEBP, XML}
CLOSED = {DelegationStatus.CONCLUIDO.value, DelegationStatus.REVOGADO.value}


class DelegationError(ValueError):
    """A step the request does not accept (pt-BR message, HTTP status)."""

    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def link_path(token: str) -> str:
    return f"/enviar-documentos/{token}"


def message_text(req: DelegationRequest, condo: Condominium, url: str, expires_at: datetime) -> str:
    """The text the síndico sends through their own channel (LB-043)."""
    items = "\n".join(f"- {i['label']}" for i in req.items)
    due = f" até {req.due_date:%d/%m/%Y}" if req.due_date else ""
    return (
        f"Olá, {req.recipient_name}. Sou o síndico do {condo.name}.\n"
        f"Peço que envie{due} os documentos abaixo pelo link seguro, sem precisar de conta:\n"
        f"{items}\n\n"
        f"Assunto: {req.scope}\n"
        f"Link (vale até {expires_at:%d/%m/%Y}): {url}\n"
        "O link só recebe arquivos; ele não mostra nenhum dado do condomínio. Obrigado!"
    )


async def _audit(
    session: AsyncSession,
    action: str,
    req: DelegationRequest,
    actor: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        action=action,
        object_type="delegation_request",
        object_id=req.id,
        actor_user_id=actor,
        condominium_id=req.condominium_id,
        details=details,
    )


async def _revoke_links(session: AsyncSession, req: DelegationRequest) -> None:
    await session.execute(
        update(DelegationUploadToken)
        .where(
            DelegationUploadToken.request_id == req.id,
            DelegationUploadToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )


async def create(
    session: AsyncSession,
    access: CondoAccess,
    *,
    recipient_name: str,
    recipient_email: str | None,
    scope: str,
    items: list[str],
    due_date: date | None,
) -> DelegationRequest:
    labels = [i.strip()[:200] for i in items if i and i.strip()]
    if not labels:
        raise DelegationError("Diga ao menos um documento esperado.")
    if len(labels) > 20:
        raise DelegationError("No máximo 20 documentos por pedido.")
    req = DelegationRequest(
        id=uuid.uuid4(),
        condominium_id=access.condominium_id,
        recipient_name=recipient_name.strip(),
        recipient_email=(recipient_email or "").strip() or None,
        scope=scope.strip(),
        items=[{"label": label, "done": False} for label in labels],
        due_date=due_date,
        status=DelegationStatus.RASCUNHO.value,
        created_by_user_id=access.user_id,
    )
    session.add(req)
    await session.flush()
    await _audit(session, "delegation.created", req, access.user_id, {"items": len(labels)})
    return req


@dataclass(frozen=True)
class NewLink:
    token: str
    path: str
    expires_at: datetime
    message: str


async def authorize(
    session: AsyncSession, access: CondoAccess, condo: Condominium, req: DelegationRequest
) -> NewLink:
    """The síndico authorizes: a new send-only link (the previous one stops working)."""
    if req.status in CLOSED:
        raise DelegationError("Este pedido já foi encerrado.", 409)
    await _revoke_links(session, req)
    token = secrets.token_urlsafe(32)
    expires = utcnow() + timedelta(days=LINK_VALID_DAYS)
    session.add(
        DelegationUploadToken(
            condominium_id=req.condominium_id,
            request_id=req.id,
            token_hash=_hash(token),
            expires_at=expires,
            max_files=MAX_FILES_PER_LINK,
        )
    )
    req.status = DelegationStatus.LINK_GERADO.value
    req.authorized_by_user_id = access.user_id
    req.authorized_at = utcnow()
    req.shared_at = None
    await session.flush()
    await _audit(session, "delegation.link_created", req, access.user_id)
    path = link_path(token)
    url = get_settings().web_base_url.rstrip("/") + path
    return NewLink(token, path, expires, message_text(req, condo, url, expires))


async def mark_shared(session: AsyncSession, access: CondoAccess, req: DelegationRequest) -> None:
    if req.status != DelegationStatus.LINK_GERADO.value:
        raise DelegationError("Só um link gerado e ainda não enviado pode ser marcado.", 409)
    req.status = DelegationStatus.COMPARTILHADO.value
    req.shared_at = utcnow()
    await _audit(session, "delegation.shared", req, access.user_id)


async def set_items(
    session: AsyncSession, access: CondoAccess, req: DelegationRequest, done: list[bool]
) -> None:
    """A person ticks what was received (coverage "3 de 5 itens recebidos")."""
    if req.status == DelegationStatus.REVOGADO.value:
        raise DelegationError("Este pedido foi revogado.", 409)
    if len(done) != len(req.items):
        raise DelegationError("Marque cada documento esperado.")
    req.items = [{**item, "done": bool(d)} for item, d in zip(req.items, done, strict=True)]
    await _audit(session, "delegation.items", req, access.user_id, {"done": sum(done)})


async def conclude(session: AsyncSession, access: CondoAccess, req: DelegationRequest) -> None:
    if req.status in CLOSED:
        raise DelegationError("Este pedido já foi encerrado.", 409)
    await _revoke_links(session, req)
    req.status = DelegationStatus.CONCLUIDO.value
    req.concluded_at = utcnow()
    await _audit(session, "delegation.concluded", req, access.user_id)


async def revoke(session: AsyncSession, access: CondoAccess, req: DelegationRequest) -> None:
    """Immediate: the link stops accepting files on the next request."""
    if req.status in CLOSED:
        raise DelegationError("Este pedido já foi encerrado.", 409)
    await _revoke_links(session, req)
    req.status = DelegationStatus.REVOGADO.value
    req.revoked_at = utcnow()
    await _audit(session, "delegation.revoked", req, access.user_id)


async def current_link(
    session: AsyncSession, req: DelegationRequest
) -> DelegationUploadToken | None:
    return await session.scalar(
        select(DelegationUploadToken)
        .where(DelegationUploadToken.request_id == req.id)
        .order_by(DelegationUploadToken.created_at.desc())
        .limit(1)
    )


def effective_status(req: DelegationRequest, link: DelegationUploadToken | None) -> str:
    """``expirado`` is not stored: an open request whose link passed its date."""
    if (
        req.status in {s.value for s in DELEGATION_OPEN}
        and link is not None
        and link.revoked_at is None
        and link.expires_at <= utcnow()
    ):
        return "expirado"
    return req.status


# --------------------------------------------------------------------------- the public link


async def open_link(session: AsyncSession, token: str) -> DelegationUploadToken | None:
    """A link that may receive files now, or None (for any reason: never say which)."""
    if not token or len(token) > 100:
        return None
    link = await session.scalar(
        select(DelegationUploadToken).where(DelegationUploadToken.token_hash == _hash(token))
    )
    if link is None or link.revoked_at is not None or link.expires_at <= utcnow():
        return None
    return link


async def request_of(session: AsyncSession, link: DelegationUploadToken) -> DelegationRequest:
    """Call with the transaction scoped to ``link.condominium_id`` (RLS)."""
    req = await session.get(DelegationRequest, link.request_id)
    assert req is not None
    return req


@dataclass(frozen=True)
class Received:
    filename: str
    accepted: bool
    duplicate: bool = False
    error: str | None = None


async def receive(
    session: AsyncSession,
    link: DelegationUploadToken,
    req: DelegationRequest,
    files: list[tuple[str, bytes]],
) -> list[Received]:
    """Store files for the request's condominium; never read anything back to the sender."""
    if req.status not in {s.value for s in DELEGATION_OPEN}:
        raise DelegationError("Este link não recebe mais arquivos.", 404)
    hour_ago = utcnow() - timedelta(hours=1)
    recent = int(
        await session.scalar(
            select(func.count()).where(
                AuditLog.action == "delegation.file_received",
                AuditLog.object_id == req.id,
                AuditLog.created_at > hour_ago,
            )
        )
        or 0
    )
    out: list[Received] = []
    for filename, data in files:
        if link.files_received >= link.max_files:
            out.append(
                Received(filename, False, error="Este link já recebeu o máximo de arquivos.")
            )
            continue
        if recent >= MAX_FILES_PER_HOUR:
            out.append(Received(filename, False, error="Muitos envios agora. Tente em uma hora."))
            continue
        try:
            if sniff(filename, data) not in LINK_TYPES:
                raise UnsupportedFile("")
        except UnsupportedFile:
            out.append(
                Received(
                    filename,
                    False,
                    error="Tipo não aceito por este link: envie PDF, foto ou XML de nota fiscal.",
                )
            )
            continue
        outcome = await ingest_file(
            session,
            condominium_id=req.condominium_id,
            filename=filename,
            data=data,
            origin=DocumentOrigin.PEDIDO,
            actor_user_id=None,
        )
        if outcome.document_id is None:
            out.append(Received(outcome.filename, False, error=outcome.error))
            continue
        if outcome.duplicate:
            out.append(Received(outcome.filename, True, duplicate=True))
            continue
        doc = await session.get(Document, outcome.document_id)
        assert doc is not None
        doc.delegation_request_id = req.id
        link.files_received += 1
        recent += 1
        await _audit(
            session,
            "delegation.file_received",
            req,
            None,
            {"document_id": str(doc.id), "link_id": str(link.id)},
        )
        out.append(Received(outcome.filename, True))
    if any(r.accepted and not r.duplicate for r in out) and req.status in (
        DelegationStatus.LINK_GERADO.value,
        DelegationStatus.COMPARTILHADO.value,
    ):
        req.status = DelegationStatus.ARQUIVO_RECEBIDO.value
    await session.flush()
    return out
