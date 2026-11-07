"""Delegated requests for documents (LF4, ADR-L04, D97): ``delegation_request`` (RLS) and
``delegation_upload_token`` (only the hash of a send-only link; looked up by that hash, like
``magic_link_token``, so no RLS policy), ``document.delegation_request_id`` and the new
document origin ``pedido``.

Approved by Marcio on 07/11/2026 (additive; downgrade removes what this creates, and turns
``pedido`` documents into ``upload`` ones so no file is lost).

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here: migrations never import lists from the application code.
STATUSES = ("rascunho", "link_gerado", "compartilhado", "arquivo_recebido", "concluido", "revogado")
ORIGINS_BEFORE = ("upload", "email", "seed")
ORIGIN_CHECK = "ck_document_origin_valid"


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
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
    ]


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "delegation_request",
        *_timestamps(),
        sa.Column("condominium_id", sa.UUID(), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("items", json_type, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("authorized_by_user_id", sa.UUID(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_delegation_request_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_delegation_request_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_delegation_request_created_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["authorized_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_delegation_request_authorized_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delegation_request")),
    )
    for col in ("condominium_id", "created_by_user_id", "authorized_by_user_id"):
        op.create_index(op.f(f"ix_delegation_request_{col}"), "delegation_request", [col])
    op.execute('ALTER TABLE "delegation_request" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "delegation_request" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )

    op.create_table(
        "delegation_upload_token",
        *_timestamps(),
        sa.Column("condominium_id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_files", sa.Integer(), nullable=False),
        sa.Column("files_received", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_delegation_upload_token_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["delegation_request.id"],
            name=op.f("fk_delegation_upload_token_request_id_delegation_request"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delegation_upload_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_delegation_upload_token_token_hash")),
    )
    for col in ("condominium_id", "request_id"):
        op.create_index(op.f(f"ix_delegation_upload_token_{col}"), "delegation_upload_token", [col])

    op.add_column("document", sa.Column("delegation_request_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_document_delegation_request_id_delegation_request"),
        "document",
        "delegation_request",
        ["delegation_request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_document_delegation_request_id"), "document", ["delegation_request_id"]
    )
    op.drop_constraint(op.f(ORIGIN_CHECK), "document", type_="check")
    op.create_check_constraint(
        op.f(ORIGIN_CHECK), "document", f"origin IN ({_in((*ORIGINS_BEFORE, 'pedido'))})"
    )


def downgrade() -> None:
    op.execute("UPDATE document SET origin = 'upload' WHERE origin = 'pedido'")
    op.drop_constraint(op.f(ORIGIN_CHECK), "document", type_="check")
    op.create_check_constraint(op.f(ORIGIN_CHECK), "document", f"origin IN ({_in(ORIGINS_BEFORE)})")
    op.drop_index(op.f("ix_document_delegation_request_id"), table_name="document")
    op.drop_constraint(
        op.f("fk_document_delegation_request_id_delegation_request"), "document", type_="foreignkey"
    )
    op.drop_column("document", "delegation_request_id")
    op.drop_table("delegation_upload_token")
    op.drop_table("delegation_request")
