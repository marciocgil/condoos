"""R06 — Fornecedor irregular.

Registry status different from "ATIVA" on the expense date (status date on or before the
issue date). Amount at risk = expense value.
"""

from app.core.br import format_cnpj
from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import Evidence, FindingDraft, Rule, RuleContext, expense_evidence


class IrregularSupplier(Rule):
    code = "R06"
    name = "Fornecedor com situação cadastral irregular"
    description = (
        "Fornecedor com situação cadastral na Receita diferente de ATIVA na data da despesa."
    )
    default_severity = Severity.ALTA

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            s = ctx.suppliers.get(e.supplier_id) if e.supplier_id else None
            if s is None or not s.registration_status or s.registration_status == "ATIVA":
                continue
            since = s.registration_status_date
            if since is not None and since > e.issue_date:
                continue  # was still active when the expense was issued
            status = s.registration_status.lower()
            since_text = f" desde {since:%d/%m/%Y}" if since else ""
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=f"Fornecedor com situação cadastral {status}",
                    explanation=(
                        f"O CNPJ {format_cnpj(s.cnpj)} de {s.legal_name} está com situação "
                        f'"{s.registration_status}" na Receita Federal{since_text}, e houve '
                        f"despesa de {brl(e.amount)} emitida em {e.issue_date:%d/%m/%Y}."
                    ),
                    amount_at_risk=e.amount,
                    subject_key=f"R06:{e.id}",
                    evidence=[
                        *expense_evidence(ctx, e),
                        Evidence(
                            "supplier",
                            str(s.id),
                            f"Cadastro CNPJ · {s.registration_status}",
                            f"Situação desde {since:%d/%m/%Y}" if since else "",
                        ),
                    ],
                    rule_inputs={
                        "cnpj": format_cnpj(s.cnpj),
                        "valor": str(e.amount),
                        "situacao_cadastral": s.registration_status,
                        "data_situacao": since.isoformat() if since else None,
                        "data_despesa": e.issue_date.isoformat(),
                    },
                    supplier_id=s.id,
                )
            )
        return out
