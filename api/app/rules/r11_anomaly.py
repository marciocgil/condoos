"""R11 — Variação anômala.

Monthly spend of a category > mean + sigma × standard deviation of the previous 12 months
(only months with spending, at least min_months of them). Contract-bound expenses are left
out: contracts are audited by R02/R03/R05. Amount at risk = spend above the limit.
"""

import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl
from app.core.time import add_months
from app.db.enums import Severity
from app.matching.categories import category_label
from app.rules.base import FindingDraft, Rule, RuleContext, expense_evidence


class AnomalousVariation(Rule):
    code = "R11"
    name = "Variação anômala de gasto"
    description = (
        "Gasto da categoria no mês acima da média mais a variação típica dos meses anteriores "
        "(contratos ficam fora)."
    )
    default_severity = Severity.BAIXA
    default_params: ClassVar[dict[str, Any]] = {"sigma": 2, "min_months": 6}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        p = self.params(ctx)
        sigma, min_months = Decimal(str(p["sigma"])), int(p["min_months"])
        history_start = add_months(ctx.competence, -12)
        totals: dict[str, dict[date, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for e in ctx.expenses:
            if e.contract_id is None and history_start <= e.competence <= ctx.competence:
                totals[e.category][e.competence] += e.amount
        out: list[FindingDraft] = []
        for category, by_month in totals.items():
            current = by_month.get(ctx.competence)
            history = [v for m, v in by_month.items() if m < ctx.competence]
            if current is None or len(history) < min_months:
                continue
            mean = Decimal(str(statistics.fmean(history)))
            sd = Decimal(str(statistics.stdev(history))) if len(history) > 1 else Decimal("0")
            limit = (mean + sigma * sd).quantize(Decimal("0.01"))
            if current <= limit:
                continue
            excess = current - limit
            month_items = [
                e for e in ctx.month_expenses if e.category == category and e.contract_id is None
            ]
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=f"Gasto com {category_label(category)} acima do padrão",
                    explanation=(
                        f"O gasto com {category_label(category)} em {ctx.competence:%m/%Y} foi de {brl(current)}. "
                        f"A média dos {len(history)} meses anteriores é {brl(mean)}, e o limite "
                        f"usual (média + {p['sigma']} vezes a variação típica) é {brl(limit)}. Excesso de "
                        f"{brl(excess)}."
                    ),
                    amount_at_risk=excess,
                    subject_key=f"R11:{category}:{ctx.competence:%Y-%m}",
                    evidence=[ev for e in month_items for ev in expense_evidence(ctx, e)],
                    rule_inputs={
                        "categoria": category,
                        "gasto_mes": str(current),
                        "media_12m": str(mean.quantize(Decimal("0.01"))),
                        "desvio_padrao": str(sd.quantize(Decimal("0.01"))),
                        "limite": str(limit),
                        "excesso": str(excess),
                        "meses_historico": len(history),
                        "sigma": p["sigma"],
                    },
                )
            )
        return out
