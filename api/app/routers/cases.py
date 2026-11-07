"""Cases (Assuntos) of a condominium (spec §8; D75, D80): list with the "no next action, no
control" flags, detail with links, tasks and the append-only timeline, and the changes
allowed by ``app.cases``. Everyone who sees the condominium reads its cases; changes need
``manage_cases`` or, for one's own case or task, ``update_task``."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, Field
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, access_for, require
from app.auth.rbac import CondoAccess, Permission
from app.cases import (
    CaseError,
    LinkTarget,
    add_event,
    add_link,
    add_task,
    allowed_transitions,
    can_manage,
    can_update_task,
    create_case,
    is_open,
    transition,
    unlink,
    update_case,
    update_task,
    user_names,
)
from app.config import get_settings
from app.core.time import DEFAULT_TIMEZONE, local_today, utcnow
from app.db.enums import (
    CLOSED_CASE,
    CLOSED_TASK,
    VISIBLE_TO_BOARD,
    CaseCategory,
    CaseLinkTarget,
    CaseOrigin,
    CaseSeverity,
    CaseStatus,
    DocumentOrigin,
    TaskStatus,
)
from app.db.models import (
    CaseEvent,
    CaseLink,
    CaseRecord,
    CaseTask,
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    Membership,
    Supplier,
)
from app.db.session import DbSession
from app.ingestion.documents import ingest_file

router = APIRouter(tags=["cases"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanUpload = Annotated[CondoAccess, Depends(require(Permission.UPLOAD_DOCUMENT))]


def _parse_due(value: Any) -> Any:
    """ "2026-11-12" is a day (end of that day, local time); anything longer is a datetime."""
    if isinstance(value, str) and len(value) == 10:
        return date.fromisoformat(value)
    return value


Due = Annotated[datetime | date, BeforeValidator(_parse_due)]


# --------------------------------------------------------------------------- schemas


class LinkIn(BaseModel):
    target_type: CaseLinkTarget
    target_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=500)


class CaseIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    category: CaseCategory
    origin: CaseOrigin = CaseOrigin.HUMAN_REQUEST
    severity: CaseSeverity = CaseSeverity.MEDIA
    owner_user_id: uuid.UUID | None = None  # default: whoever creates it
    next_action: str = Field(min_length=3, max_length=300)
    next_action_due_at: Due
    resolution_criterion: str = Field(min_length=5, max_length=500)
    requires_evidence: bool = True
    links: list[LinkIn] = Field(default=[], max_length=20)
    create_anyway_reason: str | None = Field(default=None, max_length=500)


class CaseUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: CaseCategory | None = None
    severity: CaseSeverity | None = None
    owner_user_id: uuid.UUID | None = None
    next_action: str | None = Field(default=None, min_length=3, max_length=300)
    next_action_due_at: Due | None = None
    resolution_criterion: str | None = Field(default=None, min_length=5, max_length=500)
    requires_evidence: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)


class TransitionIn(BaseModel):
    to: CaseStatus
    reason: str | None = Field(default=None, max_length=1000)
    suspended_until: date | None = None
    next_action: str | None = Field(default=None, min_length=3, max_length=300)
    next_action_due_at: Due | None = None


class UnlinkIn(BaseModel):
    reason: str = Field(max_length=500)


class CommentIn(BaseModel):
    body: str = Field(min_length=2, max_length=2000)


class EvidenceIn(BaseModel):
    document_id: uuid.UUID
    description: str | None = Field(default=None, max_length=500)


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    assignee_user_id: uuid.UUID | None = None
    assignee_label: str | None = Field(default=None, max_length=200)
    due_at: Due
    requires_evidence: bool = False


class TaskUpdateIn(BaseModel):
    status: TaskStatus | None = None
    due_at: Due | None = None
    reason: str | None = Field(default=None, max_length=1000)
    evidence_document_id: uuid.UUID | None = None


class Person(BaseModel):
    id: uuid.UUID
    name: str


class CaseRowOut(BaseModel):
    id: uuid.UUID
    condominium_id: uuid.UUID
    condominium_name: str
    number: str
    title: str
    category: str
    severity: str
    status: str
    origin: str
    owner: Person | None
    next_action: str | None
    next_action_due_at: datetime | None
    suspended_until: date | None
    open_tasks: int
    attention: list[str]  # sem_dono | sem_prazo | atrasado | suspensao_vencida
    created_at: datetime


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    assignee: Person | None
    assignee_label: str | None
    due_at: datetime
    status: str
    blocked_reason: str | None
    requires_evidence: bool
    overdue: bool
    completed_at: datetime | None
    can_update: bool
    allowed_moves: list[str]


class LinkOut(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    label: str
    detail: str | None = None
    as_evidence: bool
    reason: str | None
    linked_by: str
    linked_at: datetime
    unlinked_at: datetime | None
    active: bool


class EventOut(BaseModel):
    id: uuid.UUID
    at: datetime
    who: str
    kind: str
    from_value: str | None
    to_value: str | None
    reason: str | None
    details: dict[str, Any]


class CaseDetailOut(CaseRowOut):
    description: str
    resolution_criterion: str
    requires_evidence: bool
    suspension_reason: str | None
    created_by: str
    closed_at: datetime | None
    can_manage: bool
    can_comment: bool
    can_add_evidence: bool
    allowed_transitions: list[str]
    tasks: list[TaskOut]
    links: list[LinkOut]
    cited_by: list[dict[str, str]]
    events: list[EventOut]
    people: list[Person]  # who can own a case or a task here (only for managers)


# --------------------------------------------------------------------------- helpers


def _error(exc: CaseError) -> HTTPException:
    detail: Any = str(exc) if exc.data is None else {"message": str(exc), **exc.data}
    return HTTPException(exc.status, detail)


def _due(value: Due | None, tz: str) -> datetime | None:
    """A date means the end of that day in the condominium's time zone."""
    if value is None or isinstance(value, datetime):
        if isinstance(value, datetime) and value.tzinfo is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Informe a data e hora com fuso."
            )
        return value
    return datetime.combine(value, time(23, 59), tzinfo=ZoneInfo(tz or DEFAULT_TIMEZONE))


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


async def _case(db: DbSession, access: CondoAccess, case_id: uuid.UUID) -> CaseRecord:
    case = await db.scalar(
        select(CaseRecord)
        .where(CaseRecord.id == case_id, CaseRecord.condominium_id == access.condominium_id)
        .with_for_update()
    )
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assunto não encontrado.")
    return case


def _attention(case: CaseRecord, open_tasks: int, today: date) -> list[str]:
    if CaseStatus(case.status) in CLOSED_CASE:
        return []
    flags = []
    if case.status == CaseStatus.SUSPENSO.value:
        if case.suspended_until and case.suspended_until < today:
            flags.append("suspensao_vencida")
        return flags
    if case.owner_user_id is None:
        flags.append("sem_dono")
    if case.next_action_due_at is None:
        flags.append("sem_prazo")
    elif case.next_action_due_at < utcnow():
        flags.append("atrasado")
    return flags


async def _rows(
    db: DbSession,
    cases: list[CaseRecord],
    names: dict[uuid.UUID, str],
    condos: dict[uuid.UUID, Condominium],
) -> list[CaseRowOut]:
    ids = [c.id for c in cases]
    tasks: dict[uuid.UUID, int] = dict.fromkeys(ids, 0)
    if ids:
        for t in await db.scalars(
            select(CaseTask).where(
                CaseTask.case_id.in_(ids), CaseTask.status.not_in([s.value for s in CLOSED_TASK])
            )
        ):
            tasks[t.case_id] += 1
    out = []
    for c in cases:
        condo = condos[c.condominium_id]
        out.append(
            CaseRowOut(
                id=c.id,
                condominium_id=c.condominium_id,
                condominium_name=condo.name,
                number=c.number,
                title=c.title,
                category=c.category,
                severity=c.severity,
                status=c.status,
                origin=c.origin,
                owner=(
                    Person(id=c.owner_user_id, name=names.get(c.owner_user_id, "—"))
                    if c.owner_user_id
                    else None
                ),
                next_action=c.next_action,
                next_action_due_at=c.next_action_due_at,
                suspended_until=c.suspended_until,
                open_tasks=tasks[c.id],
                attention=_attention(c, tasks[c.id], local_today(condo.timezone)),
                created_at=c.created_at,
            )
        )
    return out


async def _list(
    db: DbSession,
    condos: list[Condominium],
    user_id: uuid.UUID,
    situation: str,
    owner: str | None,
    category: CaseCategory | None,
    severity: CaseSeverity | None,
) -> list[CaseRowOut]:
    if not condos:
        return []
    stmt = select(CaseRecord).where(CaseRecord.condominium_id.in_([c.id for c in condos]))
    closed = [s.value for s in CLOSED_CASE]
    if situation == "abertos":
        stmt = stmt.where(CaseRecord.status.not_in(closed))
    elif situation == "encerrados":
        stmt = stmt.where(CaseRecord.status.in_(closed))
    if owner == "me":  # mine: I own it or I have an open task in it
        mine = select(CaseTask.case_id).where(
            CaseTask.assignee_user_id == user_id,
            CaseTask.status.not_in([s.value for s in CLOSED_TASK]),
        )
        stmt = stmt.where((CaseRecord.owner_user_id == user_id) | CaseRecord.id.in_(mine))
    elif owner:
        try:
            stmt = stmt.where(CaseRecord.owner_user_id == uuid.UUID(owner))
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Responsável inválido."
            ) from exc
    if category:
        stmt = stmt.where(CaseRecord.category == category.value)
    if severity:
        stmt = stmt.where(CaseRecord.severity == severity.value)
    cases = list(await db.scalars(stmt.order_by(CaseRecord.next_action_due_at.asc().nulls_first())))
    names = await user_names(db, {c.owner_user_id for c in cases if c.owner_user_id})
    rows = await _rows(db, cases, names, {c.id: c for c in condos})
    # Attention first (no owner, overdue...), then by due date, as the queue is read top-down.
    return sorted(
        rows,
        key=lambda r: (
            not r.attention,
            r.next_action_due_at or datetime.max.replace(tzinfo=utcnow().tzinfo),
        ),
    )


async def _link_labels(
    db: DbSession, access: CondoAccess, links: list[CaseLink]
) -> dict[uuid.UUID, tuple[str, str | None] | None]:
    """Label per link; None hides it (a finding the viewer may not see yet)."""
    by_type: dict[str, list[uuid.UUID]] = {}
    for link in links:
        by_type.setdefault(link.target_type, []).append(link.target_id)
    labels: dict[tuple[str, uuid.UUID], tuple[str, str | None] | None] = {}
    cid = access.condominium_id
    sees_pending = access.can(Permission.VIEW_PENDING_FINDINGS)
    visible = {s.value for s in VISIBLE_TO_BOARD}
    if ids := by_type.get("finding"):
        for f in await db.scalars(
            select(Finding).where(Finding.id.in_(ids), Finding.condominium_id == cid)
        ):
            labels[("finding", f.id)] = (
                (f.title, f"{f.rule_code} · {f.status}")
                if f.status in visible or sees_pending
                else None
            )
    if ids := by_type.get("document"):
        for d in await db.scalars(
            select(Document).where(Document.id.in_(ids), Document.condominium_id == cid)
        ):
            labels[("document", d.id)] = (d.original_filename, d.doc_type)
    if ids := by_type.get("contract"):
        for k in await db.scalars(
            select(Contract).where(Contract.id.in_(ids), Contract.condominium_id == cid)
        ):
            labels[("contract", k.id)] = (k.object, None)
    if ids := by_type.get("expense"):
        for e in await db.scalars(
            select(Expense).where(Expense.id.in_(ids), Expense.condominium_id == cid)
        ):
            labels[("expense", e.id)] = (
                e.description,
                f"R$ {Decimal(e.amount):.2f}".replace(".", ","),
            )
    if ids := by_type.get("supplier"):
        for s in await db.scalars(select(Supplier).where(Supplier.id.in_(ids))):
            labels[("supplier", s.id)] = (s.legal_name, None)
    if ids := by_type.get("opportunity"):
        from app.db.models import Opportunity

        drafts = access.can(Permission.VIEW_OPPORTUNITY_DRAFT)
        for o in await db.scalars(
            select(Opportunity).where(Opportunity.id.in_(ids), Opportunity.condominium_id == cid)
        ):
            labels[("opportunity", o.id)] = (
                (f"{o.number} — {o.title}", o.status) if drafts or o.presented_at else None
            )
    if ids := by_type.get("case"):
        for c in await db.scalars(
            select(CaseRecord).where(CaseRecord.id.in_(ids), CaseRecord.condominium_id == cid)
        ):
            labels[("case", c.id)] = (f"{c.number} — {c.title}", c.status)
    return {link.id: labels.get((link.target_type, link.target_id)) for link in links}


async def _people(db: DbSession, condo: Condominium) -> list[Person]:
    """Who can own a case or a task here (anyone with manage_cases or update_task)."""
    candidates = set(
        await db.scalars(
            select(Membership.user_id).where(
                (Membership.condominium_id == condo.id)
                | (Membership.management_company_id == condo.management_company_id),
                Membership.revoked_at.is_(None),
            )
        )
    )
    from app.db.models import CondoAssignment

    candidates |= set(
        await db.scalars(
            select(CondoAssignment.user_id).where(
                CondoAssignment.condominium_id == condo.id, CondoAssignment.revoked_at.is_(None)
            )
        )
    )
    out = []
    for uid in candidates:
        acc = await access_for(db, uid, condo)
        if acc.can(Permission.MANAGE_CASES) or acc.can(Permission.UPDATE_TASK):
            out.append(uid)
    names = await user_names(db, set(out))
    return sorted((Person(id=u, name=names[u]) for u in out if u in names), key=lambda p: p.name)


async def _detail(db: DbSession, access: CondoAccess, case: CaseRecord) -> CaseDetailOut:
    condo = await _condo(db, access)
    tasks = list(
        await db.scalars(
            select(CaseTask).where(CaseTask.case_id == case.id).order_by(CaseTask.due_at)
        )
    )
    links = list(
        await db.scalars(
            select(CaseLink).where(CaseLink.case_id == case.id).order_by(CaseLink.created_at)
        )
    )
    events = list(
        await db.scalars(
            select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at)
        )
    )
    cited = list(
        await db.scalars(
            select(CaseRecord)
            .join(CaseLink, CaseLink.case_id == CaseRecord.id)
            .where(
                CaseLink.target_type == "case",
                CaseLink.target_id == case.id,
                CaseLink.unlinked_at.is_(None),
                CaseRecord.condominium_id == condo.id,
            )
        )
    )
    ids = {case.owner_user_id, case.created_by_user_id}
    ids |= {t.assignee_user_id for t in tasks} | {e.actor_user_id for e in events}
    ids |= {link.linked_by_user_id for link in links}
    names = await user_names(db, {i for i in ids if i})
    [row] = await _rows(db, [case], names, {condo.id: condo})
    labels = await _link_labels(db, access, links)
    manage = can_manage(access, case)
    has_task = any(
        t.assignee_user_id == access.user_id and t.status not in {s.value for s in CLOSED_TASK}
        for t in tasks
    )
    now = utcnow()
    from app.cases import TASK_MOVES

    return CaseDetailOut(
        **row.model_dump(),
        description=case.description,
        resolution_criterion=case.resolution_criterion,
        requires_evidence=case.requires_evidence,
        suspension_reason=case.suspension_reason,
        created_by=(
            names.get(case.created_by_user_id, "Sistema") if case.created_by_user_id else "Sistema"
        ),
        closed_at=case.closed_at,
        can_manage=manage,
        can_comment=manage or has_task or access.can(Permission.COMMENT_FINDING),
        can_add_evidence=is_open(case)
        and (manage or has_task)
        and access.can(Permission.UPLOAD_DOCUMENT),
        allowed_transitions=[s.value for s in allowed_transitions(access, case)],
        tasks=[
            TaskOut(
                id=t.id,
                title=t.title,
                assignee=(
                    Person(id=t.assignee_user_id, name=names.get(t.assignee_user_id, "—"))
                    if t.assignee_user_id
                    else None
                ),
                assignee_label=t.assignee_label,
                due_at=t.due_at,
                status=t.status,
                blocked_reason=t.blocked_reason,
                requires_evidence=t.requires_evidence,
                overdue=t.status not in {s.value for s in CLOSED_TASK} and t.due_at < now,
                completed_at=t.completed_at,
                can_update=is_open(case) and can_update_task(access, case, t),
                allowed_moves=(
                    [m.value for m in TASK_MOVES[TaskStatus(t.status)]]
                    if is_open(case) and can_update_task(access, case, t)
                    else []
                ),
            )
            for t in tasks
        ],
        links=[
            LinkOut(
                id=link.id,
                target_type=link.target_type,
                target_id=link.target_id,
                label=labels[link.id][0],  # type: ignore[index]
                detail=labels[link.id][1],  # type: ignore[index]
                as_evidence=link.as_evidence,
                reason=link.reason,
                linked_by=(
                    names.get(link.linked_by_user_id, "Sistema")
                    if link.linked_by_user_id
                    else "Sistema"
                ),
                linked_at=link.created_at,
                unlinked_at=link.unlinked_at,
                active=link.unlinked_at is None,
            )
            for link in links
            if labels.get(link.id) is not None
        ],
        cited_by=[{"id": str(c.id), "number": c.number, "title": c.title} for c in cited],
        events=[
            EventOut(
                id=e.id,
                at=e.created_at,
                who=names.get(e.actor_user_id, "Sistema") if e.actor_user_id else "Sistema",
                kind=e.kind,
                from_value=e.from_value,
                to_value=e.to_value,
                reason=e.reason,
                details=e.details,
            )
            for e in events
        ],
        people=await _people(db, condo) if manage else [],
    )


# --------------------------------------------------------------------------- routes


@router.get("/condominiums/{condominium_id}/cases")
async def list_cases(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    situacao: Literal["abertos", "encerrados", "todos"] = "abertos",
    responsavel: str | None = None,
    categoria: CaseCategory | None = None,
    criticidade: CaseSeverity | None = None,
) -> list[CaseRowOut]:
    condo = await _condo(db, access)
    return await _list(db, [condo], access.user_id, situacao, responsavel, categoria, criticidade)


@router.get("/portfolio/cases")
async def portfolio_cases(
    db: DbSession,
    principal: CurrentPrincipal,
    situacao: Literal["abertos", "encerrados", "todos"] = "abertos",
    responsavel: str | None = None,
    categoria: CaseCategory | None = None,
    criticidade: CaseSeverity | None = None,
    condominium_id: uuid.UUID | None = None,
) -> list[CaseRowOut]:
    condos = []
    for c in await db.scalars(
        select(Condominium).where(Condominium.id.in_(principal.condominium_ids))
    ):
        if condominium_id is not None and c.id != condominium_id:
            continue
        if (await access_for(db, principal.user.id, c)).can(Permission.VIEW):
            condos.append(c)
    return await _list(db, condos, principal.user.id, situacao, responsavel, categoria, criticidade)


@router.post("/condominiums/{condominium_id}/cases", status_code=status.HTTP_201_CREATED)
async def create_case_route(
    condominium_id: uuid.UUID, body: CaseIn, access: CanView, db: DbSession
) -> Any:
    if not access.can(Permission.MANAGE_CASES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite abrir assuntos.")
    for origin, target, label in (
        (CaseOrigin.FINDING, CaseLinkTarget.FINDING, "achado"),
        (CaseOrigin.OPPORTUNITY, CaseLinkTarget.OPPORTUNITY, "oportunidade"),
    ):
        if body.origin == origin and not any(link.target_type == target for link in body.links):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Assunto aberto a partir de {label} precisa do vínculo com ele.",
            )
    condo = await _condo(db, access)
    try:
        case = await create_case(
            db,
            access,
            title=body.title,
            description=body.description,
            category=body.category.value,
            origin=body.origin.value,
            severity=body.severity.value,
            owner_user_id=body.owner_user_id or access.user_id,
            next_action=body.next_action,
            next_action_due_at=_due(body.next_action_due_at, condo.timezone),  # type: ignore[arg-type]
            resolution_criterion=body.resolution_criterion,
            requires_evidence=body.requires_evidence,
            links=[
                (LinkTarget(link.target_type, link.target_id), link.reason) for link in body.links
            ],
            create_anyway_reason=body.create_anyway_reason,
            today=local_today(condo.timezone),
        )
    except CaseError as exc:
        if exc.status == status.HTTP_409_CONFLICT and exc.data:
            # Duplicate candidates: nothing written; the client chooses what to do.
            return JSONResponse(status_code=409, content={"detail": str(exc), **exc.data})
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


@router.get("/condominiums/{condominium_id}/cases/{case_id}")
async def get_case(
    condominium_id: uuid.UUID, case_id: uuid.UUID, access: CanView, db: DbSession
) -> CaseDetailOut:
    case = await db.scalar(
        select(CaseRecord).where(
            CaseRecord.id == case_id, CaseRecord.condominium_id == access.condominium_id
        )
    )
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assunto não encontrado.")
    return await _detail(db, access, case)


@router.patch("/condominiums/{condominium_id}/cases/{case_id}")
async def update_case_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    body: CaseUpdateIn,
    access: CanView,
    db: DbSession,
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    if not can_manage(access, case):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite editar este assunto.")
    condo = await _condo(db, access)
    changes = body.model_dump(exclude_unset=True, exclude={"reason"})
    for key in ("category", "severity"):
        if changes.get(key) is not None:
            changes[key] = changes[key].value
    if "next_action_due_at" in changes:
        changes["next_action_due_at"] = _due(changes["next_action_due_at"], condo.timezone)
    changes = {k: v for k, v in changes.items() if v is not None}
    try:
        await update_case(db, access, case, changes, body.reason)
    except CaseError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


@router.post("/condominiums/{condominium_id}/cases/{case_id}/transitions")
async def transition_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    body: TransitionIn,
    access: CanView,
    db: DbSession,
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    condo = await _condo(db, access)
    try:
        await transition(
            db,
            access,
            case,
            body.to,
            reason=body.reason,
            suspended_until=body.suspended_until,
            next_action=body.next_action,
            next_action_due_at=_due(body.next_action_due_at, condo.timezone),
            today=local_today(condo.timezone),
        )
    except CaseError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


@router.post(
    "/condominiums/{condominium_id}/cases/{case_id}/links", status_code=status.HTTP_201_CREATED
)
async def link_route(
    condominium_id: uuid.UUID, case_id: uuid.UUID, body: LinkIn, access: CanView, db: DbSession
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    if not can_manage(access, case):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite vincular registros.")
    try:
        await add_link(
            db, access, case, LinkTarget(body.target_type, body.target_id), reason=body.reason
        )
    except CaseError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, case)


@router.post("/condominiums/{condominium_id}/cases/{case_id}/links/{link_id}/unlink")
async def unlink_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    link_id: uuid.UUID,
    body: UnlinkIn,
    access: CanView,
    db: DbSession,
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    if not can_manage(access, case):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite desfazer vínculos.")
    link = await db.scalar(
        select(CaseLink).where(CaseLink.id == link_id, CaseLink.case_id == case.id)
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vínculo não encontrado.")
    try:
        await unlink(db, access, case, link, body.reason)
    except CaseError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


async def _may_add_evidence(db: DbSession, access: CondoAccess, case: CaseRecord) -> None:
    has_task = await db.scalar(
        select(CaseTask.id).where(
            CaseTask.case_id == case.id,
            CaseTask.assignee_user_id == access.user_id,
            CaseTask.status.not_in([s.value for s in CLOSED_TASK]),
        )
    )
    if not (can_manage(access, case) or has_task):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Seu papel não permite anexar evidência aqui."
        )
    if not is_open(case):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Assunto encerrado: reabra para anexar evidência."
        )


@router.post(
    "/condominiums/{condominium_id}/cases/{case_id}/evidence", status_code=status.HTTP_201_CREATED
)
async def evidence_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    body: EvidenceIn,
    access: CanUpload,
    db: DbSession,
) -> CaseDetailOut:
    """An existing document of the condominium (a note, a report) as evidence."""
    case = await _case(db, access, case_id)
    await _may_add_evidence(db, access, case)
    try:
        await add_link(
            db,
            access,
            case,
            LinkTarget(CaseLinkTarget.DOCUMENT, body.document_id),
            reason=body.description,
            as_evidence=True,
        )
    except CaseError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, case)


@router.post(
    "/condominiums/{condominium_id}/cases/{case_id}/evidence/upload",
    status_code=status.HTTP_201_CREATED,
)
async def evidence_upload_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    access: CanUpload,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=500)] = None,
) -> CaseDetailOut:
    """A photo or report sent now: stored as a document, not sent to extraction."""
    case = await _case(db, access, case_id)
    await _may_add_evidence(db, access, case)
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    outcome = await ingest_file(
        db,
        condominium_id=access.condominium_id,
        filename=file.filename or "evidencia",
        data=data,
        origin=DocumentOrigin.UPLOAD,
        actor_user_id=access.user_id,
        process=False,
    )
    if outcome.document_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, outcome.error or "Arquivo inválido."
        )
    try:
        await add_link(
            db,
            access,
            case,
            LinkTarget(CaseLinkTarget.DOCUMENT, outcome.document_id),
            reason=description,
            as_evidence=True,
        )
    except CaseError as exc:
        raise _error(exc) from exc
    return await _detail(db, access, case)


@router.post(
    "/condominiums/{condominium_id}/cases/{case_id}/comments", status_code=status.HTTP_201_CREATED
)
async def comment_route(
    condominium_id: uuid.UUID, case_id: uuid.UUID, body: CommentIn, access: CanView, db: DbSession
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    detail = await _detail(db, access, case)
    if not detail.can_comment:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite comentar.")
    await add_event(
        db, case, kind="comment", actor_user_id=access.user_id, reason=body.body.strip()
    )
    await db.flush()
    return await _detail(db, access, case)


@router.post(
    "/condominiums/{condominium_id}/cases/{case_id}/tasks", status_code=status.HTTP_201_CREATED
)
async def add_task_route(
    condominium_id: uuid.UUID, case_id: uuid.UUID, body: TaskIn, access: CanView, db: DbSession
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    condo = await _condo(db, access)
    try:
        await add_task(
            db,
            access,
            case,
            title=body.title,
            assignee_user_id=body.assignee_user_id,
            assignee_label=body.assignee_label,
            due_at=_due(body.due_at, condo.timezone),  # type: ignore[arg-type]
            requires_evidence=body.requires_evidence,
        )
    except CaseError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


@router.patch("/condominiums/{condominium_id}/cases/{case_id}/tasks/{task_id}")
async def update_task_route(
    condominium_id: uuid.UUID,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskUpdateIn,
    access: CanView,
    db: DbSession,
) -> CaseDetailOut:
    case = await _case(db, access, case_id)
    task = await db.scalar(
        select(CaseTask)
        .where(CaseTask.id == task_id, CaseTask.case_id == case.id)
        .with_for_update()
    )
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarefa não encontrada.")
    condo = await _condo(db, access)
    try:
        await update_task(
            db,
            access,
            case,
            task,
            status=body.status,
            due_at=_due(body.due_at, condo.timezone),
            reason=body.reason,
            evidence_document_id=body.evidence_document_id,
        )
    except CaseError as exc:
        raise _error(exc) from exc
    await db.flush()
    return await _detail(db, access, case)


@router.get("/condominiums/{condominium_id}/findings/{finding_id}/cases")
async def cases_of_finding(
    condominium_id: uuid.UUID, finding_id: uuid.UUID, access: CanView, db: DbSession
) -> list[dict[str, str]]:
    """Cases (open or closed) currently linked to a finding, for the finding detail."""
    rows = await db.scalars(
        select(CaseRecord)
        .join(CaseLink, CaseLink.case_id == CaseRecord.id)
        .where(
            CaseRecord.condominium_id == access.condominium_id,
            CaseLink.target_type == "finding",
            CaseLink.target_id == finding_id,
            CaseLink.unlinked_at.is_(None),
        )
        .order_by(CaseRecord.number)
    )
    return [
        {"id": str(c.id), "number": c.number, "title": c.title, "status": c.status} for c in rows
    ]
