"""The next action proposed for a finding (FR-033, D126).

Chosen by code from the rule, never by the model: what to do, why (the rule's own reading),
the evidence it rests on and its authorisation state. When the step is an action of the
catalogue, the state comes from ``app.policy.evaluate`` (needs the síndico's approval, denied,
paused); when it is a step inside the CondoOS (register an approval, ask for a document,
check a payment) it is "você mesmo faz, no CondoOS", and nothing leaves the system. A finding
contested, ignored, discarded or superseded has no next action.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import FindingStatus
from app.db.models import Condominium, Finding
from app.policy import CATALOGUE, POLICY_VERSION, evaluate

NEXT_ACTION_VERSION = "proxima_acao_v1"
# Contested, ignored, discarded or superseded: nothing to do. A confirmed finding is exactly
# when the next action matters.
CLOSED = {
    FindingStatus.CONTESTADO.value,
    FindingStatus.IGNORADO.value,
    FindingStatus.DESCARTADO.value,
    FindingStatus.SUPERADO.value,
}


@dataclass(frozen=True)
class Step:
    title: str
    why: str
    action_type: str | None = None  # a catalogue action, decided by the policy
    internal: str | None = None  # a step inside the CondoOS: "pedido", "aprovacao", "conferir"


STEPS: dict[str, Step] = {
    "R01": Step(
        "Cobrar do fornecedor a devolução do valor pago em duplicidade",
        "Duas despesas com os mesmos dados indicam pagamento em dobro.",
        action_type="fornecedor.cobrar",
    ),
    "R02": Step(
        "Cobrar do fornecedor a diferença acima do valor contratado",
        "A nota está acima do valor do contrato em vigor, além da tolerância.",
        action_type="fornecedor.cobrar",
    ),
    "R03": Step(
        "Cobrar do fornecedor o reajuste aplicado acima do índice",
        "O reajuste aplicado supera o índice do contrato no período.",
        action_type="fornecedor.cobrar",
    ),
    "R04": Step(
        "Pedir ao fornecedor a explicação do serviço fora do escopo",
        "A nota descreve serviço que não aparece no escopo do contrato.",
        action_type="fornecedor.cobrar",
    ),
    "R05": Step(
        "Pedir o aditivo ou o contrato renovado",
        "Há pagamento depois do fim da vigência do contrato.",
        internal="pedido",
    ),
    "R06": Step(
        "Conferir a situação do fornecedor na Receita antes do próximo pagamento",
        "O CNPJ do fornecedor não está ativo na Receita.",
        internal="conferir",
    ),
    "R07": Step(
        "Conferir se a atividade do fornecedor cobre o serviço",
        "A atividade do CNPJ não corresponde ao serviço cobrado.",
        internal="conferir",
    ),
    "R08": Step(
        "Registrar a declaração de relação com o fornecedor na próxima reunião",
        "Há indício de relação entre o fornecedor e alguém do corpo diretivo.",
        internal="conferir",
    ),
    "R09": Step(
        "Pedir a nota ou o recibo do pagamento",
        "Há pagamento no extrato sem documento correspondente.",
        internal="pedido",
    ),
    "R10": Step(
        "Conferir com a administradora se a conta foi paga",
        "Há documento vencido sem pagamento encontrado no extrato.",
        internal="conferir",
    ),
    "R11": Step(
        "Pedir à administradora a explicação da variação",
        "O valor foge do padrão dos meses anteriores.",
        internal="pedido",
    ),
    "R12": Step(
        "Registrar a aprovação da despesa (ata ou proposta aprovada)",
        "A despesa passa da alçada e não há aprovação registrada.",
        internal="aprovacao",
    ),
}
INTERNAL_STATE = {
    "pedido": "Você mesmo faz no CondoOS: o pedido de documentos gera o link e o texto; "
    "o síndico envia.",
    "aprovacao": "Você mesmo faz no CondoOS: a administradora registra a aprovação ligada "
    "ao documento.",
    "conferir": "Conferência interna: nada sai do CondoOS.",
}


async def next_action(
    session: AsyncSession, condo: Condominium, f: Finding
) -> dict[str, Any] | None:
    if f.status in CLOSED:
        return None
    step = STEPS.get(f.rule_code)
    if step is None:
        return None
    evidence = [
        {"label": str(e.get("label") or e.get("rotulo") or e.get("kind") or "evidência")}
        for e in (f.evidence or [])[:5]
        if isinstance(e, dict)
    ]
    out: dict[str, Any] = {
        "title": step.title,
        "why": f"{step.why} {f.explanation}".strip()[:600],
        "evidence": evidence,
        "version": NEXT_ACTION_VERSION,
    }
    if step.action_type is not None:
        result = await evaluate(
            session,
            condo,
            action_type=step.action_type,
            cost_cap=Decimal("0"),
            supplier_id=f.supplier_id,
        )
        out.update(
            {
                "action_type": step.action_type,
                "action_label": CATALOGUE[step.action_type].label,
                "authorization": result.decision.value,
                "authorization_text": result.reason,
                "policy_version": POLICY_VERSION,
            }
        )
    else:
        out.update(
            {
                "action_type": None,
                "internal": step.internal,
                "authorization": "interna",
                "authorization_text": INTERNAL_STATE[step.internal or "conferir"],
                "policy_version": POLICY_VERSION,
            }
        )
    return out
