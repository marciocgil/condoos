"""Delegated requests for documents (LF4, D97).

Inside the condominium: drafting, ticking items, concluding and revoking need
``manage_cases``; authorizing (creating the link) is the síndico's (``approve_in_condo``).
Reading is open to whoever views the condominium; the link itself is shown only once, when
it is created.

Public: ``/submit/{token}`` without a session. It answers a minimal description of the
request and accepts files; any invalid, expired or revoked link is the same 404.
"""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.db.models import Condominium, DelegationRequest, DelegationUploadToken, Document
from app.db.session import DbSession, set_tenant_scope
from app.delegation import (
    DelegationError,
    authorize,
    conclude,
    create,
    current_link,
    effective_status,
    mark_shared,
    open_link,
    receive,
    request_of,
    revoke,
    set_items,
)
from app.routers.documents import DocumentStatusOut, _status

router = APIRouter(prefix="/condominiums/{condominium_id}/delegations", tags=["delegations"])
public_router = APIRouter(prefix="/submit", tags=["delegations"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_CASES))]
CanAuthorize = Annotated[CondoAccess, Depends(require(Permission.APPROVE_IN_CONDO))]
NOT_FOUND = "Link inválido, vencido ou revogado."


class DelegationIn(BaseModel):
    recipient_name: str = Field(min_length=3, max_length=200)
    recipient_email: EmailStr | None = None
    scope: str = Field(min_length=10, max_length=1000)
    items: list[str] = Field(min_length=1, max_length=20)
    due_date: date | None = None


class ItemsIn(BaseModel):
    done: list[bool] = Field(max_length=20)


class DelegationOut(BaseModel):
    id: uuid.UUID
    recipient_name: str
    recipient_email: str | None
    scope: str
    items: list[dict[str, Any]]
    due_date: date | None
    status: str
    link_expires_at: datetime | None
    files_received: int
    created_at: datetime
    authorized_at: datetime | None
    shared_at: datetime | None
    documents: list[DocumentStatusOut] = []


class NewLinkOut(BaseModel):
    request: DelegationOut
    link: str  # shown once; only its hash is stored
    message: str


async def _out(db: DbSession, req: DelegationRequest, with_docs: bool = False) -> DelegationOut:
    link = await current_link(db, req)
    docs: list[DocumentStatusOut] = []
    if with_docs:
        docs = [
            _status(d)
            for d in await db.scalars(
                select(Document)
                .where(
                    Document.condominium_id == req.condominium_id,
                    Document.delegation_request_id == req.id,
                )
                .order_by(Document.created_at)
            )
        ]
    return DelegationOut(
        id=req.id,
        recipient_name=req.recipient_name,
        recipient_email=req.recipient_email,
        scope=req.scope,
        items=list(req.items),
        due_date=req.due_date,
        status=effective_status(req, link),
        link_expires_at=link.expires_at if link else None,
        files_received=sum(
            (
                await db.scalars(
                    select(DelegationUploadToken.files_received).where(
                        DelegationUploadToken.request_id == req.id
                    )
                )
            ).all()
        ),
        created_at=req.created_at,
        authorized_at=req.authorized_at,
        shared_at=req.shared_at,
        documents=docs,
    )


async def _req(db: DbSession, access: CondoAccess, request_id: uuid.UUID) -> DelegationRequest:
    req = await db.scalar(
        select(DelegationRequest)
        .where(
            DelegationRequest.id == request_id,
            DelegationRequest.condominium_id == access.condominium_id,
        )
        .with_for_update()
    )
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado.")
    return req


def _fail(exc: DelegationError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.get("")
async def list_delegations(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[DelegationOut]:
    rows = await db.scalars(
        select(DelegationRequest)
        .where(DelegationRequest.condominium_id == access.condominium_id)
        .order_by(DelegationRequest.created_at.desc())
        .limit(100)
    )
    return [await _out(db, r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_delegation(
    condominium_id: uuid.UUID, body: DelegationIn, access: CanManage, db: DbSession
) -> DelegationOut:
    try:
        req = await create(
            db,
            access,
            recipient_name=body.recipient_name,
            recipient_email=str(body.recipient_email) if body.recipient_email else None,
            scope=body.scope,
            items=body.items,
            due_date=body.due_date,
        )
    except DelegationError as exc:
        raise _fail(exc) from exc
    return await _out(db, req)


@router.get("/{request_id}")
async def get_delegation(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanView, db: DbSession
) -> DelegationOut:
    return await _out(db, await _req(db, access, request_id), with_docs=True)


@router.post("/{request_id}/authorize")
async def authorize_delegation(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanAuthorize, db: DbSession
) -> NewLinkOut:
    """The síndico authorizes: a new link (shown only now) and the text to send."""
    req = await _req(db, access, request_id)
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    try:
        link = await authorize(db, access, condo, req)
    except DelegationError as exc:
        raise _fail(exc) from exc
    url = get_settings().web_base_url.rstrip("/") + link.path
    return NewLinkOut(request=await _out(db, req), link=url, message=link.message)


@router.post("/{request_id}/shared")
async def shared_delegation(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanManage, db: DbSession
) -> DelegationOut:
    req = await _req(db, access, request_id)
    try:
        await mark_shared(db, access, req)
    except DelegationError as exc:
        raise _fail(exc) from exc
    return await _out(db, req)


@router.post("/{request_id}/items")
async def items_delegation(
    condominium_id: uuid.UUID,
    request_id: uuid.UUID,
    body: ItemsIn,
    access: CanManage,
    db: DbSession,
) -> DelegationOut:
    req = await _req(db, access, request_id)
    try:
        await set_items(db, access, req, body.done)
    except DelegationError as exc:
        raise _fail(exc) from exc
    return await _out(db, req, with_docs=True)


@router.post("/{request_id}/conclude")
async def conclude_delegation(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanManage, db: DbSession
) -> DelegationOut:
    req = await _req(db, access, request_id)
    try:
        await conclude(db, access, req)
    except DelegationError as exc:
        raise _fail(exc) from exc
    return await _out(db, req)


@router.post("/{request_id}/revoke")
async def revoke_delegation(
    condominium_id: uuid.UUID, request_id: uuid.UUID, access: CanManage, db: DbSession
) -> DelegationOut:
    req = await _req(db, access, request_id)
    try:
        await revoke(db, access, req)
    except DelegationError as exc:
        raise _fail(exc) from exc
    return await _out(db, req)


# --------------------------------------------------------------------------- public


class PublicRequestOut(BaseModel):
    condominium: str
    recipient_name: str
    scope: str
    items: list[str]
    due_date: date | None
    expires_at: datetime
    files_received: int
    max_files: int


class PublicReceivedOut(BaseModel):
    filename: str
    accepted: bool
    duplicate: bool
    error: str | None


async def _public(db: DbSession, token: str) -> tuple[DelegationUploadToken, DelegationRequest]:
    link = await open_link(db, token)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    # From here on this transaction sees only the request's condominium (RLS).
    await set_tenant_scope(db, [link.condominium_id])
    req = await request_of(db, link)
    if req.status in ("concluido", "revogado", "rascunho"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return link, req


@public_router.get("/{token}")
async def public_request(token: str, db: DbSession) -> PublicRequestOut:
    """What the link is for. No data of the condominium beyond its name."""
    link, req = await _public(db, token)
    condo = await db.get(Condominium, req.condominium_id)
    assert condo is not None
    return PublicRequestOut(
        condominium=condo.name,
        recipient_name=req.recipient_name,
        scope=req.scope,
        items=[str(i["label"]) for i in req.items],
        due_date=req.due_date,
        expires_at=link.expires_at,
        files_received=link.files_received,
        max_files=link.max_files,
    )


@public_router.post("/{token}", status_code=status.HTTP_201_CREATED)
async def public_upload(
    token: str, files: list[UploadFile], db: DbSession
) -> list[PublicReceivedOut]:
    """Send-only: stores the files for the request; answers only what was accepted."""
    link, req = await _public(db, token)
    if not files or len(files) > 10:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Envie de 1 a 10 arquivos por vez."
        )
    limit = get_settings().max_upload_mb * 1024 * 1024
    payload = [(f.filename or "arquivo", await f.read(limit + 1)) for f in files]
    try:
        received = await receive(db, link, req, payload)
    except DelegationError as exc:
        raise _fail(exc) from exc
    return [
        PublicReceivedOut(
            filename=r.filename, accepted=r.accepted, duplicate=r.duplicate, error=r.error
        )
        for r in received
    ]
