"""Data issues (ADR-L05, LB-030, D95): a conflict between sources of the same fact, an
expected document missing, a stale datum or a suspected duplicate. Not a finding and not a
case. Resolved with the prevailing version and a reason, or dismissed; never deleted.
History in audit_log. RLS by condominium.

Approved by Marcio on 07/11/2026 (additive; downgrade drops the table).

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
# Frozen here: migrations never import lists from the application code.
KINDS = (
    "conflito_documentos",
    "documento_esperado_ausente",
    "dado_vencido",
    "duplicidade_suspeita",
)
STATUSES = ("aberto", "resolvido", "descartado")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "data_issue",
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
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("capability", sa.String(length=5), nullable=False),
        sa.Column("subject_type", sa.String(length=30), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("field_name", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("sources", json_type, nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolution", json_type, nullable=True),
        sa.CheckConstraint(f"kind IN ({_in(KINDS)})", name=op.f("ck_data_issue_kind_valid")),
        sa.CheckConstraint(f"status IN ({_in(STATUSES)})", name=op.f("ck_data_issue_status_valid")),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_data_issue_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_data_issue_resolved_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_issue")),
        sa.UniqueConstraint(
            "condominium_id", "dedupe_key", name=op.f("uq_data_issue_condominium_id")
        ),
    )
    op.create_index(op.f("ix_data_issue_condominium_id"), "data_issue", ["condominium_id"])
    op.create_index(op.f("ix_data_issue_subject_id"), "data_issue", ["subject_id"])
    op.create_index(
        op.f("ix_data_issue_resolved_by_user_id"), "data_issue", ["resolved_by_user_id"]
    )
    op.execute('ALTER TABLE "data_issue" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "data_issue" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )


def downgrade() -> None:
    op.drop_table("data_issue")
