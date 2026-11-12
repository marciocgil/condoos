"""Adhesion term of a condominium (D128).

- ``adhesion_term`` (RLS, append only): the signed term that authorises the use of the
  condominium's data, with the version, the document and who registered it and when. The
  implantation progress (8 items) is computed from records on every read, never stored.

Approved by Marcio on 12/11/2026 ("Pode seguir com a fatia 2"). Additive. Downgrade drops
the table.

Revision ID: 0033
Revises: 0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
T = "adhesion_term"


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def upgrade() -> None:
    op.create_table(
        T,
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
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("accepted_by", sa.UUID(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f(f"fk_{T}_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f(f"fk_{T}_document_id_document"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_by"],
            ["app_user.id"],
            name=op.f(f"fk_{T}_accepted_by_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{T}")),
    )
    for column in ("condominium_id", "document_id", "accepted_by"):
        op.create_index(op.f(f"ix_{T}_{column}"), T, [column])
    op.execute(f'ALTER TABLE "{T}" ENABLE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_isolation ON "{T}" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )
    app_role, _ = _roles()
    if app_role:
        op.execute(f'REVOKE UPDATE, DELETE ON "{T}" FROM "{app_role}"')


def downgrade() -> None:
    op.drop_table(T)
