"""R10 — Nota sem pagamento.

An expense of the audited month, past its due date (or issue date) by more than grace_days,
with no matching debit in the bank statement. Amount at risk = expense value.
"""

from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import FindingDraft, Rule, RuleContext, expense_evidence


class UnpaidDocument(Rule):
    code = "R10"
    name = "Nota sem pagamento registrado"
    description = "Despesa vencida há mais que a carência sem débito correspondente no extrato."
    default_severity = Severity.BAIXA
    default_params: ClassVar[dict[str, Any]] = {"grace_days": 10}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        grace = int(self.params(ctx)["grace_days"])
        paid = {t.expense_id for t in ctx.transactions if t.expense_id}
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            due = e.due_date or e.issue_date
            if e.id in paid or (ctx.reference_date - due).days <= grace:
                continue
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f"A despesa de {brl(e.amount)} com {ctx.supplier_name(e)}, com vencimento "
                        f"em {due:%d/%m/%Y}, não tem débito correspondente no extrato após "
                        f"{grace} dias."
                    ),
                    amount_at_risk=e.amount,
                    subject_key=f"R10:{e.id}",
                    evidence=expense_evidence(ctx, e),
                    rule_inputs={
                        "valor": str(e.amount),
                        "vencimento": due.isoformat(),
                        "dias_carencia": grace,
                    },
                    supplier_id=e.supplier_id,
                )
            )
        return out
