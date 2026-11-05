"""R09 — Pago sem nota.

A debit in the audited month with no fiscal backing — no matched expense, or a matched
expense with neither invoice number nor fiscal/receipt document — once grace_days have
passed since the debit. Bank fees and transfers between the condominium's own accounts are
ignored. For public utilities (energy, water, gas) the bill itself is the fiscal document: a
debit matched to an expense with its bill is backed (D62). Amount at risk = debit value.
"""

import re
from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.rules.base import Evidence, FindingDraft, Rule, RuleContext

BANK_OWN = re.compile(
    r"tarifa|cesta de servi|\biof\b|juros|encargos|aplica[cç][aã]o|resgate|mesma titularidade",
    re.I,
)


# Utility bills (concessionárias) are fiscal documents in their own right.
UTILITY_CATEGORIES = {"energia", "agua", "gas"}


class PaidWithoutDocument(Rule):
    code = "R09"
    name = "Débito sem nota fiscal"
    default_severity = Severity.MEDIA
    default_params: ClassVar[dict[str, Any]] = {"grace_days": 10}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        grace = int(self.params(ctx)["grace_days"])
        expenses = {e.id: e for e in ctx.expenses}
        out: list[FindingDraft] = []
        for t in ctx.transactions:
            if t.amount >= 0 or not (ctx.competence <= t.posted_at <= ctx.month_end):
                continue
            if (ctx.reference_date - t.posted_at).days < grace or BANK_OWN.search(t.description):
                continue
            e = expenses.get(t.expense_id) if t.expense_id else None
            if e is not None and (
                e.invoice_number
                or any(role in ("fiscal", "recibo") for role, _ in ctx.documents.get(e.id, []))
                or (e.category in UTILITY_CATEGORIES and ctx.documents.get(e.id))
            ):
                continue
            value = -t.amount
            who = t.payee_name or "favorecido não identificado"
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f"Débito de {brl(value)} em {t.posted_at:%d/%m/%Y} para {who} sem nota "
                        f"fiscal ou recibo correspondente após {grace} dias."
                    ),
                    amount_at_risk=value,
                    subject_key=f"R09:{t.id}",
                    evidence=[
                        Evidence(
                            "bank_transaction",
                            str(t.id),
                            f"Extrato · {t.posted_at:%d/%m/%Y} · R$ {value}",
                            t.description[:200],
                        )
                    ],
                    rule_inputs={
                        "valor": str(value),
                        "data_debito": t.posted_at.isoformat(),
                        "dias_carencia": grace,
                    },
                    supplier_id=e.supplier_id if e else None,
                )
            )
        return out
