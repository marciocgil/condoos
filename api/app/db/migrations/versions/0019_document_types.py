"""CondoOS Launch LB-020 (D91): new document types — regimento interno, apólice de seguro,
balancete, laudo técnico and plano de manutenção. Classified, kept as text and searchable; no
structured extraction. A contract amendment stays "contrato" (D66).

Approved by Marcio on 07/11/2026. Only the CHECK on ``document.doc_type`` changes.
Downgrade turns documents of the new types into "outro" (the file and its text are kept)
before restoring the previous CHECK.

Revision ID: 0019
Revises: 0018
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here on purpose: migrations never import lists from the application code.
PREVIOUS = (
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
ADDED = ("regimento", "apolice", "balancete", "laudo", "plano_manutencao")
NAME = "ck_document_doc_type_valid"


def _check(values: Sequence[str]) -> str:
    return "doc_type IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "document", type_="check")
    op.create_check_constraint(op.f(NAME), "document", _check((*PREVIOUS, *ADDED)))


def downgrade() -> None:
    added = ", ".join(f"'{v}'" for v in ADDED)
    op.execute(f"UPDATE document SET doc_type = 'outro' WHERE doc_type IN ({added})")
    op.drop_constraint(op.f(NAME), "document", type_="check")
    op.create_check_constraint(op.f(NAME), "document", _check(PREVIOUS))
