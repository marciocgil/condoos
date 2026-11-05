"""Finding status "superado": the rule no longer detects it and nobody acted on it (D61).

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "'aguardando_validacao', 'publicado', 'confirmado', 'contestado', 'ignorado', 'descartado'"
NEW = OLD + ", 'superado'"


def _replace(values: str) -> None:
    op.execute("ALTER TABLE finding DROP CONSTRAINT ck_finding_status_valid")
    op.execute(
        f"ALTER TABLE finding ADD CONSTRAINT ck_finding_status_valid CHECK (status IN ({values}))"
    )


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    op.execute("UPDATE finding SET status = 'publicado' WHERE status = 'superado'")
    _replace(OLD)
