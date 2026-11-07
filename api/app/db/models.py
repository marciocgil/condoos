"""SQLAlchemy models. See docs/decisions.md for deviations from the spec's data model.

Every table that holds condominium data carries ``condominium_id`` and is protected by
Row-Level Security (see migration 0001) in addition to explicit filters in the code.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import DEFAULT_TIMEZONE
from app.db.base import Base, IdTimestampMixin
from app.db.enums import (
    MEMBERSHIP_ROLES,
    AdjustmentIndex,
    BankTransactionOrigin,
    BoardPosition,
    CaseCategory,
    CaseLinkTarget,
    CaseOrigin,
    CaseSeverity,
    CaseStatus,
    ChatRole,
    CompetenceStatus,
    DecisionAction,
    DocumentOrigin,
    DocumentType,
    ExtractionStatus,
    FindingStatus,
    JobStatus,
    PlatformRole,
    ReviewRequirement,
    Severity,
    TaskStatus,
)

Json = JSON().with_variant(JSONB(), "postgresql")
EMBEDDING_DIM = 384
Money = Numeric(14, 2)


def _enum_check(column: str, enum: type[StrEnum]) -> CheckConstraint:
    values = ", ".join(f"'{v.value}'" for v in enum)
    return CheckConstraint(f"{column} IN ({values})", name=f"{column}_valid")


def _uuid_fk(target: str, *, nullable: bool = False, ondelete: str = "RESTRICT") -> Any:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True
    )


# --------------------------------------------------------------------------- tenancy / users


class ManagementCompany(IdTimestampMixin, Base):
    __tablename__ = "management_company"

    name: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)


class Condominium(IdTimestampMixin, Base):
    __tablename__ = "condominium"

    # Nullable: a professional síndico may operate without a management company (decision D3).
    management_company_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "management_company.id", nullable=True
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    units: Mapped[int] = mapped_column(Integer)
    address: Mapped[str] = mapped_column(String(300))
    # {"default": "5000.00", "by_category": {"obras": "2000.00"}}
    approval_limits: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    # {"R01": {"tolerance_pct": 1, "window_days": 45}, ...}; overrides rule defaults.
    rule_params: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    expense_categories: Mapped[list[str]] = mapped_column(Json, default=list)
    retention_years: Mapped[int] = mapped_column(Integer, default=5)
    # IANA time zone for deadlines, agenda and "today" (ADR-P07, migration 0011).
    timezone: Mapped[str] = mapped_column(
        String(64), default=DEFAULT_TIMEZONE, server_default=DEFAULT_TIMEZONE
    )
    # Whether the management company's manager may review findings (D74). Optional by design:
    # the condominium is the client and never depends on a management company (D73).
    management_company_reviews: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class AppUser(IdTimestampMixin, Base):
    # "user" is a reserved word in PostgreSQL (decision D6).
    __tablename__ = "app_user"

    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(IdTimestampMixin, Base):
    """A role either on a single condominium or on a whole management company."""

    __tablename__ = "membership"
    __table_args__ = (
        CheckConstraint(
            "role IN (" + ", ".join(f"'{r.value}'" for r in MEMBERSHIP_ROLES) + ")",
            name="role_valid",
        ),
        CheckConstraint(
            "(condominium_id IS NULL) <> (management_company_id IS NULL)",
            name="exactly_one_scope",
        ),
        CheckConstraint(
            "management_company_id IS NULL OR role IN ('gerente', 'analista')",
            name="company_scope_roles",
        ),
        UniqueConstraint("user_id", "condominium_id", "management_company_id", "role"),
    )

    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)
    management_company_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "management_company.id", nullable=True
    )
    role: Mapped[str] = mapped_column(String(20))
    # Temporary and revocable access for external participants (D77, migration 0011).
    # All NULL = permanent access, as before. A revoked row is kept (history) and can be
    # reactivated by granting the same access again.
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformRoleGrant(IdTimestampMixin, Base):
    """A CondoOS staff role (admin or reviewer). Grants no condominium by itself: access to
    each condominium needs a ``condo_assignment`` (least privilege, D77)."""

    __tablename__ = "platform_role"
    __table_args__ = (_enum_check("role", PlatformRole), UniqueConstraint("user_id", "role"))

    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    role: Mapped[str] = mapped_column(String(20))
    granted_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    reason: Mapped[str] = mapped_column(String(300))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CondoAssignment(IdTimestampMixin, Base):
    """A CondoOS staff member assigned to one condominium, with an optional end date."""

    __tablename__ = "condo_assignment"
    __table_args__ = (
        _enum_check("platform_role", PlatformRole),
        UniqueConstraint("condominium_id", "user_id", "platform_role"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    platform_role: Mapped[str] = mapped_column(String(20))
    granted_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    reason: Mapped[str] = mapped_column(String(300))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BoardMember(IdTimestampMixin, Base):
    """Síndico, subsíndico and conselheiros, whether or not they are system users (D2)."""

    __tablename__ = "board_member"
    __table_args__ = (_enum_check("position", BoardPosition),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    full_name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(20))
    term_start: Mapped[date] = mapped_column(Date)
    term_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")


class MagicLinkToken(IdTimestampMixin, Base):
    __tablename__ = "magic_link_token"

    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSession(IdTimestampMixin, Base):
    __tablename__ = "user_session"

    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- suppliers / contracts


class Supplier(IdTimestampMixin, Base):
    """Public CNPJ registry data. Shared across tenants; access goes through tenant data."""

    __tablename__ = "supplier"

    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cnae_main: Mapped[dict[str, Any] | None] = mapped_column(Json, nullable=True)
    cnae_secondary: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    registration_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    registration_status_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [{"name": "...", "cpf_masked": "***.456.789-**", "qualification": "..."}]
    partners: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # brasilapi | seed | documento (only what a fiscal document showed) | manual
    enrichment_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Last enrichment problem (e.g. "nao_encontrado"); data from earlier runs is kept.
    enrichment_error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Contract(IdTimestampMixin, Base):
    __tablename__ = "contract"
    __table_args__ = (
        _enum_check("adjustment_index", AdjustmentIndex),
        CheckConstraint(
            "adjustment_base_month IS NULL OR adjustment_base_month BETWEEN 1 AND 12",
            name="base_month_range",
        ),
        CheckConstraint(
            "billing_frequency_months IN (0, 1, 2, 3, 6, 12)", name="billing_frequency_valid"
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    supplier_id: Mapped[uuid.UUID] = _uuid_fk("supplier.id")
    object: Mapped[str] = mapped_column(String(300))
    scope_items: Mapped[list[str]] = mapped_column(Json, default=list)
    monthly_value: Mapped[Decimal] = mapped_column(Money)
    adjustment_index: Mapped[str] = mapped_column(String(10))
    # When adjustment_index is OUTRO: which one, as the contract says (e.g. "IGP-DI").
    adjustment_index_other: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adjustment_base_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Expected billing (NF) every N months from the start; 0 = on demand, no fixed billing (D70).
    billing_frequency_months: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )


class ContractAmendment(IdTimestampMixin, Base):
    """A contract amendment (termo aditivo): new value, new end date or extra scope from a date
    on (D66). The contract keeps its original terms; rules use the terms in force."""

    __tablename__ = "contract_amendment"
    __table_args__ = (UniqueConstraint("document_id"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    contract_id: Mapped[uuid.UUID] = _uuid_fk("contract.id", ondelete="CASCADE")
    document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    effective_date: Mapped[date] = mapped_column(Date)
    monthly_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    scope_items: Mapped[list[str]] = mapped_column(Json, default=list)
    description: Mapped[str] = mapped_column(String(500), default="")


# --------------------------------------------------------------------------- documents / money


class Document(IdTimestampMixin, Base):
    __tablename__ = "document"
    __table_args__ = (
        _enum_check("doc_type", DocumentType),
        _enum_check("origin", DocumentOrigin),
        _enum_check("extraction_status", ExtractionStatus),
        UniqueConstraint("condominium_id", "sha256"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    doc_type: Mapped[str] = mapped_column(String(20), default=DocumentType.OUTRO.value)
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(300))
    mime_type: Mapped[str] = mapped_column(String(100))
    origin: Mapped[str] = mapped_column(String(10))
    extraction_status: Mapped[str] = mapped_column(
        String(20), default=ExtractionStatus.PENDING.value
    )
    extracted: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    field_confidence: Mapped[dict[str, float]] = mapped_column(Json, default=dict)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    # Why the document is in the exception queue (pt-BR, shown to the analyst).
    review_reasons: Mapped[list[str]] = mapped_column(Json, default=list)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class ExtractionCorrection(IdTimestampMixin, Base):
    """A human correction of an extracted field: training data for extraction (spec §7)."""

    __tablename__ = "extraction_correction"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    document_id: Mapped[uuid.UUID] = _uuid_fk("document.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    doc_type: Mapped[str] = mapped_column(String(20))
    field_name: Mapped[str] = mapped_column(String(60))
    extracted_value: Mapped[Any] = mapped_column(Json, nullable=True)
    corrected_value: Mapped[Any] = mapped_column(Json, nullable=True)
    extracted_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    extraction_source: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Expense(IdTimestampMixin, Base):
    __tablename__ = "expense"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk("supplier.id", nullable=True)
    contract_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "contract.id", nullable=True, ondelete="SET NULL"
    )
    document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    competence: Mapped[date] = mapped_column(Date, index=True)  # always day 1 of the month
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(String(500))
    invoice_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # seed | documento | manual
    origin: Mapped[str] = mapped_column(String(15), default="manual", server_default="manual")


class ExpenseDocument(IdTimestampMixin, Base):
    """Documents behind an expense: the fiscal document, the boleto, the receipt."""

    __tablename__ = "expense_document"
    __table_args__ = (
        CheckConstraint("role IN ('fiscal', 'cobranca', 'recibo')", name="role_valid"),
        UniqueConstraint("document_id"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    expense_id: Mapped[uuid.UUID] = _uuid_fk("expense.id", ondelete="CASCADE")
    document_id: Mapped[uuid.UUID] = _uuid_fk("document.id", ondelete="CASCADE")
    role: Mapped[str] = mapped_column(String(10))


class MatchIssue(IdTimestampMixin, Base):
    """An ambiguous match that a person must resolve (spec §5.5: never pick at random)."""

    __tablename__ = "match_issue"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('pagamento_ambiguo', 'contrato_ambiguo', 'boleto_ambiguo')", name="kind_valid"
        ),
        CheckConstraint("status IN ('aberto', 'resolvido')", name="status_valid"),
        UniqueConstraint("condominium_id", "kind", "subject_id"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    kind: Mapped[str] = mapped_column(String(20))
    subject_type: Mapped[str] = mapped_column(String(20))  # expense | bank_transaction | document
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # [{"type": "expense", "id": "...", "label": "..."}]
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    description: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10), default="aberto")
    resolved_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class BankTransaction(IdTimestampMixin, Base):
    __tablename__ = "bank_transaction"
    __table_args__ = (
        _enum_check("origin", BankTransactionOrigin),
        UniqueConstraint("condominium_id", "external_id"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    posted_at: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Money)  # negative = debit
    payee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payee_document: Mapped[str | None] = mapped_column(String(14), nullable=True)
    description: Mapped[str] = mapped_column(String(300))
    origin: Mapped[str] = mapped_column(String(15))
    # Stable id from the source (FITID, CNAB nosso número, hash of the CSV line) for idempotency.
    external_id: Mapped[str] = mapped_column(String(120))
    expense_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "expense.id", nullable=True, ondelete="SET NULL"
    )


class Approval(IdTimestampMixin, Base):
    """Recorded approval of an expense (rule R12). Typed by the manager or taken from minutes."""

    __tablename__ = "approval"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    expense_id: Mapped[uuid.UUID] = _uuid_fk("expense.id", ondelete="CASCADE")
    approved_by: Mapped[str] = mapped_column(String(200))
    approved_at: Mapped[date] = mapped_column(Date)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class Competence(IdTimestampMixin, Base):
    """A condominium's accounting month; closing it produces the monthly report."""

    __tablename__ = "competence"
    __table_args__ = (
        _enum_check("status", CompetenceStatus),
        UniqueConstraint("condominium_id", "month"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    month: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default=CompetenceStatus.ABERTA.value)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    report_pdf_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_xlsx_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- findings


class Finding(IdTimestampMixin, Base):
    __tablename__ = "finding"
    __table_args__ = (
        _enum_check("severity", Severity),
        _enum_check("status", FindingStatus),
        UniqueConstraint("condominium_id", "dedupe_key"),
        Index("ix_finding_condo_competence", "condominium_id", "competence"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    rule_code: Mapped[str] = mapped_column(String(5))
    severity: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(300))
    explanation: Mapped[str] = mapped_column(Text)
    amount_at_risk: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(25))
    # [{"kind": "document|expense|bank_transaction|contract", "id": "...", "excerpt": "...",
    #   "page": 1}]
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    rule_inputs: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    competence: Mapped[date] = mapped_column(Date)
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    # "regra": deterministic text of the rule; "ia": rewritten by the model and validated.
    explanation_source: Mapped[str] = mapped_column(
        String(10), default="regra", server_default="regra"
    )
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk("supplier.id", nullable=True)
    # Same rule + same subject => same finding when the pipeline is re-run (idempotency).
    dedupe_key: Mapped[str] = mapped_column(String(200))
    # Review proportional to risk (D74, migration 0012): what the policy required and which
    # policy version decided it. ``confidence`` and ``category`` are filled by future rules.
    review_requirement: Mapped[str] = mapped_column(
        String(20), default=ReviewRequirement.NONE.value, server_default="none"
    )
    review_policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ReviewPolicy(IdTimestampMixin, Base):
    """Versioned review policy (D74). ``condominium_id`` NULL = the platform default, which
    every condominium reads; a condominium row overrides it from ``valid_from`` on. Append
    only: a change is a new version."""

    __tablename__ = "review_policy"
    __table_args__ = (UniqueConstraint("condominium_id", "version"),)

    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)
    version: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    rules: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    reason: Mapped[str] = mapped_column(String(300))


class Decision(IdTimestampMixin, Base):
    """Append-only. The application role has no UPDATE/DELETE grant on this table."""

    __tablename__ = "decision"
    __table_args__ = (_enum_check("action", DecisionAction),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    finding_id: Mapped[uuid.UUID] = _uuid_fk("finding.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    action: Mapped[str] = mapped_column(String(25))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FindingComment(IdTimestampMixin, Base):
    __tablename__ = "finding_comment"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    finding_id: Mapped[uuid.UUID] = _uuid_fk("finding.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    body: Mapped[str] = mapped_column(Text)


# --------------------------------------------------------------------------- reference / infra


class IndexValue(IdTimestampMixin, Base):
    __tablename__ = "index_value"
    __table_args__ = (UniqueConstraint("index_name", "month"),)

    index_name: Mapped[str] = mapped_column(String(10))
    month: Mapped[date] = mapped_column(Date)
    pct_change: Mapped[Decimal] = mapped_column(Numeric(9, 4))
    source: Mapped[str] = mapped_column(String(40), default="bcb_sgs")


class Job(IdTimestampMixin, Base):
    __tablename__ = "job"
    __table_args__ = (
        _enum_check("status", JobStatus),
        Index("ix_job_claim", "status", "run_after"),
    )

    job_type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    status: Mapped[str] = mapped_column(String(10), default=JobStatus.QUEUED.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)


class LlmCall(IdTimestampMixin, Base):
    __tablename__ = "llm_calls"

    purpose: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)


class ChatMessage(IdTimestampMixin, Base):
    __tablename__ = "chat_message"
    __table_args__ = (_enum_check("role", ChatRole),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    # {"tipo": "abrir_achado", "ref": "achado:<id>", "rotulo": "..."} (assistant only)
    suggested_action: Mapped[dict[str, Any] | None] = mapped_column(Json, nullable=True)


class DocumentChunk(IdTimestampMixin, Base):
    """A passage of a contract, convention, rules or minutes, for the chat's document search.

    ``embedding`` (384 dims, local multilingual model) and ``search_vector`` (Portuguese full
    text) are combined in a hybrid ranking (decision D52).
    """

    __tablename__ = "document_chunk"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("ix_document_chunk_fts", "search_vector", postgresql_using="gin"),
        Index(
            "ix_document_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    document_id: Mapped[uuid.UUID] = _uuid_fk("document.id", ondelete="CASCADE")
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    # NULL when the embedding model is disabled: the chunk is then found by full text only.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('portuguese', text)", persisted=True)
    )


class AuditLog(IdTimestampMixin, Base):
    """Append-only trail of relevant writes. Metadata holds ids only, never personal data."""

    __tablename__ = "audit_log"

    actor_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    action: Mapped[str] = mapped_column(String(60))
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


# --------------------------------------------------------------------------- cases (D75, D80)


class CaseRecord(IdTimestampMixin, Base):
    """Assunto: a situation to organise, follow and close with evidence (spec §8). Linked to
    findings and other records, never a kind of finding (D75). ``case`` is a reserved SQL
    word, hence ``case_record``."""

    __tablename__ = "case_record"
    __table_args__ = (
        _enum_check("status", CaseStatus),
        _enum_check("origin", CaseOrigin),
        _enum_check("severity", CaseSeverity),
        _enum_check("category", CaseCategory),
        UniqueConstraint("condominium_id", "number"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    number: Mapped[str] = mapped_column(String(20))  # A-2026-0001, per condominium
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20))
    origin: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30))
    owner_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    next_action: Mapped[str | None] = mapped_column(String(300), nullable=True)
    next_action_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    suspension_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolution_criterion: Mapped[str] = mapped_column(String(500))
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseEvent(IdTimestampMixin, Base):
    """Timeline of a case (FR-023). Append only, like ``decision``; details hold ids only."""

    __tablename__ = "case_event"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    case_id: Mapped[uuid.UUID] = _uuid_fk("case_record.id")
    actor_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    actor_kind: Mapped[str] = mapped_column(String(10), default="user")  # user | system | ai
    kind: Mapped[str] = mapped_column(String(30))
    from_value: Mapped[str | None] = mapped_column(String(300), nullable=True)
    to_value: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class CaseLink(IdTimestampMixin, Base):
    """N:N between a case and another record. Unlinking only fills ``unlinked_at``."""

    __tablename__ = "case_link"
    __table_args__ = (_enum_check("target_type", CaseLinkTarget),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    case_id: Mapped[uuid.UUID] = _uuid_fk("case_record.id")
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    as_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linked_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unlinked_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class CaseTask(IdTimestampMixin, Base):
    __tablename__ = "case_task"
    __table_args__ = (_enum_check("status", TaskStatus),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    case_id: Mapped[uuid.UUID] = _uuid_fk("case_record.id")
    title: Mapped[str] = mapped_column(String(200))
    assignee_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    assignee_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.ABERTA.value)
    blocked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


# Tables protected by Row-Level Security, with the column holding the tenant id.
RLS_TABLES: dict[str, str] = {
    "condominium": "id",
    "board_member": "condominium_id",
    "contract": "condominium_id",
    "document": "condominium_id",
    "expense": "condominium_id",
    "bank_transaction": "condominium_id",
    "approval": "condominium_id",
    "contract_amendment": "condominium_id",
    "competence": "condominium_id",
    "finding": "condominium_id",
    "decision": "condominium_id",
    "finding_comment": "condominium_id",
    "chat_message": "condominium_id",
    "extraction_correction": "condominium_id",
    "expense_document": "condominium_id",
    "match_issue": "condominium_id",
    "document_chunk": "condominium_id",
    "condo_assignment": "condominium_id",
    "review_policy": "condominium_id",
    "case_record": "condominium_id",
    "case_event": "condominium_id",
    "case_link": "condominium_id",
    "case_task": "condominium_id",
}

# Tables the application role may only read and insert into (never update or delete).
APPEND_ONLY_TABLES: tuple[str, ...] = ("decision", "audit_log", "review_policy", "case_event")
