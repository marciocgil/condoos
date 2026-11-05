"""Per-condominium settings (spec §9): approval limits, rule parameters, expense categories
and members. Every change is recorded in audit_log (keys only, never values of people)."""

import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.db.models import AppUser, BoardMember, Condominium, Membership
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
    name: str
    email: str
    role: str
    scope: str  # condominio | administradora


class BoardOut(BaseModel):
    full_name: str
    position: str


class SettingsOut(BaseModel):
    approval_limits: dict[str, Any]
    expense_categories: list[str]
    rules: list[RuleParamsOut]
    members: list[MemberOut]
    board: list[BoardOut]


class SettingsIn(BaseModel):
    approval_limits: dict[str, Any] | None = None
    rule_params: dict[str, dict[str, Any]] | None = None
    expense_categories: list[str] | None = None


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
    members = (
        await db.execute(
            select(AppUser.name, AppUser.email, Membership.role, Membership.condominium_id)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(
                or_(
                    Membership.condominium_id == condo.id,
                    Membership.management_company_id == condo.management_company_id,
                )
            )
            .order_by(AppUser.name)
        )
    ).all()
    board = await db.scalars(
        select(BoardMember)
        .where(BoardMember.condominium_id == condo.id)
        .order_by(BoardMember.position)
    )
    return SettingsOut(
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
            MemberOut(name=n, email=e, role=r, scope="condominio" if cid else "administradora")
            for n, e, r, cid in members
        ],
        board=[BoardOut(full_name=b.full_name, position=b.position) for b in board],
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
    if changed:
        await record_audit(
            db,
            action="settings.updated",
            object_type="condominium",
            object_id=condo.id,
            actor_user_id=access.user_id,
            condominium_id=condo.id,
            details={"fields": changed},
        )
    await db.flush()
    return await _out(db, condo)
