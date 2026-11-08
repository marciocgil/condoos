"""The CondoOS sends the document request by e-mail (LB-053, D103).

The only thing the system sends out. It rides on the action requests of D83: the e-mail is
frozen in the action payload (recipient, sender name, reply-to, subject, body), the síndico
approves that exact version, and the dispatcher checks everything again before sending.

- The body carries ``{link}``: the link is made at the moment of sending, so its token is
  never stored. Making it revokes the request's previous link (one active link per request).
- "Sent" means "accepted by the mail server" — never delivered or read.
- After sending, the recipient's address is masked in the payload; its SHA-256 stays.
- Limits: 1 recipient, no attachment, fixed text plus a short note; 1 e-mail per request per
  24 h and 3 in all; 20 per condominium per day. Pausable on its own.
"""

import hashlib
import re
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import active_membership
from app.auth.mailer import OutgoingEmail, get_mailer
from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import (
    OPEN_ACTION,
    ActionDecisionKind,
    ActionStatus,
    DelegationEventKind,
    DelegationStatus,
    OutboxStatus,
    Role,
)
from app.db.models import (
    ActionRequest,
    AppUser,
    Condominium,
    DelegationEvent,
    DelegationRequest,
    Membership,
    OutboxEvent,
)
from app.delegation import DelegationError, _event, _open, issue_link, link_url, sender_name
from app.policy import ActionPayload, EmailDraft

ACTION_TYPE = "pedido_documento.enviar_email"
PER_REQUEST_DAY = 1
PER_REQUEST_TOTAL = 3
PER_CONDO_DAY = 20
MAX_SEND_ATTEMPTS = 3
EMAIL_RE = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[a-z]{2,}$", re.IGNORECASE)


def sending_enabled() -> bool:
    """Only with a real mail server (Mailpit locally) or the test mailer."""
    return get_settings().mailer in ("smtp", "memory")


def mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def _sha(address: str) -> str:
    return hashlib.sha256(address.encode()).hexdigest()


def body_text(req: DelegationRequest, condo: Condominium, sender: str, note: str) -> str:
    lines = "\n".join(f"• {i['label']}" for i in req.items)
    note_block = f"Recado do síndico: {note}\n\n" if note else ""
    return (
        f"Olá, {req.recipient_name}.\n\n"
        f"{sender}, do {condo.name}, pede estes documentos até {req.due_date:%d/%m/%Y}:\n"
        f"{lines}\n\n"
        f"{note_block}"
        "Envie os arquivos (PDF, foto ou XML) por este link, sem cadastro:\n{link}\n\n"
        "O link serve só para envio e vale por 7 dias. Para falar com o síndico, responda "
        "este e-mail.\n\n"
        f"Enviado pelo CondoOS em nome do {condo.name}, com aprovação do síndico."
    )


async def _sindico_email(
    session: AsyncSession, access: CondoAccess, condo: Condominium
) -> str | None:
    """Reply-To: the approver's own address when the síndico prepares it; otherwise the
    condominium's síndico (D103, question 2)."""
    if access.can(Permission.APPROVE_IN_CONDO):
        user = await session.get(AppUser, access.user_id)
        return user.email if user else None
    return await session.scalar(
        select(AppUser.email)
        .join(Membership, Membership.user_id == AppUser.id)
        .where(
            Membership.condominium_id == condo.id,
            Membership.role == Role.SINDICO.value,
            *active_membership(),
        )
        .order_by(Membership.created_at)
        .limit(1)
    )


async def _count_sent(
    session: AsyncSession, condo_id: uuid.UUID, request_id: uuid.UUID | None, hours: int | None
) -> int:
    stmt = (
        select(func.count())
        .select_from(DelegationEvent)
        .where(
            DelegationEvent.condominium_id == condo_id,
            DelegationEvent.kind == DelegationEventKind.EMAIL_ENVIADO.value,
        )
    )
    if request_id is not None:
        stmt = stmt.where(DelegationEvent.request_id == request_id)
    if hours is not None:
        stmt = stmt.where(DelegationEvent.created_at >= utcnow() - timedelta(hours=hours))
    return int(await session.scalar(stmt) or 0)


async def check_limits(session: AsyncSession, req: DelegationRequest) -> str | None:
    if await _count_sent(session, req.condominium_id, req.id, 24) >= PER_REQUEST_DAY:
        return "Este pedido já foi enviado por e-mail nas últimas 24 horas."
    if await _count_sent(session, req.condominium_id, req.id, None) >= PER_REQUEST_TOTAL:
        return f"Este pedido já foi enviado por e-mail {PER_REQUEST_TOTAL} vezes (o limite)."
    if await _count_sent(session, req.condominium_id, None, 24) >= PER_CONDO_DAY:
        return f"Limite de {PER_CONDO_DAY} e-mails de pedido por dia neste condomínio."
    return None


def _of_request(request_id: uuid.UUID) -> Any:
    return ActionRequest.payload["email"]["delegation_request_id"].as_string() == str(request_id)


async def email_actions(session: AsyncSession, req: DelegationRequest) -> list[ActionRequest]:
    return list(
        await session.scalars(
            select(ActionRequest)
            .where(
                ActionRequest.condominium_id == req.condominium_id,
                ActionRequest.action_type == ACTION_TYPE,
                _of_request(req.id),
            )
            .order_by(ActionRequest.created_at.desc())
        )
    )


async def prepare(
    session: AsyncSession,
    access: CondoAccess,
    condo: Condominium,
    req: DelegationRequest,
    *,
    to: str,
    note: str,
    idempotency_key: str,
) -> ActionRequest:
    """Freeze the exact e-mail as an action waiting for the síndico's approval."""
    from app.actions import ActionError, create_request

    if not sending_enabled():
        raise DelegationError("O envio por e-mail não está configurado neste ambiente.", 409)
    _open(req)
    if req.status == DelegationStatus.RASCUNHO.value:
        raise DelegationError("O síndico precisa autorizar o pedido antes do envio.", 409)
    address = to.strip().lower()
    if not EMAIL_RE.match(address) or len(address) > 254:
        raise DelegationError("Informe um e-mail válido (um só destinatário).")
    note = " ".join(note.split())
    if len(note) > 500:
        raise DelegationError("O recado tem no máximo 500 caracteres.")
    if any(ActionStatus(a.status) in OPEN_ACTION for a in await email_actions(session, req)):
        raise DelegationError("Já há um envio por e-mail deste pedido em andamento.", 409)
    problem = await check_limits(session, req)
    if problem:
        raise DelegationError(problem, 409)
    sender = await sender_name(session, req.authorized_by_user_id or access.user_id)
    draft = EmailDraft(
        delegation_request_id=req.id,
        to=address,
        to_sha256=_sha(address),
        from_name=f"CondoOS em nome do {condo.name}"[:200],
        reply_to=await _sindico_email(session, access, condo),
        subject=f"Pedido de documentos do {condo.name}"[:200],
        body=body_text(req, condo, sender, note),
        note=note,
    )
    payload = ActionPayload(
        effect=f"Enviar por e-mail a {req.recipient_name} o pedido de documentos, com um link "
        "novo só para envio (o link anterior deixa de valer).",
        reason="Receber os documentos sem que o síndico precise encaminhar o link.",
        executor="CondoOS, depois da aprovação do síndico",
        email=draft,
    )
    try:
        action, _ = await create_request(
            session,
            access,
            condo,
            action_type=ACTION_TYPE,
            title=f"Pedido de documentos por e-mail · {req.recipient_name}"[:200],
            payload=payload,
            cost_cap=0,  # type: ignore[arg-type]
            idempotency_key=idempotency_key,
            internal=True,
        )
    except ActionError as exc:
        raise DelegationError(str(exc), exc.status) from exc
    return action


async def on_approved(session: AsyncSession, action: ActionRequest, user_id: uuid.UUID) -> None:
    req = await _request_of(session, action)
    if req is not None:
        await _event(
            session,
            req,
            DelegationEventKind.EMAIL_APROVADO,
            user_id,
            {"action_request_id": str(action.id)},
        )


async def _request_of(session: AsyncSession, action: ActionRequest) -> DelegationRequest | None:
    raw = (action.payload.get("email") or {}).get("delegation_request_id")
    if not raw:
        return None
    req = await session.get(DelegationRequest, uuid.UUID(str(raw)))
    return req if req is not None and req.condominium_id == action.condominium_id else None


def _masked(payload: dict[str, Any]) -> dict[str, Any]:
    email = dict(payload["email"])
    email["to"] = mask(str(email["to"]))
    return {**payload, "email": email}


async def send(session: AsyncSession, action: ActionRequest, event: OutboxEvent) -> None:
    """Dispatcher step for the request e-mail, after the generic re-checks (status, hash,
    validity, policy). Never raises for a mail failure: it records the attempt and retries
    later, up to MAX_SEND_ATTEMPTS, then blocks and tells the síndico."""
    from app.actions import DISPATCH_JOB, _decide
    from app.core.jobs import enqueue

    req = await _request_of(session, action)
    problem: str | None = None
    if req is None:
        problem = "O pedido de documentos não foi encontrado."
    elif req.status == DelegationStatus.RASCUNHO.value:
        problem = "O pedido voltou a rascunho."
    else:
        try:
            _open(req)
        except DelegationError:
            problem = "O pedido foi encerrado antes do envio."
        else:
            problem = await check_limits(session, req)
    if problem is not None:
        event.status = OutboxStatus.BLOQUEADO.value
        event.last_error = problem
        if req is not None:
            await _event(session, req, DelegationEventKind.EMAIL_FALHOU, None, {"motivo": problem})
        await _decide(
            session,
            action,
            kind=ActionDecisionKind.BLOQUEAR,
            user_id=None,
            to_status=ActionStatus.BLOQUEADA,
            comment=f"{problem} Nada foi enviado.",
        )
        return
    assert req is not None
    draft = action.payload["email"]
    try:
        async with session.begin_nested():
            token, _expires = await issue_link(session, req, None)
            message_id = await get_mailer().send(
                OutgoingEmail(
                    to=str(draft["to"]),
                    subject=str(draft["subject"]),
                    body=str(draft["body"]).replace("{link}", link_url(token)),
                    reply_to=draft.get("reply_to"),
                    from_name=str(draft["from_name"]),
                )
            )
    except Exception as exc:  # the server refused or could not be reached
        event.last_error = f"Servidor de e-mail: {type(exc).__name__}"
        if event.attempts < MAX_SEND_ATTEMPTS:
            await enqueue(
                session,
                DISPATCH_JOB,
                {
                    "idempotency_key": event.idempotency_key,
                    "condominium_id": str(req.condominium_id),
                },
                condominium_id=req.condominium_id,
                dedupe_key=f"{DISPATCH_JOB}:{event.idempotency_key}:retry{event.attempts}",
                run_after=utcnow() + timedelta(minutes=2**event.attempts),
            )
            return
        reason = (
            f"O servidor de e-mail recusou o envio {MAX_SEND_ATTEMPTS} vezes. Confira o "
            "endereço ou mande o link pelo seu canal."
        )
        event.status = OutboxStatus.BLOQUEADO.value
        await _event(session, req, DelegationEventKind.EMAIL_FALHOU, None, {"motivo": reason})
        await _decide(
            session,
            action,
            kind=ActionDecisionKind.BLOQUEAR,
            user_id=None,
            to_status=ActionStatus.BLOQUEADA,
            comment=reason,
        )
        return
    now = utcnow()
    event.status = OutboxStatus.DESPACHADO.value
    event.dispatched_at = now
    event.receipt = {"message_id": message_id, "accepted_at": now.isoformat()}
    req.shared_at = now
    await _event(
        session,
        req,
        DelegationEventKind.EMAIL_ENVIADO,
        None,
        {"action_request_id": str(action.id), "to_domain": str(draft["to"]).partition("@")[2]},
    )
    action.payload = _masked(dict(action.payload))
    action.executed_at = now
    action.execution_note = (
        "E-mail aceito pelo servidor de e-mail. Isso não confirma a entrega nem a leitura."
    )
    await _decide(
        session,
        action,
        kind=ActionDecisionKind.EXECUTAR,
        user_id=None,
        to_status=ActionStatus.EXECUTADA,
        comment=action.execution_note,
    )
    await record_audit(
        session,
        action="delegation.email_sent",
        object_type="delegation_request",
        object_id=req.id,
        condominium_id=req.condominium_id,
        details={"action_request_id": str(action.id)},
    )
