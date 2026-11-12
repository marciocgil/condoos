"""Per-condominium settings (spec §9): approval limits, rule parameters, expense categories
and members. Every change is recorded in audit_log (keys only, never values of people)."""

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.auth.deps import active_membership, invite_cutoff, require
from app.auth.rbac import CondoAccess, Permission
from app.cases import user_names
from app.condo_settings import ensure_baseline, history, record_version
from app.core.br import format_cnpj
from app.core.changes import record_change
from app.core.time import utcnow
from app.db.models import AppUser, BoardMember, CondoAssignment, Condominium, Membership
from app.db.session import DbSession
from app.rules.engine import ALL_RULES

router = APIRouter(prefix="/condominiums/{condominium_id}/settings", tags=["settings"])
CanConfigure = Annotated[CondoAccess, Depends(require(Permission.CONFIGURE))]


class RuleParamsOut(BaseModel):
    code: str
    name: str
    defaults: dict[str, Any]
    overrides: dict[str, Any]


class MemberOut(BaseModel):
    id: uuid.UUID | None = None  # membership id (condominium-scoped ones can be removed)
    name: str
    email: str
    role: str
    scope: str  # condominio | administradora | condoos
    # convidado | convite_vencido (FR-002, D126) | ativo; expired and revoked accesses are not
    # listed.
    status: str = "ativo"
    expires_at: datetime | None = None


class BoardOut(BaseModel):
    id: uuid.UUID | None = None
    full_name: str
    position: str
    term_start: date | None = None
    term_end: date | None = None
    has_login: bool = False


class ProfileOut(BaseModel):
    name: str
    cnpj: str
    units: int
    address: str
    retention_years: int
    timezone: str
    management_company_reviews: bool


class SettingsVersionOut(BaseModel):
    version: int
    valid_from: datetime
    changed_by: str | None
    reason: str | None
    approval_limits: dict[str, Any]
    rule_params: dict[str, Any]


class SettingsOut(BaseModel):
    profile: ProfileOut | None = None
    approval_limits: dict[str, Any]
    # Versions of the limits and rule parameters, newest first (CB-012).
    history: list[SettingsVersionOut] = []
    expense_categories: list[str]
    rules: list[RuleParamsOut]
    members: list[MemberOut]
    board: list[BoardOut]


class SettingsIn(BaseModel):
    approval_limits: dict[str, Any] | None = None
    rule_params: dict[str, dict[str, Any]] | None = None
    expense_categories: list[str] | None = None
    reason: str | None = None  # why the limits or parameters changed (kept in the version)


def _money(value: Any, label: str) -> str:
    try:
        amount = Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Valor inválido em {label}."
        ) from exc
    if amount <= 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"{label} deve ser maior que zero."
        )
    return str(amount.quantize(Decimal("0.01")))


async def _out(db: DbSession, condo: Condominium) -> SettingsOut:
    cutoff = invite_cutoff()
    members = (
        await db.execute(
            select(
                AppUser.name,
                AppUser.email,
                Membership.role,
                Membership.condominium_id,
                Membership.id,
                Membership.accepted_at,
                Membership.invited_at,
                Membership.expires_at,
            )
            .join(Membership, Membership.user_id == AppUser.id)
            .where(
                or_(
                    Membership.condominium_id == condo.id,
                    Membership.management_company_id == condo.management_company_id,
                ),
                # Expired invitations stay listed (as "convite vencido") so they can be resent.
                *active_membership()[:2],
            )
            .order_by(AppUser.name)
        )
    ).all()
    staff = (
        await db.execute(
            select(AppUser.name, AppUser.email, CondoAssignment.platform_role)
            .join(CondoAssignment, CondoAssignment.user_id == AppUser.id)
            .where(
                CondoAssignment.condominium_id == condo.id,
                CondoAssignment.revoked_at.is_(None),
                or_(
                    CondoAssignment.valid_until.is_(None),
                    CondoAssignment.valid_until > utcnow(),
                ),
            )
            .order_by(AppUser.name)
        )
    ).all()
    board = await db.scalars(
        select(BoardMember)
        .where(BoardMember.condominium_id == condo.id)
        .order_by(BoardMember.position)
    )
    versions = await history(db, condo.id)
    who = await user_names(db, {v.changed_by_user_id for v in versions if v.changed_by_user_id})
    return SettingsOut(
        history=[
            SettingsVersionOut(
                version=v.version,
                valid_from=v.valid_from,
                changed_by=who.get(v.changed_by_user_id) if v.changed_by_user_id else None,
                reason=v.reason,
                approval_limits=dict(v.approval_limits),
                rule_params=dict(v.rule_params),
            )
            for v in versions
        ],
        profile=ProfileOut(
            name=condo.name,
            cnpj=format_cnpj(condo.cnpj),
            units=condo.units,
            address=condo.address,
            retention_years=condo.retention_years,
            timezone=condo.timezone,
            management_company_reviews=condo.management_company_reviews,
        ),
        approval_limits=condo.approval_limits or {},
        expense_categories=condo.expense_categories or [],
        rules=[
            RuleParamsOut(
                code=r.code,
                name=r.name,
                defaults=dict(r.default_params),
                overrides=(condo.rule_params or {}).get(r.code, {}),
            )
            for r in ALL_RULES
        ],
        members=[
            MemberOut(
                id=mid if cid else None,
                name=n,
                email=e,
                role=r,
                scope="condominio" if cid else "administradora",
                status=(
                    "ativo"
                    if accepted is not None or invited is None
                    else "convite_vencido" if invited <= cutoff else "convidado"
                ),
                expires_at=expires,
            )
            for n, e, r, cid, mid, accepted, invited, expires in members
        ]
        + [MemberOut(name=n, email=e, role=r, scope="condoos") for n, e, r in staff],
        board=[
            BoardOut(
                id=b.id,
                full_name=b.full_name,
                position=b.position,
                term_start=b.term_start,
                term_end=b.term_end,
                has_login=b.user_id is not None,
            )
            for b in board
        ],
    )


@router.get("")
async def get_settings_(
    condominium_id: uuid.UUID, access: CanConfigure, db: DbSession
) -> SettingsOut:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    return await _out(db, condo)


@router.put("")
async def update_settings(
    condominium_id: uuid.UUID, body: SettingsIn, access: CanConfigure, db: DbSession
) -> SettingsOut:
    condo = await db.get(Condominium, access.condominium_id, with_for_update=True)
    assert condo is not None
    changed: list[str] = []
    before = (dict(condo.approval_limits or {}), dict(condo.rule_params or {}))
    categories_before = list(condo.expense_categories or [])
    await ensure_baseline(db, condo)
    if body.approval_limits is not None:
        limits: dict[str, Any] = {}
        if body.approval_limits.get("default") not in (None, ""):
            limits["default"] = _money(body.approval_limits["default"], "alçada padrão")
        limits["by_category"] = {
            cat: _money(v, f"alçada de {cat}")
            for cat, v in (body.approval_limits.get("by_category") or {}).items()
            if v not in (None, "")
        }
        condo.approval_limits = limits
        changed.append("approval_limits")
    if body.rule_params is not None:
        known = {r.code: r for r in ALL_RULES}
        cleaned: dict[str, dict[str, Any]] = {}
        for code, params in body.rule_params.items():
            rule = known.get(code)
            if rule is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT, f"Regra desconhecida: {code}."
                )
            for key, value in params.items():
                default = rule.default_params.get(key)
                if default is None:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_CONTENT,
                        f"Parâmetro desconhecido em {code}: {key}.",
                    )
                if isinstance(default, list):
                    if not isinstance(value, list):
                        raise HTTPException(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"{code}.{key} deve ser uma lista.",
                        )
                else:
                    try:
                        number = float(value)
                    except (TypeError, ValueError) as exc:
                        raise HTTPException(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"{code}.{key} deve ser um número.",
                        ) from exc
                    if number < 0:
                        raise HTTPException(
                            status.HTTP_422_UNPROCESSABLE_CONTENT,
                            f"{code}.{key} não pode ser negativo.",
                        )
                    value = (
                        int(number) if isinstance(default, int) and number.is_integer() else number
                    )
                cleaned.setdefault(code, {})[key] = value
        condo.rule_params = cleaned
        changed.append("rule_params")
    if body.expense_categories is not None:
        cats = sorted({c.strip().lower() for c in body.expense_categories if c.strip()})
        if not cats:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Informe ao menos uma categoria."
            )
        condo.expense_categories = cats
        changed.append("expense_categories")
    version = None
    if (dict(condo.approval_limits or {}), dict(condo.rule_params or {})) != before:
        version = (
            await record_version(db, condo, actor_user_id=access.user_id, reason=body.reason)
        ).version
    if changed:
        await record_change(
            db,
            action="settings.updated",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=access.user_id,
            condominium_id=condo.id,
            before={
                "approval_limits": before[0],
                "rule_params": before[1],
                "expense_categories": categories_before,
            },
            after={
                "approval_limits": dict(condo.approval_limits or {}),
                "rule_params": dict(condo.rule_params or {}),
                "expense_categories": list(condo.expense_categories or []),
            },
            reason=body.reason,
            setting_version=version,
            extra={"fields": changed},
        )
    await db.flush()
    return await _out(db, condo)
