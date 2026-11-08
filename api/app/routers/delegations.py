"""Delegated document requests (D95). Authenticated routes for the condominium, and the
public upload route reached only by a link token.

Permissions: prepare = ``MANAGE_CASES`` (síndico, CondoOS admin and reviewer); authorise,
issue the link and mark as shared = ``APPROVE_IN_CONDO`` (síndico only); attend an item =
``MANAGE_CASES``; revoke or close = ``MANAGE_DELEGATION`` (síndico and CondoOS admin).
"""

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.deps import CurrentPrincipal, require
from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.core.ratelimit import WindowLimiter, client_ip
from app.core.time import local_today
from app.db.enums import ExtractionStatus
from app.db.models import Condominium, DataIssue, DelegationEvent, DelegationRequest, Document
from app.db.session import DbSession
from app.delegation import (
    DelegationError,
    attend_item,
    authorize,
    create,
    finish,
    issue_link,
    link_url,
    mark_shared,
    message_text,
    open_link,
    progress,
    public_view,
    receive,
    refresh,
    sender_name,
    suggest_items,
)
from app.reports.data import DOC_TYPE_LABEL
from app.routers.documents import MAX_FILES_PER_REQUEST
from app.routers.portfolio import _manager_access

router = APIRouter(tags=["delegations"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
OPEN = ("rascunho", "autorizado", "aguardando_envio", "recebendo")
CanPrepare = Annotated[CondoAccess, Depends(require(Permission.MANAGE_CASES))]
CanAuthorize = Annotated[CondoAccess, Depends(require(Permission.APPROVE_IN_CONDO))]
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_DELEGATION))]
NOT_FOUND = "Link inválido ou fora do prazo. Peça um novo link a quem enviou."


class ItemIn(BaseModel):
    key: str | None = Field(default=None, max_length=120)
    label: str = Field(max_length=200)
    kind: str = Field(default="outro", max_length=30)
    contract_id: str | None = None
    competence: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class RequestIn(BaseModel):
    recipient_name: str = Field(max_length=200)
    recipient_role: Literal["administradora", "fornecedor", "contador", "zelador", "outro"]
    items: list[ItemIn] = Field(max_length=20)
    scope: str = Field(default="", max_length=2000)
    due_date: date
    case_id: uuid.UUID | None = None


class LinkIn(BaseModel):
    days: int = Field(default=7, ge=1, le=30)


def _http(exc: DelegationError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


async def _request(db: DbSession, access: CondoAccess, rid: uuid.UUID) -> DelegationRequest:
    req = await db.scalar(
        select(DelegationRequest).where(
            DelegationRequest.id == rid, DelegationRequest.condominium_id == access.condominium_id
        )
    )
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado.")
    return req


async def _today(db: DbSession, access: CondoAccess) -> date:
    condo = await db.get(Condominium, access.condominium_id)
    return local_today(condo.timezone if condo else None)


def _summary(req: DelegationRequest) -> dict[str, Any]:
    return {
        "id": str(req.id),
        "recipient_name": req.recipient_name,
        "recipient_role": req.recipient_role,
        "status": req.status,
        "due_date": req.due_date.isoformat(),
        "shared_at": req.shared_at.isoformat() if req.shared_at else None,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "progress": progress(req),
    }


async def _detail(db: DbSession, access: CondoAccess, req: DelegationRequest) -> dict[str, Any]:
    events = await db.scalars(
        select(DelegationEvent)
        .where(DelegationEvent.request_id == req.id)
        .order_by(DelegationEvent.created_at)
    )
    docs = await db.scalars(
        select(Document)
        .where(Document.delegation_request_id == req.id)
        .order_by(Document.created_at)
    )
    can = access.can
    open_ = req.status not in ("concluido", "encerrado", "expirado", "revogado")
    return {
        **_summary(req),
        "scope": req.scope,
        "items": req.items,
        "events": [
            {"kind": e.kind, "by_person": e.user_id is not None, "at": e.created_at.isoformat()}
            for e in events
        ],
        "documents": [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "doc_type_label": DOC_TYPE_LABEL.get(d.doc_type, d.doc_type),
                "extraction_status": d.extraction_status,
            }
            for d in docs
        ],
        "can": {
            "authorize": req.status == "rascunho" and can(Permission.APPROVE_IN_CONDO),
            "issue_link": open_ and req.status != "rascunho" and can(Permission.APPROVE_IN_CONDO),
            "attend": open_ and can(Permission.MANAGE_CASES),
            "finish": open_ and can(Permission.MANAGE_DELEGATION),
        },
    }


@router.get("/condominiums/{condominium_id}/delegations/suggestions")
async def suggestions(
    condominium_id: uuid.UUID, access: CanPrepare, db: DbSession
) -> list[dict[str, Any]]:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return await suggest_items(db, condo, local_today(condo.timezone))


@router.get("/condominiums/{condominium_id}/delegations")
async def list_requests(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[dict[str, Any]]:
    today = await _today(db, access)
    rows = list(
        await db.scalars(
            select(DelegationRequest)
            .where(DelegationRequest.condominium_id == access.condominium_id)
            .order_by(DelegationRequest.created_at.desc())
        )
    )
    for req in rows:
        await refresh(db, req, today)
    return [_summary(r) for r in rows]


@router.get("/condominiums/{condominium_id}/delegations/board")
async def board(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, list[dict[str, Any]]]:
    """Hoje (LB-044): what waits for the person × what is with others. Computed from the
    requests and the documents at each read; nothing is stored and nothing is sent."""
    today = await _today(db, access)
    can = access.can
    rows = list(
        await db.scalars(
            select(DelegationRequest)
            .where(
                DelegationRequest.condominium_id == access.condominium_id,
                DelegationRequest.status.in_(OPEN),
            )
            .order_by(DelegationRequest.due_date)
        )
    )
    mine: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for req in rows:
        await refresh(db, req, today)
        if req.status not in OPEN:
            continue
        base = {
            "request_id": str(req.id),
            "recipient_name": req.recipient_name,
            "recipient_role": req.recipient_role,
            "due_date": req.due_date.isoformat(),
            "progress": progress(req),
        }
        received = await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(Document.delegation_request_id == req.id)
        )
        pending_manual = any(
            not i.get("attended_at") and i.get("kind") != "nota_fiscal" for i in req.items
        )
        if req.status == "rascunho":
            if can(Permission.APPROVE_IN_CONDO):
                mine.append({**base, "kind": "autorizar"})
            continue
        if req.shared_at is None and can(Permission.APPROVE_IN_CONDO):
            mine.append({**base, "kind": "enviar_link"})
        elif received and pending_manual and can(Permission.MANAGE_CASES):
            mine.append({**base, "kind": "conferir", "received": int(received or 0)})
        others.append({**base, "kind": "terceiro", "late": req.due_date < today})
    in_review = int(
        await db.scalar(
            select(func.count())
            .select_from(Document)
            .where(
                Document.condominium_id == access.condominium_id,
                Document.extraction_status == ExtractionStatus.NEEDS_REVIEW.value,
                Document.reviewed_at.is_(None),
            )
        )
        or 0
    )
    open_issues = int(
        await db.scalar(
            select(func.count())
            .select_from(DataIssue)
            .where(DataIssue.condominium_id == access.condominium_id, DataIssue.status == "aberto")
        )
        or 0
    )
    if in_review or open_issues:
        others.append({"kind": "equipe", "documents": in_review, "conflicts": open_issues})
    return {"mine": mine, "others": others}


@router.get("/portfolio/delegations")
async def portfolio_requests(
    db: DbSession, principal: CurrentPrincipal, condominium_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    """The team's desktop (LB-044): requests of every condominium the person manages, open
    ones first and by due date; then the closed ones, most recent first."""
    out: list[dict[str, Any]] = []
    for condo, access in await _manager_access(db, principal):
        if condominium_id is not None and condo.id != condominium_id:
            continue
        today = local_today(condo.timezone)
        rows = await db.scalars(
            select(DelegationRequest).where(DelegationRequest.condominium_id == condo.id)
        )
        for req in rows:
            await refresh(db, req, today)
            out.append(
                {
                    **_summary(req),
                    "condominium_id": str(condo.id),
                    "condominium": condo.name,
                    "can_prepare": access.can(Permission.MANAGE_CASES),
                }
            )
    open_ = [r for r in out if r["status"] in OPEN]
    closed = [r for r in out if r["status"] not in OPEN]
    open_.sort(key=lambda r: r["due_date"])
    closed.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return open_ + closed


@router.post("/condominiums/{condominium_id}/delegations", status_code=status.HTTP_201_CREATED)
async def create_request(
    condominium_id: uuid.UUID, body: RequestIn, access: CanPrepare, db: DbSession
) -> dict[str, Any]:
    try:
        req = await create(
            db,
            condominium_id=access.condominium_id,
            user_id=access.user_id,
            recipient_name=body.recipient_name,
            recipient_role=body.recipient_role,
            items=[i.model_dump() for i in body.items],
            scope=body.scope,
            due_date=body.due_date,
            today=await _today(db, access),
            # The síndico preparing it authorises it at once; the CondoOS team only drafts.
            authorize_now=access.can(Permission.APPROVE_IN_CONDO),
            case_id=body.case_id,
        )
    except DelegationError as exc:
        raise _http(exc) from exc
    return await _detail(db, access, req)


@router.get("/condominiums/{condominium_id}/delegations/{request_id}")
async def get_request(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    req = await _request(db, access, request_id)
    await refresh(db, req, await _today(db, access))
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/delegations/{request_id}/authorize")
async def authorize_request(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanAuthorize, db: DbSession
) -> dict[str, Any]:
    req = await _request(db, access, request_id)
    try:
        await authorize(db, req, access.user_id)
    except DelegationError as exc:
        raise _http(exc) from exc
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/delegations/{request_id}/link")
async def make_link(
    condominium_id: uuid.UUID,
    request_id: uuid.UUID,
    body: LinkIn,
    access: CanAuthorize,
    db: DbSession,
) -> dict[str, Any]:
    """The link and the ready text. The token is shown only in this answer; nothing is sent."""
    req = await _request(db, access, request_id)
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    try:
        token, expires = await issue_link(db, req, access.user_id, body.days)
    except DelegationError as exc:
        raise _http(exc) from exc
    url = link_url(token)
    sender = await sender_name(db, access.user_id)
    return {
        "url": url,
        "expires_at": expires.isoformat(),
        "text": message_text(req, condo, sender, url, expires),
        "request": await _detail(db, access, req),
    }


@router.post("/condominiums/{condominium_id}/delegations/{request_id}/shared")
async def shared(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanAuthorize, db: DbSession
) -> dict[str, Any]:
    req = await _request(db, access, request_id)
    try:
        await mark_shared(db, req, access.user_id)
    except DelegationError as exc:
        raise _http(exc) from exc
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/delegations/{request_id}/items/{key}/attend")
async def attend(
    condominium_id: uuid.UUID,
    request_id: uuid.UUID,
    key: str,
    access: CanPrepare,
    db: DbSession,
) -> dict[str, Any]:
    req = await _request(db, access, request_id)
    try:
        if req.status in ("concluido", "encerrado", "expirado", "revogado"):
            raise DelegationError("Este pedido já foi encerrado.", 409)
        await attend_item(db, req, key, access.user_id)
        await refresh(db, req, await _today(db, access))
    except DelegationError as exc:
        raise _http(exc) from exc
    return await _detail(db, access, req)


@router.post("/condominiums/{condominium_id}/delegations/{request_id}/{verb}")
async def close_request(
    condominium_id: uuid.UUID,
    request_id: uuid.UUID,
    verb: Literal["close", "revoke"],
    access: CanManage,
    db: DbSession,
) -> dict[str, Any]:
    req = await _request(db, access, request_id)
    try:
        await finish(db, req, access.user_id, revoke=verb == "revoke")
    except DelegationError as exc:
        raise _http(exc) from exc
    return await _detail(db, access, req)


# --------------------------------------------------------------------------- public


TOO_MANY = "Muitas tentativas a partir desta rede. Tente de novo em alguns minutos."


def public_rate_limit(request: Request) -> None:
    """Limit per client address on the public routes (D100), on top of the per-link limits.
    The same answer for every token, so the limit says nothing about which links exist."""
    s = get_settings()
    limiter = getattr(request.app.state, "public_link_limiter", None)
    if limiter is None:
        limiter = WindowLimiter(s.public_link_max_requests, s.public_link_window_seconds)
        request.app.state.public_link_limiter = limiter
    if not limiter.hit(client_ip(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            TOO_MANY,
            headers={"Retry-After": str(limiter.window)},
        )


PublicLimit = Annotated[None, Depends(public_rate_limit)]


@router.get("/public/delegations/{token}")
async def public_request(token: str, db: DbSession, _limit: PublicLimit) -> dict[str, Any]:
    opened = await open_link(db, token)
    if opened is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return public_view(opened)


@router.post("/public/delegations/{token}/files")
async def public_upload(
    token: str,
    db: DbSession,
    _limit: PublicLimit,
    files: Annotated[list[UploadFile], File()],
) -> list[dict[str, Any]]:
    """Upload only: the answer says, per file, received, already received or refused (why)."""
    opened = await open_link(db, token)
    if opened is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    if not files or len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Envie de 1 a {MAX_FILES_PER_REQUEST} arquivos por vez.",
        )
    limit = get_settings().max_upload_mb * 1024 * 1024
    out = []
    for f in files:
        data = await f.read(limit + 1)
        outcome = await receive(db, opened, f.filename or "arquivo", data)
        out.append(
            {"filename": outcome.filename, "duplicate": outcome.duplicate, "error": outcome.error}
        )
    return out
