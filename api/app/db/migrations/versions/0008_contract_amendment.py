"""Contract amendments (termos aditivos), with Row-Level Security (D66).

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contract_amendment",
        sa.Column("condominium_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("monthly_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "scope_items",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=500), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_contract_amendment_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contract.id"],
            name=op.f("fk_contract_amendment_contract_id_contract"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_contract_amendment_document_id_document"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_amendment")),
        sa.UniqueConstraint("document_id", name=op.f("uq_contract_amendment_document_id")),
    )
    op.create_index(
        op.f("ix_contract_amendment_condominium_id"),
        "contract_amendment",
        ["condominium_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contract_amendment_contract_id"),
        "contract_amendment",
        ["contract_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contract_amendment_document_id"),
        "contract_amendment",
        ["document_id"],
        unique=False,
    )
    # Row-Level Security, same policy as the other tenant tables (list frozen here, D32).
    scope = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
    op.execute('ALTER TABLE "contract_amendment" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "contract_amendment" '
        f"USING (condominium_id = ANY ({scope})) WITH CHECK (condominium_id = ANY ({scope}))"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contract_amendment_document_id"), table_name="contract_amendment")
    op.drop_index(op.f("ix_contract_amendment_contract_id"), table_name="contract_amendment")
    op.drop_index(op.f("ix_contract_amendment_condominium_id"), table_name="contract_amendment")
    op.drop_table("contract_amendment")
