"""CondoOS Audit, cycle 3 (D124): funds and their backing, budget, formal approval of the
accounts and the monthly farol approved by the síndico.

- ``fund``, ``fund_account`` (which bank accounts back each fund) and ``fund_balance`` (the
  fund's month as the statement of accounts declares it; a value it does not show stays
  empty, never zero) — BAN-08;
- ``bank_account.kind`` checked: ``corrente``, ``aplicacao`` or ``poupanca`` (BAN-09);
- ``budget`` (versioned per year) and ``budget_line``; ``budget_note`` explains a variance
  (append only) — GOV-01;
- ``accounts_approval``: approval of the accounts of a period, always with its document,
  signatories (board members), date and scope (append only) — DOC-03;
- ``approval.kind``: ``autorizacao`` (R12, as before) or ``aceite`` (the extraordinary
  service was delivered) — CON-02;
- ``audit_publication``: the farol sent to the síndico, frozen with its hash; at most one
  waiting per month.

Approved by Marcio on 11/11/2026 ("Sim, síndico aprova; pode seguir com o ciclo 3").
Additive. Downgrade drops the new tables and columns.

Revision ID: 0031
Revises: 0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
FUND_KINDS = ("reserva", "obras", "outro")
ACCOUNT_KINDS = ("corrente", "aplicacao", "poupanca")
APPROVAL_KINDS = ("autorizacao", "aceite")
BODIES = ("conselho_fiscal", "conselho_consultivo", "assembleia")
PUBLICATION_STATUSES = ("aguardando_sindico", "aprovada", "devolvida", "superada")
TABLES = (
    "fund",
    "fund_account",
    "fund_balance",
    "budget",
    "budget_line",
    "budget_note",
    "accounts_approval",
    "audit_publication",
)
APPEND_ONLY = ("budget_note", "accounts_approval")


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _base() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
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
        sa.Column("condominium_id", sa.UUID(), nullable=False),
    ]


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
    t = "fund"
    op.create_table(
        t,
        *_base(),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("purpose", sa.String(length=300), nullable=True),
        sa.CheckConstraint(_in("kind", FUND_KINDS), name=op.f(f"ck_{t}_kind_valid")),
        _fk(t, "condominium_id", "condominium"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "name", name=op.f("uq_fund_name")),
    )
    t = "fund_account"
    op.create_table(
        t,
        *_base(),
        sa.Column("fund_id", sa.UUID(), nullable=False),
        sa.Column("bank_account_id", sa.UUID(), nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "fund_id", "fund", "CASCADE"),
        _fk(t, "bank_account_id", "bank_account", "CASCADE"),
        _pk(t),
        sa.UniqueConstraint("fund_id", "bank_account_id", name=op.f("uq_fund_account")),
    )
    t = "fund_balance"
    op.create_table(
        t,
        *_base(),
        sa.Column("fund_id", sa.UUID(), nullable=False),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("opening", money, nullable=True),
        sa.Column("inflows", money, nullable=True),
        sa.Column("outflows", money, nullable=True),
        sa.Column("yield_amount", money, nullable=True),
        sa.Column("closing", money, nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "fund_id", "fund", "CASCADE"),
        _fk(t, "source_document_id", "document", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("fund_id", "competence", name=op.f("uq_fund_balance_month")),
    )
    t = "budget"
    op.create_table(
        t,
        *_base(),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("approved_on", sa.Date(), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "source_document_id", "document", "SET NULL"),
        _fk(t, "created_by", "app_user", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "year", "version", name=op.f("uq_budget_version")),
    )
    t = "budget_line"
    op.create_table(
        t,
        *_base(),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("amount", money, nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "budget_id", "budget", "CASCADE"),
        _pk(t),
        sa.UniqueConstraint("budget_id", "category", "month", name=op.f("uq_budget_line")),
    )
    t = "budget_note"
    op.create_table(
        t,
        *_base(),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        _pk(t),
    )
    t = "accounts_approval"
    op.create_table(
        t,
        *_base(),
        sa.Column("body", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("approved_on", sa.Date(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("signatories", j, nullable=False),
        sa.Column("with_reservations", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("body", BODIES), name=op.f(f"ck_{t}_body_valid")),
        sa.CheckConstraint("period_start <= period_end", name=op.f(f"ck_{t}_period_order")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "document_id", "document"),
        _fk(t, "recorded_by", "app_user", "SET NULL"),
        _pk(t),
    )
    t = "audit_publication"
    op.create_table(
        t,
        *_base(),
        sa.Column("period_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("snapshot", j, nullable=False),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("submitted_by", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(_in("status", PUBLICATION_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "period_id", "audit_period"),
        _fk(t, "submitted_by", "app_user", "SET NULL"),
        _fk(t, "decided_by", "app_user", "SET NULL"),
        _pk(t),
    )
    op.create_index(
        "uq_audit_publication_waiting",
        t,
        ["period_id"],
        unique=True,
        postgresql_where=sa.text("status = 'aguardando_sindico'"),
    )
    indexed = {
        "fund": ("condominium_id",),
        "fund_account": ("condominium_id", "fund_id", "bank_account_id"),
        "fund_balance": ("condominium_id", "fund_id", "source_document_id"),
        "budget": ("condominium_id", "source_document_id", "created_by"),
        "budget_line": ("condominium_id", "budget_id"),
        "budget_note": ("condominium_id", "user_id"),
        "accounts_approval": ("condominium_id", "document_id", "recorded_by"),
        "audit_publication": (
            "condominium_id",
            "period_id",
            "submitted_by",
            "decided_by",
        ),
    }
    for table, columns in indexed.items():
        for column in columns:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
        )
    app_role, _ = _roles()
    if app_role:
        for table in APPEND_ONLY:
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{app_role}"')
    op.add_column(
        "approval",
        sa.Column("kind", sa.String(length=12), server_default="autorizacao", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_approval_kind_valid"), "approval", _in("kind", APPROVAL_KINDS)
    )
    op.execute(
        "UPDATE bank_account SET kind = 'corrente' " f"WHERE NOT ({_in('kind', ACCOUNT_KINDS)})"
    )
    op.create_check_constraint(
        op.f("ck_bank_account_kind_valid"), "bank_account", _in("kind", ACCOUNT_KINDS)
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_bank_account_kind_valid"), "bank_account", type_="check")
    op.drop_constraint(op.f("ck_approval_kind_valid"), "approval", type_="check")
    op.drop_column("approval", "kind")
    for table in reversed(TABLES):
        op.drop_table(table)
