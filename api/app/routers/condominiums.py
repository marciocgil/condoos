"""Read endpoints scoped to one condominium.

Every query filters by ``condominium_id`` explicitly; Row-Level Security is the second layer.
"""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, require
from app.auth.rbac import CondoAccess, Permission
from app.db.models import Competence, Condominium, Contract, Expense, Supplier
from app.db.session import DbSession
from app.routers.schemas import (
    CompetenceOut,
    CondominiumOut,
    ContractOut,
    ExpenseOut,
)
from app.rules.contracts import amendments_by_contract, billed_totals, terms_at

router = APIRouter(prefix="/condominiums", tags=["condominiums"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
Db = DbSession


def _parse_month(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Use o formato AAAA-MM para a competência."
        ) from exc


@router.get("")
async def list_condominiums(db: Db, principal: CurrentPrincipal) -> list[CondominiumOut]:
    rows = await db.scalars(
        select(Condominium)
        .where(Condominium.id.in_(principal.condominium_ids))
        .order_by(Condominium.name)
    )
    return [CondominiumOut.model_validate(c) for c in rows]


@router.get("/{condominium_id}")
async def get_condominium(condominium_id: uuid.UUID, access: CanView, db: Db) -> CondominiumOut:
    condo = await db.scalar(select(Condominium).where(Condominium.id == access.condominium_id))
    if condo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")
    return CondominiumOut.model_validate(condo)


@router.get("/{condominium_id}/competences")
async def list_competences(
    condominium_id: uuid.UUID, access: CanView, db: Db
) -> list[CompetenceOut]:
    rows = await db.scalars(
        select(Competence)
        .where(Competence.condominium_id == access.condominium_id)
        .order_by(Competence.month.desc())
    )
    return [CompetenceOut.model_validate(r) for r in rows]


@router.get("/{condominium_id}/expenses")
async def list_expenses(
    condominium_id: uuid.UUID,
    access: CanView,
    db: Db,
    competence: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> list[ExpenseOut]:
    stmt = select(Expense).where(Expense.condominium_id == access.condominium_id)
    month = _parse_month(competence)
    if month is not None:
        stmt = stmt.where(Expense.competence == month)
    rows = await db.scalars(stmt.order_by(Expense.issue_date, Expense.id))
    return [ExpenseOut.model_validate(r) for r in rows]


@router.get("/{condominium_id}/contracts")
async def list_contracts(condominium_id: uuid.UUID, access: CanView, db: Db) -> list[ContractOut]:
    rows = await db.execute(
        select(Contract, Supplier.legal_name, Supplier.cnpj)
        .outerjoin(Supplier, Supplier.id == Contract.supplier_id)
        .where(Contract.condominium_id == access.condominium_id)
        .order_by(Contract.end_date.nulls_last(), Contract.object)
    )
    rows_list = list(rows)
    amendments = await amendments_by_contract(db, [c.id for c, _, _ in rows_list])
    billed = await billed_totals(db, [c.id for c, _, _ in rows_list if c.nature == "pontual"])
    today = date.today().replace(day=1)
    out = []
    for contract, supplier_name, supplier_cnpj in rows_list:
        item = ContractOut.model_validate(contract)
        item.supplier_name = supplier_name or contract.supplier_name
        item.supplier_cnpj = supplier_cnpj
        mine = amendments.get(contract.id, [])
        item.original_monthly_value = contract.monthly_value
        item.monthly_value, _ = terms_at(contract, mine, today)  # value in force (D66)
        item.amendments = len(mine)
        item.billed_total = billed.get(contract.id)
        out.append(item)
    return out
