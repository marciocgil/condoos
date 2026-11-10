"""R08 — Conflito de interesse.

A partner of a supplier paid in the month has the same full name (accents, case and spaces
ignored) as a síndico, subsíndico or conselheiro whose term covers the expense date.
Partial names never match. Amount at risk = everything paid to that supplier in the 12
months up to the audited month.
"""

from datetime import date
from decimal import Decimal

from app.core.money import brl
from app.core.time import add_months
from app.db.enums import Severity
from app.matching.text import normalize_name
from app.rules.base import Evidence, FindingDraft, Rule, RuleContext, expense_evidence

POSITION = {
    "sindico": "síndico(a)",
    "subsindico": "subsíndico(a)",
    "conselheiro": "conselheiro(a)",
}


class ConflictOfInterest(Rule):
    code = "R08"
    name = "Sócio do fornecedor é membro do corpo diretivo"
    description = (
        "Sócio do fornecedor com o mesmo nome completo de um membro do corpo diretivo em "
        "mandato."
    )
    default_severity = Severity.ALTA

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        out: list[FindingDraft] = []
        seen: set[str] = set()
        start = add_months(ctx.competence, -11)
        for e in ctx.month_expenses:
            s = ctx.suppliers.get(e.supplier_id) if e.supplier_id else None
            if s is None or str(s.id) in seen:
                continue
            partners = {normalize_name(p.get("name", "")): p for p in s.partners or []}
            for member in ctx.board:
                if not _active(member.term_start, member.term_end, e.issue_date):
                    continue
                partner = partners.get(normalize_name(member.full_name))
                if partner is None:
                    continue
                seen.add(str(s.id))
                paid = [
                    x
                    for x in ctx.expenses
                    if x.supplier_id == s.id and start <= x.competence <= ctx.competence
                ]
                total = sum((x.amount for x in paid), Decimal("0"))
                position = POSITION.get(member.position, member.position)
                out.append(
                    FindingDraft(
                        rule_code=self.code,
                        severity=self.default_severity,
                        title=f"Sócio do fornecedor é {position} do condomínio",
                        explanation=(
                            f"{member.full_name}, {position} do condomínio, aparece como sócio(a) "
                            f"de {s.legal_name} no cadastro da Receita Federal. Nos últimos 12 "
                            f"meses o condomínio pagou {brl(total)} a essa empresa. Ponto de "
                            f"atenção: verificar se a contratação foi aprovada com ciência do "
                            f"vínculo."
                        ),
                        amount_at_risk=total,
                        subject_key=f"R08:{s.id}:{member.id}",
                        evidence=[
                            Evidence(
                                "supplier",
                                str(s.id),
                                "Quadro societário (Receita Federal)",
                                f"{partner.get('name')} · {partner.get('qualification', '')}",
                            ),
                            Evidence(
                                "board_member",
                                str(member.id),
                                f"Corpo diretivo · {position}",
                                member.full_name,
                            ),
                            *expense_evidence(ctx, e),
                        ],
                        rule_inputs={
                            "socio": partner.get("name"),
                            "membro": member.full_name,
                            "cargo": member.position,
                            "total_pago_12m": str(total),
                            "despesas_12m": len(paid),
                            "meses_periodo": 12,
                        },
                        supplier_id=s.id,
                    )
                )
                break
        return out


def _active(start: date, end: date | None, when: date) -> bool:
    return start <= when and (end is None or when <= end)
