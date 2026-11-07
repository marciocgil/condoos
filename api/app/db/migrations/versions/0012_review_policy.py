"""Review proportional to risk (D74): versioned review policy, review requirement on each
finding, status ``pendente_evidencia`` and action ``solicitar_evidencia``.

Approved plan: docs/data-model.md §3 and §7. The platform default reproduces the behaviour
before D74 (serious findings wait for review, the others are published). Lists and the
default policy are frozen here (D32).

Revision ID: 0012
Revises: 0011
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"

OLD_STATUSES = (
    "aguardando_validacao",
    "publicado",
    "confirmado",
    "contestado",
    "ignorado",
    "descartado",
    "superado",
)
NEW_STATUSES = (*OLD_STATUSES, "pendente_evidencia")
OLD_ACTIONS = ("validar", "descartar", "confirmar", "contestar", "ignorar", "reabrir")
NEW_ACTIONS = (*OLD_ACTIONS, "solicitar_evidencia")
REQUIREMENTS = ("none", "qualified_review", "internal_review", "pending_evidence")

PLATFORM_DEFAULT_V1 = [
    {"object": "opportunity", "requirement": "internal_review", "reviewers": ["condoos_reviewer"]},
    {
        "object": "finding",
        "match": {"severity": ["alta"]},
        "requirement": "qualified_review",
        "reviewers": ["condoos_reviewer", "gerente"],
    },
    {"object": "finding", "requirement": "none"},
]


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _app_role() -> str | None:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    return make_url(get_settings().database_url).username


def upgrade() -> None:
    # -- finding ---------------------------------------------------------------------------
    op.add_column(
        "finding",
        sa.Column(
            "review_requirement", sa.String(length=20), server_default="none", nullable=False
        ),
    )
    op.add_column("finding", sa.Column("review_policy_version", sa.Integer(), nullable=True))
    op.add_column("finding", sa.Column("confidence", sa.String(length=10), nullable=True))
    op.add_column("finding", sa.Column("category", sa.String(length=40), nullable=True))
    op.execute(
        "ALTER TABLE finding ADD CONSTRAINT ck_finding_review_requirement_valid "
        f"CHECK (review_requirement IN ({_in(REQUIREMENTS)}))"
    )
    # Backfill with the default policy: serious findings were the ones reviewed.
    op.execute(
        "UPDATE finding SET review_requirement = 'qualified_review', review_policy_version = 1 "
        "WHERE severity = 'alta'"
    )
    op.execute("UPDATE finding SET review_policy_version = 1 WHERE review_policy_version IS NULL")
    op.execute("ALTER TABLE finding DROP CONSTRAINT ck_finding_status_valid")
    op.execute(
        f"ALTER TABLE finding ADD CONSTRAINT ck_finding_status_valid CHECK (status IN ({_in(NEW_STATUSES)}))"
    )

    # -- decision ----------------------------------------------------------------------------
    op.alter_column("decision", "action", type_=sa.String(length=25), existing_nullable=False)
    op.execute("ALTER TABLE decision DROP CONSTRAINT ck_decision_action_valid")
    op.execute(
        f"ALTER TABLE decision ADD CONSTRAINT ck_decision_action_valid CHECK (action IN ({_in(NEW_ACTIONS)}))"
    )

    # -- review_policy (append-only; NULL condominium = platform default) ------------------
    op.create_table(
        "review_policy",
        sa.Column("condominium_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "rules",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=300), nullable=False),
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
            name=op.f("fk_review_policy_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_review_policy_created_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_policy")),
        sa.UniqueConstraint(
            "condominium_id", "version", name=op.f("uq_review_policy_condominium_id")
        ),
    )
    op.create_index(op.f("ix_review_policy_condominium_id"), "review_policy", ["condominium_id"])
    op.create_index(
        op.f("ix_review_policy_created_by_user_id"), "review_policy", ["created_by_user_id"]
    )
    op.execute('ALTER TABLE "review_policy" ENABLE ROW LEVEL SECURITY')
    # Everyone reads the platform default (NULL); a condominium's own rows only in its scope.
    # Writes are never allowed for NULL rows from the application role.
    op.execute(
        'CREATE POLICY tenant_isolation ON "review_policy" '
        f"USING (condominium_id IS NULL OR condominium_id = ANY ({SCOPE})) "
        f"WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )
    app_role = _app_role()
    if app_role:
        op.execute(f'REVOKE UPDATE, DELETE ON "review_policy" FROM "{app_role}"')
    rules = json.dumps(PLATFORM_DEFAULT_V1).replace("'", "''")
    op.execute(
        "INSERT INTO review_policy (condominium_id, version, valid_from, rules, reason) VALUES "
        f"(NULL, 1, '2026-01-01T00:00:00Z', '{rules}'::jsonb, "
        "'Padrão da plataforma: graves revisados, demais publicados; economia sempre revisada (D74)')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE finding SET status = 'aguardando_validacao' WHERE status = 'pendente_evidencia'"
    )
    op.drop_table("review_policy")
    op.execute("DELETE FROM decision WHERE action = 'solicitar_evidencia'")
    op.execute("ALTER TABLE decision DROP CONSTRAINT ck_decision_action_valid")
    op.execute(
        f"ALTER TABLE decision ADD CONSTRAINT ck_decision_action_valid CHECK (action IN ({_in(OLD_ACTIONS)}))"
    )
    op.alter_column("decision", "action", type_=sa.String(length=10), existing_nullable=False)
    op.execute("ALTER TABLE finding DROP CONSTRAINT ck_finding_status_valid")
    op.execute(
        f"ALTER TABLE finding ADD CONSTRAINT ck_finding_status_valid CHECK (status IN ({_in(OLD_STATUSES)}))"
    )
    op.execute("ALTER TABLE finding DROP CONSTRAINT ck_finding_review_requirement_valid")
    for column in ("category", "confidence", "review_policy_version", "review_requirement"):
        op.drop_column("finding", column)
