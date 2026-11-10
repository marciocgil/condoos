"""R05 — Contrato vencido.

Payment date (bank debit when matched, else due date, else issue date) after the contract's
end date. Amount at risk = expense value.
"""

from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import FindingDraft, Rule, RuleContext, contract_evidence, expense_evidence


class ExpiredContract(Rule):
    code = "R05"
    name = "Pagamento após o fim do contrato"
    description = "Pagamento feito depois do fim da vigência do contrato."
    default_severity = Severity.MEDIA

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            c = ctx.contracts.get(e.contract_id) if e.contract_id else None
            if c is None or c.end_date is None:
                continue
            paid_on = ctx.payment_date(e)
            if paid_on <= c.end_date:
                continue
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f"O contrato com {ctx.supplier_name(e)} ({c.object}) terminou em "
                        f"{c.end_date:%d/%m/%Y}, mas houve pagamento de {brl(e.amount)} em "
                        f"{paid_on:%d/%m/%Y}. Ponto de atenção: verificar aditivo ou novo contrato."
                    ),
                    amount_at_risk=e.amount,
                    subject_key=f"R05:{e.id}",
                    evidence=[*expense_evidence(ctx, e), contract_evidence(c)],
                    rule_inputs={
                        "valor": str(e.amount),
                        "fim_vigencia": c.end_date.isoformat(),
                        "data_pagamento": paid_on.isoformat(),
                    },
                    supplier_id=e.supplier_id,
                )
            )
        return out
