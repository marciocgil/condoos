"""Opportunities and savings stages (D76, D81): opportunity, opportunity_finding,
savings_record (append-only) and opportunity_review (append-only). All with RLS.

Approved plan: docs/data-model.md §5 and §7. Lists are frozen here (D32).

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"

STATUSES = (
    "identificada",
    "em_revisao_interna",
    "devolvida",
    "rejeitada",
    "aprovada_para_cliente",
    "aprovada_pelo_condominio",
    "recusada_pelo_condominio",
    "em_execucao",
    "implementada",
    "resultado_medido",
    "encerrada",
)
TYPES = (
    "reajuste",
    "cobranca_inconsistente",
    "renegociacao",
    "racionalizacao_escopo",
    "recuperacao",
    "compra_alternativa",
    "eficiencia_operacional",
)
STAGES = ("potencial", "estimada_validada", "aprovada", "contratada", "realizada")
ACTIONS = (
    "aprovar",
    "ajustar",
    "devolver",
    "rejeitar",
    "reabrir_revisao",
    "condominio_aprovar",
    "condominio_recusar",
)
TABLES = ("opportunity_review", "savings_record", "opportunity_finding", "opportunity")
APPEND_ONLY = ("savings_record", "opportunity_review")


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


def _money(name: str) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.Numeric(precision=14, scale=2), nullable=False)


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "opportunity",
        *_base("opportunity"),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("opportunity_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        *_fk("opportunity", "contract_id", "contract", nullable=True, ondelete="SET NULL"),
        *_fk("opportunity", "supplier_id", "supplier", nullable=True, ondelete="RESTRICT"),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("operational_impact", sa.String(length=500), nullable=False),
        sa.Column("legal_contractual_risk", sa.String(length=10), nullable=False),
        sa.Column("implementation_readiness", sa.String(length=30), nullable=False),
        sa.Column("review_requirement", sa.String(length=20), nullable=False),
        sa.Column("review_policy_version", sa.Integer(), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True), nullable=True),
        *_fk("opportunity", "created_by_user_id", "app_user", nullable=True, ondelete="SET NULL"),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_opportunity_status_valid")
        ),
        sa.CheckConstraint(
            f"opportunity_type IN ({_in(TYPES)})",
            name=op.f("ck_opportunity_opportunity_type_valid"),
        ),
        sa.CheckConstraint(
            "legal_contractual_risk IN ('baixo', 'medio', 'alto')",
            name=op.f("ck_opportunity_legal_contractual_risk_valid"),
        ),
        sa.UniqueConstraint("condominium_id", "number", name=op.f("uq_opportunity_condominium_id")),
    )
    op.create_table(
        "opportunity_finding",
        *_base("opportunity_finding"),
        *_fk(
            "opportunity_finding",
            "opportunity_id",
            "opportunity",
            nullable=False,
            ondelete="RESTRICT",
        ),
        *_fk("opportunity_finding", "finding_id", "finding", nullable=False, ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "opportunity_id", "finding_id", name=op.f("uq_opportunity_finding_opportunity_id")
        ),
    )
    op.create_table(
        "savings_record",
        *_base("savings_record"),
        *_fk(
            "savings_record", "opportunity_id", "opportunity", nullable=False, ondelete="RESTRICT"
        ),
        sa.Column("stage", sa.String(length=20), nullable=False),
        _money("amount"),
        sa.Column("periodicity", sa.String(length=10), nullable=False),
        _money("annualized_amount"),
        _money("one_time_cost"),
        _money("net_amount"),
        sa.Column("baseline_period_start", sa.Date(), nullable=False),
        sa.Column("baseline_period_end", sa.Date(), nullable=False),
        _money("baseline_amount"),
        sa.Column("method_code", sa.String(length=40), nullable=False),
        sa.Column("assumptions", json_type, nullable=False),
        sa.Column("evidence", json_type, nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column("quality_risks", sa.Text(), server_default="", nullable=False),
        sa.Column("version_hash", sa.String(length=64), nullable=False),
        *_fk(
            "savings_record", "recorded_by_user_id", "app_user", nullable=True, ondelete="SET NULL"
        ),
        *_fk(
            "savings_record", "supersedes_id", "savings_record", nullable=True, ondelete="RESTRICT"
        ),
        sa.CheckConstraint(f"stage IN ({_in(STAGES)})", name=op.f("ck_savings_record_stage_valid")),
        sa.CheckConstraint(
            "periodicity IN ('unica', 'mensal', 'anual')",
            name=op.f("ck_savings_record_periodicity_valid"),
        ),
        sa.CheckConstraint(
            "confidence IN ('alta', 'media', 'baixa')",
            name=op.f("ck_savings_record_confidence_valid"),
        ),
    )
    op.create_table(
        "opportunity_review",
        *_base("opportunity_review"),
        *_fk(
            "opportunity_review",
            "opportunity_id",
            "opportunity",
            nullable=False,
            ondelete="RESTRICT",
        ),
        *_fk("opportunity_review", "user_id", "app_user", nullable=False, ondelete="RESTRICT"),
        sa.Column("action", sa.String(length=25), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("from_status", sa.String(length=30), nullable=False),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("reviewed_version_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            f"action IN ({_in(ACTIONS)})", name=op.f("ck_opportunity_review_action_valid")
        ),
    )
    indexes = {
        "opportunity": ["condominium_id", "contract_id", "supplier_id", "created_by_user_id"],
        "opportunity_finding": ["condominium_id", "opportunity_id", "finding_id"],
        "savings_record": [
            "condominium_id",
            "opportunity_id",
            "recorded_by_user_id",
            "supersedes_id",
        ],
        "opportunity_review": ["condominium_id", "opportunity_id", "user_id"],
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
    if app_role:  # values and decisions are photographs: never edited (D76)
        for table in APPEND_ONLY:
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{app_role}"')


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
