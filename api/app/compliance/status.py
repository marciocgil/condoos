"""The situation of an obligation, computed on every read and never stored (D112).

Words are chosen with care: a missing record is "nenhum documento registrado no CondoOS",
never "não cumprida"; nothing here says "irregular", "em conformidade" or "conforme".
Declaring compliance is a professional's call, never the system's (Especificação §9).
"""

import calendar
from dataclasses import dataclass
from datetime import date

from app.db.enums import ComplianceApplicability, EvidenceSource
from app.db.models import ComplianceEvidence, ComplianceObligation

# Most urgent first: the screen lists in this order.
ORDER = (
    "vencido",
    "vence_em_breve",
    "sem_documento",
    "sem_validade",
    "lendo",
    "a_validar",
    "em_dia",
    "nao_aplicavel",
    "arquivada",
)
ALERT = frozenset({"vencido", "vence_em_breve"})
LABEL = {
    "vencido": "Vencido",
    "vence_em_breve": "Vence em breve",
    "sem_documento": "Sem documento",
    "sem_validade": "Sem validade",
    "lendo": "Lendo o documento",
    "a_validar": "A validar",
    "em_dia": "Em dia",
    "nao_aplicavel": "Não se aplica",
    "arquivada": "Arquivada",
}
UNCONFIRMED = {
    EvidenceSource.IA.value: "data lida pela IA, a confirmar",
    EvidenceSource.TEXTO.value: "data lida do texto do documento, a confirmar",
}


@dataclass(frozen=True)
class Situation:
    code: str
    label: str
    text: str
    valid_until: date | None = None
    computed: bool = False  # validity = issue date + validated periodicity
    days_left: int | None = None
    to_confirm: str | None = None  # why the date still needs a person

    @property
    def alert(self) -> bool:
        return self.code in ALERT

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "label": self.label,
            "text": self.text,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "computed": self.computed,
            "days_left": self.days_left,
            "to_confirm": self.to_confirm,
            "alert": self.alert,
        }


def _d(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def plus_months(d: date, months: int) -> date:
    """Same day ``months`` later (the last day of the month when it does not exist)."""
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def effective_until(ob: ComplianceObligation, ev: ComplianceEvidence) -> tuple[date | None, bool]:
    if ev.valid_until is not None:
        return ev.valid_until, False
    if ev.issued_on is not None and ob.periodicity_months:
        return plus_months(ev.issued_on, ob.periodicity_months), True
    return None, False


def situation(
    ob: ComplianceObligation, latest: ComplianceEvidence | None, today: date
) -> Situation:
    def make(code: str, text: str, **kw: object) -> Situation:
        return Situation(code, LABEL[code], text, **kw)  # type: ignore[arg-type]

    if ob.archived_at is not None:
        return make("arquivada", "Obrigação arquivada")
    if ob.applicability == ComplianceApplicability.NAO_APLICAVEL.value:
        return make("nao_aplicavel", "Não se aplica a este condomínio (validado)")
    if ob.applicability == ComplianceApplicability.A_VALIDAR.value:
        return make("a_validar", "Confirme se se aplica a este condomínio")
    if latest is None:
        return make("sem_documento", "Nenhum documento registrado no CondoOS")
    if latest.source == EvidenceSource.LENDO.value:
        return make("lendo", "Lendo a validade do documento")
    until, computed = effective_until(ob, latest)
    to_confirm = None if latest.confirmed else UNCONFIRMED.get(latest.source)
    if until is None:
        return make("sem_validade", "Documento sem validade registrada", to_confirm=to_confirm)
    days = (until - today).days
    common: dict[str, object] = {
        "valid_until": until,
        "computed": computed,
        "days_left": days,
        "to_confirm": to_confirm,
    }
    if days < 0:
        return make("vencido", f"Documento registrado venceu em {_d(until)}", **common)
    if days <= ob.lead_days:
        when = "hoje" if days == 0 else "amanhã" if days == 1 else f"em {days} dias"
        return make("vence_em_breve", f"Vence {when} ({_d(until)})", **common)
    return make("em_dia", f"Documento válido até {_d(until)}", **common)
