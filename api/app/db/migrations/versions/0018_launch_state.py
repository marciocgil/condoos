"""CondoOS Launch (ADR-L01, D89): ``launch_state`` keeps the human choices of the
implementation journey — first goal, steps put off for later, card dismissed. Milestones and
capability readiness are computed from the data and never stored. RLS by condominium.

Approved by Marcio on 07/11/2026 (Q-L04). Additive; downgrade drops the table.

Revision ID: 0018
Revises: 0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
GOALS = ("economizar", "pendencias", "fornecedores", "panorama")


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    goals = ", ".join(f"'{g}'" for g in GOALS)
    op.create_table(
        "launch_state",
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
        sa.Column("goal", sa.String(length=20), nullable=True),
        sa.Column("postponed", json_type, server_default=sa.text("'{}'"), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            f"goal IS NULL OR goal IN ({goals})", name=op.f("ck_launch_state_goal_valid")
        ),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_launch_state_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_launch_state_updated_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_launch_state")),
        sa.UniqueConstraint("condominium_id", name=op.f("uq_launch_state_condominium_id")),
    )
    op.create_index(op.f("ix_launch_state_condominium_id"), "launch_state", ["condominium_id"])
    op.create_index(
        op.f("ix_launch_state_updated_by_user_id"), "launch_state", ["updated_by_user_id"]
    )
    op.execute('ALTER TABLE "launch_state" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "launch_state" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )


def downgrade() -> None:
    op.drop_table("launch_state")
