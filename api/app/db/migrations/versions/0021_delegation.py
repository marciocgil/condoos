"""CondoOS Launch LF4 (D95, ADR-L04): documents requested from people without a login.

- ``delegation_request`` (RLS): who asks, who authorised, the recipient by name and role
  only (no contact: the system sends nothing), the items, due date and status.
- ``delegation_link`` (RLS): the upload link; only the SHA-256 of the token is stored.
- ``delegation_event`` (RLS, append only): the request's history; external uploads have no
  user and carry ids only.
- ``document.origin`` accepts ``pedido``; ``document.delegation_request_id`` links a file to
  the request it answered.
- ``app_delegation_link_condominium(hash)``: SECURITY DEFINER lookup of the condominium of a
  link, so the public upload route runs with the app role inside that tenant (RLS).

Approved by Marcio on 07/11/2026 (Q-L06). Additive. Downgrade turns ``pedido`` documents
into ``upload`` (files and text stay) and drops what this created.

Revision ID: 0021
Revises: 0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
# Frozen here on purpose: migrations never import lists from the application code.
STATUSES = (
    "rascunho",
    "autorizado",
    "aguardando_envio",
    "recebendo",
    "concluido",
    "encerrado",
    "expirado",
    "revogado",
)
ROLES = ("administradora", "fornecedor", "contador", "zelador", "outro")
EVENTS = (
    "criado",
    "autorizado",
    "link_gerado",
    "compartilhado",
    "arquivo_recebido",
    "arquivo_recusado",
    "item_atendido",
    "concluido",
    "encerrado",
    "expirado",
    "revogado",
)
ORIGINS_BEFORE = ("upload", "email", "seed")
ORIGIN_CHECK = "ck_document_origin_valid"
TABLES = ("delegation_event", "delegation_link", "delegation_request")


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _roles() -> tuple[str | None, str | None]:
    from sqlalchemy.engine import make_url

    from app.config import get_settings

    s = get_settings()
    return make_url(s.database_url).username, make_url(s.database_worker_url).username


def _base() -> list[sa.Column]:  # type: ignore[type-arg]
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
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def upgrade() -> None:
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "delegation_request",
        *_base(),
        sa.Column("prepared_by_user_id", sa.UUID(), nullable=True),
        sa.Column("authorized_by_user_id", sa.UUID(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("recipient_role", sa.String(length=20), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("items", json_type, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in(STATUSES)})", name=op.f("ck_delegation_request_status_valid")
        ),
        sa.CheckConstraint(
            f"recipient_role IN ({_in(ROLES)})",
            name=op.f("ck_delegation_request_recipient_role_valid"),
        ),
        _fk("delegation_request", "condominium_id", "condominium"),
        _fk("delegation_request", "prepared_by_user_id", "app_user", "SET NULL"),
        _fk("delegation_request", "authorized_by_user_id", "app_user", "SET NULL"),
        _fk("delegation_request", "case_id", "case_record"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delegation_request")),
    )
    op.create_table(
        "delegation_link",
        *_base(),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_files", sa.Integer(), nullable=False),
        sa.Column("files_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        _fk("delegation_link", "condominium_id", "condominium"),
        _fk("delegation_link", "request_id", "delegation_request"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delegation_link")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_delegation_link_token_hash")),
    )
    op.create_table(
        "delegation_event",
        *_base(),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.CheckConstraint(f"kind IN ({_in(EVENTS)})", name=op.f("ck_delegation_event_kind_valid")),
        _fk("delegation_event", "condominium_id", "condominium"),
        _fk("delegation_event", "request_id", "delegation_request"),
        _fk("delegation_event", "user_id", "app_user", "SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delegation_event")),
    )
    indexes = {
        "delegation_request": [
            "condominium_id",
            "prepared_by_user_id",
            "authorized_by_user_id",
            "case_id",
        ],
        "delegation_link": ["condominium_id", "request_id"],
        "delegation_event": ["condominium_id", "request_id", "user_id"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY tenant_isolation ON "{table}" '
            f"USING (condominium_id = ANY ({SCOPE})) WITH CHECK (condominium_id = ANY ({SCOPE}))"
        )
    app_role, worker_role = _roles()
    if app_role:  # the history is append-only, like case_event (D80)
        op.execute(f'REVOKE UPDATE, DELETE ON "delegation_event" FROM "{app_role}"')

    op.add_column("document", sa.Column("delegation_request_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_document_delegation_request_id_delegation_request"),
        "document",
        "delegation_request",
        ["delegation_request_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_document_delegation_request_id"), "document", ["delegation_request_id"]
    )
    op.drop_constraint(op.f(ORIGIN_CHECK), "document", type_="check")
    op.create_check_constraint(
        op.f(ORIGIN_CHECK), "document", f"origin IN ({_in((*ORIGINS_BEFORE, 'pedido'))})"
    )

    # The public upload route knows only the token: this finds the link's condominium (and
    # nothing else) so the rest of the request runs with the app role inside that tenant.
    op.execute("""
        CREATE OR REPLACE FUNCTION app_delegation_link_condominium(p_hash text)
        RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
          SELECT condominium_id FROM delegation_link WHERE token_hash = p_hash
        $$;
        """)
    op.execute("REVOKE ALL ON FUNCTION app_delegation_link_condominium(text) FROM PUBLIC")
    for role in (app_role, worker_role):
        if role:
            op.execute(
                f'GRANT EXECUTE ON FUNCTION app_delegation_link_condominium(text) TO "{role}"'
            )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_delegation_link_condominium(text)")
    op.execute("UPDATE document SET origin = 'upload' WHERE origin = 'pedido'")
    op.drop_constraint(op.f(ORIGIN_CHECK), "document", type_="check")
    op.create_check_constraint(op.f(ORIGIN_CHECK), "document", f"origin IN ({_in(ORIGINS_BEFORE)})")
    op.drop_index(op.f("ix_document_delegation_request_id"), table_name="document")
    op.drop_constraint(
        op.f("fk_document_delegation_request_id_delegation_request"),
        "document",
        type_="foreignkey",
    )
    op.drop_column("document", "delegation_request_id")
    for table in TABLES:
        op.drop_table(table)
