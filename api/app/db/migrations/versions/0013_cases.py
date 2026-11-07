"""Cases (Assuntos, D75, D80): case_record, case_event (append-only timeline), case_link
(N:N with history) and case_task. All tenant tables with RLS.

Approved plan: docs/data-model.md §4 and §7. Lists are frozen here (D32).

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"

STATUSES = (
    "novo",
    "em_triagem",
    "em_planejamento",
    "aguardando_aprovacao",
    "em_execucao",
    "aguardando_terceiro",
    "aguardando_validacao",
    "resolvido",
    "cancelado",
    "reaberto",
    "suspenso_justificadamente",
)
ORIGINS = (
    "finding",
    "opportunity",
    "human_request",
    "maintenance",
    "obligation",
    "external_event",
)
SEVERITIES = ("baixa", "media", "alta", "critica")
CATEGORIES = (
    "financeiro",
    "contrato",
    "manutencao",
    "conformidade",
    "administrativo",
    "atendimento",
    "seguranca",
    "obra",
    "outro",
)
TARGETS = ("finding", "opportunity", "document", "contract", "supplier", "expense", "case")
TASK_STATUSES = ("aberta", "em_andamento", "bloqueada", "concluida", "cancelada")
TABLES = ("case_task", "case_link", "case_event", "case_record")


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


def _user_fk(table: str, column: str) -> list[Any]:
    return [
        sa.Column(column, sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            [column],
            ["app_user.id"],
            name=op.f(f"fk_{table}_{column}_app_user"),
            ondelete="SET NULL",
        ),
    ]


def _case_fk(table: str) -> list[Any]:
    return [
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["case_record.id"],
            name=op.f(f"fk_{table}_case_id_case_record"),
            ondelete="RESTRICT",
        ),
    ]


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def upgrade() -> None:
    op.create_table(
        "case_record",
        *_base("case_record"),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_user_fk("case_record", "owner_user_id"),
        sa.Column("next_action", sa.String(length=300), nullable=True),
        sa.Column("next_action_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_until", sa.Date(), nullable=True),
        sa.Column("suspension_reason", sa.String(length=500), nullable=True),
        sa.Column("resolution_criterion", sa.String(length=500), nullable=False),
        sa.Column("requires_evidence", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_user_fk("case_record", "created_by_user_id"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_case_record_status_valid")
        ),
        sa.CheckConstraint(f"origin IN ({_in(ORIGINS)})", name=op.f("ck_case_record_origin_valid")),
        sa.CheckConstraint(
            f"severity IN ({_in(SEVERITIES)})", name=op.f("ck_case_record_severity_valid")
        ),
        sa.CheckConstraint(
            f"category IN ({_in(CATEGORIES)})", name=op.f("ck_case_record_category_valid")
        ),
        # "Sem próxima ação, sem controle" (spec §8.4): an open case has an owner, a next
        # action and a due date, unless it is formally suspended with a reason and a date.
        sa.CheckConstraint(
            "status IN ('resolvido', 'cancelado') OR (status = 'suspenso_justificadamente' "
            "AND suspended_until IS NOT NULL AND suspension_reason IS NOT NULL) OR "
            "(owner_user_id IS NOT NULL AND next_action IS NOT NULL "
            "AND next_action_due_at IS NOT NULL)",
            name=op.f("ck_case_record_next_action_required"),
        ),
        sa.UniqueConstraint("condominium_id", "number", name=op.f("uq_case_record_condominium_id")),
    )
    op.create_table(
        "case_event",
        *_base("case_event"),
        *_case_fk("case_event"),
        *_user_fk("case_event", "actor_user_id"),
        sa.Column("actor_kind", sa.String(length=10), server_default="user", nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("from_value", sa.String(length=300), nullable=True),
        sa.Column("to_value", sa.String(length=300), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "details",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'system', 'ai')", name=op.f("ck_case_event_actor_kind_valid")
        ),
    )
    op.create_table(
        "case_link",
        *_base("case_link"),
        *_case_fk("case_link"),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("as_evidence", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        *_user_fk("case_link", "linked_by_user_id"),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        *_user_fk("case_link", "unlinked_by_user_id"),
        sa.CheckConstraint(
            f"target_type IN ({_in(TARGETS)})", name=op.f("ck_case_link_target_type_valid")
        ),
    )
    op.create_table(
        "case_task",
        *_base("case_task"),
        *_case_fk("case_task"),
        sa.Column("title", sa.String(length=200), nullable=False),
        *_user_fk("case_task", "assignee_user_id"),
        sa.Column("assignee_label", sa.String(length=200), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="aberta", nullable=False),
        sa.Column("blocked_reason", sa.String(length=500), nullable=True),
        sa.Column("requires_evidence", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_user_fk("case_task", "completed_by_user_id"),
        sa.CheckConstraint(
            f"status IN ({_in(TASK_STATUSES)})", name=op.f("ck_case_task_status_valid")
        ),
        sa.CheckConstraint(
            "assignee_user_id IS NOT NULL OR assignee_label IS NOT NULL",
            name=op.f("ck_case_task_assignee_required"),
        ),
    )
    indexes = {
        "case_record": ["condominium_id", "owner_user_id", "created_by_user_id"],
        "case_event": ["condominium_id", "case_id", "actor_user_id"],
        "case_link": [
            "condominium_id",
            "case_id",
            "target_id",
            "linked_by_user_id",
            "unlinked_by_user_id",
        ],
        "case_task": ["condominium_id", "case_id", "assignee_user_id", "completed_by_user_id"],
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
    if app_role:  # the timeline is append-only, like decision and audit_log (D14)
        op.execute(f'REVOKE UPDATE, DELETE ON "case_event" FROM "{app_role}"')


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
