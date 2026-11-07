"""More document types (LB-020, D93): apólice de seguro, balancete, regimento interno, laudo
técnico and plano de manutenção. Classification and search only; no structured extraction.

Approved by Marcio on 07/11/2026. "Termo aditivo" is not a type of its own: it stays a
``contrato`` document that becomes a ``contract_amendment`` (D66).

Downgrade: documents of the new types become ``outro`` (their text and file are kept) and
the previous CHECK is restored.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here: migrations never import lists from the application code.
BEFORE = (
    "nfse",
    "nfe",
    "boleto",
    "recibo",
    "extrato",
    "cnab_retorno",
    "contrato",
    "convencao",
    "ata",
    "outro",
)
NEW = ("apolice", "balancete", "regimento", "laudo", "plano_manutencao")
NAME = "ck_document_doc_type_valid"


def _check(values: tuple[str, ...]) -> str:
    return "doc_type IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "document", type_="check")
    op.create_check_constraint(op.f(NAME), "document", _check(BEFORE + NEW))


def downgrade() -> None:
    new = ", ".join(f"'{v}'" for v in NEW)
    op.execute(f"UPDATE document SET doc_type = 'outro' WHERE doc_type IN ({new})")
    op.drop_constraint(op.f(NAME), "document", type_="check")
    op.create_check_constraint(op.f(NAME), "document", _check(BEFORE))
