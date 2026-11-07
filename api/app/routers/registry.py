"""Registration screens of the management company (D67): condominium data, board, logins,
contracts, and new condominiums. Manager only (permission ``configure``); every change is
audited with ids and field names, never people's data.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, active_membership, require
from app.auth.rbac import CondoAccess, Permission
from app.auth.service import normalize_email
from app.core.audit import record_audit
from app.core.br import is_valid_cnpj, only_digits
from app.core.jobs import enqueue
from app.core.time import is_valid_timezone, utcnow
from app.db.enums import AdjustmentIndex, BoardPosition, PlatformRole, Role
from app.db.models import (
    AppUser,
    BoardMember,
    Competence,
    Condominium,
    Contract,
    Membership,
)
from app.db.session import DbSession, get_worker_engine, sessionmaker_for
from app.enrichment.suppliers import get_or_create_supplier
from app.onboarding import BoardIn, CondoIn, OnboardingIn, onboard
from app.platform import active_grant, assign
from app.routers.schemas import ContractOut

router = APIRouter(tags=["registry"])

CanConfigure = Annotated[CondoAccess, Depends(require(Permission.CONFIGURE))]
BOARD_ROLES = Literal["sindico", "subsindico", "conselheiro"]


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


async def _recheck_open_months(db: DbSession, condominium_id: uuid.UUID) -> None:
    """Re-run the rules of the open months after a change that affects them."""
    for month in await db.scalars(
        select(Competence.month).where(
            Competence.condominium_id == condominium_id, Competence.status == "aberta"
        )
    ):
        await enqueue(
            db,
            "rules.evaluate",
            {"condominium_id": str(condominium_id), "competence": f"{month:%Y-%m}"},
            condominium_id=condominium_id,
            priority=True,
        )


async def _audit(
    db: DbSession,
    access: CondoAccess,
    action: str,
    object_type: str,
    object_id: uuid.UUID,
    details: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        db,
        action=action,
        object_type=object_type,
        object_id=object_id,
        actor_user_id=access.user_id,
        condominium_id=access.condominium_id,
        details=details or {},
    )


# --------------------------------------------------------------------------- profile


class ProfileIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    units: int = Field(gt=0)
    address: str = Field(min_length=5, max_length=300)
    retention_years: int = Field(ge=5, le=30)
    timezone: str | None = None  # IANA name (ADR-P07); None keeps the current one

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_timezone(v):
            raise ValueError("fuso horário desconhecido (use o nome IANA, ex.: America/Sao_Paulo)")
        return v


@router.put("/condominiums/{condominium_id}/profile")
async def update_profile(
    condominium_id: uuid.UUID, body: ProfileIn, access: CanConfigure, db: DbSession
) -> dict[str, str]:
    condo = await db.get(Condominium, access.condominium_id, with_for_update=True)
    assert condo is not None
    changed = [k for k, v in body.model_dump(exclude_none=True).items() if getattr(condo, k) != v]
    for key in changed:
        setattr(condo, key, getattr(body, key))
    if changed:
        await _audit(
            db, access, "condominium.updated", "condominium", condo.id, {"fields": changed}
        )
    return {"message": "Dados do condomínio salvos."}


# --------------------------------------------------------------------------- board


class BoardMemberIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=200)
    position: BoardPosition
    term_start: date
    term_end: date | None = None

    @field_validator("term_end")
    @classmethod
    def _after_start(cls, v: date | None, info: Any) -> date | None:
        start = info.data.get("term_start")
        if v is not None and start is not None and v < start:
            raise ValueError("o fim do mandato é anterior ao início")
        return v


async def _board_member(db: DbSession, access: CondoAccess, member_id: uuid.UUID) -> BoardMember:
    member = await db.scalar(
        select(BoardMember).where(
            BoardMember.id == member_id, BoardMember.condominium_id == access.condominium_id
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro do corpo diretivo não encontrado.")
    return member


@router.post("/condominiums/{condominium_id}/board", status_code=status.HTTP_201_CREATED)
async def add_board_member(
    condominium_id: uuid.UUID, body: BoardMemberIn, access: CanConfigure, db: DbSession
) -> dict[str, str]:
    member = BoardMember(
        id=uuid.uuid4(),
        condominium_id=access.condominium_id,
        full_name=body.full_name.strip(),
        position=body.position.value,
        term_start=body.term_start,
        term_end=body.term_end,
    )
    db.add(member)
    await db.flush()
    await _audit(
        db, access, "board.added", "board_member", member.id, {"position": member.position}
    )
    await _recheck_open_months(db, access.condominium_id)  # R08 compares board names
    return {"id": str(member.id)}


@router.put("/condominiums/{condominium_id}/board/{member_id}")
async def update_board_member(
    condominium_id: uuid.UUID,
    member_id: uuid.UUID,
    body: BoardMemberIn,
    access: CanConfigure,
    db: DbSession,
) -> dict[str, str]:
    member = await _board_member(db, access, member_id)
    member.full_name = body.full_name.strip()
    member.position = body.position.value
    member.term_start = body.term_start
    member.term_end = body.term_end
    await _audit(db, access, "board.updated", "board_member", member.id)
    await _recheck_open_months(db, access.condominium_id)
    return {"id": str(member.id)}


@router.delete("/condominiums/{condominium_id}/board/{member_id}")
async def remove_board_member(
    condominium_id: uuid.UUID, member_id: uuid.UUID, access: CanConfigure, db: DbSession
) -> dict[str, str]:
    member = await _board_member(db, access, member_id)
    await db.delete(member)
    await _audit(db, access, "board.removed", "board_member", member_id)
    await _recheck_open_months(db, access.condominium_id)
    return {"message": "Removido do corpo diretivo."}


# --------------------------------------------------------------------------- logins


class MemberIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    email: EmailStr
    role: BOARD_ROLES
    # Temporary access for external participants (D77); None = no end date.
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _future(cls, v: datetime | None) -> datetime | None:
        if v is not None and (v.tzinfo is None or v <= utcnow()):
            raise ValueError("o fim do acesso precisa ser uma data futura com fuso")
        return v


@router.post("/condominiums/{condominium_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    condominium_id: uuid.UUID, body: MemberIn, access: CanConfigure, db: DbSession
) -> dict[str, str]:
    email = normalize_email(body.email)
    user = await db.scalar(select(AppUser).where(AppUser.email == email))
    if user is None:
        user = AppUser(id=uuid.uuid4(), name=body.name.strip(), email=email, is_active=True)
        db.add(user)
        await db.flush()
    existing = await db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.condominium_id == access.condominium_id,
            Membership.role == body.role,
        )
    )
    now = utcnow()
    if (
        existing is not None
        and existing.revoked_at is None
        and (existing.expires_at is None or existing.expires_at > now)
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Essa pessoa já tem esse acesso.")
    details: dict[str, Any] = {"role": body.role, "temporary": body.expires_at is not None}
    if existing is not None:  # revoked or expired: granted again, history kept in the audit
        membership = existing
        membership.revoked_at = None
        membership.expires_at = body.expires_at
        membership.invited_at = now
        membership.accepted_at = None
        details["reactivated"] = True
    else:
        membership = Membership(
            id=uuid.uuid4(),
            user_id=user.id,
            condominium_id=access.condominium_id,
            role=body.role,
            invited_at=now,
            expires_at=body.expires_at,
        )
        db.add(membership)
    await db.flush()
    await _audit(db, access, "member.added", "membership", membership.id, details)
    return {"id": str(membership.id)}


@router.delete("/condominiums/{condominium_id}/members/{membership_id}")
async def remove_member(
    condominium_id: uuid.UUID, membership_id: uuid.UUID, access: CanConfigure, db: DbSession
) -> dict[str, str]:
    membership = await db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.condominium_id == access.condominium_id,
            Membership.revoked_at.is_(None),
        )
    )
    if membership is None:  # company-wide accesses are not removed from a condominium
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Acesso não encontrado.")
    if membership.user_id == access.user_id:
        raise _unprocessable("Você não pode remover o próprio acesso.")
    # Revoked, not deleted (D77): the row keeps who had which access and until when.
    membership.revoked_at = utcnow()
    await _audit(db, access, "member.removed", "membership", membership_id)
    return {"message": "Acesso removido. As sessões abertas perdem o acesso na próxima ação."}


# --------------------------------------------------------------------------- contracts


class ContractIn(BaseModel):
    supplier_cnpj: str
    supplier_name: str = Field(min_length=3, max_length=200)
    object: str = Field(min_length=3, max_length=300)
    scope_items: list[str] = []
    monthly_value: str
    adjustment_index: AdjustmentIndex
    adjustment_index_other: str | None = Field(default=None, max_length=120)
    adjustment_base_month: int | None = Field(default=None, ge=1, le=12)
    billing_frequency_months: Literal[0, 1, 2, 3, 6, 12] = 1  # 0 = on demand (D70)
    start_date: date
    end_date: date | None = None

    @field_validator("supplier_cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if not is_valid_cnpj(only_digits(v)):
            raise ValueError("CNPJ do fornecedor inválido")
        return only_digits(v)

    def value(self) -> Decimal:
        raw = self.monthly_value.strip()
        if "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        try:
            amount = Decimal(raw).quantize(Decimal("0.01"))
        except InvalidOperation as exc:
            raise _unprocessable("Valor mensal inválido.") from exc
        if amount <= 0:
            raise _unprocessable("O valor mensal deve ser maior que zero.")
        return amount

    def check(self) -> None:
        if self.end_date is not None and self.end_date < self.start_date:
            raise _unprocessable("O fim da vigência é anterior ao início.")
        if (
            self.adjustment_index == AdjustmentIndex.OUTRO
            and not (self.adjustment_index_other or "").strip()
        ):
            raise _unprocessable("Descreva qual é o índice de reajuste.")

    def base_month(self) -> int | None:
        """D68: without an explicit month, the adjustment is in the month the term started."""
        if self.adjustment_index in (AdjustmentIndex.FIXO, AdjustmentIndex.NENHUM):
            return None
        return self.adjustment_base_month or self.start_date.month


async def _apply(db: DbSession, contract: Contract, body: ContractIn) -> None:
    body.check()
    supplier = await get_or_create_supplier(db, body.supplier_cnpj, body.supplier_name.strip())
    contract.supplier_id = supplier.id
    contract.object = body.object.strip()
    contract.scope_items = [s.strip() for s in body.scope_items if s.strip()]
    contract.monthly_value = body.value()
    contract.adjustment_index = body.adjustment_index.value
    contract.adjustment_index_other = (
        (body.adjustment_index_other or "").strip() or None
        if body.adjustment_index == AdjustmentIndex.OUTRO
        else None
    )
    contract.adjustment_base_month = body.base_month()
    contract.billing_frequency_months = body.billing_frequency_months
    contract.start_date = body.start_date
    contract.end_date = body.end_date
    if supplier.enriched_at is None:
        await enqueue(
            db,
            "supplier.enrich",
            {"cnpj": supplier.cnpj},
            dedupe_key=f"supplier:{supplier.cnpj}:enrich",
        )


@router.post("/condominiums/{condominium_id}/contracts", status_code=status.HTTP_201_CREATED)
async def create_contract(
    condominium_id: uuid.UUID, body: ContractIn, access: CanConfigure, db: DbSession
) -> ContractOut:
    contract = Contract(id=uuid.uuid4(), condominium_id=access.condominium_id)
    await _apply(db, contract, body)
    db.add(contract)
    await db.flush()
    await _audit(db, access, "contract.created", "contract", contract.id)
    await _recheck_open_months(db, access.condominium_id)
    out = ContractOut.model_validate(contract)
    out.supplier_name = body.supplier_name.strip()
    return out


@router.put("/condominiums/{condominium_id}/contracts/{contract_id}")
async def update_contract(
    condominium_id: uuid.UUID,
    contract_id: uuid.UUID,
    body: ContractIn,
    access: CanConfigure,
    db: DbSession,
) -> ContractOut:
    contract = await db.scalar(
        select(Contract).where(
            Contract.id == contract_id, Contract.condominium_id == access.condominium_id
        )
    )
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contrato não encontrado.")
    await _apply(db, contract, body)
    await db.flush()
    await _audit(db, access, "contract.updated", "contract", contract.id)
    await _recheck_open_months(db, access.condominium_id)
    out = ContractOut.model_validate(contract)
    out.supplier_name = body.supplier_name.strip()
    return out


# --------------------------------------------------------------------------- new condominium


class NewCondominiumIn(BaseModel):
    condominium: CondoIn
    board: list[BoardIn] = Field(min_length=1)


@router.post("/portfolio/condominiums", status_code=status.HTTP_201_CREATED)
async def create_condominium(
    body: NewCondominiumIn, principal: CurrentPrincipal, db: DbSession
) -> dict[str, str]:
    """A manager of a management company creates a condominium in it; a CondoOS admin
    creates a condominium contracting directly, without a management company (D73), and is
    assigned to it."""
    company_id = await db.scalar(
        select(Membership.management_company_id).where(
            Membership.user_id == principal.user.id,
            Membership.management_company_id.is_not(None),
            Membership.role == Role.GERENTE.value,
            *active_membership(),
        )
    )
    is_admin = await active_grant(db, principal.user.id, PlatformRole.CONDOOS_ADMIN) is not None
    if company_id is None and not is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Só o gerente da administradora ou o administrador CondoOS cadastra condomínios.",
        )
    spec = OnboardingIn(condominium=body.condominium, board=body.board)
    # The new condominium is not in this request's tenant scope yet (RLS): it is created in
    # its own transaction with the worker role, after the checks above.
    async with sessionmaker_for(get_worker_engine())() as session, session.begin():
        from app.db.models import ManagementCompany

        if company_id is not None:
            company = await session.get(ManagementCompany, company_id)
            assert company is not None
            spec.management_company_cnpj = company.cnpj
        try:
            condo = await onboard(session, spec)
        except ValueError as exc:
            raise _unprocessable(str(exc)) from exc
        await record_audit(
            session,
            action="condominium.created",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=principal.user.id,
            condominium_id=condo.id,
        )
        if company_id is None:  # CondoOS admin: assigned to what it created
            admin = await session.get(AppUser, principal.user.id)
            assert admin is not None
            await assign(
                session,
                condominium_id=condo.id,
                user=admin,
                role=PlatformRole.CONDOOS_ADMIN,
                reason="Cadastro do condomínio",
                actor_user_id=principal.user.id,
            )
    return {"id": str(condo.id), "slug": condo.slug}
