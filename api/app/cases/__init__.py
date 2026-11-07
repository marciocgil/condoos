"""Cases (Assuntos): the central record to organise, follow and close a situation with
evidence (spec §8; D75, D80).

Rules kept here, not in the routes:
- every open case has an owner, a next action and a due date, unless formally suspended
  with a reason and a date (spec §8.4; also a CHECK in migration 0013);
- status changes follow ``TRANSITIONS`` (spec §8.2) and some need a reason;
- ``resolvido`` needs the resolution criterion: every task closed and, when the case
  requires evidence, at least one active evidence; "o fornecedor disse que fez" is
  ``aguardando_validacao``, never ``resolvido`` (WF-04);
- links are N:N and never deleted (``unlinked_at``); a record already linked to another
  open case needs a reason;
- possible duplicates are offered before a case is created;
- the timeline (``case_event``) is append-only and holds ids and short texts only.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import access_for
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import (
    CLOSED_CASE,
    CLOSED_TASK,
    VISIBLE_TO_BOARD,
    CaseLinkTarget,
    CaseStatus,
    TaskStatus,
)
from app.db.models import (
    AppUser,
    CaseEvent,
    CaseLink,
    CaseRecord,
    CaseTask,
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    Supplier,
)

S = CaseStatus

TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    S.NOVO: frozenset({S.EM_TRIAGEM}),
    S.EM_TRIAGEM: frozenset({S.EM_PLANEJAMENTO, S.CANCELADO, S.SUSPENSO}),
    S.EM_PLANEJAMENTO: frozenset({S.AGUARDANDO_APROVACAO, S.EM_EXECUCAO, S.CANCELADO, S.SUSPENSO}),
    S.AGUARDANDO_APROVACAO: frozenset({S.EM_EXECUCAO, S.EM_PLANEJAMENTO}),
    S.EM_EXECUCAO: frozenset({S.AGUARDANDO_TERCEIRO, S.AGUARDANDO_VALIDACAO, S.SUSPENSO}),
    S.AGUARDANDO_TERCEIRO: frozenset({S.EM_EXECUCAO, S.AGUARDANDO_VALIDACAO}),
    S.AGUARDANDO_VALIDACAO: frozenset({S.RESOLVIDO, S.EM_EXECUCAO}),
    S.RESOLVIDO: frozenset({S.REABERTO}),
    S.CANCELADO: frozenset({S.REABERTO}),
    S.REABERTO: frozenset({S.EM_TRIAGEM}),
    S.SUSPENSO: frozenset({S.EM_TRIAGEM, S.EM_PLANEJAMENTO, S.EM_EXECUCAO}),
}

# Moves that always need a written reason (cancel, suspend, reopen, resolve, a failed
# validation going back to execution).
REASON_REQUIRED: frozenset[CaseStatus] = frozenset(
    {S.CANCELADO, S.SUSPENSO, S.REABERTO, S.RESOLVIDO}
)

DUPLICATE_WINDOW_DAYS = 14
OWNER_PERMISSIONS = frozenset({Permission.MANAGE_CASES, Permission.UPDATE_TASK})


class CaseError(ValueError):
    """Message shown to the user (pt-BR); ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int = 422, data: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.data = data


@dataclass(frozen=True)
class LinkTarget:
    target_type: CaseLinkTarget
    target_id: uuid.UUID


def is_open(case: CaseRecord) -> bool:
    return CaseStatus(case.status) not in CLOSED_CASE


def can_manage(access: CondoAccess, case: CaseRecord) -> bool:
    """Manage any case, or the cases one owns (the management company works on its own)."""
    return access.can(Permission.MANAGE_CASES) or (
        access.can(Permission.UPDATE_TASK) and case.owner_user_id == access.user_id
    )


def can_update_task(access: CondoAccess, case: CaseRecord, task: CaseTask) -> bool:
    return can_manage(access, case) or (
        access.can(Permission.UPDATE_TASK) and task.assignee_user_id == access.user_id
    )


def allowed_transitions(access: CondoAccess, case: CaseRecord) -> list[CaseStatus]:
    if not can_manage(access, case):
        return []
    return sorted(TRANSITIONS[CaseStatus(case.status)], key=list(CaseStatus).index)


# --------------------------------------------------------------------------- helpers


async def add_event(
    session: AsyncSession,
    case: CaseRecord,
    *,
    kind: str,
    actor_user_id: uuid.UUID | None,
    from_value: str | None = None,
    to_value: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
    actor_kind: str = "user",
) -> None:
    session.add(
        CaseEvent(
            id=uuid.uuid4(),
            condominium_id=case.condominium_id,
            case_id=case.id,
            actor_user_id=actor_user_id,
            actor_kind=actor_kind if actor_user_id else "system",
            kind=kind,
            from_value=from_value,
            to_value=to_value,
            reason=reason,
            details=details or {},
        )
    )


def _text(value: str | None, label: str, *, minimum: int = 5) -> str:
    text = (value or "").strip()
    if len(text) < minimum:
        raise CaseError(f"Escreva {label} (mínimo de {minimum} caracteres).")
    return text


async def check_assignee(
    session: AsyncSession, condo: Condominium, user_id: uuid.UUID, label: str
) -> None:
    """Owners and assignees must be people who can act on cases in this condominium."""
    access = await access_for(session, user_id, condo)
    if not (access.permissions & OWNER_PERMISSIONS):
        raise CaseError(f"{label}: essa pessoa não tem acesso para tratar assuntos aqui.")


async def next_number(session: AsyncSession, condo: Condominium, today: date) -> str:
    # The condominium row is locked by the caller: numbers are sequential per condominium.
    prefix = f"A-{today.year}-"
    last = await session.scalar(
        select(func.max(CaseRecord.number)).where(
            CaseRecord.condominium_id == condo.id, CaseRecord.number.like(f"{prefix}%")
        )
    )
    seq = int(last.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


async def check_target(
    session: AsyncSession, access: CondoAccess, target: LinkTarget, case_id: uuid.UUID | None
) -> None:
    """The record exists in this condominium and the person may see it; 404 otherwise."""
    cid = access.condominium_id
    t, tid = target.target_type, target.target_id
    found: Any = None
    if t == CaseLinkTarget.OPPORTUNITY:  # visible only once the CondoOS review approved it
        from app.db.models import Opportunity

        o = await session.scalar(
            select(Opportunity).where(Opportunity.id == tid, Opportunity.condominium_id == cid)
        )
        found = (
            o
            if o is not None
            and (o.presented_at is not None or access.can(Permission.VIEW_OPPORTUNITY_DRAFT))
            else None
        )
    elif t == CaseLinkTarget.FINDING:
        f = await session.scalar(
            select(Finding).where(Finding.id == tid, Finding.condominium_id == cid)
        )
        visible = f is not None and (
            f.status in {s.value for s in VISIBLE_TO_BOARD}
            or access.can(Permission.VIEW_PENDING_FINDINGS)
        )
        found = f if visible else None
    elif t == CaseLinkTarget.DOCUMENT:
        found = await session.scalar(
            select(Document.id).where(Document.id == tid, Document.condominium_id == cid)
        )
    elif t == CaseLinkTarget.CONTRACT:
        found = await session.scalar(
            select(Contract.id).where(Contract.id == tid, Contract.condominium_id == cid)
        )
    elif t == CaseLinkTarget.EXPENSE:
        found = await session.scalar(
            select(Expense.id).where(Expense.id == tid, Expense.condominium_id == cid)
        )
    elif t == CaseLinkTarget.SUPPLIER:  # suppliers are shared: only those of this condominium
        found = await session.scalar(
            select(Supplier.id).where(
                Supplier.id == tid,
                or_(
                    Supplier.id.in_(
                        select(Contract.supplier_id).where(Contract.condominium_id == cid)
                    ),
                    Supplier.id.in_(
                        select(Expense.supplier_id).where(Expense.condominium_id == cid)
                    ),
                ),
            )
        )
    elif t == CaseLinkTarget.CASE:
        if tid == case_id:
            raise CaseError("Um assunto não pode ser vinculado a ele mesmo.")
        found = await session.scalar(
            select(CaseRecord.id).where(CaseRecord.id == tid, CaseRecord.condominium_id == cid)
        )
    if found is None:
        raise CaseError("Registro para vincular não encontrado.", 404)


async def open_cases_linked_to(
    session: AsyncSession, condominium_id: uuid.UUID, targets: list[LinkTarget]
) -> list[CaseRecord]:
    if not targets:
        return []
    conditions = [
        (CaseLink.target_type == t.target_type.value) & (CaseLink.target_id == t.target_id)
        for t in targets
    ]
    return list(
        await session.scalars(
            select(CaseRecord)
            .join(CaseLink, CaseLink.case_id == CaseRecord.id)
            .where(
                CaseRecord.condominium_id == condominium_id,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
                CaseLink.unlinked_at.is_(None),
                or_(*conditions),
            )
            .distinct()
        )
    )


async def duplicate_candidates(
    session: AsyncSession, condominium_id: uuid.UUID, category: str, targets: list[LinkTarget]
) -> list[CaseRecord]:
    """Open cases sharing a linked record, or of the same category opened recently."""
    by_link = await open_cases_linked_to(session, condominium_id, targets)
    since = utcnow() - timedelta(days=DUPLICATE_WINDOW_DAYS)
    recent = list(
        await session.scalars(
            select(CaseRecord).where(
                CaseRecord.condominium_id == condominium_id,
                CaseRecord.category == category,
                CaseRecord.created_at >= since,
                CaseRecord.status.not_in([s.value for s in CLOSED_CASE]),
            )
        )
    )
    seen: dict[uuid.UUID, CaseRecord] = {c.id: c for c in by_link}
    for c in recent:
        seen.setdefault(c.id, c)
    return list(seen.values())


async def add_link(
    session: AsyncSession,
    access: CondoAccess,
    case: CaseRecord,
    target: LinkTarget,
    *,
    reason: str | None,
    as_evidence: bool = False,
) -> CaseLink:
    await check_target(session, access, target, case.id)
    active = await session.scalar(
        select(CaseLink).where(
            CaseLink.case_id == case.id,
            CaseLink.target_type == target.target_type.value,
            CaseLink.target_id == target.target_id,
            CaseLink.unlinked_at.is_(None),
        )
    )
    if active is not None:
        if as_evidence and active.as_evidence:
            return active  # already evidence (e.g. attached, then cited by a task): fine
        if as_evidence and not active.as_evidence:
            active.as_evidence = True
            await add_event(
                session,
                case,
                kind="evidence_added",
                actor_user_id=access.user_id,
                reason=reason,
                details={
                    "target_type": target.target_type.value,
                    "target_id": str(target.target_id),
                },
            )
            return active
        raise CaseError("Esse registro já está vinculado a este assunto.", 409)
    others = [
        c
        for c in await open_cases_linked_to(session, case.condominium_id, [target])
        if c.id != case.id
    ]
    text = (reason or "").strip() or None
    if others and (text is None or len(text) < 5):
        numbers = ", ".join(sorted(c.number for c in others))
        raise CaseError(
            f"Esse registro já está no assunto {numbers}. Explique por que ele também "
            "pertence a este (mínimo de 5 caracteres).",
            data={"linked_cases": [str(c.id) for c in others]},
        )
    link = CaseLink(
        id=uuid.uuid4(),
        condominium_id=case.condominium_id,
        case_id=case.id,
        target_type=target.target_type.value,
        target_id=target.target_id,
        as_evidence=as_evidence,
        reason=text,
        linked_by_user_id=access.user_id,
    )
    session.add(link)
    await add_event(
        session,
        case,
        kind="evidence_added" if as_evidence else "linked",
        actor_user_id=access.user_id,
        reason=text,
        details={"target_type": target.target_type.value, "target_id": str(target.target_id)},
    )
    await session.flush()
    return link


async def unlink(
    session: AsyncSession, access: CondoAccess, case: CaseRecord, link: CaseLink, reason: str
) -> None:
    if link.unlinked_at is not None:
        raise CaseError("Esse vínculo já foi desfeito.", 409)
    text = _text(reason, "o motivo para desfazer o vínculo")
    link.unlinked_at = utcnow()
    link.unlinked_by_user_id = access.user_id
    await add_event(
        session,
        case,
        kind="unlinked",
        actor_user_id=access.user_id,
        reason=text,
        details={"target_type": link.target_type, "target_id": str(link.target_id)},
    )


# --------------------------------------------------------------------------- lifecycle


async def create_case(
    session: AsyncSession,
    access: CondoAccess,
    *,
    title: str,
    description: str,
    category: str,
    origin: str,
    severity: str,
    owner_user_id: uuid.UUID,
    next_action: str,
    next_action_due_at: datetime,
    resolution_criterion: str,
    requires_evidence: bool,
    links: list[tuple[LinkTarget, str | None]],
    create_anyway_reason: str | None,
    today: date,
) -> CaseRecord:
    condo = await session.scalar(
        select(Condominium).where(Condominium.id == access.condominium_id).with_for_update()
    )
    assert condo is not None
    await check_assignee(session, condo, owner_user_id, "Responsável")
    if next_action_due_at <= utcnow() - timedelta(minutes=1):
        raise CaseError("O prazo da próxima ação precisa ser futuro.")
    for target, _ in links:
        await check_target(session, access, target, None)
    candidates = await duplicate_candidates(session, condo.id, category, [t for t, _ in links])
    anyway = (create_anyway_reason or "").strip()
    if candidates and len(anyway) < 5:
        raise CaseError(
            "Pode já existir um assunto para isso. Vincule ao existente ou explique por que "
            "criar outro.",
            409,
            data={
                "candidates": [
                    {"id": str(c.id), "number": c.number, "title": c.title, "status": c.status}
                    for c in sorted(candidates, key=lambda c: c.number)
                ]
            },
        )
    case = CaseRecord(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        number=await next_number(session, condo, today),
        title=_text(title, "o título", minimum=3),
        description=(description or "").strip(),
        category=category,
        origin=origin,
        severity=severity,
        status=CaseStatus.NOVO.value,
        owner_user_id=owner_user_id,
        next_action=_text(next_action, "a próxima ação", minimum=3),
        next_action_due_at=next_action_due_at,
        resolution_criterion=_text(resolution_criterion, "o critério de conclusão"),
        requires_evidence=requires_evidence,
        created_by_user_id=access.user_id,
    )
    session.add(case)
    await session.flush()
    await add_event(
        session,
        case,
        kind="created",
        actor_user_id=access.user_id,
        to_value=CaseStatus.NOVO.value,
        reason=anyway or None,
        details={"origin": origin, "owner_user_id": str(owner_user_id)},
    )
    if owner_user_id != access.user_id:  # internal notification: shows in "Meus assuntos"
        await add_event(
            session,
            case,
            kind="owner_changed",
            actor_user_id=access.user_id,
            to_value=str(owner_user_id),
        )
    for target, reason in links:
        await add_link(session, access, case, target, reason=reason)
    await record_audit(
        session,
        action="case.created",
        object_type="case_record",
        object_id=case.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"origin": origin, "links": len(links), "duplicate_override": bool(candidates)},
    )
    return case


async def update_case(
    session: AsyncSession,
    access: CondoAccess,
    case: CaseRecord,
    changes: dict[str, Any],
    reason: str | None,
) -> list[str]:
    """Edit fields of an open case. Changing the due date or the owner needs a reason."""
    if not is_open(case):
        raise CaseError("Assunto encerrado: reabra para editar.", 409)
    changed: list[str] = []
    text = (reason or "").strip() or None
    condo = await session.get(Condominium, case.condominium_id)
    assert condo is not None
    if "owner_user_id" in changes and changes["owner_user_id"] != case.owner_user_id:
        if not access.can(Permission.MANAGE_CASES):
            raise CaseError("Só quem gerencia assuntos troca o responsável.", 403)
        await check_assignee(session, condo, changes["owner_user_id"], "Responsável")
    if "next_action_due_at" in changes and changes["next_action_due_at"] != case.next_action_due_at:
        if text is None or len(text) < 5:
            raise CaseError("Explique por que o prazo mudou (mínimo de 5 caracteres).")
        if changes["next_action_due_at"] <= utcnow():
            raise CaseError("O prazo da próxima ação precisa ser futuro.")
    for field_name, value in changes.items():
        old = getattr(case, field_name)
        if value == old:
            continue
        if field_name in ("title", "next_action"):
            value = _text(value, "o texto", minimum=3)
        setattr(case, field_name, value)
        changed.append(field_name)
        kind = {
            "owner_user_id": "owner_changed",
            "next_action_due_at": "due_changed",
            "next_action": "next_action_changed",
        }.get(field_name, "updated")
        await add_event(
            session,
            case,
            kind=kind,
            actor_user_id=access.user_id,
            from_value=None if old is None else str(old)[:300],
            to_value=None if value is None else str(value)[:300],
            reason=text if kind in ("owner_changed", "due_changed") else None,
            details={"field": field_name},
        )
    return changed


async def transition(
    session: AsyncSession,
    access: CondoAccess,
    case: CaseRecord,
    to: CaseStatus,
    *,
    reason: str | None,
    suspended_until: date | None = None,
    next_action: str | None = None,
    next_action_due_at: datetime | None = None,
    today: date,
) -> None:
    current = CaseStatus(case.status)
    if not can_manage(access, case):
        raise CaseError("Seu papel não permite mudar este assunto.", 403)
    if to not in TRANSITIONS[current]:
        raise CaseError("Essa mudança de estado não é permitida agora.", 409)
    text = (reason or "").strip() or None
    needs_reason = to in REASON_REQUIRED or (
        current == S.AGUARDANDO_VALIDACAO and to == S.EM_EXECUCAO
    )
    if needs_reason and (text is None or len(text) < 5):
        raise CaseError("Escreva o motivo desta mudança (mínimo de 5 caracteres).")
    if to == S.RESOLVIDO:
        await _check_resolution(session, case)
    if to == S.SUSPENSO:
        if suspended_until is None or suspended_until <= today:
            raise CaseError("Informe até quando o assunto fica suspenso (data futura).")
        case.suspended_until = suspended_until
        case.suspension_reason = text
    elif current == S.SUSPENSO:
        case.suspended_until = None
        case.suspension_reason = None
    if next_action is not None:
        case.next_action = _text(next_action, "a próxima ação", minimum=3)
    if next_action_due_at is not None:
        if next_action_due_at <= utcnow():
            raise CaseError("O prazo da próxima ação precisa ser futuro.")
        case.next_action_due_at = next_action_due_at
    if (
        to not in CLOSED_CASE
        and to != S.SUSPENSO
        and (case.owner_user_id is None or not case.next_action or case.next_action_due_at is None)
    ):
        raise CaseError("Defina responsável, próxima ação e prazo antes desta mudança.")
    case.status = to.value
    case.closed_at = utcnow() if to in CLOSED_CASE else None
    await add_event(
        session,
        case,
        kind="status_changed",
        actor_user_id=access.user_id,
        from_value=current.value,
        to_value=to.value,
        reason=text,
        details={"suspended_until": suspended_until.isoformat()} if suspended_until else {},
    )
    await record_audit(
        session,
        action="case.status_changed",
        object_type="case_record",
        object_id=case.id,
        actor_user_id=access.user_id,
        condominium_id=case.condominium_id,
        details={"from": current.value, "to": to.value},
    )


async def _check_resolution(session: AsyncSession, case: CaseRecord) -> None:
    open_tasks = await session.scalar(
        select(func.count()).where(
            CaseTask.case_id == case.id,
            CaseTask.status.not_in([s.value for s in CLOSED_TASK]),
        )
    )
    if open_tasks:
        raise CaseError(f"Ainda há {open_tasks} tarefa(s) em aberto neste assunto.", 409)
    if case.requires_evidence:
        evidence = await session.scalar(
            select(func.count()).where(
                CaseLink.case_id == case.id,
                CaseLink.as_evidence.is_(True),
                CaseLink.unlinked_at.is_(None),
            )
        )
        if not evidence:
            raise CaseError(
                "Este assunto só pode ser resolvido com evidência anexada "
                f"(critério: {case.resolution_criterion}).",
                409,
            )


# --------------------------------------------------------------------------- tasks


async def add_task(
    session: AsyncSession,
    access: CondoAccess,
    case: CaseRecord,
    *,
    title: str,
    assignee_user_id: uuid.UUID | None,
    assignee_label: str | None,
    due_at: datetime,
    requires_evidence: bool,
) -> CaseTask:
    if not can_manage(access, case):
        raise CaseError("Seu papel não permite criar tarefas neste assunto.", 403)
    if not is_open(case):
        raise CaseError("Assunto encerrado: reabra para criar tarefas.", 409)
    condo = await session.get(Condominium, case.condominium_id)
    assert condo is not None
    label = (assignee_label or "").strip() or None
    if assignee_user_id is not None:
        await check_assignee(session, condo, assignee_user_id, "Responsável pela tarefa")
    elif label is None:
        raise CaseError("Indique quem faz a tarefa (uma pessoa com acesso ou um nome).")
    if due_at <= utcnow():
        raise CaseError("O prazo da tarefa precisa ser futuro.")
    task = CaseTask(
        id=uuid.uuid4(),
        condominium_id=case.condominium_id,
        case_id=case.id,
        title=_text(title, "o título da tarefa", minimum=3),
        assignee_user_id=assignee_user_id,
        assignee_label=label,
        due_at=due_at,
        status=TaskStatus.ABERTA.value,
        requires_evidence=requires_evidence,
    )
    session.add(task)
    await session.flush()
    await add_event(
        session,
        case,
        kind="task_created",
        actor_user_id=access.user_id,
        to_value=task.title,
        details={
            "task_id": str(task.id),
            "assignee_user_id": str(assignee_user_id) if assignee_user_id else None,
        },
    )
    return task


TASK_MOVES: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.ABERTA: frozenset(
        {TaskStatus.EM_ANDAMENTO, TaskStatus.BLOQUEADA, TaskStatus.CONCLUIDA, TaskStatus.CANCELADA}
    ),
    TaskStatus.EM_ANDAMENTO: frozenset(
        {TaskStatus.BLOQUEADA, TaskStatus.CONCLUIDA, TaskStatus.CANCELADA}
    ),
    TaskStatus.BLOQUEADA: frozenset({TaskStatus.EM_ANDAMENTO, TaskStatus.CANCELADA}),
    TaskStatus.CONCLUIDA: frozenset({TaskStatus.EM_ANDAMENTO}),
    TaskStatus.CANCELADA: frozenset(),
}


async def update_task(
    session: AsyncSession,
    access: CondoAccess,
    case: CaseRecord,
    task: CaseTask,
    *,
    status: TaskStatus | None,
    due_at: datetime | None,
    reason: str | None,
    evidence_document_id: uuid.UUID | None,
) -> None:
    if not can_update_task(access, case, task):
        raise CaseError("Seu papel não permite atualizar esta tarefa.", 403)
    if not is_open(case):
        raise CaseError("Assunto encerrado: reabra para mexer nas tarefas.", 409)
    text = (reason or "").strip() or None
    if due_at is not None and due_at != task.due_at:
        if text is None or len(text) < 5:
            raise CaseError("Explique por que o prazo da tarefa mudou (mínimo de 5 caracteres).")
        if due_at <= utcnow():
            raise CaseError("O prazo da tarefa precisa ser futuro.")
        old = task.due_at
        task.due_at = due_at
        await add_event(
            session,
            case,
            kind="task_due_changed",
            actor_user_id=access.user_id,
            from_value=old.isoformat(),
            to_value=due_at.isoformat(),
            reason=text,
            details={"task_id": str(task.id)},
        )
    if status is None or status.value == task.status:
        return
    current = TaskStatus(task.status)
    if status not in TASK_MOVES[current]:
        raise CaseError("Essa mudança de estado da tarefa não é permitida agora.", 409)
    if status in (TaskStatus.BLOQUEADA, TaskStatus.CANCELADA) and (text is None or len(text) < 5):
        raise CaseError("Escreva o motivo (mínimo de 5 caracteres).")
    if status == TaskStatus.CONCLUIDA and task.requires_evidence:
        if evidence_document_id is None:
            raise CaseError("Esta tarefa exige evidência para ser concluída.")
        await add_link(
            session,
            access,
            case,
            LinkTarget(CaseLinkTarget.DOCUMENT, evidence_document_id),
            reason=f"Evidência da tarefa: {task.title}"[:500],
            as_evidence=True,
        )
    task.status = status.value
    task.blocked_reason = text if status == TaskStatus.BLOQUEADA else None
    if status == TaskStatus.CONCLUIDA:
        task.completed_at = utcnow()
        task.completed_by_user_id = access.user_id
    elif current == TaskStatus.CONCLUIDA:
        task.completed_at = None
        task.completed_by_user_id = None
    await add_event(
        session,
        case,
        kind="task_status_changed",
        actor_user_id=access.user_id,
        from_value=current.value,
        to_value=status.value,
        reason=text,
        details={"task_id": str(task.id)},
    )


async def user_names(session: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = await session.execute(select(AppUser.id, AppUser.name).where(AppUser.id.in_(ids)))
    return {i: n for i, n in rows}
