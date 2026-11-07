"""Readiness per capability (ADR-L03, D89): what each capability can do with the data the
condominium has now, and what is missing. Computed on read, never stored.

States (``docs/condoos-planning/launch/04-prontidao-por-capacidade.md``):

- ``nao_configurado``: an entry requirement is missing (no document, no contract);
- ``analise_parcial``: there is data, but a requirement is missing or something awaits
  confirmation; results carry a coverage label;
- ``supervisionada``: every requirement holds; actions still need a person's approval.

``autorizada`` does not exist yet: no policy rule answers "allow" (D83). Requirements are
binary; no percentage turns a capability on.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEXED_TYPES
from app.core.time import add_months, local_today
from app.data_issues import open_issues
from app.db.enums import CompetenceStatus, DocumentType, ExtractionStatus, PlatformRole
from app.db.models import (
    BankTransaction,
    Competence,
    CondoAssignment,
    Condominium,
    Contract,
    Document,
    DocumentChunk,
    Expense,
)
from app.llm.client import resolve_mode
from app.pending import month_pending
from app.policy import active_pause, approval_limit
from app.reports.data import pending_for_month

State = Literal["nao_configurado", "analise_parcial", "supervisionada"]
STATE_LABEL: dict[str, str] = {
    "nao_configurado": "Ainda não configurado",
    "analise_parcial": "Análise parcial",
    "supervisionada": "Funcionando com sua aprovação",
}
FISCAL_TYPES = (
    DocumentType.NFSE.value,
    DocumentType.NFE.value,
    DocumentType.BOLETO.value,
    DocumentType.RECIBO.value,
)


@dataclass
class Readiness:
    key: str
    title: str
    state: State
    missing: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "state": self.state,
            "state_label": STATE_LABEL[self.state],
            "missing": self.missing,
            "facts": self.facts,
        }


def _month_end(month: date) -> date:
    return (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


async def _count(session: AsyncSession, stmt: Any) -> int:
    return int(await session.scalar(stmt) or 0)


def chat_available() -> bool:
    """Free questions need the model; in ``replay``/``off`` the chat answers 503."""
    return resolve_mode() in ("live", "record")


async def documents_capability(session: AsyncSession, condo_id: uuid.UUID) -> Readiness:
    """C1 — questions about documents (contracts, convention, minutes)."""
    r = Readiness("C1", "Perguntas sobre documentos", "nao_configurado")
    read = await _count(
        session,
        select(func.count())
        .select_from(Document)
        .where(
            Document.condominium_id == condo_id,
            Document.doc_type.in_(INDEXED_TYPES),
            Document.extraction_status == ExtractionStatus.DONE.value,
            Document.text_content.is_not(None),
        ),
    )
    indexed = await _count(
        session,
        select(func.count(func.distinct(DocumentChunk.document_id))).where(
            DocumentChunk.condominium_id == condo_id
        ),
    )
    r.facts = {"documentos_lidos": read, "documentos_indexados": indexed}
    if read == 0:
        r.missing = ["Envie um contrato, a convenção ou uma ata."]
        return r
    r.state = "supervisionada"
    if indexed < read:
        r.state = "analise_parcial"
        r.missing.append(
            f"{read - indexed} de {read} documentos ainda sendo preparados para busca."
        )
    if not chat_available():
        r.state = "analise_parcial"
        r.missing.append(
            "Perguntas livres estão indisponíveis agora; a leitura por campos continua valendo."
        )
    return r


async def contracts_capability(session: AsyncSession, condo_id: uuid.UUID) -> Readiness:
    """C2 — reading of contracts: supplier, value, index and term with their sources."""
    r = Readiness("C2", "Leitura de contratos", "nao_configurado")
    docs = (
        await session.execute(
            select(Document.extraction_status, Document.reviewed_at).where(
                Document.condominium_id == condo_id,
                Document.doc_type == DocumentType.CONTRATO.value,
                # only the version in force of each document (D85)
                ~Document.id.in_(
                    select(Document.supersedes_id).where(
                        Document.condominium_id == condo_id, Document.supersedes_id.is_not(None)
                    )
                ),
            )
        )
    ).all()
    contracts = await _count(
        session,
        select(func.count()).select_from(Contract).where(Contract.condominium_id == condo_id),
    )
    to_confirm = sum(
        1
        for d in docs
        if d.extraction_status == ExtractionStatus.NEEDS_REVIEW.value and d.reviewed_at is None
    )
    in_progress = sum(
        1
        for d in docs
        if d.extraction_status
        in (ExtractionStatus.PENDING.value, ExtractionStatus.PROCESSING.value)
    )
    r.facts = {
        "documentos_de_contrato": len(docs),
        "contratos_organizados": contracts,
        "a_confirmar": to_confirm,
        "em_leitura": in_progress,
    }
    if not docs and contracts == 0:
        r.missing = ["Envie um contrato de serviço contínuo (portaria, limpeza, elevador)."]
        return r
    r.state = "supervisionada"
    if to_confirm:
        r.state = "analise_parcial"
        r.missing.append(
            f"{to_confirm} contrato(s) com campos a confirmar por um revisor antes de qualquer "
            "cálculo."
        )
    if in_progress:
        r.state = "analise_parcial"
        r.missing.append(f"{in_progress} contrato(s) ainda em leitura.")
    if contracts == 0:
        r.state = "analise_parcial"
        r.missing.append("Nenhum contrato organizado ainda a partir dos documentos lidos.")
    return r


async def billing_capability(
    session: AsyncSession, condo_id: uuid.UUID, contracts: Readiness
) -> Readiness:
    """C3 — comparing charges with contracts (Optimize): needs contracts, the month's bills
    and the bank statement. Coverage is always stated; never "complete" with gaps."""
    r = Readiness("C3", "Confronto de cobranças com contratos", "nao_configurado")
    if contracts.state == "nao_configurado":
        r.missing = ["Primeiro preciso de ao menos um contrato lido."]
        return r
    month = await session.scalar(
        select(func.max(Expense.competence)).where(Expense.condominium_id == condo_id)
    )
    if month is None:
        r.missing = ["Envie as notas fiscais ou boletos do último mês."]
        return r
    end = _month_end(month)
    in_force = await _count(
        session,
        select(func.count())
        .select_from(Contract)
        .where(
            Contract.condominium_id == condo_id,
            Contract.start_date <= end,
            or_(Contract.end_date.is_(None), Contract.end_date >= month),
        ),
    )
    billed = await _count(
        session,
        select(func.count(func.distinct(Expense.contract_id))).where(
            Expense.condominium_id == condo_id,
            Expense.competence == month,
            Expense.contract_id.is_not(None),
        ),
    )
    bank = await _count(
        session,
        select(func.count())
        .select_from(BankTransaction)
        .where(
            BankTransaction.condominium_id == condo_id,
            and_(BankTransaction.posted_at >= month, BankTransaction.posted_at <= end),
        ),
    )
    waiting = await _count(
        session,
        select(func.count())
        .select_from(Document)
        .where(
            Document.condominium_id == condo_id,
            Document.doc_type.in_(FISCAL_TYPES),
            Document.extraction_status == ExtractionStatus.NEEDS_REVIEW.value,
            Document.reviewed_at.is_(None),
        ),
    )
    label = month.strftime("%m/%Y")
    r.facts = {
        "mes": month.strftime("%Y-%m"),
        "contratos_vigentes": in_force,
        "contratos_com_cobranca": billed,
        "movimentos_bancarios": bank,
        "documentos_a_conferir": waiting,
    }
    r.state = "supervisionada"
    if contracts.state != "supervisionada":
        r.state = "analise_parcial"
        r.missing.append("Há contratos com campos a confirmar; o confronto deles espera a revisão.")
    if in_force and billed < in_force:
        r.state = "analise_parcial"
        r.missing.append(f"{billed} de {in_force} contratos vigentes com cobrança em {label}.")
    if bank == 0:
        r.state = "analise_parcial"
        r.missing.append(f"Sem extrato bancário de {label} (envie em OFX ou CSV).")
    if waiting:
        r.state = "analise_parcial"
        r.missing.append(f"{waiting} nota(s) ou boleto(s) aguardando conferência.")
    return r


async def actions_capability(session: AsyncSession, condo_id: uuid.UUID) -> Readiness:
    """C7 — actions with the síndico's approval (D83): need the approval limit in force and
    no kill switch on actions. Never "autorizada": every action waits for a person."""
    r = Readiness("C7", "Ações com sua aprovação", "nao_configurado")
    condo = await session.get(Condominium, condo_id)
    limit = approval_limit(condo) if condo is not None else None
    paused = await active_pause(session, condo_id, "action.dispatch") is not None
    r.facts = {"alcada_configurada": limit is not None, "acoes_pausadas": paused}
    if limit is None:
        r.missing = [
            "Alçada do síndico não configurada: a regra de alçada não avalia e nenhuma ação "
            "com custo pode ser aprovada. Peça à administradora ou à equipe CondoOS."
        ]
        return r
    r.state = "supervisionada"
    if paused:
        r.state = "analise_parcial"
        r.missing.append("As ações estão pausadas neste condomínio.")
    return r


async def _reviewer_assigned(session: AsyncSession, condo_id: uuid.UUID) -> bool:
    now = func.now()
    found = await session.scalar(
        select(CondoAssignment.id)
        .where(
            CondoAssignment.condominium_id == condo_id,
            CondoAssignment.platform_role == PlatformRole.CONDOOS_REVIEWER.value,
            CondoAssignment.revoked_at.is_(None),
            or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
        )
        .limit(1)
    )
    return found is not None


async def savings_capability(
    session: AsyncSession, condo_id: uuid.UUID, billing: Readiness
) -> Readiness:
    """C4 — savings recommendations (Optimize): need the comparison of charges working and a
    CondoOS reviewer, since no recommendation reaches the condominium unreviewed (D74, D81)."""
    r = Readiness("C4", "Recomendações de economia", "nao_configurado")
    reviewer = await _reviewer_assigned(session, condo_id)
    r.facts = {"revisora_atribuida": reviewer}
    if billing.state == "nao_configurado":
        r.missing = ["Primeiro preciso confrontar cobranças com contratos."]
        return r
    r.state = "supervisionada"
    if not reviewer:
        r.state = "analise_parcial"
        r.missing.append(
            "Sem revisora CondoOS atribuída: oportunidades ficam internas até a revisão."
        )
    if billing.state != "supervisionada":
        r.state = "analise_parcial"
        r.missing.append("O confronto de cobranças ainda é parcial; a estimativa também será.")
    return r


async def expected_documents_capability(
    session: AsyncSession, condo_id: uuid.UUID, today: date
) -> Readiness:
    """C8 — expected documents: the invoices the contracts in force should bring last month
    (``pending.py``, D70). A missing invoice is "not received yet", never "not issued"."""
    r = Readiness("C8", "Documentos esperados dos contratos", "nao_configurado")
    month = add_months(today.replace(day=1), -1)
    pending = await month_pending(session, condo_id, month, today)
    expected = [c for c in pending.contracts if c.status != "aguardando"]
    waiting = [c for c in pending.contracts if c.status == "aguardando"]
    received = [c for c in expected if c.status == "faturado"]
    label = month.strftime("%m/%Y")
    r.facts = {
        "mes": month.strftime("%Y-%m"),
        "esperados": len(expected),
        "recebidos": len(received),
        "no_prazo": len(waiting),
    }
    if not pending.contracts:
        r.missing = ["Nenhum contrato com faturamento periódico vigente em " + label + "."]
        return r
    r.state = "supervisionada"
    missing = len(expected) - len(received)
    if missing:
        r.state = "analise_parcial"
        r.missing.append(
            f"Nota fiscal de {label} ainda não recebida para {missing} de {len(expected)} "
            "contrato(s). Pode ter sido emitida e não enviada: confira com a administradora."
        )
    return r


async def closing_capability(session: AsyncSession, condo_id: uuid.UUID) -> Readiness:
    """C9 — closing the month: the latest competence, with its exception queue empty and
    someone who may close it (the management's manager or a CondoOS reviewer, D77)."""
    r = Readiness("C9", "Fechamento do mês", "nao_configurado")
    comp = await session.scalar(
        select(Competence)
        .where(Competence.condominium_id == condo_id)
        .order_by(Competence.month.desc())
        .limit(1)
    )
    if comp is None:
        r.missing = ["Nenhum mês avaliado ainda."]
        return r
    label = comp.month.strftime("%m/%Y")
    condo = await session.get(Condominium, condo_id)
    closer = (condo is not None and condo.management_company_id is not None) or (
        await _reviewer_assigned(session, condo_id)
    )
    r.facts = {"mes": comp.month.strftime("%Y-%m"), "status": comp.status}
    if comp.status == CompetenceStatus.FECHADA.value:
        r.state = "supervisionada"
        return r
    queue = await pending_for_month(session, condo_id, comp.month)
    r.facts["fila"] = queue
    r.state = "supervisionada"
    if any(queue.values()):
        r.state = "analise_parcial"
        r.missing.append(
            f"{sum(queue.values())} item(ns) na fila de {label}; o relatório só fecha com a fila "
            "vazia. Até lá, é prévia."
        )
    if not closer:
        r.state = "analise_parcial"
        r.missing.append("Ninguém pode fechar o mês: atribua uma revisora CondoOS.")
    return r


def _with_conflicts(r: Readiness, conflicts: list[Any]) -> Readiness:
    """An open data conflict (D93) makes the capability partial, with its title."""
    mine = [c for c in conflicts if r.key in (c.capabilities or [])]
    if not mine or r.state == "nao_configurado":
        return r
    r.state = "analise_parcial"
    r.facts["divergencias_abertas"] = len(mine)
    for c in mine:
        r.missing.append(f"Divergência em validação: {c.title}.")
    return r


async def readiness(
    session: AsyncSession, condo_id: uuid.UUID, today: date | None = None
) -> list[Readiness]:
    if today is None:
        condo = await session.get(Condominium, condo_id)
        today = local_today(condo.timezone if condo else None)
    c1 = await documents_capability(session, condo_id)
    conflicts = await open_issues(session, condo_id)
    c2 = _with_conflicts(await contracts_capability(session, condo_id), conflicts)
    c3 = _with_conflicts(await billing_capability(session, condo_id, c2), conflicts)
    c4 = await savings_capability(session, condo_id, c3)
    c7 = await actions_capability(session, condo_id)
    c8 = await expected_documents_capability(session, condo_id, today)
    c9 = await closing_capability(session, condo_id)
    return [c1, c2, c3, c4, c7, c8, c9]
