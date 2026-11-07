"""Readiness per capability (ADR-L03, D89): what each capability can do with the data the
condominium has now, and what is missing. Computed on read, never stored.

States (``docs/condoos-planning/launch/04-prontidao-por-capacidade.md``):
``nao_configurado`` (an entry requirement is missing), ``analise_parcial`` (there is data, but
some requirement is unmet) and ``supervisionada`` (every requirement met; actions still need a
person's approval each time). ``autorizada`` does not exist in the product (D83).

Requirements are binary. No percentage or score turns a capability on.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEXED_TYPES
from app.config import get_settings
from app.core.time import local_today, month_start, utcnow
from app.db.enums import (
    AdjustmentIndex,
    DocumentOrigin,
    DocumentType,
    ExtractionStatus,
    PlatformRole,
    Role,
)
from app.db.models import (
    Competence,
    CondoAssignment,
    Condominium,
    Contract,
    Document,
    DocumentChunk,
    Expense,
    IndexValue,
    Membership,
)
from app.launch import coverage as cov
from app.launch.journey import month_coverage
from app.llm.client import resolve_mode
from app.policy import active_pause, approval_limit

NAO_CONFIGURADO = "nao_configurado"
ANALISE_PARCIAL = "analise_parcial"
SUPERVISIONADA = "supervisionada"

STATE_LABELS = {
    NAO_CONFIGURADO: "Ainda não configurado",
    ANALISE_PARCIAL: "Análise parcial",
    SUPERVISIONADA: "Funcionando com sua aprovação",
}

# Indices the CondoOS loads from the Central Bank (BCB SGS).
BCB_INDICES = {AdjustmentIndex.IPCA.value, AdjustmentIndex.IGPM.value, AdjustmentIndex.INPC.value}


@dataclass(frozen=True)
class Requirement:
    key: str
    label: str
    met: bool
    detail: str = ""
    # An entry requirement: without it the capability is "nao_configurado".
    entry: bool = False


@dataclass(frozen=True)
class Readiness:
    capability: str
    name: str
    requirements: list[Requirement]
    coverage: dict[str, Any] = field(default_factory=dict)

    @property
    def state(self) -> str:
        if any(r.entry and not r.met for r in self.requirements):
            return NAO_CONFIGURADO
        if all(r.met for r in self.requirements):
            return SUPERVISIONADA
        return ANALISE_PARCIAL

    @property
    def missing(self) -> list[Requirement]:
        return [r for r in self.requirements if not r.met]

    def unmet(self, key: str) -> bool:
        return any(r.key == key and not r.met for r in self.requirements)


def assistant_available() -> bool:
    """The chat answers only with an API key and a mode that calls the model."""
    key = get_settings().anthropic_api_key
    has_key = bool(key and key.get_secret_value().strip())
    return has_key and resolve_mode() in ("live", "record")


def _current() -> Any:
    """A document that no newer version replaces (D85)."""
    newer = Document.__table__.alias("newer")
    return ~exists().where(newer.c.supersedes_id == Document.id)


async def c1_documents(session: AsyncSession, condo: Condominium) -> Readiness:
    done_indexable = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(exists().where(DocumentChunk.document_id == Document.id)),
            ).where(
                Document.condominium_id == condo.id,
                Document.doc_type.in_(INDEXED_TYPES),
                Document.extraction_status == ExtractionStatus.DONE.value,
                Document.text_content.is_not(None),
                _current(),
            )
        )
    ).one()
    total, indexed = int(done_indexable[0]), int(done_indexable[1])
    return Readiness(
        "C1",
        "Perguntas sobre documentos",
        [
            Requirement(
                "documento_lido",
                "Contrato, convenção ou ata lido",
                total > 0,
                (
                    f"{total} documento(s) lido(s)"
                    if total
                    else "Envie um contrato, a convenção " "ou uma ata."
                ),
                entry=True,
            ),
            Requirement(
                "trechos_indexados",
                "Trechos prontos para consulta",
                total > 0 and indexed == total,
                f"{indexed} de {total} com trechos" if total else "",
            ),
            Requirement(
                "assistente_disponivel",
                "Assistente disponível",
                assistant_available(),
                (
                    ""
                    if assistant_available()
                    else "O assistente está indisponível agora; os "
                    "documentos podem ser lidos pelos trechos."
                ),
            ),
        ],
    )


async def c2_contracts(session: AsyncSession, condo: Condominium) -> Readiness:
    contracts = (
        await session.scalars(select(Contract).where(Contract.condominium_id == condo.id))
    ).all()
    today = local_today(condo.timezone)
    active = [c for c in contracts if c.start_date <= today and (c.end_date or today) >= today]
    to_confirm = int(
        await session.scalar(
            select(func.count()).where(
                Document.condominium_id == condo.id,
                Document.doc_type == DocumentType.CONTRATO.value,
                Document.needs_review.is_(True),
                Document.reviewed_at.is_(None),
                _current(),
            )
        )
        or 0
    )
    with_source = set(
        (
            await session.scalars(
                select(Document.id).where(
                    Document.condominium_id == condo.id,
                    Document.id.in_([c.source_document_id for c in active if c.source_document_id]),
                    Document.text_content.is_not(None),
                )
            )
        ).all()
    )
    no_source = [c for c in active if c.source_document_id not in with_source]
    return Readiness(
        "C2",
        "Leitura de contrato",
        [
            Requirement(
                "contrato_recebido",
                "Contrato recebido",
                bool(contracts) or to_confirm > 0,
                "" if contracts or to_confirm else "Envie um contrato de serviço contínuo.",
                entry=True,
            ),
            Requirement(
                "contrato_cadastrado",
                "Contrato com fornecedor, valor e vigência confirmados",
                bool(contracts),
                f"{len(contracts)} contrato(s)" if contracts else "Nenhum contrato confirmado.",
            ),
            Requirement(
                "sem_campo_a_confirmar",
                "Nenhum contrato com campo a confirmar",
                to_confirm == 0,
                f"{to_confirm} contrato(s) com campo a confirmar" if to_confirm else "",
            ),
            Requirement(
                "contratos_com_documento",
                "Contratos vigentes com o documento de origem",
                not no_source,
                f"{len(no_source)} contrato(s) vigente(s) sem o documento" if no_source else "",
            ),
        ],
    )


async def reference_month(session: AsyncSession, condominium_id: uuid.UUID) -> date | None:
    """The latest month with an expense: the month the comparison of charges looks at."""
    latest = await session.scalar(
        select(func.max(Expense.competence)).where(Expense.condominium_id == condominium_id)
    )
    return month_start(latest) if latest is not None else None


async def c3_charges(session: AsyncSession, condo: Condominium, c2: Readiness) -> Readiness:
    contracts = (
        await session.scalars(select(Contract).where(Contract.condominium_id == condo.id))
    ).all()
    today = local_today(condo.timezone)
    billed = [
        c
        for c in contracts
        if c.billing_frequency_months > 0
        and c.start_date <= today
        and (c.end_date or today) >= today
    ]
    month = await reference_month(session, condo.id)
    with_invoice, expected = (0, 0)
    if month is not None:
        with_invoice, expected = await month_coverage(session, condo.id, month)
    indices = {c.adjustment_index for c in billed if c.adjustment_index in BCB_INDICES}
    loaded = set(
        (
            await session.scalars(
                select(IndexValue.index_name).where(IndexValue.index_name.in_(indices)).distinct()
            )
        ).all()
    )
    lacking_index = sorted(indices - loaded)
    coverage: dict[str, Any] = {}
    if month is not None:
        coverage = {
            "mes": f"{month:%Y-%m}",
            "contratos_com_fatura": with_invoice,
            "contratos_esperados": expected,
        }
    if month is None:
        invoice_detail = "Nenhuma fatura recebida ainda."
    elif expected == 0:
        invoice_detail = f"Nenhum contrato com fatura prevista em {month:%m/%Y}."
    else:
        invoice_detail = f"{with_invoice} de {expected} contrato(s) com fatura em {month:%m/%Y}"
    return Readiness(
        "C3",
        "Confronto de cobranças",
        [
            Requirement(
                "contrato_com_cobranca",
                "Contrato vigente com cobrança periódica",
                bool(billed),
                "" if billed else "Nenhum contrato vigente com cobrança periódica.",
                entry=True,
            ),
            Requirement(
                "leitura_de_contrato",
                "Leitura de contrato funcionando",
                c2.state == SUPERVISIONADA,
                "" if c2.state == SUPERVISIONADA else "Falta concluir a leitura dos contratos.",
            ),
            Requirement(
                "faturas_casadas",
                "Fatura do mês casada com cada contrato",
                month is not None and expected > 0 and with_invoice == expected,
                invoice_detail,
            ),
            Requirement(
                "indices_disponiveis",
                "Índices de reajuste disponíveis",
                not lacking_index,
                f"Sem série carregada: {', '.join(lacking_index)}" if lacking_index else "",
            ),
        ],
        coverage,
    )


async def c7_actions(session: AsyncSession, condo: Condominium) -> Readiness:
    """Operational actions (D83): the policy only takes requests with the síndico's limit
    set (policy v2, D93), someone who approves, and automations not paused."""
    limit = approval_limit(condo)
    now = utcnow()
    approver = await session.scalar(
        select(Membership.id).where(
            Membership.condominium_id == condo.id,
            Membership.role == Role.SINDICO.value,
            Membership.revoked_at.is_(None),
            Membership.accepted_at.is_not(None),
            or_(Membership.expires_at.is_(None), Membership.expires_at > now),
        )
    )
    paused = await active_pause(session, condo.id, "action.dispatch") is not None
    return Readiness(
        "C7",
        "Ações com sua aprovação",
        [
            Requirement(
                "alcada_configurada",
                "Alçada do síndico configurada",
                limit is not None,
                "" if limit is not None else "Sem alçada, nenhuma ação é pedida.",
                entry=True,
            ),
            Requirement(
                "sindico_ativo",
                "Síndico com acesso para aprovar",
                approver is not None,
                "" if approver else "O síndico ainda não fez o primeiro acesso.",
            ),
            Requirement(
                "acoes_nao_pausadas",
                "Ações não pausadas",
                not paused,
                "As ações estão pausadas neste condomínio." if paused else "",
            ),
        ],
    )


async def _active_reviewer(session: AsyncSession, condominium_id: uuid.UUID) -> bool:
    now = utcnow()
    return (
        await session.scalar(
            select(CondoAssignment.id).where(
                CondoAssignment.condominium_id == condominium_id,
                CondoAssignment.platform_role == PlatformRole.CONDOOS_REVIEWER.value,
                CondoAssignment.revoked_at.is_(None),
                or_(CondoAssignment.valid_until.is_(None), CondoAssignment.valid_until > now),
            )
        )
        is not None
    )


async def c4_savings(session: AsyncSession, condo: Condominium, c3: Readiness) -> Readiness:
    """Savings recommendations (D81): only on top of a working comparison of charges, and
    only with a CondoOS reviewer to review each one before the condominium sees it."""
    reviewer = await _active_reviewer(session, condo.id)
    return Readiness(
        "C4",
        "Recomendação de economia",
        [
            Requirement(
                "confronto_funcionando",
                "Confronto de cobranças funcionando",
                c3.state == SUPERVISIONADA,
                "" if c3.state == SUPERVISIONADA else "Falta concluir o confronto de cobranças.",
                entry=True,
            ),
            Requirement(
                "revisor_atribuido",
                "Revisor CondoOS atribuído",
                reviewer,
                "" if reviewer else "Sem revisor, nenhuma recomendação chega ao condomínio.",
            ),
        ],
    )


async def c8_expected_documents(session: AsyncSession, condo: Condominium) -> Readiness:
    """Expected documents (D70): contracts with periodic billing, a known input channel and,
    for the latest month whose issue window has ended, every expected invoice received.
    Invoices still within the window are "aguardando", never missing."""
    today = local_today(condo.timezone)
    billed = [
        c
        for c in (
            await session.scalars(select(Contract).where(Contract.condominium_id == condo.id))
        ).all()
        if c.billing_frequency_months > 0 and (c.end_date or today) >= today
    ]
    channel = await session.scalar(
        select(Document.id)
        .where(
            Document.condominium_id == condo.id,
            Document.origin.in_([DocumentOrigin.UPLOAD.value, DocumentOrigin.EMAIL.value]),
        )
        .limit(1)
    )
    month = cov.last_settled_month(today)
    coverage = await cov.month_coverage(session, condo.id, month, today)
    received = coverage.missing == 0
    return Readiness(
        "C8",
        "Documentos esperados",
        [
            Requirement(
                "contrato_com_cobranca",
                "Contrato vigente com cobrança periódica",
                bool(billed),
                "" if billed else "Nenhum contrato vigente com cobrança periódica.",
                entry=True,
            ),
            Requirement(
                "canal_de_entrada",
                "Canal de entrada com documento recebido",
                channel is not None,
                "" if channel else "Nenhum documento enviado ou recebido por e-mail ainda.",
            ),
            Requirement(
                "notas_do_mes_recebidas",
                f"Notas de {cov.month_name(month)} recebidas",
                received,
                (
                    ""
                    if received
                    else f"{coverage.invoiced} de {coverage.contracts_expected} contratos com nota"
                ),
            ),
        ],
        {
            "mes": f"{month:%Y-%m}",
            "contratos_com_fatura": coverage.invoiced,
            "contratos_esperados": coverage.contracts_expected,
        },
    )


async def c9_closing(session: AsyncSession, condo: Condominium) -> Readiness:
    """Closing the month (spec §7): the month's queue empty and someone who may close it
    (the management company's manager or a CondoOS reviewer, D77)."""
    latest = await session.scalar(
        select(Competence)
        .where(Competence.condominium_id == condo.id)
        .order_by(Competence.month.desc())
        .limit(1)
    )
    from app.reports.data import pending_for_month  # reports imports the launch package

    queue = (
        sum((await pending_for_month(session, condo.id, latest.month)).values()) if latest else 0
    )
    manager = None
    if condo.management_company_id is not None:
        now = utcnow()
        manager = await session.scalar(
            select(Membership.id).where(
                Membership.management_company_id == condo.management_company_id,
                Membership.role == Role.GERENTE.value,
                Membership.revoked_at.is_(None),
                or_(Membership.expires_at.is_(None), Membership.expires_at > now),
            )
        )
    closer = manager is not None or await _active_reviewer(session, condo.id)
    name = cov.month_name(latest.month) if latest else ""
    return Readiness(
        "C9",
        "Fechamento do mês",
        [
            Requirement(
                "mes_conferido",
                "Mês já conferido pelas regras",
                latest is not None,
                "" if latest else "Nenhum mês conferido ainda.",
                entry=True,
            ),
            Requirement(
                "fila_do_mes_vazia",
                f"Fila de {name} vazia" if latest else "Fila do mês vazia",
                latest is not None and queue == 0,
                f"{queue} {'item' if queue == 1 else 'itens'} na fila" if queue else "",
            ),
            Requirement(
                "quem_fecha",
                "Quem fecha o mês atribuído",
                closer,
                "" if closer else "Atribua um revisor CondoOS ou o gerente da administradora.",
            ),
        ],
        {"mes": f"{latest.month:%Y-%m}"} if latest else {},
    )


async def readiness(session: AsyncSession, condo: Condominium) -> list[Readiness]:
    """C1-C4 and C7-C9. C5 and C6 (delegation and messages) enter with LF4."""
    c1 = await c1_documents(session, condo)
    c2 = await c2_contracts(session, condo)
    c3 = await c3_charges(session, condo, c2)
    c4 = await c4_savings(session, condo, c3)
    c7 = await c7_actions(session, condo)
    c8 = await c8_expected_documents(session, condo)
    c9 = await c9_closing(session, condo)
    return [c1, c2, c3, c4, c7, c8, c9]
