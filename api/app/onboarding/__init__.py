"""Onboarding of a new condominium for a pilot: python -m app.onboarding <file.json>

The file describes the condominium, its board (with e-mail when the person will log in) and
extra members. Contracts are not typed here: they come from the uploaded contract documents
(D59). Runs with the owner role (DATABASE_ADMIN_URL) and refuses to overwrite: an existing
slug or CNPJ is an error, never an update.
"""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import normalize_email
from app.core.audit import record_audit
from app.core.br import is_valid_cnpj
from app.db.enums import BoardPosition, Role
from app.db.models import AppUser, BoardMember, Condominium, ManagementCompany, Membership

DEFAULT_CATEGORIES = [
    "portaria",
    "limpeza",
    "manutencao",
    "elevadores",
    "jardinagem",
    "energia",
    "agua",
    "gas",
    "dedetizacao",
    "obras",
]
BOARD_ROLE = {
    BoardPosition.SINDICO: Role.SINDICO,
    BoardPosition.SUBSINDICO: Role.SUBSINDICO,
    BoardPosition.CONSELHEIRO: Role.CONSELHEIRO,
}


def _digits(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


class ApprovalLimits(BaseModel):
    default: str
    by_category: dict[str, str] = {}

    @field_validator("default")
    @classmethod
    def _money(cls, v: str) -> str:
        try:
            return f"{Decimal(v.replace('.', '').replace(',', '.') if ',' in v else v):.2f}"
        except InvalidOperation as exc:
            raise ValueError("valor inválido") from exc


class CondoIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    cnpj: str
    units: int = Field(gt=0)
    address: str = Field(min_length=5, max_length=300)
    approval_limits: ApprovalLimits
    retention_years: int = Field(default=5, ge=5, le=30)  # fiscal documents: at least 5 years

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str) -> str:
        if not is_valid_cnpj(_digits(v)):
            raise ValueError("CNPJ inválido")
        return _digits(v)


class BoardIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    position: BoardPosition
    term_start: date
    term_end: date | None = None
    email: EmailStr | None = None  # with an e-mail the person gets a login with the board role


class MemberIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    email: EmailStr
    role: Literal["sindico", "subsindico", "conselheiro"]


class OnboardingIn(BaseModel):
    management_company_cnpj: str | None = None
    management_company_name: str | None = None  # alternative to the CNPJ (exact name)
    condominium: CondoIn
    board: list[BoardIn] = Field(min_length=1)
    members: list[MemberIn] = []


async def _user(session: AsyncSession, name: str, email: str) -> AppUser:
    email = normalize_email(email)
    user = await session.scalar(select(AppUser).where(AppUser.email == email))
    if user is None:
        user = AppUser(id=uuid.uuid4(), name=name, email=email, is_active=True)
        session.add(user)
        await session.flush()
    return user


async def onboard(session: AsyncSession, spec: OnboardingIn) -> Condominium:
    c = spec.condominium
    clash = await session.scalar(
        select(Condominium.slug).where(or_(Condominium.slug == c.slug, Condominium.cnpj == c.cnpj))
    )
    if clash is not None:
        raise ValueError(f"já existe um condomínio com este slug ou CNPJ ({clash})")
    if not any(b.position == BoardPosition.SINDICO for b in spec.board):
        raise ValueError("o corpo diretivo precisa de um síndico")
    company_id = None
    if spec.management_company_cnpj or spec.management_company_name:
        company_id = await session.scalar(
            select(ManagementCompany.id).where(
                ManagementCompany.cnpj == _digits(spec.management_company_cnpj)
                if spec.management_company_cnpj
                else ManagementCompany.name == spec.management_company_name
            )
        )
        if company_id is None:
            raise ValueError("administradora não encontrada")
    condo = Condominium(
        id=uuid.uuid4(),
        management_company_id=company_id,
        name=c.name,
        slug=c.slug,
        cnpj=c.cnpj,
        units=c.units,
        address=c.address,
        approval_limits=c.approval_limits.model_dump(),
        rule_params={},
        expense_categories=DEFAULT_CATEGORIES,
        retention_years=c.retention_years,
    )
    session.add(condo)
    await session.flush()
    grants: list[tuple[AppUser, Role]] = []
    for b in spec.board:
        user = await _user(session, b.name, b.email) if b.email else None
        session.add(
            BoardMember(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                full_name=b.name,
                position=b.position.value,
                term_start=b.term_start,
                term_end=b.term_end,
                user_id=user.id if user else None,
            )
        )
        if user is not None and b.position in BOARD_ROLE:
            grants.append((user, BOARD_ROLE[b.position]))
    for m in spec.members:
        grants.append((await _user(session, m.name, m.email), Role(m.role)))
    for user, role in {(u.id, r): (u, r) for u, r in grants}.values():
        session.add(
            Membership(id=uuid.uuid4(), user_id=user.id, condominium_id=condo.id, role=role.value)
        )
    await record_audit(
        session,
        action="condominium.onboarded",
        object_type="condominium",
        object_id=condo.id,
        condominium_id=condo.id,
        details={"board": len(spec.board), "logins": len(grants)},
    )
    await session.flush()
    return condo
