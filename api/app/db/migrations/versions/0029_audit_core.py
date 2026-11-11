"""CondoOS Audit, cycle 1 (D122): bank accounts and statements, audit periods and runs,
control results of the monthly "farol", facts and evidence edges, and versioned prompts of
the agents A0–A9.

Tenant tables (RLS by ``condominium_id``):
- ``bank_account``: one account per bank/branch/number read from the statement;
- ``bank_statement``: one imported statement file, with opening and closing balances as the
  file states them (never derived);
- ``bank_transaction.bank_account_id`` / ``statement_id`` (nullable: older imports have none);
- ``audit_period`` (one per condominium and month), ``audit_run``, ``audit_stage_run``,
  ``audit_agent_run`` (agent, prompt version and hash used, inputs, outputs);
- ``audit_control_result`` (one row per control evaluation; a new evaluation supersedes the
  previous one, nothing is deleted) and ``audit_control_review`` (append only);
- ``audit_fact`` (immutable fact read from a document, with page, excerpt, extractor version
  and confidence) and ``evidence_edge`` (link between records, suggested or verified).

Platform tables (no tenant data): ``agent_prompt_version`` (immutable text, SHA-256, status),
``agent_prompt_event`` and ``prompt_test_run`` (append only).

Approved by Marcio on 11/11/2026 ("execute o Ciclo 1 diretamente no código"). Additive.
Downgrade drops the new tables and columns.

Revision ID: 0029
Revises: 0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
CONTROL_STATUSES = (
    "VALIDADO",
    "COM_RESSALVA",
    "PENDENTE",
    "DIVERGENTE",
    "NAO_AVALIADO",
    "NAO_APLICAVEL",
)
REVIEW_STATES = ("DRAFT", "NEEDS_HUMAN_REVIEW", "REVIEWED", "APPROVED_FOR_PUBLICATION")
RUN_STATUSES = ("em_execucao", "concluida", "falhou")
STAGE_STATUSES = ("aguardando", "em_execucao", "concluida", "com_pendencias", "falhou", "pulada")
PROMPT_STATUSES = ("DRAFT", "IN_REVIEW", "ACTIVE", "ARCHIVED")
EDGE_KINDS = ("sugerido", "verificado")
TENANT_TABLES = (
    "bank_account",
    "bank_statement",
    "audit_period",
    "audit_run",
    "audit_stage_run",
    "audit_agent_run",
    "audit_control_result",
    "audit_control_review",
    "audit_fact",
    "evidence_edge",
)
APPEND_ONLY_TENANT = ("audit_control_review", "audit_fact")
APPEND_ONLY_PLATFORM = ("agent_prompt_event", "prompt_test_run")


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _base(tenant: bool = True) -> list[sa.Column]:  # type: ignore[type-arg]
    cols = [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]
    if tenant:
        cols.append(sa.Column("condominium_id", sa.UUID(), nullable=False))
    return cols


def _fk(
    table: str, column: str, target: str, ondelete: str = "RESTRICT"
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def _pk(table: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}"))


def upgrade() -> None:
    j = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    money = sa.Numeric(14, 2)

    t = "bank_account"
    op.create_table(
        t,
        *_base(),
        sa.Column("bank_code", sa.String(length=10), nullable=False),
        sa.Column("branch", sa.String(length=20), nullable=False),
        sa.Column("number", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=15), server_default="corrente", nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _pk(t),
        sa.UniqueConstraint(
            "condominium_id", "bank_code", "branch", "number", name=op.f("uq_bank_account_number")
        ),
    )
    t = "bank_statement"
    op.create_table(
        t,
        *_base(),
        sa.Column("bank_account_id", sa.UUID(), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("opening_balance", money, nullable=True),
        sa.Column("opening_date", sa.Date(), nullable=True),
        sa.Column("closing_balance", money, nullable=True),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("balance_source", sa.String(length=40), nullable=True),
        sa.Column("transactions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "bank_account_id", "bank_account", "SET NULL"),
        _fk(t, "document_id", "document", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "document_id", name=op.f("uq_bank_statement_doc")),
    )
    op.add_column("bank_transaction", sa.Column("bank_account_id", sa.UUID(), nullable=True))
    op.add_column("bank_transaction", sa.Column("statement_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_bank_transaction_bank_account_id_bank_account"),
        "bank_transaction",
        "bank_account",
        ["bank_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_bank_transaction_statement_id_bank_statement"),
        "bank_transaction",
        "bank_statement",
        ["statement_id"],
        ["id"],
        ondelete="SET NULL",
    )

    t = "audit_period"
    op.create_table(
        t,
        *_base(),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "created_by", "app_user", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "competence", name=op.f("uq_audit_period_month")),
    )
    t = "audit_run"
    op.create_table(
        t,
        *_base(),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", j, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(_in("status", RUN_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "period_id", "audit_period"),
        _fk(t, "requested_by", "app_user", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("period_id", "number", name=op.f("uq_audit_run_number")),
    )
    t = "audit_stage_run"
    op.create_table(
        t,
        *_base(),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", j, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in("status", STAGE_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "run_id", "audit_run", "CASCADE"),
        _pk(t),
        sa.UniqueConstraint("run_id", "stage", name=op.f("uq_audit_stage_run_stage")),
    )
    t = "agent_prompt_version"
    op.create_table(
        t,
        *_base(tenant=False),
        sa.Column("agent_id", sa.String(length=4), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("model_role", sa.String(length=15), nullable=False),
        sa.Column("config", j, nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("change_note", sa.String(length=500), nullable=False),
        sa.Column("based_on_id", sa.UUID(), nullable=True),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_in("status", PROMPT_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "based_on_id", "agent_prompt_version", "SET NULL"),
        _fk(t, "author_user_id", "app_user", "SET NULL"),
        _fk(t, "approved_by", "app_user", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("agent_id", "version", name=op.f("uq_agent_prompt_version")),
    )
    op.create_index(
        "uq_agent_prompt_active",
        t,
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    t = "agent_prompt_event"
    op.create_table(
        t,
        *_base(tenant=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("detail", j, nullable=False),
        _fk(t, "version_id", "agent_prompt_version"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        _pk(t),
    )
    t = "prompt_test_run"
    op.create_table(
        t,
        *_base(tenant=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("results", j, nullable=False),
        _fk(t, "version_id", "agent_prompt_version"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        _pk(t),
    )
    t = "audit_agent_run"
    op.create_table(
        t,
        *_base(),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=4), nullable=False),
        sa.Column("prompt_version_id", sa.UUID(), nullable=True),
        sa.Column("runtime_prompt_sha256", sa.String(length=64), nullable=True),
        sa.Column("llm_invoked", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_refs", j, nullable=False),
        sa.Column("output", j, nullable=False),
        sa.Column("unresolved", j, nullable=False),
        sa.Column("warnings", j, nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "run_id", "audit_run", "CASCADE"),
        _fk(t, "prompt_version_id", "agent_prompt_version", "SET NULL"),
        _pk(t),
    )
    t = "audit_control_result"
    op.create_table(
        t,
        *_base(),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("control_id", sa.String(length=10), nullable=False),
        sa.Column("rule_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("review_state", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=True),
        sa.Column("tests", j, nullable=False),
        sa.Column("evidence_refs", j, nullable=False),
        sa.Column("coverage", sa.Numeric(6, 4), nullable=True),
        sa.Column("differences", money, server_default="0", nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("missing", j, nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("agents", j, nullable=False),
        sa.Column("source", sa.String(length=15), server_default="motor", nullable=False),
        sa.Column("superseded_by_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("status", CONTROL_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        sa.CheckConstraint(
            _in("review_state", REVIEW_STATES), name=op.f(f"ck_{t}_review_state_valid")
        ),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "period_id", "audit_period"),
        _fk(t, "run_id", "audit_run"),
        _fk(t, "superseded_by_id", "audit_control_result", "SET NULL"),
        _pk(t),
    )
    op.create_index(
        "ix_audit_control_result_current",
        t,
        ["period_id", "control_id"],
        postgresql_where=sa.text("superseded_by_id IS NULL"),
    )
    t = "audit_control_review"
    op.create_table(
        t,
        *_base(),
        sa.Column("result_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("from_status", sa.String(length=15), nullable=False),
        sa.Column("to_status", sa.String(length=15), nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "result_id", "audit_control_result"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        _pk(t),
    )
    t = "audit_fact"
    op.create_table(
        t,
        *_base(),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("field_name", sa.String(length=60), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", j, nullable=True),
        sa.Column("competence", sa.Date(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("extractor_version", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("verified_status", sa.String(length=15), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "document_id", "document", "CASCADE"),
        _pk(t),
        sa.UniqueConstraint(
            "condominium_id", "fingerprint", name=op.f("uq_audit_fact_fingerprint")
        ),
    )
    t = "evidence_edge"
    op.create_table(
        t,
        *_base(),
        sa.Column("from_type", sa.String(length=20), nullable=False),
        sa.Column("from_id", sa.UUID(), nullable=False),
        sa.Column("to_type", sa.String(length=20), nullable=False),
        sa.Column("to_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("amount", money, nullable=True),
        sa.CheckConstraint(_in("kind", EDGE_KINDS), name=op.f(f"ck_{t}_kind_valid")),
        _fk(t, "condominium_id", "condominium"),
        _pk(t),
        sa.UniqueConstraint(
            "condominium_id",
            "from_type",
            "from_id",
            "to_type",
            "to_id",
            name=op.f("uq_evidence_edge_pair"),
        ),
    )
    indexed = {
        "bank_statement": ("condominium_id", "bank_account_id"),
        "bank_transaction": ("bank_account_id", "statement_id"),
        "audit_run": ("period_id",),
        "audit_stage_run": ("run_id",),
        "audit_agent_run": ("run_id", "agent_id", "prompt_version_id"),
        "audit_control_result": ("period_id", "run_id"),
        "audit_control_review": ("result_id",),
        "audit_fact": ("document_id",),
        "evidence_edge": ("from_id", "to_id"),
        "agent_prompt_event": ("version_id",),
        "prompt_test_run": ("version_id",),
    }
    for table, columns in indexed.items():
        for column in columns:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
        )
    app_role, _ = _roles()
    if app_role:
        for table in (*APPEND_ONLY_TENANT, *APPEND_ONLY_PLATFORM):
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{app_role}"')


def downgrade() -> None:
    for table in (
        "evidence_edge",
        "audit_fact",
        "audit_control_review",
        "audit_control_result",
        "audit_agent_run",
        "prompt_test_run",
        "agent_prompt_event",
        "agent_prompt_version",
        "audit_stage_run",
        "audit_run",
        "audit_period",
    ):
        op.drop_table(table)
    op.drop_constraint(
        op.f("fk_bank_transaction_statement_id_bank_statement"), "bank_transaction", "foreignkey"
    )
    op.drop_constraint(
        op.f("fk_bank_transaction_bank_account_id_bank_account"), "bank_transaction", "foreignkey"
    )
    op.drop_column("bank_transaction", "statement_id")
    op.drop_column("bank_transaction", "bank_account_id")
    op.drop_table("bank_statement")
    op.drop_table("bank_account")
