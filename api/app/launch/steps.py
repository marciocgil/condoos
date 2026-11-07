"""Next best steps (LB-003, D89): at most three, one primary, from what is actually missing.

A step appears only while its condition is unmet in the data, in the order the chosen goal
gives, and is hidden while put off ("Fazer depois"). Every step says why it matters and what
it unlocks. Steps only point to screens that already exist; none of them acts by itself.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import DocumentType, LaunchGoal
from app.db.models import CaseRecord, Condominium, Document
from app.launch.readiness import NAO_CONFIGURADO, Readiness

MAX_STEPS = 3


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    why: str
    unlocks: str
    # Which existing screen does it: "enviar" (upload), "contratos", "assuntos".
    screen: str


CATALOGUE: dict[str, Step] = {
    s.key: s
    for s in (
        Step(
            "enviar_contrato",
            "Envie um contrato de serviço contínuo (portaria, limpeza, elevador)",
            "Com o contrato, o CondoOS lê valor, reajuste e vigência e mostra o trecho de "
            "onde tirou cada um.",
            "Leitura de contrato",
            "enviar",
        ),
        Step(
            "confirmar_contrato",
            "Confirme os campos do contrato que ficaram em dúvida",
            "Campo com dúvida nunca vira fato: só depois de confirmado entra nas conferências.",
            "Leitura de contrato e confronto de cobranças",
            "contratos",
        ),
        Step(
            "enviar_documento_contrato",
            "Envie o documento dos contratos cadastrados sem arquivo",
            "Sem o documento, não há trecho para mostrar de onde vem cada valor.",
            "Leitura de contrato com evidência",
            "enviar",
        ),
        Step(
            "enviar_faturas",
            "Envie as notas fiscais do mês dos contratos",
            "Com a nota do mês, o CondoOS compara o que foi cobrado com o que o contrato prevê.",
            "Confronto de cobranças",
            "enviar",
        ),
        Step(
            "enviar_convencao",
            "Envie a convenção do condomínio",
            "Com a convenção, dá para perguntar sobre regras e alçadas com a citação do trecho.",
            "Perguntas sobre documentos",
            "enviar",
        ),
        Step(
            "enviar_ata",
            "Envie a última ata de assembleia",
            "A ata mostra o que foi decidido e o que ficou pendente, com o trecho.",
            "Perguntas sobre documentos",
            "enviar",
        ),
        Step(
            "criar_assunto",
            "Conte o que está pendente: crie o primeiro assunto",
            "Um assunto tem responsável, prazo e próxima ação, e não se perde.",
            "Acompanhamento de pendências",
            "assuntos",
        ),
    )
}

STEP_KEYS: frozenset[str] = frozenset(CATALOGUE)

_CONTRACT_FIRST = [
    "enviar_contrato",
    "confirmar_contrato",
    "enviar_faturas",
    "enviar_documento_contrato",
]
ORDER: dict[str | None, list[str]] = {
    None: _CONTRACT_FIRST,
    LaunchGoal.ECONOMIZAR.value: _CONTRACT_FIRST,
    LaunchGoal.FORNECEDORES.value: [
        "enviar_contrato",
        "enviar_documento_contrato",
        "confirmar_contrato",
        "enviar_faturas",
    ],
    LaunchGoal.PENDENCIAS.value: ["criar_assunto", "enviar_ata", *_CONTRACT_FIRST],
    LaunchGoal.PANORAMA.value: ["enviar_convencao", "enviar_ata", *_CONTRACT_FIRST],
}


async def _has_document(session: AsyncSession, condo: Condominium, doc_type: str) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(Document.condominium_id == condo.id, Document.doc_type == doc_type)
            )
        )
    )


async def pending_keys(
    session: AsyncSession, condo: Condominium, readiness: list[Readiness]
) -> set[str]:
    """Steps whose condition is unmet in the data right now."""
    by_cap = {r.capability: r for r in readiness}
    c2, c3 = by_cap["C2"], by_cap["C3"]
    keys: set[str] = set()
    if c2.state == NAO_CONFIGURADO:
        keys.add("enviar_contrato")
    if c2.unmet("sem_campo_a_confirmar"):
        keys.add("confirmar_contrato")
    if c2.unmet("contratos_com_documento"):
        keys.add("enviar_documento_contrato")
    if c3.state != NAO_CONFIGURADO and c3.unmet("faturas_casadas"):
        keys.add("enviar_faturas")
    if not await _has_document(session, condo, DocumentType.CONVENCAO.value):
        keys.add("enviar_convencao")
    if not await _has_document(session, condo, DocumentType.ATA.value):
        keys.add("enviar_ata")
    if not await session.scalar(select(exists().where(CaseRecord.condominium_id == condo.id))):
        keys.add("criar_assunto")
    return keys


def choose(
    pending: set[str], goal: str | None, postponed: dict[str, str], today: date
) -> list[Step]:
    """At most three steps in the goal's order, skipping those put off until after today."""
    out: list[Step] = []
    for key in ORDER.get(goal, ORDER[None]):
        if key not in pending:
            continue
        until = postponed.get(key)
        if until is not None and date.fromisoformat(until) >= today:
            continue
        out.append(CATALOGUE[key])
        if len(out) == MAX_STEPS:
            break
    return out
