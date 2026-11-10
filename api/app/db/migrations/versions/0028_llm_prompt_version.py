"""Which prompt version each model call used (D121).

``llm_calls.prompt_sha256``: SHA-256 of the exact system prompt sent (the prompt files of
``app/prompts`` as composed for that purpose). Calls made before this migration have none.
No content is stored, only the fingerprint; the text of each version is in the Git history.

Approved by Marcio on 10/11/2026. Additive. Downgrade drops the column.

Revision ID: 0028
Revises: 0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("prompt_sha256", sa.String(length=64), nullable=True))
    op.create_index("ix_llm_calls_purpose_prompt", "llm_calls", ["purpose", "prompt_sha256"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_purpose_prompt", table_name="llm_calls")
    op.drop_column("llm_calls", "prompt_sha256")
