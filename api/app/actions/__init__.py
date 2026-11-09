"""Action requests with approval and frozen scope (VS-05, D83; spec §7.5, §9.5).

A person asks for an action (charge a supplier, ask for a quote, schedule a visit), the
policy engine (``app.policy``) decides what it needs, the síndico approves exactly what was
shown (by its hash), and an outbox event hands it to the dispatcher. The dispatcher checks
everything again at the moment of the action. No connector exists in the pilot, so the
dispatcher never sends anything: the action waits for a person to carry it out and record
it. Every step is an ``action_decision`` row (append only).
"""

import hashlib
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.cases import CaseError, add_event
from app.core.audit import record_audit
from app.core.jobs import enqueue
from app.core.time import utcnow
from app.db.enums import (
    OPEN_ACTION,
    ActionDecisionKind,
    ActionStatus,
    OutboxStatus,
    PolicyDecision,
    Role,
)
from app.db.models import (
    ActionDecision,
    ActionRequest,
    CaseRecord,
    Condominium,
    Membership,
    Opportunity,
    OutboxEvent,
    Supplier,
)
from app.policy import APPROVAL_VALID_DAYS, CATALOGUE, ActionPayload, evaluate

DISPATCH_JOB = "action.dispatch"

ActionError = CaseError  # same shape: pt-BR message and HTTP status


def payload_hash(action_type: str, title: str, payload: dict[str, Any], cost_cap: Decimal) -> str:
    """Hash of everything the approver sees. Any change gives a different hash."""
    canonical = json.dumps(
        {
            "action_type": action_type,
            "title": title,
            "payload": payload,
            "cost_cap": f"{cost_cap:.2f}",
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def current_hash(req: ActionRequest) -> str:
    return payload_hash(req.action_type, req.title, dict(req.payload), Decimal(req.cost_cap))


def is_open(req: ActionRequest) -> bool:
    return ActionStatus(req.status) in OPEN_ACTION


def can_request(access: CondoAccess) -> bool:
    return access.can(Permission.MANAGE_CASES)


def allowed_actions(access: CondoAccess, req: ActionRequest) -> list[str]:
    status = ActionStatus(req.status)
    out: list[str] = []
    if status == ActionStatus.AGUARDANDO_APROVACAO:
        if access.can(Permission.APPROVE_IN_CONDO):
            out += ["aprovar", "pedir_ajustes", "recusar"]
        if can_request(access):
            out.append("ajustar")
    if status == ActionStatus.AGUARDANDO_EXECUCAO_MANUAL and can_request(access):
        out.append("registrar_execucao")
    if status in OPEN_ACTION and (
        can_request(access) or req.requested_by_user_id == access.user_id
    ):
        out.append("cancelar")
    return out


async def _decide(
    session: AsyncSession,
    req: ActionRequest,
    *,
    kind: ActionDecisionKind,
    user_id: uuid.UUID | None,
    to_status: ActionStatus,
    comment: str | None = None,
) -> ActionDecision:
    decision = ActionDecision(
        id=uuid.uuid4(),
        condominium_id=req.condominium_id,
        action_request_id=req.id,
        user_id=user_id,
        kind=kind.value,
        comment=comment,
        payload_hash=req.payload_hash,
        from_status=req.status,
        to_status=to_status.value,
        policy_version=req.policy_version,
    )
    session.add(decision)
    req.status = to_status.value
    if req.case_id is not None:
        case = await session.get(CaseRecord, req.case_id)
        if case is not None:
            await add_event(
                session,
                case,
                kind="acao",
                actor_user_id=user_id,
                to_value=to_status.value,
                reason=comment,
                details={"action_request_id": str(req.id), "decision": kind.value},
            )
    await record_audit(
        session,
        action=f"action.{kind.value}",
        object_type="action_request",
        object_id=req.id,
        actor_user_id=user_id,
        condominium_id=req.condominium_id,
        details={"to_status": to_status.value, "payload_hash": req.payload_hash},
    )
    return decision


def _comment(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if len(text) < 5:
        raise ActionError(f"Escreva {label} (mínimo de 5 caracteres).")
    return text


async def _check_payload(
    session: AsyncSession, condo: Condominium, payload: ActionPayload
) -> dict[str, Any]:
    if payload.supplier_id is not None:
        supplier = await session.get(Supplier, payload.supplier_id)
        if supplier is None:
            raise ActionError("Fornecedor não encontrado.", 404)
    if payload.due_date is not None:
        try:
            date.fromisoformat(payload.due_date)
        except ValueError as exc:
            raise ActionError("Prazo inválido: use a data no formato AAAA-MM-DD.") from exc
    return payload.model_dump(mode="json")


def _supplier_of(payload: dict[str, Any] | None) -> uuid.UUID | None:
    raw = (payload or {}).get("supplier_id")
    return uuid.UUID(str(raw)) if raw else None


async def _policy_or_raise(
    session: AsyncSession,
    condo: Condominium,
    action_type: str,
    cost_cap: Decimal,
    supplier_id: uuid.UUID | None = None,
) -> Any:
    result = await evaluate(
        session, condo, action_type=action_type, cost_cap=cost_cap, supplier_id=supplier_id
    )
    if result.decision == PolicyDecision.PAUSE:
        raise ActionError(result.reason, 409)
    if result.decision != PolicyDecision.REQUIRE_APPROVAL:
        raise ActionError(result.reason, 422)
    return result


async def create_request(
    session: AsyncSession,
    access: CondoAccess,
    condo: Condominium,
    *,
    action_type: str,
    title: str,
    payload: ActionPayload,
    cost_cap: Decimal,
    idempotency_key: str,
    case_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None,
    internal: bool = False,
) -> tuple[ActionRequest, bool]:
    """Returns the request and whether it was created now (False = the same key again).
    ``internal`` is set only by the screens that own an internal type (the request e-mail)."""
    if not can_request(access):
        raise ActionError("Seu papel não pode pedir ações neste condomínio.", 403)
    spec = CATALOGUE.get(action_type)
    if spec is not None and spec.internal and not internal:
        raise ActionError("Este tipo de ação é pedido pela própria tela do pedido.", 422)
    if payload.email is not None and (spec is None or not spec.sends_email):
        raise ActionError("Só o pedido de documentos por e-mail leva um e-mail.", 422)
    key = idempotency_key.strip()
    if not 8 <= len(key) <= 120:
        raise ActionError("Chave de idempotência inválida.")
    existing = await session.scalar(
        select(ActionRequest).where(
            ActionRequest.condominium_id == condo.id, ActionRequest.idempotency_key == key
        )
    )
    if existing is not None:
        return existing, False
    title = _comment(title, "o título da ação")[:200]
    cost_cap = Decimal(cost_cap).quantize(Decimal("0.01"))
    if case_id is not None:
        case = await session.get(CaseRecord, case_id)
        if case is None or case.condominium_id != condo.id:
            raise ActionError("Assunto não encontrado.", 404)
    if opportunity_id is not None:
        opp = await session.get(Opportunity, opportunity_id)
        if opp is None or opp.condominium_id != condo.id or opp.presented_at is None:
            raise ActionError("Oportunidade não encontrada.", 404)
    frozen = await _check_payload(session, condo, payload)
    policy = await evaluate(
        session,
        condo,
        action_type=action_type,
        cost_cap=cost_cap,
        supplier_id=payload.supplier_id,
    )
    if policy.decision != PolicyDecision.REQUIRE_APPROVAL:
        # Denials are recorded (who asked for what) but no request is created.
        await record_audit(
            session,
            action="action.denied_by_policy",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=access.user_id,
            condominium_id=condo.id,
            details={
                "action_type": action_type[:60],
                "decision": policy.decision.value,
                "policy_version": policy.version,
            },
        )
        status = 409 if policy.decision == PolicyDecision.PAUSE else 422
        # ``data`` tells the route to answer without rolling back the audit row.
        raise ActionError(
            policy.reason,
            status,
            {"policy_decision": policy.decision.value, "policy_version": policy.version},
        )
    req = ActionRequest(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        case_id=case_id,
        opportunity_id=opportunity_id,
        action_type=action_type,
        title=title,
        payload=frozen,
        payload_hash=payload_hash(action_type, title, frozen, cost_cap),
        cost_cap=cost_cap,
        policy_decision=policy.decision.value,
        policy_version=policy.version,
        policy_reason=policy.reason,
        status=ActionStatus.AGUARDANDO_APROVACAO.value,
        idempotency_key=key,
        requested_by_user_id=access.user_id,
    )
    session.add(req)
    await session.flush()
    req.status = ""  # the first decision records the transition from nothing
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.SOLICITAR,
        user_id=access.user_id,
        to_status=ActionStatus.AGUARDANDO_APROVACAO,
    )
    return req, True


def _void_approval(req: ActionRequest) -> None:
    req.approved_hash = None
    req.approved_by_user_id = None
    req.approval_expires_at = None


async def _cancel_outbox(session: AsyncSession, req: ActionRequest) -> None:
    for event in await session.scalars(
        select(OutboxEvent).where(
            OutboxEvent.action_request_id == req.id,
            OutboxEvent.status == OutboxStatus.PENDENTE.value,
        )
    ):
        event.status = OutboxStatus.CANCELADO.value


async def adjust(
    session: AsyncSession,
    access: CondoAccess,
    condo: Condominium,
    req: ActionRequest,
    *,
    title: str,
    payload: ActionPayload,
    cost_cap: Decimal,
    comment: str | None,
) -> ActionRequest:
    """Change what is being asked. A material change after approval voids it (spec §9.5)."""
    if not can_request(access):
        raise ActionError("Seu papel não pode ajustar ações.", 403)
    spec = CATALOGUE.get(req.action_type)
    if (spec is not None and spec.internal) or payload.email is not None:
        raise ActionError("Para mudar o e-mail, cancele e prepare um novo pelo pedido.", 409)
    if ActionStatus(req.status) not in (
        ActionStatus.AGUARDANDO_APROVACAO,
        ActionStatus.ENFILEIRADA,
        ActionStatus.AGUARDANDO_EXECUCAO_MANUAL,
    ):
        raise ActionError("Esta ação não pode mais ser ajustada.", 409)
    title = _comment(title, "o título da ação")[:200]
    cost_cap = Decimal(cost_cap).quantize(Decimal("0.01"))
    frozen = await _check_payload(session, condo, payload)
    new_hash = payload_hash(req.action_type, title, frozen, cost_cap)
    if new_hash == req.payload_hash:
        raise ActionError("Nada mudou no pedido.")
    policy = await _policy_or_raise(session, condo, req.action_type, cost_cap, payload.supplier_id)
    was_approved = req.approved_hash is not None
    req.title, req.payload, req.cost_cap, req.payload_hash = title, frozen, cost_cap, new_hash
    req.policy_decision, req.policy_version = policy.decision.value, policy.version
    req.policy_reason = policy.reason
    if was_approved:
        _void_approval(req)
        await _cancel_outbox(session, req)
    note = (comment or "").strip() or None
    if was_approved:
        note = "Pedido alterado depois da aprovação: a aprovação anterior foi anulada." + (
            f" {note}" if note else ""
        )
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.AJUSTAR,
        user_id=access.user_id,
        to_status=ActionStatus.AGUARDANDO_APROVACAO,
        comment=note,
    )
    return req


async def approve(
    session: AsyncSession,
    access: CondoAccess,
    condo: Condominium,
    req: ActionRequest,
    *,
    seen_hash: str,
    comment: str | None,
) -> ActionRequest:
    """Approve exactly the version the approver saw; the policy is checked again now."""
    if not access.can(Permission.APPROVE_IN_CONDO):
        raise ActionError("Só quem aprova pelo condomínio pode aprovar ações.", 403)
    if req.status != ActionStatus.AGUARDANDO_APROVACAO.value:
        raise ActionError("Esta ação não está aguardando aprovação.", 409)
    if seen_hash != req.payload_hash or current_hash(req) != req.payload_hash:
        raise ActionError(
            "O pedido mudou depois que você abriu a tela. Confira a versão atual antes de aprovar.",
            409,
        )
    policy = await _policy_or_raise(
        session, condo, req.action_type, Decimal(req.cost_cap), _supplier_of(req.payload)
    )
    req.policy_version, req.policy_reason = policy.version, policy.reason
    req.approved_hash = req.payload_hash
    req.approved_by_user_id = access.user_id
    req.approval_expires_at = utcnow() + timedelta(days=APPROVAL_VALID_DAYS)
    decision = await _decide(
        session,
        req,
        kind=ActionDecisionKind.APROVAR,
        user_id=access.user_id,
        to_status=ActionStatus.ENFILEIRADA,
        comment=(comment or "").strip() or None,
    )
    if CATALOGUE[req.action_type].sends_email:
        from app.delegation.email import on_approved

        await on_approved(session, req, access.user_id)
    # One outbox row per approval: reprocessing the same approval never duplicates it.
    key = f"{req.id}:{decision.id}"
    await session.execute(
        insert(OutboxEvent)
        .values(
            id=uuid.uuid4(),
            condominium_id=req.condominium_id,
            action_request_id=req.id,
            idempotency_key=key,
            status=OutboxStatus.PENDENTE.value,
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
    )
    await enqueue(
        session,
        DISPATCH_JOB,
        {"idempotency_key": key, "condominium_id": str(req.condominium_id)},
        condominium_id=req.condominium_id,
        dedupe_key=f"{DISPATCH_JOB}:{key}",
        priority=True,
    )
    return req


async def request_changes(
    session: AsyncSession, access: CondoAccess, req: ActionRequest, *, comment: str | None
) -> ActionRequest:
    if not access.can(Permission.APPROVE_IN_CONDO):
        raise ActionError("Só quem aprova pelo condomínio pode pedir ajustes.", 403)
    if req.status != ActionStatus.AGUARDANDO_APROVACAO.value:
        raise ActionError("Esta ação não está aguardando aprovação.", 409)
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.AJUSTAR,
        user_id=access.user_id,
        to_status=ActionStatus.AGUARDANDO_APROVACAO,
        comment=_comment(comment, "o ajuste pedido"),
    )
    return req


async def reject(
    session: AsyncSession, access: CondoAccess, req: ActionRequest, *, comment: str | None
) -> ActionRequest:
    """WF-06: a rejected action never reaches the dispatcher."""
    if not access.can(Permission.APPROVE_IN_CONDO):
        raise ActionError("Só quem aprova pelo condomínio pode recusar ações.", 403)
    if req.status != ActionStatus.AGUARDANDO_APROVACAO.value:
        raise ActionError("Esta ação não está aguardando aprovação.", 409)
    await _cancel_outbox(session, req)
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.RECUSAR,
        user_id=access.user_id,
        to_status=ActionStatus.RECUSADA,
        comment=_comment(comment, "o motivo da recusa"),
    )
    return req


async def cancel(
    session: AsyncSession, access: CondoAccess, req: ActionRequest, *, comment: str | None
) -> ActionRequest:
    if "cancelar" not in allowed_actions(access, req):
        raise ActionError("Esta ação não pode ser cancelada por você.", 409)
    _void_approval(req)
    await _cancel_outbox(session, req)
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.CANCELAR,
        user_id=access.user_id,
        to_status=ActionStatus.CANCELADA,
        comment=_comment(comment, "o motivo do cancelamento"),
    )
    return req


async def record_execution(
    session: AsyncSession,
    access: CondoAccess,
    req: ActionRequest,
    *,
    note: str | None,
    final_cost: Decimal,
) -> tuple[ActionRequest, str | None]:
    """A person did it outside the system. The approval is checked again now: expired or a
    cost above the approved cap voids it and sends the request back for approval (SEC-04,
    SEC-05). Returns the request and, when blocked, the reason."""
    if not can_request(access):
        raise ActionError("Seu papel não pode registrar a execução.", 403)
    if req.status != ActionStatus.AGUARDANDO_EXECUCAO_MANUAL.value:
        raise ActionError("Esta ação não está aguardando execução.", 409)
    text = _comment(note, "o que foi feito")
    final_cost = Decimal(final_cost).quantize(Decimal("0.01"))
    if final_cost < 0:
        raise ActionError("Custo inválido.")
    blocked = await _recheck(session, req, final_cost=final_cost, user_id=access.user_id)
    if blocked is not None:
        return req, blocked
    req.executed_at = utcnow()
    req.executed_by_user_id = access.user_id
    req.execution_note = text
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.EXECUTAR,
        user_id=access.user_id,
        to_status=ActionStatus.EXECUTADA,
        comment=f"{text} (custo informado: R$ {final_cost:.2f})",
    )
    return req, None


APPROVER_GONE = (
    "Quem aprovou não é mais síndico deste condomínio: a aprovação foi anulada e o pedido "
    "voltou para aprovação de quem responde agora."
)


async def approver_active(session: AsyncSession, req: ActionRequest) -> bool:
    """Whether the person who approved still holds an active síndico access in this
    condominium (LB-061, D109). Approving is the síndico's alone (``APPROVE_IN_CONDO``)."""
    if req.approved_by_user_id is None:
        return False
    now = utcnow()
    found = await session.scalar(
        select(Membership.id)
        .where(
            Membership.condominium_id == req.condominium_id,
            Membership.user_id == req.approved_by_user_id,
            Membership.role == Role.SINDICO.value,
            Membership.revoked_at.is_(None),
            or_(Membership.expires_at.is_(None), Membership.expires_at > now),
        )
        .limit(1)
    )
    return found is not None


async def revalidate_approvals(
    session: AsyncSession, condo_id: uuid.UUID, *, user_id: uuid.UUID | None
) -> int:
    """Troca de síndico (F06, LB-061, D109): every open approval given by someone who is no
    longer síndico goes back to approval. Nothing approved by a person who left is carried
    out. Returns how many requests went back."""
    reverted = 0
    for req in await session.scalars(
        select(ActionRequest)
        .where(
            ActionRequest.condominium_id == condo_id,
            ActionRequest.approved_by_user_id.is_not(None),
            ActionRequest.status.in_(
                [ActionStatus.ENFILEIRADA.value, ActionStatus.AGUARDANDO_EXECUCAO_MANUAL.value]
            ),
        )
        .with_for_update()
    ):
        if await approver_active(session, req):
            continue
        _void_approval(req)
        await _cancel_outbox(session, req)
        await _decide(
            session,
            req,
            kind=ActionDecisionKind.INVALIDAR,
            user_id=user_id,
            to_status=ActionStatus.AGUARDANDO_APROVACAO,
            comment=APPROVER_GONE,
        )
        reverted += 1
    return reverted


async def _recheck(
    session: AsyncSession,
    req: ActionRequest,
    *,
    final_cost: Decimal | None,
    user_id: uuid.UUID | None,
) -> str | None:
    """Back to approval when the approval no longer covers what is about to happen."""
    reason: str | None = None
    kind = ActionDecisionKind.INVALIDAR
    if not await approver_active(session, req):
        reason = APPROVER_GONE
    elif req.approval_expires_at is None or req.approval_expires_at <= utcnow():
        reason = "A aprovação venceu antes da execução: o pedido voltou para aprovação."
        kind = ActionDecisionKind.EXPIRAR
    elif final_cost is not None and final_cost > Decimal(req.cost_cap):
        reason = (
            f"O custo informado (R$ {final_cost:.2f}) supera o teto aprovado "
            f"(R$ {Decimal(req.cost_cap):.2f}): o pedido voltou para nova aprovação."
        )
        req.cost_cap = final_cost
        req.payload_hash = current_hash(req)
    if reason is None:
        return None
    _void_approval(req)
    await _cancel_outbox(session, req)
    await _decide(
        session,
        req,
        kind=kind,
        user_id=user_id,
        to_status=ActionStatus.AGUARDANDO_APROVACAO,
        comment=reason,
    )
    return reason


async def dispatch_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Worker handler for the outbox (runs with the worker role). Idempotent: an event that
    is no longer pending is a no-op. Checks status, hash, validity and policy again; with no
    connector configured, it hands the action to a person and sends nothing."""
    event = await session.scalar(
        select(OutboxEvent)
        .where(OutboxEvent.idempotency_key == str(payload["idempotency_key"]))
        .with_for_update()
    )
    if event is None or event.status != OutboxStatus.PENDENTE.value:
        return
    event.attempts += 1
    req = await session.get(ActionRequest, event.action_request_id, with_for_update=True)
    assert req is not None
    condo = await session.get(Condominium, req.condominium_id)
    assert condo is not None
    problem: str | None = None
    if req.status != ActionStatus.ENFILEIRADA.value:
        problem = "O pedido não está mais aprovado."
    elif req.approved_hash != req.payload_hash or current_hash(req) != req.approved_hash:
        problem = "O conteúdo do pedido não corresponde ao que foi aprovado."
    if problem is not None:
        event.status = OutboxStatus.BLOQUEADO.value
        event.last_error = problem
        if req.status == ActionStatus.ENFILEIRADA.value:
            await _decide(
                session,
                req,
                kind=ActionDecisionKind.BLOQUEAR,
                user_id=None,
                to_status=ActionStatus.BLOQUEADA,
                comment=problem,
            )
        return
    blocked = await _recheck(session, req, final_cost=None, user_id=None)
    if blocked is not None:
        event.status = OutboxStatus.BLOQUEADO.value
        event.last_error = blocked
        return
    policy = await evaluate(
        session,
        condo,
        action_type=req.action_type,
        cost_cap=Decimal(req.cost_cap),
        supplier_id=_supplier_of(req.payload),
    )
    if policy.decision == PolicyDecision.PAUSE:
        # Paused after this job was claimed: keep the event pending; the job retries later.
        raise RuntimeError("automation paused")
    if policy.decision != PolicyDecision.REQUIRE_APPROVAL:
        # The limits changed after the approval: back to the approver.
        event.status = OutboxStatus.BLOQUEADO.value
        event.last_error = policy.reason
        _void_approval(req)
        await _decide(
            session,
            req,
            kind=ActionDecisionKind.INVALIDAR,
            user_id=None,
            to_status=ActionStatus.AGUARDANDO_APROVACAO,
            comment=policy.reason,
        )
        return
    if CATALOGUE[req.action_type].sends_email:
        # The one connector (D103): the request e-mail. Everything else sends nothing.
        from app.delegation.email import send

        await send(session, req, event)
        return
    event.status = OutboxStatus.DESPACHADO.value
    event.dispatched_at = utcnow()
    await _decide(
        session,
        req,
        kind=ActionDecisionKind.DESPACHAR,
        user_id=None,
        to_status=ActionStatus.AGUARDANDO_EXECUCAO_MANUAL,
        comment=(
            "Sem integração externa no piloto: nada foi enviado. "
            "Uma pessoa executa e registra a execução."
        ),
    )


def type_label(action_type: str) -> str:
    spec = CATALOGUE.get(action_type)
    return spec.label if spec else action_type
