"""CondoOS Audit, cycle 2 (D123): units, receivable titles, utility readings, payment
allocations (N:N), persistent audit issues and the calculation memory of each control.

Unit data is internal (gerente, analista and the CondoOS team) and never carries a
resident's name: a unit is a code ("Bloco A · 101"), its fraction and nothing else; titles
and readings point to the unit. CNAB returns stop keeping the payer's name.

- ``unit``, ``receivable_title``, ``utility_reading`` (RLS);
- ``payment_allocation`` (RLS): one bank line ↔ one expense with the amount allocated;
  suggested or verified; the sums are checked by the engine (never above the line nor the
  expense);
- ``audit_issue`` and ``audit_issue_event`` (RLS, the event append only): one issue per
  condominium, control and subject, kept across months, reopened with the same id;
- ``audit_control_result.calculation``: the calculation memory (lines and per-item rows);
- ``document.doc_type`` accepts ``titulos`` (the sanitised list of titles, without names).

Approved by Marcio on 11/11/2026 ("pode seguir com o ciclo 2"; data by unit only for the
internal team, without resident names). Additive. Downgrade drops the new tables and column
and moves ``titulos`` documents to ``outro``; it clears the payer names nowhere (they are not
restored).

Revision ID: 0030
Revises: 0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
DOC_TYPES = (
    "nfse",
    "nfe",
    "boleto",
    "recibo",
    "extrato",
    "cnab_retorno",
    "contrato",
    "convencao",
    "ata",
    "outro",
    "regimento",
    "apolice",
    "balancete",
    "laudo",
    "plano_manutencao",
    "comprovante",
    "guia_tributo",
    "relatorio_adm",
    "extrato_rendimento",
)
TITLE_KINDS = (
    "ordinaria",
    "reserva",
    "obras",
    "agua",
    "gas",
    "energia",
    "multa",
    "acordo",
    "outro",
)
TITLE_STATUSES = ("aberto", "pago", "cancelado", "acordo")
UTILITIES = ("agua", "gas", "energia")
EDGE_KINDS = ("sugerido", "verificado")
ISSUE_STATUSES = ("aberta", "resolvida")
TABLES = (
    "unit",
    "receivable_title",
    "utility_reading",
    "payment_allocation",
    "audit_issue",
    "audit_issue_event",
)
DOC_CHECK = "ck_document_doc_type_valid"


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
    t = "unit"
    op.create_table(
        t,
        *_base(),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("block", sa.String(length=20), nullable=True),
        sa.Column("fraction", sa.Numeric(10, 8), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "source_document_id", "document", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "code", name=op.f("uq_unit_code")),
    )
    t = "receivable_title"
    op.create_table(
        t,
        *_base(),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("reference_competence", sa.Date(), nullable=True),
        sa.Column("kind", sa.String(length=15), nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("our_number", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("paid_amount", money, nullable=True),
        sa.Column("cancelled_at", sa.Date(), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("import_key", sa.String(length=64), nullable=False),
        sa.CheckConstraint(_in("kind", TITLE_KINDS), name=op.f(f"ck_{t}_kind_valid")),
        sa.CheckConstraint(_in("status", TITLE_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        sa.CheckConstraint("amount > 0", name=op.f(f"ck_{t}_amount_positive")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "unit_id", "unit"),
        _fk(t, "source_document_id", "document", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint("condominium_id", "import_key", name=op.f("uq_receivable_title_key")),
    )
    t = "utility_reading"
    op.create_table(
        t,
        *_base(),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("utility", sa.String(length=10), nullable=False),
        sa.Column("previous_reading", sa.Numeric(14, 3), nullable=True),
        sa.Column("current_reading", sa.Numeric(14, 3), nullable=True),
        sa.Column("consumption", sa.Numeric(14, 3), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("utility", UTILITIES), name=op.f(f"ck_{t}_utility_valid")),
        sa.CheckConstraint("consumption >= 0", name=op.f(f"ck_{t}_consumption_positive")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "unit_id", "unit"),
        _fk(t, "source_document_id", "document", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint(
            "unit_id", "competence", "utility", name=op.f("uq_utility_reading_unit")
        ),
    )
    t = "payment_allocation"
    op.create_table(
        t,
        *_base(),
        sa.Column("bank_transaction_id", sa.UUID(), nullable=False),
        sa.Column("expense_id", sa.UUID(), nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column("kind", sa.String(length=12), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.CheckConstraint(_in("kind", EDGE_KINDS), name=op.f(f"ck_{t}_kind_valid")),
        sa.CheckConstraint("amount > 0", name=op.f(f"ck_{t}_amount_positive")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "bank_transaction_id", "bank_transaction", "CASCADE"),
        _fk(t, "expense_id", "expense", "CASCADE"),
        _pk(t),
        sa.UniqueConstraint(
            "bank_transaction_id", "expense_id", name=op.f("uq_payment_allocation_pair")
        ),
    )
    t = "audit_issue"
    op.create_table(
        t,
        *_base(),
        sa.Column("control_id", sa.String(length=10), nullable=False),
        sa.Column("subject_key", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("first_competence", sa.Date(), nullable=False),
        sa.Column("last_competence", sa.Date(), nullable=False),
        sa.Column("amount", money, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("status", ISSUE_STATUSES), name=op.f(f"ck_{t}_status_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "case_id", "case_record", "SET NULL"),
        _pk(t),
        sa.UniqueConstraint(
            "condominium_id", "control_id", "subject_key", name=op.f("uq_audit_issue_subject")
        ),
    )
    t = "audit_issue_event"
    op.create_table(
        t,
        *_base(),
        sa.Column("issue_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=15), nullable=False),
        sa.Column("competence", sa.Date(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("detail", j, nullable=False),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "issue_id", "audit_issue"),
        _fk(t, "run_id", "audit_run", "SET NULL"),
        _pk(t),
    )
    op.add_column(
        "audit_control_result", sa.Column("calculation", j, server_default="[]", nullable=False)
    )
    indexed = {
        "unit": ("condominium_id",),
        "receivable_title": ("unit_id", "competence"),
        "utility_reading": ("competence",),
        "payment_allocation": ("condominium_id", "expense_id"),
        "audit_issue": ("condominium_id",),
        "audit_issue_event": ("issue_id",),
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
        op.execute(f'REVOKE UPDATE, DELETE ON "audit_issue_event" FROM "{app_role}"')
    op.drop_constraint(op.f(DOC_CHECK), "document", type_="check")
    op.create_check_constraint(
        op.f(DOC_CHECK), "document", _in("doc_type", (*DOC_TYPES, "titulos"))
    )


def downgrade() -> None:
    op.execute("UPDATE document SET doc_type = 'outro' WHERE doc_type = 'titulos'")
    op.drop_constraint(op.f(DOC_CHECK), "document", type_="check")
    op.create_check_constraint(op.f(DOC_CHECK), "document", _in("doc_type", DOC_TYPES))
    op.drop_column("audit_control_result", "calculation")
    for table in (
        "audit_issue_event",
        "audit_issue",
        "payment_allocation",
        "utility_reading",
        "receivable_title",
        "unit",
    ):
        op.drop_table(table)
