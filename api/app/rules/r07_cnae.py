"""R07 — CNAE incompatível.

For categories mapped in ``matching.categories.COMPATIBLE_CNAE`` the check is a lookup in the
CNAE classification (deterministic). For unmapped categories the model judges, with a
structured answer and justification, and the finding is marked AI-assisted (confidence ≥
min_confidence). One finding per supplier per month. Amount at risk = sum of its expenses.
"""

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.db.models import Expense
from app.llm.client import LLMUnavailable
from app.matching.categories import category_label, cnae_compatible, supplier_cnaes
from app.rules.base import Evidence, FindingDraft, Rule, RuleContext, expense_evidence
from app.rules.judge import judge_cnae


class IncompatibleCnae(Rule):
    code = "R07"
    name = "Atividade do fornecedor incompatível com o serviço"
    default_severity = Severity.BAIXA
    default_params: ClassVar[dict[str, Any]] = {"min_confidence": 0.8}
    ai_assisted = True

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        min_conf = float(self.params(ctx)["min_confidence"])
        groups: dict[tuple[uuid.UUID, str], list[Expense]] = defaultdict(list)
        for e in ctx.month_expenses:
            s = ctx.suppliers.get(e.supplier_id) if e.supplier_id else None
            if s is not None and s.cnae_main is not None:
                groups[(s.id, e.category)].append(e)

        out: list[FindingDraft] = []
        for (supplier_id, category), expenses in groups.items():
            s = ctx.suppliers[supplier_id]
            compatible = cnae_compatible(category, supplier_cnaes(s))
            justification: str | None = None
            if compatible is None:
                try:
                    verdict = await judge_cnae(
                        ctx.session,
                        condominium_id=ctx.condominium.id,
                        cnaes=[s.cnae_main or {}, *(s.cnae_secondary or [])],
                        charged=ctx.fiscal_text(expenses[0]),
                    )
                except LLMUnavailable as exc:
                    ctx.not_evaluated[f"R07:{supplier_id}:{category}"] = (
                        f"sem IA disponível ({type(exc).__name__})"
                    )
                    continue
                compatible = verdict.compativel or verdict.confidence < min_conf
                justification = verdict.justificativa
            if compatible:
                continue
            total = sum((x.amount for x in expenses), Decimal("0"))
            main = s.cnae_main or {}
            explanation = (
                f"{s.legal_name} tem como atividade principal \"{main.get('code')} "
                f"{main.get('description', '')}\", que não corresponde ao serviço cobrado "
                f"({category_label(category)}, {brl(total)} no mês)."
            )
            if justification is not None:
                explanation += f" Análise assistida por IA: {justification}"
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=explanation,
                    amount_at_risk=total,
                    subject_key=f"R07:{supplier_id}:{category}:{ctx.competence:%Y-%m}",
                    evidence=[
                        Evidence(
                            "supplier",
                            str(supplier_id),
                            "Atividades no CNPJ",
                            "; ".join(supplier_cnaes(s)),
                        ),
                        *[ev for x in expenses for ev in expense_evidence(ctx, x)],
                    ],
                    rule_inputs={
                        "categoria": category,
                        "cnaes": supplier_cnaes(s),
                        "valor_total": str(total),
                        "avaliacao": "ia" if justification is not None else "tabela_cnae",
                    },
                    supplier_id=s.id,
                    ai_assisted=justification is not None,
                )
            )
        return out
