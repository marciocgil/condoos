"""Actions with approval and frozen scope, minimal policy and kill switch (VS-05, D83):
action_request, action_decision (append-only), outbox_event and automation_pause. All
with RLS. Nothing is sent outside the system: approved actions wait for a person.

Approved by Marcio on 07/11/2026 (additive; downgrade drops the tables). Lists frozen (D32).

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"

STATUSES = (
    "aguardando_aprovacao",
    "enfileirada",
    "aguardando_execucao_manual",
    "executada",
    "recusada",
    "cancelada",
    "bloqueada",
)
POLICY_DECISIONS = ("allow", "require_approval", "require_review", "deny", "pause")
KINDS = (
    "solicitar",
    "ajustar",
    "aprovar",
    "recusar",
    "cancelar",
    "invalidar",
    "despachar",
    "bloquear",
    "expirar",
    "executar",
)
OUTBOX_STATUSES = ("pendente", "despachado", "cancelado", "bloqueado")
TABLES = ("automation_pause", "outbox_event", "action_decision", "action_request")
APPEND_ONLY = ("action_decision",)


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _base(table: str) -> list[Any]:
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
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f(f"fk_{table}_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
    ]


def _fk(table: str, column: str, target: str, *, nullable: bool, ondelete: str) -> list[Any]:
    return [
        sa.Column(column, sa.UUID(), nullable=nullable),
        sa.ForeignKeyConstraint(
            [column],
            [f"{target}.id"],
            name=op.f(f"fk_{table}_{column}_{target}"),
            ondelete=ondelete,
        ),
    ]


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "action_request",
        *_base("action_request"),
        *_fk("action_request", "case_id", "case_record", nullable=True, ondelete="RESTRICT"),
        *_fk("action_request", "opportunity_id", "opportunity", nullable=True, ondelete="RESTRICT"),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("cost_cap", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("policy_decision", sa.String(length=20), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_reason", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        *_fk(
            "action_request",
            "requested_by_user_id",
            "app_user",
            nullable=True,
            ondelete="SET NULL",
        ),
        sa.Column("approved_hash", sa.String(length=64), nullable=True),
        *_fk(
            "action_request", "approved_by_user_id", "app_user", nullable=True, ondelete="SET NULL"
        ),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        *_fk(
            "action_request", "executed_by_user_id", "app_user", nullable=True, ondelete="SET NULL"
        ),
        sa.Column("execution_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_action_request_status_valid")
        ),
        sa.CheckConstraint(
            f"policy_decision IN ({_in(POLICY_DECISIONS)})",
            name=op.f("ck_action_request_policy_decision_valid"),
        ),
        sa.UniqueConstraint(
            "condominium_id", "idempotency_key", name=op.f("uq_action_request_condominium_id")
        ),
    )
    op.create_table(
        "action_decision",
        *_base("action_decision"),
        *_fk(
            "action_decision",
            "action_request_id",
            "action_request",
            nullable=False,
            ondelete="RESTRICT",
        ),
        *_fk("action_decision", "user_id", "app_user", nullable=True, ondelete="SET NULL"),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(f"kind IN ({_in(KINDS)})", name=op.f("ck_action_decision_kind_valid")),
    )
    op.create_table(
        "outbox_event",
        *_base("outbox_event"),
        *_fk(
            "outbox_event",
            "action_request_id",
            "action_request",
            nullable=False,
            ondelete="RESTRICT",
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in(OUTBOX_STATUSES)})", name=op.f("ck_outbox_event_status_valid")
        ),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_outbox_event_idempotency_key")),
    )
    op.create_table(
        "automation_pause",
        *_base("automation_pause"),
        sa.Column("automation_type", sa.String(length=60), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        *_fk(
            "automation_pause", "paused_by_user_id", "app_user", nullable=True, ondelete="SET NULL"
        ),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        *_fk(
            "automation_pause",
            "resumed_by_user_id",
            "app_user",
            nullable=True,
            ondelete="SET NULL",
        ),
    )
    indexes = {
        "action_request": [
            "condominium_id",
            "case_id",
            "opportunity_id",
            "requested_by_user_id",
            "approved_by_user_id",
            "executed_by_user_id",
        ],
        "action_decision": ["condominium_id", "action_request_id", "user_id"],
        "outbox_event": ["condominium_id", "action_request_id"],
        "automation_pause": ["condominium_id", "paused_by_user_id", "resumed_by_user_id"],
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
    if app_role:  # every step of an action is a photograph: never edited
        for table in APPEND_ONLY:
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{app_role}"')


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
