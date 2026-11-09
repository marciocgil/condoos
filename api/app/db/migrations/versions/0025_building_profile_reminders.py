"""Building profile and the weekly compliance e-mail (D109).

- ``condominium.building_profile`` (JSON): what the building has (elevators, piped gas...).
  It only suggests which obligations probably apply; a person still validates each one.
  Changes are recorded in ``audit_log``.
- ``condominium.compliance_email_enabled``: off until the síndico turns it on.
- ``compliance_reminder`` (RLS, append only): one row per weekly e-mail and recipient (ids,
  week, counts and the server's message id; no address, no content).

Approved by Marcio on 09/11/2026. Additive. Downgrade drops the table and both columns.

Revision ID: 0025
Revises: 0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
STATUSES = ("enviado", "falhou")
TABLE = "compliance_reminder"


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.add_column(
        "condominium",
        sa.Column("building_profile", json_type, nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "condominium",
        sa.Column(
            "compliance_email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        TABLE,
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
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("week", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("items", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=300), nullable=True),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{v}'" for v in STATUSES) + ")",
            name=op.f(f"ck_{TABLE}_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f(f"fk_{TABLE}_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f(f"fk_{TABLE}_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
        sa.UniqueConstraint(
            "condominium_id", "user_id", "week", name=op.f("uq_compliance_reminder_week")
        ),
    )
    op.create_index(op.f(f"ix_{TABLE}_condominium_id"), TABLE, ["condominium_id"])
    op.create_index(op.f(f"ix_{TABLE}_user_id"), TABLE, ["user_id"])
    op.execute(f'ALTER TABLE "{TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_isolation ON "{TABLE}" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )
    app_role, _ = _roles()
    if app_role:
        op.execute(f'REVOKE UPDATE, DELETE ON "{TABLE}" FROM "{app_role}"')


def downgrade() -> None:
    op.drop_table(TABLE)
    op.drop_column("condominium", "compliance_email_enabled")
    op.drop_column("condominium", "building_profile")
