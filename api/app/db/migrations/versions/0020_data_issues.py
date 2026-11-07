"""CondoOS Launch LF3-b (D93, ADR-L05): conflicts between documents.

- ``data_issue`` (RLS): a conflict, its two sides with excerpts, the capabilities it makes
  partial, its status and resolution (prevailing version, reason, who).
- ``data_issue_event`` (RLS, append only like ``case_event``): its history.
- ``case_link.target_type`` accepts ``data_issue``: a conflict can be linked to a case (D75).

Approved by Marcio on 07/11/2026 (Q-L05). Additive. Downgrade removes case links that point
to a data issue, drops both tables and restores the previous CHECK of ``case_link``.

Revision ID: 0020
Revises: 0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
KINDS = ("conflito_documentos", "duplicidade_suspeita", "dado_vencido")
STATUSES = ("aberto", "resolvido", "descartado")
EVENT_KINDS = ("detectado", "redetectado", "resolvido", "descartado", "superado", "reaberto")
TARGETS = ("finding", "opportunity", "document", "contract", "supplier", "expense", "case")
CASE_LINK_CHECK = "ck_case_link_target_type_valid"


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def _base(table: str) -> list[sa.Column]:  # type: ignore[type-arg]
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
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "data_issue",
        *_base("data_issue"),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("field", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("capabilities", json_type, nullable=False),
        sa.Column("amount_at_stake", sa.Numeric(14, 2), nullable=True),
        sa.Column("detector", sa.String(length=60), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("resolution", json_type, nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"kind IN ({_in(KINDS)})", name=op.f("ck_data_issue_kind_valid")),
        sa.CheckConstraint(f"status IN ({_in(STATUSES)})", name=op.f("ck_data_issue_status_valid")),
        _fk("data_issue", "condominium_id", "condominium"),
        _fk("data_issue", "supplier_id", "supplier"),
        _fk("data_issue", "resolved_by_user_id", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_issue")),
        sa.UniqueConstraint(
            "condominium_id", "dedupe_key", name=op.f("uq_data_issue_condominium_id")
        ),
    )
    op.create_table(
        "data_issue_event",
        *_base("data_issue_event"),
        sa.Column("issue_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=15), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.CheckConstraint(
            f"kind IN ({_in(EVENT_KINDS)})", name=op.f("ck_data_issue_event_kind_valid")
        ),
        _fk("data_issue_event", "condominium_id", "condominium"),
        _fk("data_issue_event", "issue_id", "data_issue"),
        _fk("data_issue_event", "user_id", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_issue_event")),
    )
    indexes = {
        "data_issue": ["condominium_id", "subject_id", "supplier_id", "resolved_by_user_id"],
        "data_issue_event": ["condominium_id", "issue_id", "user_id"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
        )
    app_role = _app_role()
    if app_role:  # the history is append-only, like case_event (D80)
        op.execute(f'REVOKE UPDATE, DELETE ON "data_issue_event" FROM "{app_role}"')

    op.drop_constraint(op.f(CASE_LINK_CHECK), "case_link", type_="check")
    op.create_check_constraint(
        op.f(CASE_LINK_CHECK), "case_link", f"target_type IN ({_in((*TARGETS, 'data_issue'))})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM case_link WHERE target_type = 'data_issue'")
    op.drop_constraint(op.f(CASE_LINK_CHECK), "case_link", type_="check")
    op.create_check_constraint(
        op.f(CASE_LINK_CHECK), "case_link", f"target_type IN ({_in(TARGETS)})"
    )
    op.drop_table("data_issue_event")
    op.drop_table("data_issue")
