"""Compliance and expiry dates (D112, FR-057, WP-16 first cut).

- ``compliance_obligation`` (RLS): what the condominium must keep valid. Applicability and
  periodicity are always set by a person; the catalogue only suggests.
- ``compliance_evidence`` (RLS, append only): a document and/or its dates; the latest wins.
- ``compliance_event`` (RLS, append only): the history of each obligation.

Approved by Marcio on 09/11/2026. Additive. Downgrade drops the three tables; no existing
data is changed.

Revision ID: 0025
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
CATEGORIES = (
    "seguranca_incendio",
    "seguro",
    "elevadores",
    "agua",
    "saude",
    "gas",
    "eletrica",
    "estrutura",
    "equipamentos",
    "outros",
)
APPLICABILITY = ("a_validar", "aplicavel", "nao_aplicavel")
SOURCES = ("pessoa", "ia", "texto", "lendo")
EVENT_KINDS = ("criada", "validada", "alterada", "evidencia", "arquivada", "reativada")
TABLES = ("compliance_obligation", "compliance_evidence", "compliance_event")
APPEND_ONLY = ("compliance_evidence", "compliance_event")


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _base(table: str) -> list[sa.Column]:  # type: ignore[type-arg]
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
    ]


def _fk(
    table: str, column: str, target: str, ondelete: str = "RESTRICT"
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    t = "compliance_obligation"
    op.create_table(
        t,
        *_base(t),
        sa.Column("catalog_key", sa.String(length=40), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("suggested_months", sa.Integer(), nullable=True),
        sa.Column("periodicity_months", sa.Integer(), nullable=True),
        sa.Column("lead_days", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("responsible", sa.String(length=200), nullable=True),
        sa.Column("applicability", sa.String(length=20), nullable=False),
        sa.Column("validated_by", sa.UUID(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_reason", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("category", CATEGORIES), name=op.f(f"ck_{t}_category_valid")),
        sa.CheckConstraint(
            _in("applicability", APPLICABILITY), name=op.f(f"ck_{t}_applicability_valid")
        ),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "supplier_id", "supplier", "SET NULL"),
        _fk(t, "validated_by", "app_user", "SET NULL"),
        _fk(t, "created_by", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
        sa.UniqueConstraint(
            "condominium_id", "catalog_key", name=op.f("uq_compliance_obligation_catalog")
        ),
    )
    t = "compliance_evidence"
    op.create_table(
        t,
        *_base(t),
        sa.Column("obligation_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(_in("source", SOURCES), name=op.f(f"ck_{t}_source_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "obligation_id", "compliance_obligation"),
        _fk(t, "document_id", "document", "SET NULL"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    t = "compliance_event"
    op.create_table(
        t,
        *_base(t),
        sa.Column("obligation_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.CheckConstraint(_in("kind", EVENT_KINDS), name=op.f(f"ck_{t}_kind_valid")),
        _fk(t, "condominium_id", "condominium"),
        _fk(t, "obligation_id", "compliance_obligation"),
        _fk(t, "user_id", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{t}")),
    )
    indexed = {
        "compliance_obligation": ("condominium_id", "supplier_id", "validated_by", "created_by"),
        "compliance_evidence": ("condominium_id", "obligation_id", "document_id", "user_id"),
        "compliance_event": ("condominium_id", "obligation_id", "user_id"),
    }
    for table, columns in indexed.items():
        for column in columns:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
        )
    app_role, _ = _roles()
    if app_role:
        for table in APPEND_ONLY:
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{app_role}"')


def downgrade() -> None:
    op.drop_table("compliance_event")
    op.drop_table("compliance_evidence")
    op.drop_table("compliance_obligation")
