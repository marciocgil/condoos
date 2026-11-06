"""Contract adjustment index "OUTRO" with a text description (D68).

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "'IPCA', 'IGPM', 'INPC', 'FIXO', 'NENHUM'"
NEW = OLD + ", 'OUTRO'"


def _check(values: str) -> None:
    op.execute("ALTER TABLE contract DROP CONSTRAINT ck_contract_adjustment_index_valid")
    op.execute(
        "ALTER TABLE contract ADD CONSTRAINT ck_contract_adjustment_index_valid "
        f"CHECK (adjustment_index IN ({values}))"
    )


def upgrade() -> None:
    _check(NEW)
    op.add_column(
        "contract", sa.Column("adjustment_index_other", sa.String(length=120), nullable=True)
    )


def downgrade() -> None:
    op.execute("UPDATE contract SET adjustment_index = 'NENHUM' WHERE adjustment_index = 'OUTRO'")
    op.drop_column("contract", "adjustment_index_other")
    _check(OLD)
