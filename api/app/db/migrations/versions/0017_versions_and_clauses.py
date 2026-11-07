"""Backlog items that change structure (D85), approved by Marcio on 07/11/2026. Additive:
nothing existing is altered or removed; downgrade drops only what this creates.

- CB-012: ``condominium_settings_version`` (RLS, append-only): every change of approval
  limits or rule parameters is a new version; rules use the version in force on the audited
  month. Version 1 is loaded from the current values.
- CB-030: ``document.field_provenance``: source, page and excerpt of each extracted field.
- CB-031: ``document.version`` and ``document.supersedes_id``: a new file of the same logical
  document is a new version; the previous one is kept.
- CB-060: notice period, automatic renewal, termination penalty and their excerpts on
  ``contract``.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    empty = sa.text("'{}'")

    # CB-012 -----------------------------------------------------------------------------
    op.create_table(
        "condominium_settings_version",
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
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("approval_limits", json_type, nullable=False),
        sa.Column("rule_params", json_type, nullable=False),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_condominium_settings_version_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_condominium_settings_version_changed_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_condominium_settings_version")),
        sa.UniqueConstraint(
            "condominium_id",
            "version",
            name=op.f("uq_condominium_settings_version_condominium_id"),
        ),
    )
    for column in ("condominium_id", "changed_by_user_id"):
        op.create_index(
            op.f(f"ix_condominium_settings_version_{column}"),
            "condominium_settings_version",
            [column],
        )
    op.execute('ALTER TABLE "condominium_settings_version" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "condominium_settings_version" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )
    op.execute(
        "INSERT INTO condominium_settings_version "
        "(condominium_id, version, approval_limits, rule_params, reason, valid_from) "
        "SELECT id, 1, coalesce(approval_limits, '{}'), coalesce(rule_params, '{}'), "
        "'Versão inicial (migração 0017)', created_at FROM condominium"
    )
    app_role = _app_role()
    if app_role:  # a version is a photograph: never edited
        op.execute(f'REVOKE UPDATE, DELETE ON "condominium_settings_version" FROM "{app_role}"')

    # CB-030 and CB-031 ------------------------------------------------------------------
    op.add_column(
        "document", sa.Column("field_provenance", json_type, server_default=empty, nullable=False)
    )
    op.add_column(
        "document",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column("document", sa.Column("supersedes_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_document_supersedes_id_document"),
        "document",
        "document",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # A document is replaced by at most one newer version.
    op.create_index(
        op.f("ix_document_supersedes_id"),
        "document",
        ["supersedes_id"],
        unique=True,
        postgresql_where=sa.text("supersedes_id IS NOT NULL"),
    )

    # CB-060 -----------------------------------------------------------------------------
    op.add_column("contract", sa.Column("notice_days", sa.Integer(), nullable=True))
    op.add_column("contract", sa.Column("auto_renewal", sa.Boolean(), nullable=True))
    op.add_column(
        "contract", sa.Column("termination_penalty", sa.String(length=300), nullable=True)
    )
    op.add_column(
        "contract", sa.Column("clause_evidence", json_type, server_default=empty, nullable=False)
    )


def downgrade() -> None:
    for column in ("clause_evidence", "termination_penalty", "auto_renewal", "notice_days"):
        op.drop_column("contract", column)
    op.drop_index(op.f("ix_document_supersedes_id"), table_name="document")
    op.drop_constraint(op.f("fk_document_supersedes_id_document"), "document", type_="foreignkey")
    for column in ("supersedes_id", "version", "field_provenance"):
        op.drop_column("document", column)
    op.drop_table("condominium_settings_version")
