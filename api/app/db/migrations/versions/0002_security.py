"""Security: database roles, Row-Level Security, append-only tables, extensions.

Revision ID: 0002
Revises: 0001

Roles and passwords come from DATABASE_URL (API role) and DATABASE_WORKER_URL (worker role).
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.db.models import APPEND_ONLY_TABLES, RLS_TABLES

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _role(url: str) -> tuple[str, str]:
    parsed = make_url(url)
    if not parsed.username or not parsed.password:
        raise RuntimeError("Database URLs must include a username and password")
    return parsed.username, parsed.password


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    settings = get_settings()
    app_role, app_pw = _role(settings.database_url)
    worker_role, worker_pw = _role(settings.database_worker_url)

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # Values come from our own settings, not from user input.
    for role, pw, extra in (
        (app_role, app_pw, "NOBYPASSRLS"),
        (worker_role, worker_pw, "BYPASSRLS"),
    ):
        op.execute(f"""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {_quote_literal(role)}) THEN
                CREATE ROLE "{role}" LOGIN PASSWORD {_quote_literal(pw)} {extra};
              ELSE
                ALTER ROLE "{role}" LOGIN PASSWORD {_quote_literal(pw)} {extra};
              END IF;
            END $$;
            """)
        op.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
        op.execute(
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"'
        )
        op.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{role}"'
        )
        # Append-only tables: never UPDATE or DELETE, whatever the code does.
        for table in APPEND_ONLY_TABLES:
            op.execute(f'REVOKE UPDATE, DELETE ON "{table}" FROM "{role}"')

    # Condominiums reachable by a user: direct memberships plus every condominium of a
    # management company where the user holds a company-level role.
    op.execute("""
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
        """)
    op.execute("REVOKE ALL ON FUNCTION app_accessible_condominium_ids(uuid) FROM PUBLIC")
    for role in (app_role, worker_role):
        op.execute(f'GRANT EXECUTE ON FUNCTION app_accessible_condominium_ids(uuid) TO "{role}"')

    # Tenant scope set per transaction with set_config('app.condominium_ids', '<csv>', true).
    # Unset or empty => no rows. The owner role (migrations, seed, SECURITY DEFINER
    # function) is not subject to the policy; the app role always is.
    scope = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
    for table, column in RLS_TABLES.items():
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING ({column} = ANY ({scope})) "
            f"WITH CHECK ({column} = ANY ({scope}))"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.execute("DROP FUNCTION IF EXISTS app_accessible_condominium_ids(uuid)")
