"""Next best steps (LB-003): at most three, one primary, from what is actually missing.

A step appears only while its condition is unmet, in the order the chosen goal gives, and is
hidden while put off ("Fazer depois"). Every step says why it matters and what it unlocks.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.launch.readiness import Readiness

GOALS = ("economizar", "pendencias", "fornecedores", "panorama")
MAX_STEPS = 3


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    why: str
    unlocks: str
    href: str  # relative to /condominio/<id>/

    def as_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "label": self.label,
            "why": self.why,
            "unlocks": self.unlocks,
            "href": self.href,
        }


CATALOGUE: dict[str, Step] = {
    s.key: s
    for s in (
        Step(
            "enviar_contrato",
            "Envie um contrato de serviço contínuo",
            "Com o contrato eu confiro valor, reajuste e prazos de aviso. Você não precisa "
            "digitar nada.",
            "Leitura de contratos",
            "enviar",
        ),
        Step(
            "enviar_faturas",
            "Envie as notas ou boletos do último mês",
            "Com as cobranças eu comparo o que foi pago com o que os contratos dizem.",
            "Confronto de cobranças",
            "enviar",
        ),
        Step(
            "enviar_extrato",
            "Envie o extrato bancário do último mês (OFX ou CSV)",
            "Com o extrato eu confiro se cada pagamento tem nota e se nada foi pago duas vezes.",
            "Confronto de cobranças",
            "enviar",
        ),
        Step(
            "enviar_convencao",
            "Envie a convenção ou a última ata",
            "Com eles eu localizo regras e decisões do condomínio quando você precisar.",
            "Perguntas sobre documentos",
            "enviar",
        ),
        Step(
            "criar_assunto",
            "Conte uma pendência que está te preocupando",
            "Eu registro com responsável, próxima ação e prazo, e acompanho até resolver.",
            "Organização de pendências",
            "assuntos/novo",
        ),
    )
}

ORDER: dict[str | None, tuple[str, ...]] = {
    "economizar": ("enviar_contrato", "enviar_faturas", "enviar_extrato", "enviar_convencao"),
    "pendencias": ("criar_assunto", "enviar_convencao", "enviar_contrato", "enviar_faturas"),
    "fornecedores": ("enviar_contrato", "enviar_faturas", "enviar_extrato", "criar_assunto"),
    "panorama": ("enviar_convencao", "enviar_contrato", "enviar_faturas", "criar_assunto"),
    None: ("enviar_contrato", "enviar_convencao", "criar_assunto", "enviar_faturas"),
}


def unmet(readiness: list[Readiness], open_cases: int) -> set[str]:
    by_key = {r.key: r for r in readiness}
    out: set[str] = set()
    if by_key["C1"].facts.get("documentos_lidos", 0) == 0:
        out.add("enviar_convencao")
    c2 = by_key["C2"]
    if c2.state == "nao_configurado":
        out.add("enviar_contrato")
    c3 = by_key["C3"].facts
    if c2.state != "nao_configurado":
        if not c3.get("mes") or c3.get("contratos_com_cobranca", 0) < c3.get(
            "contratos_vigentes", 0
        ):
            out.add("enviar_faturas")
        if c3.get("mes") and c3.get("movimentos_bancarios", 0) == 0:
            out.add("enviar_extrato")
    if open_cases == 0:
        out.add("criar_assunto")
    return out


def next_steps(
    goal: str | None,
    readiness: list[Readiness],
    open_cases: int,
    postponed: dict[str, Any],
    today: date,
) -> list[dict[str, Any]]:
    missing = unmet(readiness, open_cases)
    hidden = set()
    for key, until in (postponed or {}).items():
        try:
            if date.fromisoformat(str(until)) > today:
                hidden.add(key)
        except ValueError:
            continue
    keys = [k for k in ORDER.get(goal, ORDER[None]) if k in missing and k not in hidden]
    return [{**CATALOGUE[k].as_dict(), "primary": i == 0} for i, k in enumerate(keys[:MAX_STEPS])]
