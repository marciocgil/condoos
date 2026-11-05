"""Document chunks for the chat's hybrid search (vector + Portuguese full text).

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_chunk",
        sa.Column("condominium_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('portuguese', text)", persisted=True),
            nullable=True,
        ),
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
            name=op.f("fk_document_chunk_condominium_id_condominium"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["document.id"],
            name=op.f("fk_document_chunk_document_id_document"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunk")),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name=op.f("uq_document_chunk_document_id_chunk_index")
        ),
    )
    op.create_index(op.f("ix_document_chunk_condominium_id"), "document_chunk", ["condominium_id"])
    op.create_index(op.f("ix_document_chunk_document_id"), "document_chunk", ["document_id"])
    op.execute("CREATE INDEX ix_document_chunk_fts ON document_chunk USING gin (search_vector)")
    op.execute(
        "CREATE INDEX ix_document_chunk_embedding ON document_chunk "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    # Row-Level Security, same policy as the other tenant tables (list frozen here, D32).
    scope = "string_to_array(nullif(current_setting('app.condominium_ids', true), ''), ',')::uuid[]"
    op.execute('ALTER TABLE "document_chunk" ENABLE ROW LEVEL SECURITY')
    op.execute(
        'CREATE POLICY tenant_isolation ON "document_chunk" '
        f"USING (condominium_id = ANY ({scope})) WITH CHECK (condominium_id = ANY ({scope}))"
    )


def downgrade() -> None:
    op.drop_table("document_chunk")
