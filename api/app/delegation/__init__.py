"""Delegated document requests (D95, ADR-L04; flow F02 of the Launch).

The síndico (or the CondoOS team, as a draft) prepares a request for documents to someone
without a login; the síndico authorises it; the CondoOS makes an upload link and a ready
text. **The system sends nothing**: the síndico shares the link through their own channel
and may mark it as shared (a statement, not a delivery receipt).

The link only uploads: it never lists or downloads anything. Files go through the same
triage and reading as any upload, into the request's condominium. Items are attended by a
person, or by themselves when the contract's invoice of that month arrives (C8, D70).
Every step is a ``delegation_event`` (append only, ids only).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import record_audit
from app.core.time import add_months, utcnow
from app.db.enums import (
    CLOSED_DELEGATION,
    DelegationEventKind,
    DelegationRecipientRole,
    DelegationStatus,
    DocumentOrigin,
)
from app.db.models import (
    AppUser,
    Condominium,
    DelegationEvent,
    DelegationLink,
    DelegationRequest,
    Document,
)
from app.db.session import set_tenant_scope
from app.ingestion.documents import IngestOutcome, ingest_file
from app.pending import month_pending
from app.policy import ALL_AUTOMATIONS, active_pause

LINK_DAYS = 7
MAX_LINK_DAYS = 30
MAX_FILES = 30
MAX_ITEMS = 20
PAUSE_TYPE = "delegation.link"
ROLE_LABEL = {
    "administradora": "administradora",
    "fornecedor": "fornecedor",
    "contador": "contador(a)",
    "zelador": "zelador(a)",
    "outro": "responsável",
}
GENERIC_ITEMS: list[dict[str, Any]] = [
    {"key": "contratos", "kind": "contrato", "label": "Contratos vigentes e seus aditivos"},
    {"key": "balancete", "kind": "balancete", "label": "Balancete do último mês"},
    {"key": "extrato", "kind": "extrato", "label": "Extrato bancário do último mês (OFX ou CSV)"},
    {"key": "apolice", "kind": "apolice", "label": "Apólice de seguro do condomínio"},
]


class DelegationError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def link_url(token: str) -> str:
    return f"{get_settings().web_base_url.rstrip('/')}/enviar/{token}"


async def _event(
    session: AsyncSession,
    req: DelegationRequest,
    kind: DelegationEventKind,
    user_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        DelegationEvent(
            id=uuid.uuid4(),
            condominium_id=req.condominium_id,
            request_id=req.id,
            kind=kind.value,
            user_id=user_id,
            payload=payload or {},
        )
    )


def _open(req: DelegationRequest) -> None:
    if DelegationStatus(req.status) in CLOSED_DELEGATION:
        raise DelegationError("Este pedido já foi encerrado.", 409)


# --------------------------------------------------------------------------- suggestions


async def suggest_items(
    session: AsyncSession, condo: Condominium, today: date
) -> list[dict[str, Any]]:
    """Invoices the contracts expected last month and that did not arrive (C8), then the
    usual documents. The person chooses; nothing is asked by itself."""
    month = add_months(today.replace(day=1), -1)
    pending = await month_pending(session, condo.id, month, today)
    out: list[dict[str, Any]] = []
    for c in pending.contracts:
        if c.status not in ("sem_nf", "sem_faturamento"):
            continue
        out.append(
            {
                "key": f"nf:{c.contract_id}:{month:%Y-%m}",
                "kind": "nota_fiscal",
                "label": f"Nota fiscal de {month:%m/%Y} — {c.supplier} ({c.object})",
                "contract_id": str(c.contract_id),
                "competence": f"{month:%Y-%m}",
            }
        )
    return out + [dict(i) for i in GENERIC_ITEMS]


# --------------------------------------------------------------------------- lifecycle


def _clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        raise DelegationError("Escolha ao menos um documento para pedir.")
    if len(items) > MAX_ITEMS:
        raise DelegationError(f"Peça no máximo {MAX_ITEMS} itens por pedido.")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i in items:
        label = str(i.get("label") or "").strip()[:200]
        if len(label) < 3:
            raise DelegationError("Descreva cada documento pedido.")
        key = str(i.get("key") or f"livre:{uuid.uuid4().hex[:8]}")[:120]
        if key in seen:
            continue
        seen.add(key)
        item: dict[str, Any] = {"key": key, "label": label, "kind": str(i.get("kind") or "outro")}
        if i.get("contract_id") and i.get("competence"):
            item["contract_id"], item["competence"] = str(i["contract_id"]), str(i["competence"])
        out.append(item)
    return out


async def create(
    session: AsyncSession,
    *,
    condominium_id: uuid.UUID,
    user_id: uuid.UUID,
    recipient_name: str,
    recipient_role: str,
    items: list[dict[str, Any]],
    scope: str,
    due_date: date,
    today: date,
    authorize_now: bool,
    case_id: uuid.UUID | None = None,
) -> DelegationRequest:
    name = recipient_name.strip()
    if len(name) < 3:
        raise DelegationError("Informe o nome de quem vai enviar.")
    if recipient_role not in {r.value for r in DelegationRecipientRole}:
        raise DelegationError("Papel do destinatário inválido.")
    if due_date < today:
        raise DelegationError("O prazo não pode estar no passado.")
    req = DelegationRequest(
        id=uuid.uuid4(),
        condominium_id=condominium_id,
        prepared_by_user_id=user_id,
        recipient_name=name[:200],
        recipient_role=recipient_role,
        scope=scope.strip()[:2000],
        items=_clean_items(items),
        due_date=due_date,
        status=DelegationStatus.RASCUNHO.value,
        case_id=case_id,
    )
    session.add(req)
    await session.flush()
    await _event(session, req, DelegationEventKind.CRIADO, user_id)
    if authorize_now:
        await authorize(session, req, user_id)
    return req


async def authorize(session: AsyncSession, req: DelegationRequest, user_id: uuid.UUID) -> None:
    if req.status != DelegationStatus.RASCUNHO.value:
        raise DelegationError("Só um rascunho pode ser autorizado.", 409)
    req.status = DelegationStatus.AUTORIZADO.value
    req.authorized_by_user_id, req.authorized_at = user_id, utcnow()
    await _event(session, req, DelegationEventKind.AUTORIZADO, user_id)


async def _revoke_links(session: AsyncSession, req: DelegationRequest, now: datetime) -> None:
    await session.execute(
        update(DelegationLink)
        .where(DelegationLink.request_id == req.id, DelegationLink.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def issue_link(
    session: AsyncSession, req: DelegationRequest, user_id: uuid.UUID, days: int = LINK_DAYS
) -> tuple[str, datetime]:
    """A new upload link (a previous one stops working). The token is returned only here."""
    _open(req)
    if req.status == DelegationStatus.RASCUNHO.value:
        raise DelegationError("O síndico precisa autorizar o pedido antes do link.", 409)
    if not 1 <= days <= MAX_LINK_DAYS:
        raise DelegationError(f"Validade de 1 a {MAX_LINK_DAYS} dias.")
    now = utcnow()
    await _revoke_links(session, req, now)
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(days=days)
    session.add(
        DelegationLink(
            id=uuid.uuid4(),
            condominium_id=req.condominium_id,
            request_id=req.id,
            token_hash=token_hash(token),
            expires_at=expires,
            max_files=MAX_FILES,
        )
    )
    if req.status == DelegationStatus.AUTORIZADO.value:
        req.status = DelegationStatus.AGUARDANDO_ENVIO.value
    await _event(session, req, DelegationEventKind.LINK_GERADO, user_id, {"days": days})
    await record_audit(
        session,
        action="delegation.link_issued",
        object_type="delegation_request",
        object_id=req.id,
        actor_user_id=user_id,
        condominium_id=req.condominium_id,
    )
    return token, expires


def message_text(
    req: DelegationRequest, condo: Condominium, sender: str, url: str, expires: datetime
) -> str:
    """The ready text the síndico sends through their own channel (pt-BR)."""
    lines = "\n".join(f"• {i['label']}" for i in req.items)
    return (
        f"Olá, {req.recipient_name}. Aqui é {sender}, do {condo.name}.\n"
        f"Preciso destes documentos até {req.due_date:%d/%m/%Y}:\n{lines}\n\n"
        f"Pode enviar os arquivos (PDF, foto ou XML) por este link, sem cadastro:\n{url}\n\n"
        f"O link serve só para envio e vale até {expires:%d/%m/%Y}. Obrigado!"
    )


async def mark_shared(session: AsyncSession, req: DelegationRequest, user_id: uuid.UUID) -> None:
    _open(req)
    req.shared_at = utcnow()
    await _event(session, req, DelegationEventKind.COMPARTILHADO, user_id)


async def attend_item(
    session: AsyncSession, req: DelegationRequest, key: str, user_id: uuid.UUID | None
) -> None:
    items = [dict(i) for i in req.items]
    item = next((i for i in items if i["key"] == key), None)
    if item is None:
        raise DelegationError("Item não encontrado.", 404)
    if item.get("attended_at"):
        return
    item["attended_at"] = utcnow().isoformat()
    item["attended_by"] = str(user_id) if user_id else "automatico"
    req.items = items
    await _event(
        session, req, DelegationEventKind.ITEM_ATENDIDO, user_id, {"key": key, "auto": not user_id}
    )


async def finish(
    session: AsyncSession, req: DelegationRequest, user_id: uuid.UUID, *, revoke: bool
) -> None:
    """Close the request ("encerrado") or revoke it; links stop working, nothing received is
    deleted."""
    _open(req)
    now = utcnow()
    await _revoke_links(session, req, now)
    req.status = (DelegationStatus.REVOGADO if revoke else DelegationStatus.ENCERRADO).value
    req.closed_at = now
    kind = DelegationEventKind.REVOGADO if revoke else DelegationEventKind.ENCERRADO
    await _event(session, req, kind, user_id)


async def refresh(session: AsyncSession, req: DelegationRequest, today: date) -> None:
    """Bring the request up to date on read: invoices that arrived attend their items,
    an expired link expires the request, everything attended concludes it."""
    if DelegationStatus(req.status) in CLOSED_DELEGATION:
        return
    by_month: dict[str, set[str]] = {}
    for item in req.items:
        if item.get("kind") == "nota_fiscal" and not item.get("attended_at"):
            month = str(item.get("competence"))
            if month not in by_month:
                pending = await month_pending(
                    session, req.condominium_id, date.fromisoformat(month + "-01"), today
                )
                by_month[month] = {
                    str(c.contract_id) for c in pending.contracts if c.status == "faturado"
                }
            if str(item.get("contract_id")) in by_month[month]:
                await attend_item(session, req, item["key"], None)
    now = utcnow()
    if req.status in (DelegationStatus.AGUARDANDO_ENVIO.value, DelegationStatus.RECEBENDO.value):
        if req.items and all(i.get("attended_at") for i in req.items):
            req.status, req.closed_at = DelegationStatus.CONCLUIDO.value, now
            await _revoke_links(session, req, now)
            await _event(session, req, DelegationEventKind.CONCLUIDO, None)
            return
        active = await session.scalar(
            select(DelegationLink.id).where(
                DelegationLink.request_id == req.id,
                DelegationLink.revoked_at.is_(None),
                DelegationLink.expires_at > now,
            )
        )
        if active is None:
            req.status, req.closed_at = DelegationStatus.EXPIRADO.value, now
            await _event(session, req, DelegationEventKind.EXPIRADO, None)


def progress(req: DelegationRequest) -> dict[str, int]:
    done = sum(1 for i in req.items if i.get("attended_at"))
    return {"attended": done, "total": len(req.items)}


# --------------------------------------------------------------------------- public link


@dataclass
class Open:
    link: DelegationLink
    request: DelegationRequest
    condo: Condominium


async def open_link(session: AsyncSession, token: str) -> Open | None:
    """The link's request, or None for anything not usable — unknown, revoked, expired,
    request closed or links paused. The caller answers the same 404 for all of them."""
    if not token or len(token) > 100:
        return None
    digest = token_hash(token)
    condo_id = await session.scalar(
        text("SELECT app_delegation_link_condominium(:h)"), {"h": digest}
    )
    if condo_id is None:
        return None
    await set_tenant_scope(session, [condo_id])  # from here on, RLS keeps us in this tenant
    link = await session.scalar(select(DelegationLink).where(DelegationLink.token_hash == digest))
    if link is None or link.revoked_at is not None or link.expires_at <= utcnow():
        return None
    req = await session.get(DelegationRequest, link.request_id)
    condo = await session.get(Condominium, link.condominium_id)
    if (
        req is None
        or condo is None
        or req.status
        not in (
            DelegationStatus.AGUARDANDO_ENVIO.value,
            DelegationStatus.RECEBENDO.value,
        )
    ):
        return None
    for kind in (PAUSE_TYPE, ALL_AUTOMATIONS):
        if await active_pause(session, condo.id, kind) is not None:
            return None
    return Open(link, req, condo)


def public_view(o: Open) -> dict[str, Any]:
    """Only what the sender needs: whose request, what, until when. Nothing else."""
    return {
        "condominium": o.condo.name,
        "recipient_name": o.request.recipient_name,
        "items": [
            {"label": i["label"], "attended": bool(i.get("attended_at"))} for i in o.request.items
        ],
        "due_date": o.request.due_date.isoformat(),
        "expires_at": o.link.expires_at.isoformat(),
        "remaining_files": max(0, o.link.max_files - o.link.files_count),
    }


async def receive(session: AsyncSession, o: Open, filename: str, data: bytes) -> IngestOutcome:
    if o.link.files_count >= o.link.max_files:
        return IngestOutcome(filename, None, error="Limite de arquivos deste link atingido.")
    outcome = await ingest_file(
        session,
        condominium_id=o.condo.id,
        filename=filename,
        data=data,
        origin=DocumentOrigin.PEDIDO,
        actor_user_id=None,
    )
    now = utcnow()
    o.link.last_used_at = now
    if outcome.error:
        await _event(
            session,
            o.request,
            DelegationEventKind.ARQUIVO_RECUSADO,
            None,
            {"reason": outcome.error[:300]},
        )
        return outcome
    assert outcome.document_id is not None
    doc = await session.get(Document, outcome.document_id)
    if doc is not None and doc.delegation_request_id is None:
        doc.delegation_request_id = o.request.id
    if not outcome.duplicate:
        o.link.files_count += 1
    if o.request.status == DelegationStatus.AGUARDANDO_ENVIO.value:
        o.request.status = DelegationStatus.RECEBENDO.value
    await _event(
        session,
        o.request,
        DelegationEventKind.ARQUIVO_RECEBIDO,
        None,
        {"document_id": str(outcome.document_id), "duplicate": outcome.duplicate},
    )
    return outcome


async def sender_name(session: AsyncSession, user_id: uuid.UUID) -> str:
    user = await session.get(AppUser, user_id)
    return user.name if user else "o síndico"
