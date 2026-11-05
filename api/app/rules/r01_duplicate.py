"""R01 — Pagamento duplicado.

Two expenses of the same supplier (CNPJ) with values within ±tolerance_pct% issued up to
window_days apart **for the same competence**, or the same invoice number paid twice.
Different competences of a recurring service (e.g. a monthly contract) are not duplicates.
The later expense is the duplicate; amount at risk = its value.
"""

from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import FindingDraft, Rule, RuleContext, expense_evidence


class DuplicatePayment(Rule):
    code = "R01"
    name = "Pagamento duplicado"
    default_severity = Severity.ALTA
    default_params: ClassVar[dict[str, Any]] = {"tolerance_pct": 1, "window_days": 45}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        p = self.params(ctx)
        tol = Decimal(str(p["tolerance_pct"])) / 100
        window = int(p["window_days"])
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            if e.supplier_id is None:
                continue
            for o in ctx.expenses:
                if o.id == e.id or o.supplier_id != e.supplier_id:
                    continue
                if (o.issue_date, str(o.id)) > (e.issue_date, str(e.id)):
                    continue  # only the later one of a pair is the duplicate
                same_invoice = bool(e.invoice_number) and e.invoice_number == o.invoice_number
                similar = (
                    o.competence == e.competence
                    and abs(e.amount - o.amount) <= o.amount * tol
                    and abs((e.issue_date - o.issue_date).days) <= window
                )
                if not (same_invoice or similar):
                    continue
                reason = (
                    f"com o mesmo número de nota ({e.invoice_number})"
                    if same_invoice
                    else f"com valores dentro de {p['tolerance_pct']}% na mesma competência"
                )
                out.append(
                    FindingDraft(
                        rule_code=self.code,
                        severity=self.default_severity,
                        title=self.name,
                        explanation=(
                            f"Duas despesas de {ctx.supplier_name(e)} {reason}: {brl(o.amount)} "
                            f"emitida em {o.issue_date:%d/%m/%Y} e {brl(e.amount)} emitida em "
                            f"{e.issue_date:%d/%m/%Y}. Indício de pagamento em duplicidade."
                        ),
                        amount_at_risk=e.amount,
                        subject_key=f"R01:{e.id}",
                        evidence=expense_evidence(ctx, o) + expense_evidence(ctx, e),
                        rule_inputs={
                            "valor_original": str(o.amount),
                            "valor_duplicado": str(e.amount),
                            "data_original": o.issue_date.isoformat(),
                            "data_duplicada": e.issue_date.isoformat(),
                            "mesmo_numero_nota": same_invoice,
                            "tolerancia_pct": p["tolerance_pct"],
                            "janela_dias": window,
                        },
                        supplier_id=e.supplier_id,
                    )
                )
                break
        return out
