"""SQLAlchemy models. See docs/decisions.md for deviations from the spec's data model.

Every table that holds condominium data carries ``condominium_id`` and is protected by
Row-Level Security (see migration 0001) in addition to explicit filters in the code.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdTimestampMixin
from app.db.enums import (
    AdjustmentIndex,
    BankTransactionOrigin,
    BoardPosition,
    ChatRole,
    CompetenceStatus,
    DecisionAction,
    DocumentOrigin,
    DocumentType,
    ExtractionStatus,
    FindingStatus,
    JobStatus,
    Role,
    Severity,
)

Json = JSON().with_variant(JSONB(), "postgresql")
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
        _enum_check("role", Role),
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
    )

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    supplier_id: Mapped[uuid.UUID] = _uuid_fk("supplier.id")
    object: Mapped[str] = mapped_column(String(300))
    scope_items: Mapped[list[str]] = mapped_column(Json, default=list)
    monthly_value: Mapped[Decimal] = mapped_column(Money)
    adjustment_index: Mapped[str] = mapped_column(String(10))
    adjustment_base_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = _uuid_fk(
        "document.id", nullable=True, ondelete="SET NULL"
    )


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


class Decision(IdTimestampMixin, Base):
    """Append-only. The application role has no UPDATE/DELETE grant on this table."""

    __tablename__ = "decision"
    __table_args__ = (_enum_check("action", DecisionAction),)

    condominium_id: Mapped[uuid.UUID] = _uuid_fk("condominium.id")
    finding_id: Mapped[uuid.UUID] = _uuid_fk("finding.id")
    user_id: Mapped[uuid.UUID] = _uuid_fk("app_user.id")
    action: Mapped[str] = mapped_column(String(10))
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


# Tables protected by Row-Level Security, with the column holding the tenant id.
RLS_TABLES: dict[str, str] = {
    "condominium": "id",
    "board_member": "condominium_id",
    "contract": "condominium_id",
    "document": "condominium_id",
    "expense": "condominium_id",
    "bank_transaction": "condominium_id",
    "approval": "condominium_id",
    "competence": "condominium_id",
    "finding": "condominium_id",
    "decision": "condominium_id",
    "finding_comment": "condominium_id",
    "chat_message": "condominium_id",
    "extraction_correction": "condominium_id",
    "expense_document": "condominium_id",
    "match_issue": "condominium_id",
}

# Tables the application role may only read and insert into (never update or delete).
APPEND_ONLY_TABLES: tuple[str, ...] = ("decision", "audit_log")
