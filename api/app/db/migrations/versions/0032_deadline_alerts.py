"""Deadline alerts (FR-026, D126).

- ``deadline_alert`` (RLS): one alert per target, due date and level, created by the
  versioned alert policy, shown inside the app (channel ``app``; nothing is sent out),
  with its status: ``criado`` → ``visto`` (who and when) → ``resolvido`` (when the
  condition is gone).

Approved by Marcio on 12/11/2026 ("Aprovo tudo"). Additive. Downgrade drops the table.

Revision ID: 0032
Revises: 0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
KINDS = ("assunto_prazo", "tarefa_prazo", "conformidade", "contrato_fim", "farol_aguardando")
STATUSES = ("criado", "visto", "resolvido")
T = "deadline_alert"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


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
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("audience", sa.String(length=10), nullable=False),
        sa.Column("channel", sa.String(length=10), server_default="app", nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.String(length=200), nullable=True),
        sa.CheckConstraint(_in("kind", KINDS), name=op.f(f"ck_{T}_kind_valid")),
        sa.CheckConstraint(_in("status", STATUSES), name=op.f(f"ck_{T}_status_valid")),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f(f"fk_{T}_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["seen_by"], ["app_user.id"], name=op.f(f"fk_{T}_seen_by_app_user"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{T}")),
        sa.UniqueConstraint("condominium_id", "dedupe_key", name=op.f("uq_deadline_alert_key")),
    )
    for column in ("condominium_id", "seen_by"):
        op.create_index(op.f(f"ix_{T}_{column}"), T, [column])
    op.execute(f'ALTER TABLE "{T}" ENABLE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_isolation ON "{T}" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )


def downgrade() -> None:
    op.drop_table(T)
