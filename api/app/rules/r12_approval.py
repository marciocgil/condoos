"""R12 — Quebra de alçada.

Expense above the condominium's approval limit (per category, else the default) with no
approval recorded. Contract-bound expenses (approved when the contract was signed) and
exempt categories (utility bills by default) are not checked. Amount at risk = expense value.
"""

from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.matching.categories import category_label
from app.rules.base import FindingDraft, Rule, RuleContext, expense_evidence


class ApprovalLimit(Rule):
    code = "R12"
    name = "Despesa acima da alçada sem aprovação"
    default_severity = Severity.MEDIA
    default_params: ClassVar[dict[str, Any]] = {"exempt_categories": ["energia", "agua", "gas"]}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        limits = ctx.condominium.approval_limits or {}
        exempt = set(self.params(ctx)["exempt_categories"])
        by_category = limits.get("by_category", {})
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            if e.contract_id is not None or e.category in exempt or ctx.approvals.get(e.id):
                continue
            raw = by_category.get(e.category, limits.get("default"))
            if raw is None:
                continue
            limit = Decimal(str(raw))
            if e.amount <= limit:
                continue
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f"A despesa de {brl(e.amount)} com {ctx.supplier_name(e)} supera a "
                        f"alçada de {brl(limit)} para {category_label(e.category)} e não há aprovação "
                        f"registrada."
                    ),
                    amount_at_risk=e.amount,
                    subject_key=f"R12:{e.id}",
                    evidence=expense_evidence(ctx, e),
                    rule_inputs={
                        "valor": str(e.amount),
                        "alcada": str(limit),
                        "categoria": e.category,
                    },
                    supplier_id=e.supplier_id,
                )
            )
        return out
