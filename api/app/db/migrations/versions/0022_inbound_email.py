"""CondoOS Launch LF5 (D101): real inbound e-mail and the channel's health.

- ``condominium.inbound_token``: the random part of the address <slug>-<token>@<domain>;
  existing condominiums get one here.
- ``inbound_message`` (RLS, append only): one row per inbound e-mail with the sender's domain
  and counts only (no subject, body or full address). ``condominium_id`` is null when the
  address matched no condominium.

Approved by Marcio on 08/11/2026. Additive. Downgrade drops the table and the column; the
documents that arrived by e-mail stay.

Revision ID: 0022
Revises: 0021
"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
STATUSES = ("processada", "recusada", "falhou")
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def upgrade() -> None:
    op.add_column("condominium", sa.Column("inbound_token", sa.String(length=16), nullable=True))
    conn = op.get_bind()
    for (condo_id,) in conn.execute(sa.text("SELECT id FROM condominium")):
        token = "".join(secrets.choice(ALPHABET) for _ in range(8))
        conn.execute(
            sa.text("UPDATE condominium SET inbound_token = :t WHERE id = :i"),
            {"t": token, "i": condo_id},
        )
    op.alter_column("condominium", "inbound_token", nullable=False)
    op.create_unique_constraint(
        op.f("uq_condominium_inbound_token"), "condominium", ["inbound_token"]
    )

    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "inbound_message",
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
        sa.Column("condominium_id", sa.UUID(), nullable=True),
        sa.Column("message_hash", sa.String(length=64), nullable=False),
        sa.Column("sender_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attachments", sa.Integer(), nullable=False),
        sa.Column("documents", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("refused", sa.Integer(), nullable=False),
        sa.Column("reasons", json_type, nullable=False),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{v}'" for v in STATUSES) + ")",
            name=op.f("ck_inbound_message_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_inbound_message_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inbound_message")),
        sa.UniqueConstraint("message_hash", name=op.f("uq_inbound_message_message_hash")),
    )
    op.create_index(
        op.f("ix_inbound_message_condominium_id"), "inbound_message", ["condominium_id"]
    )
    op.execute('ALTER TABLE "inbound_message" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "inbound_message" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )
    app_role, _ = _roles()
    if app_role:
        op.execute(f'REVOKE UPDATE, DELETE ON "inbound_message" FROM "{app_role}"')


def downgrade() -> None:
    op.drop_table("inbound_message")
    op.drop_constraint(op.f("uq_condominium_inbound_token"), "condominium", type_="unique")
    op.drop_column("condominium", "inbound_token")
