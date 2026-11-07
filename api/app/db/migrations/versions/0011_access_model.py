"""Access model (D73, D77): CondoOS staff roles with per-condominium assignment, temporary
and revocable memberships, reserved roles, condominium time zone and whether the management
company reviews findings.

Approved plan: docs/data-model.md §2 and §7. Lists are frozen here (D32).

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"

OLD_MEMBERSHIP_ROLES = ("sindico", "subsindico", "conselheiro", "gerente", "analista")
NEW_MEMBERSHIP_ROLES = (*OLD_MEMBERSHIP_ROLES, "zelador", "fornecedor", "morador")
PLATFORM_ROLES = ("condoos_admin", "condoos_reviewer")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# Membership rows count only while not revoked and not expired; CondoOS staff reach a
# condominium only through an active assignment backed by an active platform role.
NEW_FUNCTION = """
CREATE OR REPLACE FUNCTION app_accessible_condominium_ids(p_user uuid)
RETURNS uuid[]
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT coalesce(array_agg(DISTINCT cid), '{}'::uuid[]) FROM (
    SELECT m.condominium_id AS cid
      FROM membership m
      JOIN app_user u ON u.id = m.user_id AND u.is_active
     WHERE m.user_id = p_user AND m.condominium_id IS NOT NULL
       AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at > now())
    UNION
    SELECT c.id
      FROM membership m
      JOIN app_user u ON u.id = m.user_id AND u.is_active
      JOIN condominium c ON c.management_company_id = m.management_company_id
     WHERE m.user_id = p_user AND m.management_company_id IS NOT NULL
       AND m.revoked_at IS NULL AND (m.expires_at IS NULL OR m.expires_at > now())
    UNION
    SELECT a.condominium_id
      FROM condo_assignment a
      JOIN platform_role p ON p.user_id = a.user_id AND p.role = a.platform_role
      JOIN app_user u ON u.id = a.user_id AND u.is_active
     WHERE a.user_id = p_user
       AND a.revoked_at IS NULL AND (a.valid_until IS NULL OR a.valid_until > now())
       AND p.revoked_at IS NULL AND (p.expires_at IS NULL OR p.expires_at > now())
  ) s
$$;
"""

OLD_FUNCTION = """
CREATE OR REPLACE FUNCTION app_accessible_condominium_ids(p_user uuid)
RETURNS uuid[]
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT coalesce(array_agg(DISTINCT cid), '{}'::uuid[]) FROM (
    SELECT m.condominium_id AS cid
      FROM membership m
      JOIN app_user u ON u.id = m.user_id AND u.is_active
     WHERE m.user_id = p_user AND m.condominium_id IS NOT NULL
    UNION
    SELECT c.id
      FROM membership m
      JOIN app_user u ON u.id = m.user_id AND u.is_active
      JOIN condominium c ON c.management_company_id = m.management_company_id
     WHERE m.user_id = p_user AND m.management_company_id IS NOT NULL
  ) s
$$;
"""


def _timestamps() -> list[sa.Column]:  # type: ignore[type-arg]
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
    ]


def upgrade() -> None:
    # -- condominium ---------------------------------------------------------------------
    op.add_column(
        "condominium",
        sa.Column(
            "timezone", sa.String(length=64), server_default="America/Sao_Paulo", nullable=False
        ),
    )
    op.add_column(
        "condominium",
        sa.Column(
            "management_company_reviews",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Existing condominiums keep today's behaviour: their manager validates serious findings.
    op.execute(
        "UPDATE condominium SET management_company_reviews = true "
        "WHERE management_company_id IS NOT NULL"
    )

    # -- membership ----------------------------------------------------------------------
    for column in ("invited_at", "accepted_at", "expires_at", "revoked_at"):
        op.add_column("membership", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.execute("ALTER TABLE membership DROP CONSTRAINT ck_membership_role_valid")
    op.execute(
        "ALTER TABLE membership ADD CONSTRAINT ck_membership_role_valid "
        f"CHECK (role IN ({_in(NEW_MEMBERSHIP_ROLES)}))"
    )

    # -- platform_role (not a tenant table: read only through the scope function) -------
    op.create_table(
        "platform_role",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            f"role IN ({_in(PLATFORM_ROLES)})", name=op.f("ck_platform_role_role_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_platform_role_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_platform_role_granted_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_role")),
        sa.UniqueConstraint("user_id", "role", name=op.f("uq_platform_role_user_id")),
    )
    op.create_index(op.f("ix_platform_role_user_id"), "platform_role", ["user_id"])
    op.create_index(
        op.f("ix_platform_role_granted_by_user_id"), "platform_role", ["granted_by_user_id"]
    )

    # -- condo_assignment (tenant table, RLS) --------------------------------------------
    op.create_table(
        "condo_assignment",
        sa.Column("condominium_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("platform_role", sa.String(length=20), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            f"platform_role IN ({_in(PLATFORM_ROLES)})",
            name=op.f("ck_condo_assignment_platform_role_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["condominium_id"],
            ["condominium.id"],
            name=op.f("fk_condo_assignment_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_condo_assignment_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["app_user.id"],
            name=op.f("fk_condo_assignment_granted_by_user_id_app_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_condo_assignment")),
        sa.UniqueConstraint(
            "condominium_id",
            "user_id",
            "platform_role",
            name=op.f("uq_condo_assignment_condominium_id"),
        ),
    )
    for column in ("condominium_id", "user_id", "granted_by_user_id"):
        op.create_index(op.f(f"ix_condo_assignment_{column}"), "condo_assignment", [column])
    op.execute('ALTER TABLE "condo_assignment" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "condo_assignment" '
        f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
    )

    # -- scope function ------------------------------------------------------------------
    op.execute(NEW_FUNCTION)


def downgrade() -> None:
    op.execute(OLD_FUNCTION)
    op.drop_table("condo_assignment")
    op.drop_table("platform_role")
    # Without the new columns a revoked or expired access would come back: remove them.
    op.execute(
        "DELETE FROM membership WHERE revoked_at IS NOT NULL OR expires_at <= now() "
        "OR role IN ('zelador', 'fornecedor', 'morador')"
    )
    op.execute("ALTER TABLE membership DROP CONSTRAINT ck_membership_role_valid")
    op.execute(
        "ALTER TABLE membership ADD CONSTRAINT ck_membership_role_valid "
        f"CHECK (role IN ({_in(OLD_MEMBERSHIP_ROLES)}))"
    )
    for column in ("revoked_at", "expires_at", "accepted_at", "invited_at"):
        op.drop_column("membership", column)
    op.drop_column("condominium", "management_company_reviews")
    op.drop_column("condominium", "timezone")
