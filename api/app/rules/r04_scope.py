"""R04 — Serviço fora do escopo (assistida por IA).

A deterministic check runs first: when the charged service shares most meaningful words with
the contract object or a scope item, it is in scope and the model is not called. Otherwise
the model judges with a structured answer and a justification; a finding is raised only when
it says "out of scope" with confidence ≥ min_confidence. Amount at risk = expense value.
Without the model the rule is reported as not evaluated (never guessed).
"""

from typing import Any, ClassVar

from app.core.money import brl
from app.db.enums import Severity
from app.llm.client import LLMUnavailable
from app.matching.text import overlap
from app.rules.base import FindingDraft, Rule, RuleContext, contract_evidence, expense_evidence
from app.rules.judge import judge_scope

IN_SCOPE_OVERLAP = 0.5


class OutOfScope(Rule):
    code = "R04"
    name = "Serviço fora do escopo do contrato"
    description = (
        "Serviço cobrado que não aparece no objeto nem no escopo do contrato; a IA só julga "
        "quando a conferência por palavras não decide."
    )
    default_severity = Severity.MEDIA
    default_params: ClassVar[dict[str, Any]] = {"min_confidence": 0.8}
    ai_assisted = True

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        min_conf = float(self.params(ctx)["min_confidence"])
        out: list[FindingDraft] = []
        for e in ctx.month_expenses:
            c = ctx.contracts.get(e.contract_id) if e.contract_id else None
            if c is None:
                continue
            charged = ctx.fiscal_text(e)
            best = max([overlap(charged, c.object), *(overlap(charged, s) for s in c.scope_items)])
            if best >= IN_SCOPE_OVERLAP:
                continue
            try:
                verdict = await judge_scope(
                    ctx.session,
                    condominium_id=ctx.condominium.id,
                    contract_object=c.object,
                    scope_items=list(c.scope_items),
                    charged=charged,
                )
            except LLMUnavailable as exc:
                ctx.not_evaluated[f"R04:{e.id}"] = f"sem IA disponível ({type(exc).__name__})"
                continue
            if verdict.dentro_do_escopo or verdict.confidence < min_conf:
                continue
            out.append(
                FindingDraft(
                    rule_code=self.code,
                    severity=self.default_severity,
                    title=self.name,
                    explanation=(
                        f'{ctx.supplier_name(e)} cobrou {brl(e.amount)} por "{charged[:160]}", '
                        f"que não aparece no escopo do contrato ({c.object}). "
                        f"Análise assistida por IA: {verdict.justificativa}"
                    ),
                    amount_at_risk=e.amount,
                    subject_key=f"R04:{e.id}",
                    evidence=[*expense_evidence(ctx, e), contract_evidence(c)],
                    rule_inputs={
                        "valor": str(e.amount),
                        "servico_cobrado": charged[:300],
                        "escopo": list(c.scope_items),
                        "confianca_ia": verdict.confidence,
                        "confianca_minima": min_conf,
                    },
                    supplier_id=e.supplier_id,
                    ai_assisted=True,
                )
            )
        return out
