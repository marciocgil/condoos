"""API response/request schemas (Pydantic v2)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MagicLinkRequest(BaseModel):
    email: EmailStr


class VerifyRequest(BaseModel):
    token: str


class MessageOut(BaseModel):
    message: str


class CondoMembershipOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    management_company_id: uuid.UUID | None
    roles: list[str]
    permissions: list[str]


class CompanyMembershipOut(BaseModel):
    id: uuid.UUID
    name: str
    roles: list[str]


class MeOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    condominiums: list[CondoMembershipOut]
    management_companies: list[CompanyMembershipOut]


class CondominiumOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    cnpj: str
    units: int
    address: str
    management_company_id: uuid.UUID | None
    approval_limits: dict[str, Any]


class ExpenseOut(ORM):
    id: uuid.UUID
    supplier_id: uuid.UUID | None
    contract_id: uuid.UUID | None
    competence: date
    issue_date: date
    due_date: date | None
    amount: Decimal
    category: str
    description: str
    invoice_number: str | None


class ContractOut(ORM):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    supplier_cnpj: str | None = None
    object: str
    scope_items: list[str]
    monthly_value: Decimal
    adjustment_index: str
    adjustment_base_month: int | None
    start_date: date
    end_date: date | None
    amendments: int = 0  # termos aditivos linked to the contract (D66)
    original_monthly_value: Decimal | None = None  # as signed; monthly_value is in force


class CompetenceOut(ORM):
    id: uuid.UUID
    month: date
    status: str


class FindingOut(ORM):
    id: uuid.UUID
    rule_code: str
    severity: str
    title: str
    explanation: str
    amount_at_risk: Decimal
    status: str
    competence: date
    ai_assisted: bool
    supplier_id: uuid.UUID | None
