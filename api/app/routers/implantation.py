"""Implanting a condominium by the síndico (D128): start, the eight items, the mandate, the
adhesion term and the approval limit."""

import re
import unicodedata
import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import implantation as imp
from app.auth.deps import CurrentPrincipal, active_membership, require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.br import is_valid_cnpj, only_digits
from app.core.ratelimit import WindowLimiter
from app.core.time import local_today, utcnow
from app.db.enums import BoardPosition, PlatformRole, Role
from app.db.models import Condominium, Membership
from app.db.session import DbSession, get_worker_engine, sessionmaker_for
from app.onboarding import BoardIn, CondoIn, OnboardingIn, onboard
from app.platform import active_grant

router = APIRouter(tags=["implantation"])

CanManage = Annotated[CondoAccess, Depends(require(Permission.MANAGE_LAUNCH))]
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
_limiter = WindowLimiter(limit=30, window_seconds=600)


async def can_implant(db: DbSession, user_id: uuid.UUID) -> bool:
    """The síndico of at least one condominium (the professional síndico, D127) or a CondoOS
    admin may start a new one."""
    sindico = await db.scalar(
        select(Membership.id).where(
            Membership.user_id == user_id,
            Membership.role == Role.SINDICO.value,
            Membership.condominium_id.is_not(None),
            *active_membership(),
        )
    )
    if sindico is not None:
        return True
    return await active_grant(db, user_id, PlatformRole.CONDOOS_ADMIN) is not None


def _slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(condominio|edificio|residencial)\b", " ", text)
    base = "-".join(re.findall(r"[a-z0-9]+", text))[:60].strip("-") or "condominio"
    return f"{base}-{uuid.uuid4().hex[:4]}"


@router.get("/implantation/eligibility")
async def eligibility(principal: CurrentPrincipal, db: DbSession) -> dict[str, bool]:
    return {"can_implant": await can_implant(db, principal.user.id)}


@router.get("/implantation/cnpj/{cnpj}")
async def lookup(cnpj: str, principal: CurrentPrincipal, db: DbSession) -> dict[str, Any]:
    """The Receita's record of the condominium's CNPJ (nothing is stored but the result)."""
    from app.enrichment.suppliers import SupplierLookupUnavailable, get_provider

    if not await can_implant(db, principal.user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu acesso não implanta condomínios.")
    digits = only_digits(cnpj)
    if not is_valid_cnpj(digits):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "CNPJ inválido: confira.")
    if not _limiter.hit(str(principal.user.id), utcnow().timestamp()):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Muitas consultas. Aguarde.")
    exists = await db.scalar(select(Condominium.id).where(Condominium.cnpj == digits))
    if exists is not None:
        return {"cnpj": digits, "already": True}
    try:
        record = await get_provider().lookup(digits)
    except SupplierLookupUnavailable:
        return {"cnpj": digits, "available": False, "found": False}
    if record is None:
        return {"cnpj": digits, "available": True, "found": False}
    address = ""
    if record.address:
        a = record.address
        parts = [
            a.get("logradouro"),
            a.get("numero"),
            a.get("bairro"),
            a.get("municipio"),
            a.get("uf"),
        ]
        address = ", ".join(p for p in parts if p)
    return {
        "cnpj": digits,
        "available": True,
        "found": True,
        "name": record.legal_name,
        "status": record.registration_status,
        "address": address,
        "is_condominium": (
            record.legal_nature_code == 3085 if record.legal_nature_code is not None else None
        ),
    }


class StartIn(BaseModel):
    cnpj: str
    name: str = Field(min_length=3, max_length=200)
    address: str = Field(min_length=5, max_length=300)
    units: int = Field(gt=0, le=5000)


@router.post("/implantation", status_code=status.HTTP_201_CREATED)
async def start(body: StartIn, principal: CurrentPrincipal, db: DbSession) -> dict[str, str]:
    """Creates the condominium with the person as its síndico (provisional mandate from today,
    adjusted in the next step). The rest is filled in later."""
    if not await can_implant(db, principal.user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu acesso não implanta condomínios.")
    user = principal.user
    spec = OnboardingIn(
        condominium=CondoIn(
            name=body.name.strip(),
            slug=_slug(body.name),
            cnpj=body.cnpj,
            units=body.units,
            address=body.address.strip(),
        ),
        board=[
            BoardIn(
                name=user.name,
                position=BoardPosition.SINDICO,
                term_start=date.today(),
                email=user.email,
            )
        ],
    )
    # The new condominium is outside this request's tenant scope (RLS): created in its own
    # transaction, after the checks, like the Carteira's "Novo condomínio" (D73).
    async with sessionmaker_for(get_worker_engine())() as session, session.begin():
        try:
            condo = await onboard(session, spec)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        await record_audit(
            session,
            action="condominium.implantation_started",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=user.id,
            condominium_id=condo.id,
            details={"by": "sindico"},
        )
    return {"id": str(condo.id)}


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return condo


@router.get("/condominiums/{condominium_id}/implantation")
async def progress(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    condo = await _condo(db, access)
    out = await imp.essentials(db, condo, local_today(condo.timezone))
    out["can_manage"] = access.can(Permission.MANAGE_LAUNCH)
    return out


class MandateIn(BaseModel):
    term_start: date
    term_end: date | None = None


@router.put("/condominiums/{condominium_id}/implantation/mandate")
async def mandate(
    condominium_id: uuid.UUID,
    body: MandateIn,
    access: CanManage,
    db: DbSession,
    principal: CurrentPrincipal,
) -> dict[str, str]:
    condo = await _condo(db, access)
    try:
        m = await imp.set_mandate(
            db,
            condo,
            name=principal.user.name,
            term_start=body.term_start,
            term_end=body.term_end,
            user_id=access.user_id,
        )
    except imp.ImplantationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"id": str(m.id)}


class TermIn(BaseModel):
    document_id: uuid.UUID


@router.post("/condominiums/{condominium_id}/implantation/term", status_code=201)
async def term(
    condominium_id: uuid.UUID, body: TermIn, access: CanManage, db: DbSession
) -> dict[str, str]:
    condo = await _condo(db, access)
    try:
        row = await imp.record_term(db, condo, body.document_id, access.user_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento não encontrado.") from exc
    return {"id": str(row.id), "version": row.version}


class LimitIn(BaseModel):
    value: str = Field(max_length=20)
    source: str = Field(max_length=300)


@router.put("/condominiums/{condominium_id}/implantation/limit")
async def limit(
    condominium_id: uuid.UUID, body: LimitIn, access: CanManage, db: DbSession
) -> dict[str, str]:
    condo = await _condo(db, access)
    try:
        await imp.set_limit(db, condo, body.value, body.source, access.user_id)
    except imp.ImplantationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"default": str((condo.approval_limits or {}).get("default"))}
