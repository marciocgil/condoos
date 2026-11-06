"""Contract billing frequency, for the monthly invoice cross-check (D70).

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "contract",
        sa.Column("billing_frequency_months", sa.Integer(), server_default="1", nullable=False),
    )
    op.execute(
        "ALTER TABLE contract ADD CONSTRAINT ck_contract_billing_frequency_valid "
        "CHECK (billing_frequency_months IN (0, 1, 2, 3, 6, 12))"
    )
    # Contracts already described as quarterly were billed every three months.
    op.execute("UPDATE contract SET billing_frequency_months = 3 WHERE object ILIKE '%trimestral%'")


def downgrade() -> None:
    op.execute("ALTER TABLE contract DROP CONSTRAINT ck_contract_billing_frequency_valid")
    op.drop_column("contract", "billing_frequency_months")
