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
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import DEFAULT_TIMEZONE
from app.db.base import Base, IdTimestampMixin
from app.db.enums import (
    MEMBERSHIP_ROLES,
    AccountKind,
    AccountsApprovalBody,
    ActionDecisionKind,
    ActionStatus,
    AdjustmentIndex,
    ApprovalKind,
    AuditIssueStatus,
    AuditRunStatus,
    AuditStageStatus,
    BankTransactionOrigin,
    BoardPosition,
    CaseCategory,
    CaseLinkTarget,
    CaseOrigin,
    CaseSeverity,
    CaseStatus,
    ChatRole,
    CompetenceStatus,
    ComplianceApplicability,
    ComplianceCategory,
    ComplianceEventKind,
    ContractNature,
    ControlReviewState,
    ControlStatus,
    DataIssueAudience,
    DataIssueEventKind,
    DataIssueKind,
    DataIssueStatus,
    DecisionAction,
    DelegationEventKind,
    DelegationRecipientRole,
    DelegationStatus,
    DocumentOrigin,
    DocumentType,
    EdgeKind,
    EvidenceSource,
    ExtractionStatus,
    FindingStatus,
    FundKind,
    InboundMessageStatus,
    JobStatus,
    OpportunityReviewAction,
    OpportunityStatus,
    OpportunityType,
    OutboxStatus,
    PlatformRole,
    PolicyDecision,
    PromptStatus,
    PublicationStatus,
    ReminderStatus,
    ReviewRequirement,
    SavingsStage,
    Severity,
    TaskStatus,
    TitleKind,
    TitleStatus,
    Utility,
)

Json = JSON().with_variant(JSONB(), "postgresql")
EMBEDDING_DIM = 384
Money = Numeric(14, 2)


INBOUND_TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # noqa: S105 (no 0/o, 1/l/i)


def new_inbound_token() -> str:
    import secrets

    return "".join(secrets.choice(INBOUND_TOKEN_ALPHABET) for _ in range(8))


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
    # Random part of the inbound e-mail address <slug>-<token>@<domain> (D101). The síndico
    # can change it; the old address stops working.
    inbound_token: Mapped[str] = mapped_column(
        String(16), unique=True, default=lambda: new_inbound_token()
    )
    # What the building has (D113): only suggests which compliance obligations apply.
    building_profile: Mapped[dict[str, Any]] = mapped_column(
        Json, default=dict, server_default=sql_text("'{}'")
    )
    # Weekly compliance e-mail to the síndico (D113): off until the síndico turns it on.
    compliance_email_enabled: Mapped[bool] = mapped_column(
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
        _enum_check("nature", ContractNature),
        CheckConstraint(
            "supplier_id IS NOT NULL OR supplier_name IS NOT NULL", name="supplier_or_name"
        ),
        CheckConstraint(
            "(nature = 'continuo' AND monthly_value IS NOT NULL) "
            "OR (nature = 'pontual' AND total_value IS NOT NULL)",
            name="value_by_nature",
        ),
        CheckConstraint("installments IS NULL OR installments >= 1", name="installments_positive"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    # Empty when the contract has no CNPJ of the contracted party (D120): the legal name is
    # in ``supplier_name`` until the first note of that supplier fills the CNPJ.
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk("supplier.id", nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nature: Mapped[str] = mapped_column(
        String(10), default=ContractNature.CONTINUO.value, server_default="continuo"
    )
    object: Mapped[str] = mapped_column(String(300))
    scope_items: Mapped[list[str]] = mapped_column(Json, default=list)
    # Continuous contracts only; a one-off contract has ``total_value`` and ``installments``.
    monthly_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    total_value: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    installments: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # Termination terms read from the contract text, each with its excerpt (CB-060, D85).
    notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_renewal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    termination_penalty: Mapped[str | None] = mapped_column(String(300), nullable=True)
    clause_evidence: Mapped[dict[str, Any]] = mapped_column(
        Json, default=dict, server_default=sql_text("'{}'")
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
        Index(
            "ix_document_supersedes_id",
            "supersedes_id",
            unique=True,
            postgresql_where=sql_text("supersedes_id IS NOT NULL"),
        ),
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
    # Per field: {"source": "xml|texto|ia|pessoa", "page": 1, "excerpt": "...", ...} (D85).
    field_provenance: Mapped[dict[str, Any]] = mapped_column(
        Json, default=dict, server_default=sql_text("'{}'")
    )
    # A new file of the same logical document (D85); the previous one is kept.
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id", ondelete="SET NULL"), nullable=True
    )
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
    # Sent through a delegated request link (D95).
    delegation_request_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "delegation_request.id", nullable=True, ondelete="SET NULL"
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
        CheckConstraint(
            "role IN ('fiscal', 'cobranca', 'recibo', 'copia', 'pagamento')", name="role_valid"
        ),
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
    # Account and statement the transaction came from (D122); None for older imports.
    bank_account_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "bank_account.id", nullable=True, ondelete="SET NULL"
    )
    statement_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "bank_statement.id", nullable=True, ondelete="SET NULL"
    )
    expense_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "expense.id", nullable=True, ondelete="SET NULL"
    )


class Approval(IdTimestampMixin, Base):
    """Recorded approval of an expense (rule R12). Typed by the manager or taken from minutes."""

    __tablename__ = "approval"
    __table_args__ = (_enum_check("kind", ApprovalKind),)

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
    # D124: "autorizacao" (R12, before the spending) or "aceite" (the service was delivered).
    kind: Mapped[str] = mapped_column(
        String(12), default=ApprovalKind.AUTORIZACAO.value, server_default="autorizacao"
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
    __table_args__ = (Index("ix_llm_calls_purpose_prompt", "purpose", "prompt_sha256"),)

    purpose: Mapped[str] = mapped_column(String(60))
    # SHA-256 of the system prompt sent (D121): which prompt version produced this call.
    prompt_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


# --------------------------------------------------------------------------- opportunities (D76, D81)


class Opportunity(IdTimestampMixin, Base):
    """A possible benefit drawn from one or more findings (D76). Invisible to the board until a
    CondoOS reviewer approves it (``presented_at``), FR-046 / OPT-01."""

    __tablename__ = "opportunity"
    __table_args__ = (
        _enum_check("status", OpportunityStatus),
        _enum_check("opportunity_type", OpportunityType),
        UniqueConstraint("condominium_id", "number"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    number: Mapped[str] = mapped_column(String(20))  # O-2026-0001
    title: Mapped[str] = mapped_column(String(200))
    opportunity_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    contract_id: Mapped[uuid.UUID | None] = _uuid_fk("contract.id", nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk("supplier.id", nullable=True)
    recommendation: Mapped[str] = mapped_column(Text)
    operational_impact: Mapped[str] = mapped_column(String(500))
    legal_contractual_risk: Mapped[str] = mapped_column(String(10))  # baixo | medio | alto
    implementation_readiness: Mapped[str] = mapped_column(String(30))
    review_requirement: Mapped[str] = mapped_column(String(20))
    review_policy_version: Mapped[int] = mapped_column(Integer)
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class OpportunityFinding(IdTimestampMixin, Base):
    __tablename__ = "opportunity_finding"
    __table_args__ = (UniqueConstraint("opportunity_id", "finding_id"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    opportunity_id: Mapped[uuid.UUID] = _uuid_fk("opportunity.id")
    finding_id: Mapped[uuid.UUID] = _uuid_fk("finding.id")


class SavingsRecord(IdTimestampMixin, Base):
    """One dated photograph of a value at one stage (append only, never summed across stages)."""

    __tablename__ = "savings_record"
    __table_args__ = (_enum_check("stage", SavingsStage),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    opportunity_id: Mapped[uuid.UUID] = _uuid_fk("opportunity.id")
    stage: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Money)  # per period below
    periodicity: Mapped[str] = mapped_column(String(10))  # unica | mensal | anual
    annualized_amount: Mapped[Decimal] = mapped_column(Money)
    one_time_cost: Mapped[Decimal] = mapped_column(Money)
    net_amount: Mapped[Decimal] = mapped_column(Money)  # annualized − one-time cost
    baseline_period_start: Mapped[date] = mapped_column(Date)
    baseline_period_end: Mapped[date] = mapped_column(Date)
    baseline_amount: Mapped[Decimal] = mapped_column(Money)
    method_code: Mapped[str] = mapped_column(String(40))
    assumptions: Mapped[list[str]] = mapped_column(Json, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    confidence: Mapped[str] = mapped_column(String(10))  # alta | media | baixa
    quality_risks: Mapped[str] = mapped_column(Text, default="")
    version_hash: Mapped[str] = mapped_column(String(64))
    recorded_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    supersedes_id: Mapped[uuid.UUID | None] = _uuid_fk("savings_record.id", nullable=True)


class OpportunityReview(IdTimestampMixin, Base):
    """Every decision on an opportunity: internal review and the condominium's (append only)."""

    __tablename__ = "opportunity_review"
    __table_args__ = (_enum_check("action", OpportunityReviewAction),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    opportunity_id: Mapped[uuid.UUID] = _uuid_fk("opportunity.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    action: Mapped[str] = mapped_column(String(25))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    reviewed_version_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


# --------------------------------------------------------------------------- briefing (D82)


class Briefing(IdTimestampMixin, Base):
    """The day's briefing of one person in one condominium (VS-04, FR-032). Built by code
    from records only; each item points to its source. A refresh is a new version."""

    __tablename__ = "briefing"
    __table_args__ = (UniqueConstraint("condominium_id", "user_id", "local_date", "version"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id", ondelete="CASCADE")
    local_date: Mapped[date] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    partial_sources: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- actions (D83)


class ActionRequest(IdTimestampMixin, Base):
    """A request to do something outside the system (VS-05). The payload is frozen by its
    hash when approved; any change voids the approval. Nothing is sent by the system in the
    pilot: an approved action waits for a person to carry it out and record it."""

    __tablename__ = "action_request"
    __table_args__ = (
        _enum_check("status", ActionStatus),
        _enum_check("policy_decision", PolicyDecision),
        UniqueConstraint("condominium_id", "idempotency_key"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    case_id: Mapped[uuid.UUID | None] = _uuid_fk("case_record.id", nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = _uuid_fk("opportunity.id", nullable=True)
    action_type: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    cost_cap: Mapped[Decimal] = mapped_column(Money)
    policy_decision: Mapped[str] = mapped_column(String(20))
    policy_version: Mapped[int] = mapped_column(Integer)
    policy_reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    requested_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    approved_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    approval_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    execution_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ActionDecision(IdTimestampMixin, Base):
    """Every step of an action request (append only): who, what, which payload version."""

    __tablename__ = "action_decision"
    __table_args__ = (_enum_check("kind", ActionDecisionKind),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    action_request_id: Mapped[uuid.UUID] = _uuid_fk("action_request.id")
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    kind: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    policy_version: Mapped[int] = mapped_column(Integer)


class OutboxEvent(IdTimestampMixin, Base):
    """Transactional outbox: one row per approved payload. The unique idempotency key makes a
    second delivery a no-op (SEC-06, WF-01)."""

    __tablename__ = "outbox_event"
    __table_args__ = (_enum_check("status", OutboxStatus),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    action_request_id: Mapped[uuid.UUID] = _uuid_fk("action_request.id")
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=OutboxStatus.PENDENTE.value)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # What the mail server answered when a connector really sent something (D103): message id
    # and the time it was accepted. Accepted is not delivered.
    receipt: Mapped[dict[str, Any] | None] = mapped_column(Json, nullable=True)


class AutomationPause(IdTimestampMixin, Base):
    """Kill switch (FR-007, US-014): pauses one automation type, or all ("*"), in one
    condominium until resumed. History is kept: resuming fills ``resumed_at``."""

    __tablename__ = "automation_pause"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    automation_type: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(String(500))
    paused_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class CondominiumSettingsVersion(IdTimestampMixin, Base):
    """Approval limits and rule parameters as they were from ``valid_from`` on (CB-012, D85).
    Append only: a change is a new version; rules use the one in force on the audited month."""

    __tablename__ = "condominium_settings_version"
    __table_args__ = (UniqueConstraint("condominium_id", "version"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    version: Mapped[int] = mapped_column(Integer)
    approval_limits: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    rule_params: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    changed_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LaunchState(IdTimestampMixin, Base):
    """The human choices of the Launch journey (ADR-L01, D89): the first goal, steps put off
    for later and whether the journey card was dismissed. Milestones and readiness are never
    stored: they are computed from the data every time (``app/launch``)."""

    __tablename__ = "launch_state"
    __table_args__ = (
        UniqueConstraint("condominium_id"),
        CheckConstraint(
            "goal IS NULL OR goal IN ('economizar', 'pendencias', 'fornecedores', 'panorama')",
            name="goal_valid",
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    goal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # {"step key": "YYYY-MM-DD"}: hidden from the next steps until that date.
    postponed: Mapped[dict[str, Any]] = mapped_column(
        Json, default=dict, server_default=sql_text("'{}'")
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class DataIssue(IdTimestampMixin, Base):
    """A conflict between documents (D93, ADR-L05): two sources say different things about
    the same record. Not a finding (it accuses nobody) and not a case (it can be linked to
    one). While open, what depends on the record is partial and actions with the supplier
    are refused by the policy."""

    __tablename__ = "data_issue"
    __table_args__ = (
        _enum_check("kind", DataIssueKind),
        _enum_check("status", DataIssueStatus),
        _enum_check("audiencia", DataIssueAudience),
        UniqueConstraint("condominium_id", "dedupe_key"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(15), default=DataIssueStatus.ABERTO.value)
    subject_type: Mapped[str] = mapped_column(String(20))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk("supplier.id", nullable=True)
    field: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    # One item per side: {"document_id", "label", "value", "page", "excerpt"}.
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    capabilities: Mapped[list[str]] = mapped_column(Json, default=list)
    amount_at_stake: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    detector: Mapped[str] = mapped_column(String(60))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    resolution: Mapped[dict[str, Any] | None] = mapped_column(Json, nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audiencia: Mapped[str] = mapped_column(
        String(15), default=DataIssueAudience.CONDOMINIO.value, server_default="condominio"
    )


class DataIssueEvent(IdTimestampMixin, Base):
    """The history of a data issue (append only, like ``case_event``)."""

    __tablename__ = "data_issue_event"
    __table_args__ = (_enum_check("kind", DataIssueEventKind),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    issue_id: Mapped[uuid.UUID] = _uuid_fk("data_issue.id")
    kind: Mapped[str] = mapped_column(String(15))
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class DelegationRequest(IdTimestampMixin, Base):
    """A request for documents to someone without a login (D95, ADR-L04). The CondoOS makes
    the link and the text; the síndico sends them through their own channel. The recipient
    is kept by name and role only: no e-mail or phone (nothing is sent by the system)."""

    __tablename__ = "delegation_request"
    __table_args__ = (
        _enum_check("status", DelegationStatus),
        _enum_check("recipient_role", DelegationRecipientRole),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    prepared_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    authorized_by_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_name: Mapped[str] = mapped_column(String(200))
    recipient_role: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(Text, default="")
    # [{"key", "label", "kind", "contract_id"?, "competence"?, "attended_at"?, "attended_by"?}]
    items: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=DelegationStatus.RASCUNHO.value)
    case_id: Mapped[uuid.UUID | None] = _uuid_fk("case_record.id", nullable=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DelegationLink(IdTimestampMixin, Base):
    """The upload link of a request: only the SHA-256 of the token is stored."""

    __tablename__ = "delegation_link"
    __table_args__ = (UniqueConstraint("token_hash"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    request_id: Mapped[uuid.UUID] = _uuid_fk("delegation_request.id")
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_files: Mapped[int] = mapped_column(Integer, default=30)
    files_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DelegationEvent(IdTimestampMixin, Base):
    """History of a request (append only). External uploads have no user; ids only."""

    __tablename__ = "delegation_event"
    __table_args__ = (_enum_check("kind", DelegationEventKind),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    request_id: Mapped[uuid.UUID] = _uuid_fk("delegation_request.id")
    kind: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class InboundMessage(IdTimestampMixin, Base):
    """One inbound e-mail and what became of it (D101, LB-051). Append only. No subject, body
    or full sender address: the sender's domain and counts only. ``condominium_id`` is null
    when the address matched no condominium (such rows are invisible to the app role)."""

    __tablename__ = "inbound_message"
    __table_args__ = (_enum_check("status", InboundMessageStatus),)

    condominium_id: Mapped[uuid.UUID | None] = _uuid_fk("condominium.id", nullable=True)
    message_hash: Mapped[str] = mapped_column(String(64), unique=True)
    sender_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    attachments: Mapped[int] = mapped_column(Integer, default=0)
    documents: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    refused: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[list[str]] = mapped_column(Json, default=list)


class ComplianceObligation(IdTimestampMixin, Base):
    """Something the condominium must keep valid (AVCB, insurance, inspections...), D112.

    Applicability and periodicity are decided by a person; the catalogue only suggests.
    The situation (in force, expiring, expired...) is computed on read, never stored."""

    __tablename__ = "compliance_obligation"
    __table_args__ = (
        _enum_check("category", ComplianceCategory),
        _enum_check("applicability", ComplianceApplicability),
        UniqueConstraint("condominium_id", "catalog_key", name="uq_compliance_obligation_catalog"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    catalog_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    suggested_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    periodicity_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_days: Mapped[int] = mapped_column(Integer, default=60)
    supplier_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "supplier.id", nullable=True, ondelete="SET NULL"
    )
    responsible: Mapped[str | None] = mapped_column(String(200), nullable=True)
    applicability: Mapped[str] = mapped_column(
        String(20), default=ComplianceApplicability.A_VALIDAR.value
    )
    validated_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class ComplianceEvidence(IdTimestampMixin, Base):
    """A document and/or dates proving an obligation (append only; the latest row wins)."""

    __tablename__ = "compliance_evidence"
    __table_args__ = (_enum_check("source", EvidenceSource),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    obligation_id: Mapped[uuid.UUID] = _uuid_fk("compliance_obligation.id")
    document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    issued_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(10))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")


class ComplianceEvent(IdTimestampMixin, Base):
    """History of an obligation (append only). Ids and codes only."""

    __tablename__ = "compliance_event"
    __table_args__ = (_enum_check("kind", ComplianceEventKind),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    obligation_id: Mapped[uuid.UUID] = _uuid_fk("compliance_obligation.id")
    kind: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    payload: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class ComplianceReminder(IdTimestampMixin, Base):
    """One weekly compliance e-mail to one síndico (D113). Append only; ids, week and counts
    only (no address, no content)."""

    __tablename__ = "compliance_reminder"
    __table_args__ = (
        _enum_check("status", ReminderStatus),
        UniqueConstraint("condominium_id", "user_id", "week", name="uq_compliance_reminder_week"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    week: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))
    items: Mapped[int] = mapped_column(Integer, default=0)
    message_id: Mapped[str | None] = mapped_column(String(300), nullable=True)


# Tables protected by Row-Level Security, with the column holding the tenant id.
# --------------------------------------------------------------------------- CondoOS Audit


class BankAccount(IdTimestampMixin, Base):
    """A bank account of the condominium, as the statement identifies it (D122)."""

    __tablename__ = "bank_account"
    __table_args__ = (
        UniqueConstraint(
            "condominium_id", "bank_code", "branch", "number", name="uq_bank_account_number"
        ),
        _enum_check("kind", AccountKind),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    bank_code: Mapped[str] = mapped_column(String(10))
    branch: Mapped[str] = mapped_column(String(20))
    number: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(120))
    # D124: an investment account has its own statement (BAN-09).
    kind: Mapped[str] = mapped_column(String(15), default="corrente", server_default="corrente")


class BankStatement(IdTimestampMixin, Base):
    """One imported statement file. Balances are kept only as the file states them; a balance
    the file does not show stays empty (never derived, never zero)."""

    __tablename__ = "bank_statement"
    __table_args__ = (
        UniqueConstraint("condominium_id", "document_id", name="uq_bank_statement_doc"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    bank_account_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "bank_account.id", nullable=True, ondelete="SET NULL"
    )
    document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    opening_balance: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    opening_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_balance: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    balance_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    transactions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    format: Mapped[str] = mapped_column(String(10))


class AuditPeriod(IdTimestampMixin, Base):
    __tablename__ = "audit_period"
    __table_args__ = (
        UniqueConstraint("condominium_id", "competence", name="uq_audit_period_month"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    competence: Mapped[date] = mapped_column(Date)  # day 1 of the month
    created_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class AuditRun(IdTimestampMixin, Base):
    __tablename__ = "audit_run"
    __table_args__ = (
        _enum_check("status", AuditRunStatus),
        UniqueConstraint("period_id", "number", name="uq_audit_run_number"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    period_id: Mapped[uuid.UUID] = _uuid_fk("audit_period.id")
    number: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15))
    requested_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditStageRun(IdTimestampMixin, Base):
    __tablename__ = "audit_stage_run"
    __table_args__ = (
        _enum_check("status", AuditStageStatus),
        UniqueConstraint("run_id", "stage", name="uq_audit_stage_run_stage"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    run_id: Mapped[uuid.UUID] = _uuid_fk("audit_run.id", ondelete="CASCADE")
    stage: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentPromptVersion(IdTimestampMixin, Base):
    """An immutable version of an agent's prompt (D122). Only the status and the approval
    and activation stamps change; the text never does."""

    __tablename__ = "agent_prompt_version"
    __table_args__ = (
        _enum_check("status", PromptStatus),
        UniqueConstraint("agent_id", "version", name="uq_agent_prompt_version"),
        Index(
            "uq_agent_prompt_active",
            "agent_id",
            unique=True,
            postgresql_where=sql_text("status = 'ACTIVE'"),
        ),
    )

    agent_id: Mapped[str] = mapped_column(String(4))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    model_role: Mapped[str] = mapped_column(String(15))
    config: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    source: Mapped[str] = mapped_column(String(200))
    change_note: Mapped[str] = mapped_column(String(500))
    based_on_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "agent_prompt_version.id", nullable=True, ondelete="SET NULL"
    )
    author_user_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    approved_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentPromptEvent(IdTimestampMixin, Base):
    """History of a prompt version (append only)."""

    __tablename__ = "agent_prompt_event"

    version_id: Mapped[uuid.UUID] = _uuid_fk("agent_prompt_version.id")
    kind: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    detail: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class PromptTestRun(IdTimestampMixin, Base):
    """A sandbox test of a prompt version (append only)."""

    __tablename__ = "prompt_test_run"

    version_id: Mapped[uuid.UUID] = _uuid_fk("agent_prompt_version.id")
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    passed: Mapped[bool] = mapped_column(Boolean)
    results: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)


class AuditAgentRun(IdTimestampMixin, Base):
    """One agent's work in an audit run: which prompt version (and its runtime hash) governed
    it, whether the model was actually called, inputs, outputs and what stayed unresolved."""

    __tablename__ = "audit_agent_run"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    run_id: Mapped[uuid.UUID] = _uuid_fk("audit_run.id", ondelete="CASCADE")
    stage: Mapped[int] = mapped_column(Integer)
    agent_id: Mapped[str] = mapped_column(String(4))
    prompt_version_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "agent_prompt_version.id", nullable=True, ondelete="SET NULL"
    )
    runtime_prompt_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_invoked: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    input_refs: Mapped[list[Any]] = mapped_column(Json, default=list)
    output: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    unresolved: Mapped[list[Any]] = mapped_column(Json, default=list)
    warnings: Mapped[list[Any]] = mapped_column(Json, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditControlResult(IdTimestampMixin, Base):
    """One evaluation of one control in one month. A new evaluation (new run or a person's
    review) supersedes the previous row; nothing is deleted or rewritten."""

    __tablename__ = "audit_control_result"
    __table_args__ = (
        _enum_check("status", ControlStatus),
        _enum_check("review_state", ControlReviewState),
        Index(
            "ix_audit_control_result_current",
            "period_id",
            "control_id",
            postgresql_where=sql_text("superseded_by_id IS NULL"),
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    period_id: Mapped[uuid.UUID] = _uuid_fk("audit_period.id")
    run_id: Mapped[uuid.UUID] = _uuid_fk("audit_run.id")
    control_id: Mapped[str] = mapped_column(String(10))
    rule_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15))
    review_state: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tests: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    evidence_refs: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    coverage: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    differences: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    rationale: Mapped[str] = mapped_column(Text)
    missing: Mapped[list[str]] = mapped_column(Json, default=list)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    agents: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    # Calculation memory (D123): {"label", "value", "formula"} lines and per-item rows.
    calculation: Mapped[list[dict[str, Any]]] = mapped_column(
        Json, default=list, server_default=sql_text("'[]'")
    )
    source: Mapped[str] = mapped_column(String(15), default="motor", server_default="motor")
    superseded_by_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "audit_control_result.id", nullable=True, ondelete="SET NULL"
    )


class AuditControlReview(IdTimestampMixin, Base):
    """A person's review of a control result (append only)."""

    __tablename__ = "audit_control_review"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    result_id: Mapped[uuid.UUID] = _uuid_fk("audit_control_result.id")
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    from_status: Mapped[str] = mapped_column(String(15))
    to_status: Mapped[str] = mapped_column(String(15))


class AuditFact(IdTimestampMixin, Base):
    """An immutable fact read from a document (A2): raw and normalised value, page, excerpt,
    method, extractor version and confidence. A new reading is a new row."""

    __tablename__ = "audit_fact"
    __table_args__ = (
        UniqueConstraint("condominium_id", "fingerprint", name="uq_audit_fact_fingerprint"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    document_id: Mapped[uuid.UUID] = _uuid_fk("document.id", ondelete="CASCADE")
    field_name: Mapped[str] = mapped_column(String(60))
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[Any] = mapped_column(Json, nullable=True)
    competence: Mapped[date | None] = mapped_column(Date, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(20))
    extractor_version: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    verified_status: Mapped[str] = mapped_column(String(15))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )
    fingerprint: Mapped[str] = mapped_column(String(64))


class EvidenceEdge(IdTimestampMixin, Base):
    """A link between two records (A3/A4): suggested or verified, with method and reason."""

    __tablename__ = "evidence_edge"
    __table_args__ = (
        _enum_check("kind", EdgeKind),
        UniqueConstraint(
            "condominium_id",
            "from_type",
            "from_id",
            "to_type",
            "to_id",
            name="uq_evidence_edge_pair",
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    from_type: Mapped[str] = mapped_column(String(20))
    from_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    to_type: Mapped[str] = mapped_column(String(20))
    to_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    reason: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)


class Unit(IdTimestampMixin, Base):
    """A unit of the condominium (D123): a code and its fraction, never a resident's name.
    Internal data: gerente, analista and the CondoOS team."""

    __tablename__ = "unit"
    __table_args__ = (UniqueConstraint("condominium_id", "code", name="uq_unit_code"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    code: Mapped[str] = mapped_column(String(40))
    block: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fraction: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )


class ReceivableTitle(IdTimestampMixin, Base):
    """A charge to a unit (boleto): competence, kind, amount, due date, payment."""

    __tablename__ = "receivable_title"
    __table_args__ = (
        _enum_check("kind", TitleKind),
        _enum_check("status", TitleStatus),
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("condominium_id", "import_key", name="uq_receivable_title_key"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    unit_id: Mapped[uuid.UUID] = _uuid_fk("unit.id")
    competence: Mapped[date] = mapped_column(Date)
    # Month of the consumption a utility charge refers to (often the previous month).
    reference_competence: Mapped[date | None] = mapped_column(Date, nullable=True)
    kind: Mapped[str] = mapped_column(String(15))
    amount: Mapped[Decimal] = mapped_column(Money)
    due_date: Mapped[date] = mapped_column(Date)
    our_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(12))
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    cancelled_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    import_key: Mapped[str] = mapped_column(String(64))


class UtilityReading(IdTimestampMixin, Base):
    __tablename__ = "utility_reading"
    __table_args__ = (
        _enum_check("utility", Utility),
        CheckConstraint("consumption >= 0", name="consumption_positive"),
        UniqueConstraint("unit_id", "competence", "utility", name="uq_utility_reading_unit"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    unit_id: Mapped[uuid.UUID] = _uuid_fk("unit.id")
    competence: Mapped[date] = mapped_column(Date)
    utility: Mapped[str] = mapped_column(String(10))
    previous_reading: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    current_reading: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    consumption: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )


class PaymentAllocation(IdTimestampMixin, Base):
    """N:N between bank lines and expenses, with the amount (D123). The engine never lets the
    allocations exceed the line or the expense."""

    __tablename__ = "payment_allocation"
    __table_args__ = (
        _enum_check("kind", EdgeKind),
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("bank_transaction_id", "expense_id", name="uq_payment_allocation_pair"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    bank_transaction_id: Mapped[uuid.UUID] = _uuid_fk("bank_transaction.id", ondelete="CASCADE")
    expense_id: Mapped[uuid.UUID] = _uuid_fk("expense.id", ondelete="CASCADE")
    amount: Mapped[Decimal] = mapped_column(Money)
    kind: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(300))


class AuditIssue(IdTimestampMixin, Base):
    """One open point of the audit, kept across months (same id when it comes back)."""

    __tablename__ = "audit_issue"
    __table_args__ = (
        _enum_check("status", AuditIssueStatus),
        UniqueConstraint(
            "condominium_id", "control_id", "subject_key", name="uq_audit_issue_subject"
        ),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    control_id: Mapped[str] = mapped_column(String(10))
    subject_key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(10))
    first_competence: Mapped[date] = mapped_column(Date)
    last_competence: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    case_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "case_record.id", nullable=True, ondelete="SET NULL"
    )


class AuditIssueEvent(IdTimestampMixin, Base):
    """History of an audit issue (append only)."""

    __tablename__ = "audit_issue_event"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    issue_id: Mapped[uuid.UUID] = _uuid_fk("audit_issue.id")
    kind: Mapped[str] = mapped_column(String(15))
    competence: Mapped[date] = mapped_column(Date)
    run_id: Mapped[uuid.UUID | None] = _uuid_fk("audit_run.id", nullable=True, ondelete="SET NULL")
    detail: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


# ----------------------------------------------------------------- CondoOS Audit, cycle 3 (D124)


class Fund(IdTimestampMixin, Base):
    """A fund of the condominium (reserve, works). Its balance must be backed by its own
    accounts: a positive balance in the consolidated account is not segregated backing."""

    __tablename__ = "fund"
    __table_args__ = (
        _enum_check("kind", FundKind),
        UniqueConstraint("condominium_id", "name", name="uq_fund_name"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))
    purpose: Mapped[str | None] = mapped_column(String(300), nullable=True)


class FundAccount(IdTimestampMixin, Base):
    """A bank account that backs a fund (several funds may share one account)."""

    __tablename__ = "fund_account"
    __table_args__ = (UniqueConstraint("fund_id", "bank_account_id", name="uq_fund_account"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    fund_id: Mapped[uuid.UUID] = _uuid_fk("fund.id", ondelete="CASCADE")
    bank_account_id: Mapped[uuid.UUID] = _uuid_fk("bank_account.id", ondelete="CASCADE")


class FundBalance(IdTimestampMixin, Base):
    """A fund's movement in a month as the statement of accounts declares it. A value the
    statement does not show stays empty (never zero)."""

    __tablename__ = "fund_balance"
    __table_args__ = (UniqueConstraint("fund_id", "competence", name="uq_fund_balance_month"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    fund_id: Mapped[uuid.UUID] = _uuid_fk("fund.id", ondelete="CASCADE")
    competence: Mapped[date] = mapped_column(Date)
    opening: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    inflows: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    outflows: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    yield_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    closing: Mapped[Decimal] = mapped_column(Money)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )


class Budget(IdTimestampMixin, Base):
    """The approved budget of a year. A new import is a new version; the latest is used."""

    __tablename__ = "budget"
    __table_args__ = (
        UniqueConstraint("condominium_id", "year", "version", name="uq_budget_version"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    year: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    approved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )
    file_sha256: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class BudgetLine(IdTimestampMixin, Base):
    __tablename__ = "budget_line"
    __table_args__ = (UniqueConstraint("budget_id", "category", "month", name="uq_budget_line"),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    budget_id: Mapped[uuid.UUID] = _uuid_fk("budget.id", ondelete="CASCADE")
    category: Mapped[str] = mapped_column(String(60))
    month: Mapped[date] = mapped_column(Date)  # day 1
    amount: Mapped[Decimal] = mapped_column(Money)


class BudgetNote(IdTimestampMixin, Base):
    """A person's explanation of a budget variance in a month (append only)."""

    __tablename__ = "budget_note"

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    competence: Mapped[date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(60))
    text: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = _uuid_fk("app_user.id", nullable=True, ondelete="SET NULL")


class AccountsApproval(IdTimestampMixin, Base):
    """The formal approval of the accounts of a period (DOC-03), always with its document:
    who signed (board members, never residents), when, what it covers (append only)."""

    __tablename__ = "accounts_approval"
    __table_args__ = (
        _enum_check("body", AccountsApprovalBody),
        CheckConstraint("period_start <= period_end", name="period_order"),
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    body: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    approved_on: Mapped[date] = mapped_column(Date)
    document_id: Mapped[uuid.UUID] = _uuid_fk("document.id")
    signatories: Mapped[list[dict[str, Any]]] = mapped_column(Json, default=list)
    with_reservations: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )


class AuditPublication(IdTimestampMixin, Base):
    """The month's farol sent to the síndico (D124). The snapshot is frozen with its hash;
    the síndico approves the version seen, and a new result after sending supersedes it."""

    __tablename__ = "audit_publication"
    __table_args__ = (_enum_check("status", PublicationStatus),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    period_id: Mapped[uuid.UUID] = _uuid_fk("audit_period.id")
    status: Mapped[str] = mapped_column(String(20))
    snapshot: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    snapshot_sha256: Mapped[str] = mapped_column(String(64))
    submitted_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = _uuid_fk(
        "app_user.id", nullable=True, ondelete="SET NULL"
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    "opportunity": "condominium_id",
    "opportunity_finding": "condominium_id",
    "savings_record": "condominium_id",
    "opportunity_review": "condominium_id",
    "briefing": "condominium_id",
    "action_request": "condominium_id",
    "action_decision": "condominium_id",
    "outbox_event": "condominium_id",
    "automation_pause": "condominium_id",
    "condominium_settings_version": "condominium_id",
    "launch_state": "condominium_id",
    "data_issue": "condominium_id",
    "data_issue_event": "condominium_id",
    "delegation_request": "condominium_id",
    "delegation_link": "condominium_id",
    "delegation_event": "condominium_id",
    "inbound_message": "condominium_id",
    "compliance_obligation": "condominium_id",
    "compliance_evidence": "condominium_id",
    "compliance_event": "condominium_id",
    "compliance_reminder": "condominium_id",
    "bank_account": "condominium_id",
    "bank_statement": "condominium_id",
    "audit_period": "condominium_id",
    "audit_run": "condominium_id",
    "audit_stage_run": "condominium_id",
    "audit_agent_run": "condominium_id",
    "audit_control_result": "condominium_id",
    "audit_control_review": "condominium_id",
    "audit_fact": "condominium_id",
    "evidence_edge": "condominium_id",
    "unit": "condominium_id",
    "receivable_title": "condominium_id",
    "utility_reading": "condominium_id",
    "payment_allocation": "condominium_id",
    "audit_issue": "condominium_id",
    "audit_issue_event": "condominium_id",
    "fund": "condominium_id",
    "fund_account": "condominium_id",
    "fund_balance": "condominium_id",
    "budget": "condominium_id",
    "budget_line": "condominium_id",
    "budget_note": "condominium_id",
    "accounts_approval": "condominium_id",
    "audit_publication": "condominium_id",
}

# Tables the application role may only read and insert into (never update or delete).
APPEND_ONLY_TABLES: tuple[str, ...] = (
    "decision",
    "audit_log",
    "review_policy",
    "case_event",
    "savings_record",
    "opportunity_review",
    "action_decision",
    "condominium_settings_version",
    "data_issue_event",
    "delegation_event",
    "inbound_message",
    "compliance_evidence",
    "compliance_event",
    "compliance_reminder",
    "audit_control_review",
    "audit_fact",
    "agent_prompt_event",
    "prompt_test_run",
    "audit_issue_event",
    "budget_note",
    "accounts_approval",
)
