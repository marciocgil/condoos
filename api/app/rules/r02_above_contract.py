"""R02 — Valor acima do contrato.

Paid value > contract monthly value adjusted by the contract index accumulated up to the
competence (from the latest amendment in force, D66), plus tolerance_pct%. In an adjustment month of an indexed contract, R03 judges
the adjustment instead (no double counting). Amount at risk = paid − adjusted value.
"""

from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import FindingDraft, Rule, RuleContext, contract_evidence, expense_evidence
from app.rules.contracts import INDEXED, contract_value_at, is_anniversary, terms_at


class AboveContract(Rule):
    code = "R02"
    name = "Valor acima do contrato"
    default_severity = Severity.MEDIA
    default_params: ClassVar[dict[str, Any]] = {"tolerance_pct": 2}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        tol = Decimal(str(self.params(ctx)["tolerance_pct"])) / 100
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            c = ctx.contracts.get(e.contract_id) if e.contract_id else None
            if c is None:
                continue
            if c.adjustment_index in INDEXED and is_anniversary(
                c.start_date, c.adjustment_base_month, e.competence
            ):
                continue  # R03
            amendments = ctx.amendments.get(c.id, [])
            expected = contract_value_at(c, amendments, e.competence, ctx.index_table)
            base_value, _ = terms_at(c, amendments, e.competence)
            if expected is None:
                ctx.not_evaluated[f"R02:{c.id}"] = (
                    "reajuste por índice não acompanhado pelo sistema"
                    if c.adjustment_index == "OUTRO"
                    else "índice do contrato sem valores no período"
                )
                continue
            if e.amount <= expected * (1 + tol):
                continue
            excess = e.amount - expected
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f"{ctx.supplier_name(e)} cobrou {brl(e.amount)} em {e.competence:%m/%Y}. "
                        f"Pelo contrato ({c.object}), o valor reajustado para o mês é "
                        f"{brl(expected)}. Divergência de {brl(excess)}."
                    ),
                    amount_at_risk=excess,
                    subject_key=f"R02:{e.id}",
                    evidence=[*expense_evidence(ctx, e), contract_evidence(c)],
                    rule_inputs={
                        "valor_pago": str(e.amount),
                        "valor_contratual_reajustado": str(expected),
                        "valor_mensal_original": str(base_value),
                        "indice": c.adjustment_index,
                        "diferenca": str(excess),
                        "tolerancia_pct": self.params(ctx)["tolerance_pct"],
                    },
                    supplier_id=e.supplier_id,
                )
            )
        return out
