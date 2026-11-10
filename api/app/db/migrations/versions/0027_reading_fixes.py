"""Reading fixes from the pilot tests (D120).

- ``document.doc_type`` accepts ``comprovante`` (payment receipt), ``guia_tributo`` (tax
  slip: DARF, GPS/DCTFWeb, FGTS, ISS), ``relatorio_adm`` (management company report) and
  ``extrato_rendimento`` (investment statement);
- ``expense_document.role`` accepts ``copia`` (another file of a note already received: no new
  expense, no duplicate alert) and ``pagamento`` (the payment receipt of an expense);
- ``data_issue.kind`` accepts the contract alerts: ``contrato_assinado_depois`` (signed after
  the term started), ``contrato_contratante`` (the contracting party is not the condominium),
  ``contrato_cnpj_condominio`` (wrong condominium CNPJ in the contract) and
  ``contrato_sem_cnpj`` (no CNPJ of the contracted party);
- ``contract``: ``supplier_id`` may be empty when the contract has no CNPJ of the contracted
  party (then ``supplier_name`` keeps the legal name); ``nature`` ``continuo`` (monthly fee,
  term, adjustment) or ``pontual`` (one-off: total value and installments, no index, no
  monthly note); ``monthly_value`` only for a continuous contract.

Approved by Marcio on 10/11/2026. Additive: existing contracts become ``continuo`` with their
supplier. Downgrade moves the new document types to ``outro``, removes the new links and
alerts, and refuses to run while a one-off contract or a contract without supplier exists.

Revision ID: 0027
Revises: 0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here on purpose: migrations never import lists from the application code.
DOC_TYPES = (
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
    "regimento",
    "apolice",
    "balancete",
    "laudo",
    "plano_manutencao",
)
NEW_DOC_TYPES = ("comprovante", "guia_tributo", "relatorio_adm", "extrato_rendimento")
ROLES = ("fiscal", "cobranca", "recibo")
NEW_ROLES = ("copia", "pagamento")
KINDS = (
    "conflito_documentos",
    "duplicidade_suspeita",
    "dado_vencido",
    "canal_parado",
    "contrato_aditado",
    "revisor_ausente",
    "sindico_sem_acesso",
    "acao_parada",
)
NEW_KINDS = (
    "contrato_assinado_depois",
    "contrato_contratante",
    "contrato_cnpj_condominio",
    "contrato_sem_cnpj",
)
NATURES = ("continuo", "pontual")

DOC_CHECK = "ck_document_doc_type_valid"
ROLE_CHECK = "ck_expense_document_role_valid"
KIND_CHECK = "ck_data_issue_kind_valid"


def _in(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _recheck(name: str, table: str, column: str, values: Sequence[str]) -> None:
    op.drop_constraint(op.f(name), table, type_="check")
    op.create_check_constraint(op.f(name), table, f"{column} IN ({_in(values)})")


def upgrade() -> None:
    _recheck(DOC_CHECK, "document", "doc_type", (*DOC_TYPES, *NEW_DOC_TYPES))
    _recheck(ROLE_CHECK, "expense_document", "role", (*ROLES, *NEW_ROLES))
    _recheck(KIND_CHECK, "data_issue", "kind", (*KINDS, *NEW_KINDS))

    op.add_column(
        "contract",
        sa.Column("nature", sa.String(length=10), server_default="continuo", nullable=False),
    )
    op.add_column("contract", sa.Column("supplier_name", sa.String(length=200), nullable=True))
    op.add_column("contract", sa.Column("total_value", sa.Numeric(14, 2), nullable=True))
    op.add_column("contract", sa.Column("installments", sa.Integer(), nullable=True))
    op.alter_column("contract", "supplier_id", nullable=True)
    op.alter_column("contract", "monthly_value", nullable=True)
    op.create_check_constraint(
        op.f("ck_contract_nature_valid"), "contract", f"nature IN ({_in(NATURES)})"
    )
    op.create_check_constraint(
        op.f("ck_contract_supplier_or_name"),
        "contract",
        "supplier_id IS NOT NULL OR supplier_name IS NOT NULL",
    )
    op.create_check_constraint(
        op.f("ck_contract_value_by_nature"),
        "contract",
        "(nature = 'continuo' AND monthly_value IS NOT NULL) "
        "OR (nature = 'pontual' AND total_value IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_contract_installments_positive"),
        "contract",
        "installments IS NULL OR installments >= 1",
    )


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM contract WHERE nature <> 'continuo' OR supplier_id IS NULL)
          THEN
            RAISE EXCEPTION 'contratos pontuais ou sem fornecedor existem: migre-os antes';
          END IF;
        END $$;
        """)
    for name in (
        "ck_contract_installments_positive",
        "ck_contract_value_by_nature",
        "ck_contract_supplier_or_name",
        "ck_contract_nature_valid",
    ):
        op.drop_constraint(op.f(name), "contract", type_="check")
    op.alter_column("contract", "monthly_value", nullable=False)
    op.alter_column("contract", "supplier_id", nullable=False)
    for column in ("installments", "total_value", "supplier_name", "nature"):
        op.drop_column("contract", column)

    alerts = f"SELECT id FROM data_issue WHERE kind IN ({_in(NEW_KINDS)})"
    op.execute(
        f"DELETE FROM case_link WHERE target_type = 'data_issue' AND target_id IN ({alerts})"
    )
    op.execute(f"DELETE FROM data_issue_event WHERE issue_id IN ({alerts})")
    op.execute(f"DELETE FROM data_issue WHERE kind IN ({_in(NEW_KINDS)})")
    _recheck(KIND_CHECK, "data_issue", "kind", KINDS)

    op.execute(f"DELETE FROM expense_document WHERE role IN ({_in(NEW_ROLES)})")
    _recheck(ROLE_CHECK, "expense_document", "role", ROLES)

    op.execute(f"UPDATE document SET doc_type = 'outro' WHERE doc_type IN ({_in(NEW_DOC_TYPES)})")
    _recheck(DOC_CHECK, "document", "doc_type", DOC_TYPES)
