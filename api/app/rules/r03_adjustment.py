"""R03 — Reajuste fora do índice.

In the adjustment month of an indexed contract (IPCA, IGP-M, INPC), the increase applied
over the previous month's payment is compared with the index accumulated over the 12 months
before the base month. Flags when applied − allowed > tolerance_pp percentage points.
Amount at risk = paid − previous × (1 + allowed), for the month evaluated.
"""

from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl, pct
from app.core.time import add_months
from app.db.enums import Severity
from app.enrichment.indices import accumulated_12m
from app.rules.base import FindingDraft, Rule, RuleContext, contract_evidence, expense_evidence
from app.rules.contracts import INDEXED, is_anniversary

INDEX_LABEL = {"IPCA": "IPCA", "IGPM": "IGP-M", "INPC": "INPC"}


class AdjustmentAboveIndex(Rule):
    code = "R03"
    name = "Reajuste acima do índice"
    default_severity = Severity.MEDIA
    default_params: ClassVar[dict[str, Any]] = {"tolerance_pp": 0.5}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        tol = Decimal(str(self.params(ctx)["tolerance_pp"]))
        prev_month = add_months(ctx.competence, -1)
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            c = ctx.contracts.get(e.contract_id) if e.contract_id else None
            if c is None or c.adjustment_index not in INDEXED:
                continue
            if not is_anniversary(c.start_date, c.adjustment_base_month, e.competence):
                continue
            previous = [
                x for x in ctx.expenses if x.contract_id == c.id and x.competence == prev_month
            ]
            if len(previous) != 1:
                continue  # no clear previous monthly payment to compare with
            prev = previous[0]
            allowed = accumulated_12m(ctx.index_table, c.adjustment_index, e.competence)
            if allowed is None:
                ctx.not_evaluated[f"R03:{c.id}"] = "índice do contrato sem valores no período"
                continue
            applied = ((e.amount / prev.amount - 1) * 100).quantize(Decimal("0.01"))
            if applied - allowed <= tol:
                continue
            fair = (prev.amount * (1 + allowed / 100)).quantize(Decimal("0.01"))
            excess = e.amount - fair
            label = INDEX_LABEL[c.adjustment_index]
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=f"Reajuste acima do {label}",
                    explanation=(
                        f"O contrato de {ctx.supplier_name(e)} prevê reajuste pelo {label} em "
                        f"{e.competence:%m/%Y}. O {label} acumulado em 12 meses foi de "
                        f"{pct(allowed)}, mas o valor passou de {brl(prev.amount)} para "
                        f"{brl(e.amount)} ({pct(applied)}). Diferença no mês: {brl(excess)}."
                    ),
                    amount_at_risk=excess,
                    subject_key=f"R03:{e.id}",
                    evidence=[
                        *expense_evidence(ctx, prev),
                        *expense_evidence(ctx, e),
                        contract_evidence(c),
                    ],
                    rule_inputs={
                        "indice": c.adjustment_index,
                        "indice_acumulado_12m_pct": str(allowed),
                        "meses_indice": 12,
                        "reajuste_aplicado_pct": str(applied),
                        "valor_anterior": str(prev.amount),
                        "valor_atual": str(e.amount),
                        "valor_com_indice": str(fair),
                        "diferenca": str(excess),
                        "tolerancia_pp": self.params(ctx)["tolerance_pp"],
                    },
                    supplier_id=e.supplier_id,
                )
            )
        return out
