"""LB-053 (D103): the CondoOS sends the document request e-mail, approved by the síndico.

- ``delegation_event.kind`` accepts ``email_aprovado``, ``email_enviado`` (accepted by the
  mail server, never "delivered") and ``email_falhou``;
- ``outbox_event.receipt``: what the mail server answered (message id, accepted at).

The action type itself is code (``app.policy``). Approved by Marcio on 08/11/2026. Additive.
Downgrade turns the e-mail events into ``compartilhado`` and drops the column.

Revision ID: 0023
Revises: 0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here on purpose: migrations never import lists from the application code.
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
EMAIL_EVENTS = ("email_aprovado", "email_enviado", "email_falhou")
CHECK = "ck_delegation_event_kind_valid"


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.drop_constraint(op.f(CHECK), "delegation_event", type_="check")
    op.create_check_constraint(
        op.f(CHECK), "delegation_event", f"kind IN ({_in((*EVENTS, *EMAIL_EVENTS))})"
    )
    json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.add_column("outbox_event", sa.Column("receipt", json_type, nullable=True))


def downgrade() -> None:
    op.drop_column("outbox_event", "receipt")
    # delegation_event is append-only for the app role; the owner runs migrations.
    op.execute(
        "UPDATE delegation_event SET kind = 'compartilhado' " f"WHERE kind IN ({_in(EMAIL_EVENTS)})"
    )
    op.drop_constraint(op.f(CHECK), "delegation_event", type_="check")
    op.create_check_constraint(op.f(CHECK), "delegation_event", f"kind IN ({_in(EVENTS)})")
