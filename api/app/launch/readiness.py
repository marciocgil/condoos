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

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import INDEXED_TYPES
from app.config import get_settings
from app.core.time import local_today, month_start
from app.db.enums import AdjustmentIndex, DocumentType, ExtractionStatus
from app.db.models import Condominium, Contract, Document, DocumentChunk, Expense, IndexValue
from app.launch.journey import month_coverage
from app.llm.client import resolve_mode

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


async def readiness(session: AsyncSession, condo: Condominium) -> list[Readiness]:
    """C1-C3 (LF2). The other capabilities enter in later Launch phases."""
    c1 = await c1_documents(session, condo)
    c2 = await c2_contracts(session, condo)
    c3 = await c3_charges(session, condo, c2)
    return [c1, c2, c3]
