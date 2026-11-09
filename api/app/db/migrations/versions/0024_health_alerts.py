"""CondoOS Launch LF6-b (D110): internal health alerts in ``data_issue``.

- ``data_issue.kind`` accepts the monitors' kinds: ``canal_parado``, ``contrato_aditado``,
  ``revisor_ausente``, ``sindico_sem_acesso`` and ``acao_parada``;
- ``data_issue.audiencia``: ``condominio`` (everyone who views the condominium, the default:
  existing rows keep it) or ``equipe`` (the CondoOS team and the management's manager only).

Approved by Marcio on 09/11/2026 (Q-L11, Q-L12). Additive. Downgrade removes the alerts, their
events and case links (the owner runs migrations; the app role cannot delete events), then
drops the column and restores the previous CHECK.

Revision ID: 0024
Revises: 0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here on purpose: migrations never import lists from the application code.
KINDS = ("conflito_documentos", "duplicidade_suspeita", "dado_vencido")
ALERT_KINDS = (
    "canal_parado",
    "contrato_aditado",
    "revisor_ausente",
    "sindico_sem_acesso",
    "acao_parada",
)
AUDIENCES = ("condominio", "equipe")
KIND_CHECK = "ck_data_issue_kind_valid"
AUDIENCE_CHECK = "ck_data_issue_audiencia_valid"


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.drop_constraint(op.f(KIND_CHECK), "data_issue", type_="check")
    op.create_check_constraint(
        op.f(KIND_CHECK), "data_issue", f"kind IN ({_in((*KINDS, *ALERT_KINDS))})"
    )
    op.add_column(
        "data_issue",
        sa.Column("audiencia", sa.String(length=15), server_default="condominio", nullable=False),
    )
    op.create_check_constraint(
        op.f(AUDIENCE_CHECK), "data_issue", f"audiencia IN ({_in(AUDIENCES)})"
    )


def downgrade() -> None:
    alerts = f"SELECT id FROM data_issue WHERE kind IN ({_in(ALERT_KINDS)})"
    op.execute(
        f"DELETE FROM case_link WHERE target_type = 'data_issue' AND target_id IN ({alerts})"
    )
    op.execute(f"DELETE FROM data_issue_event WHERE issue_id IN ({alerts})")
    op.execute(f"DELETE FROM data_issue WHERE kind IN ({_in(ALERT_KINDS)})")
    op.drop_constraint(op.f(AUDIENCE_CHECK), "data_issue", type_="check")
    op.drop_column("data_issue", "audiencia")
    op.drop_constraint(op.f(KIND_CHECK), "data_issue", type_="check")
    op.create_check_constraint(op.f(KIND_CHECK), "data_issue", f"kind IN ({_in(KINDS)})")
