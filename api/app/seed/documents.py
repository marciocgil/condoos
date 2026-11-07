"""Fictitious governing documents for the seed: convention, assembly minutes and one
text per contract. They feed the chat's document search (milestone 5).

All names, numbers and clauses are invented. Texts are deterministic so the chat
evaluation set can rely on them (e.g. the termination fine of the gatehouse contract).
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.search import index_document
from app.core.money import brl
from app.db.enums import DocumentOrigin, DocumentType, ExtractionStatus
from app.db.models import BoardMember, Condominium, Contract, Document, Supplier
from app.extraction.clauses import apply_clauses
from app.storage.base import get_storage

logger = logging.getLogger(__name__)

INDEX_NAMES = {"IPCA": "IPCA/IBGE", "IGPM": "IGP-M/FGV", "INPC": "INPC/IBGE", "NENHUM": "nenhum"}
MONTHS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
# Termination fine and notice period by contract object keyword (deterministic, invented).
TERMS = {
    "Portaria": (Decimal("0.5"), 60),
    "Limpeza": (Decimal("1"), 30),
    "elevadores": (Decimal("1"), 90),
}


def _terms(obj: str) -> tuple[Decimal, int]:
    for key, value in TERMS.items():
        if key in obj:
            return value
    return Decimal("1"), 30


def convention_text(condo: Condominium, board: list[BoardMember]) -> str:
    limits = condo.approval_limits or {}
    default = brl(Decimal(str(limits.get("default", "0"))))
    obras = brl(Decimal(str(limits.get("by_category", {}).get("obras", "0"))))
    sindico = next((b.full_name for b in board if b.position == "sindico"), "o síndico")
    return f"""CONVENÇÃO DE CONDOMÍNIO — {condo.name.upper()}
Documento fictício para demonstração do CondoOS.

CAPÍTULO I — DAS DISPOSIÇÕES GERAIS
Art. 1º O {condo.name}, situado na {condo.address}, é composto por {condo.units} unidades \
autônomas e rege-se por esta Convenção, pelo Regimento Interno e pela legislação aplicável.

CAPÍTULO II — DA ADMINISTRAÇÃO
Art. 12. O condomínio será administrado por um síndico, eleito em assembleia geral para \
mandato de dois anos, permitida a reeleição. O síndico em exercício é {sindico}.
Art. 13. Compete ao síndico contratar serviços e realizar despesas ordinárias previstas no \
orçamento anual aprovado em assembleia.
Art. 14. Despesas não previstas no orçamento acima de {default} por fornecedor, no mesmo \
mês, dependem de aprovação prévia do Conselho Consultivo, registrada por escrito.
Parágrafo único. Despesas com obras e reformas acima de {obras} dependem de aprovação do \
Conselho e da apresentação de pelo menos três orçamentos de fornecedores distintos.
Art. 15. É vedado ao síndico contratar empresa da qual seja sócio, ele próprio, seu cônjuge \
ou parente até o terceiro grau, sem aprovação expressa da assembleia.

CAPÍTULO III — DO CONSELHO CONSULTIVO
Art. 20. O Conselho Consultivo é composto por três condôminos eleitos com o síndico. \
Compete ao Conselho dar parecer sobre as contas do síndico, mensalmente, e aprovar as \
despesas previstas no Art. 14.

CAPÍTULO IV — DO FUNDO DE RESERVA
Art. 25. O fundo de reserva será formado por 5% (cinco por cento) da taxa condominial \
ordinária e só poderá ser utilizado em despesas urgentes e imprevistas ou em obras \
aprovadas em assembleia.

CAPÍTULO V — DAS ASSEMBLEIAS
Art. 30. A assembleia geral ordinária será realizada uma vez por ano, no primeiro \
trimestre, para aprovar as contas do exercício anterior e o orçamento do exercício seguinte.
Art. 31. As deliberações são tomadas por maioria simples dos presentes, salvo quórum \
especial previsto em lei ou nesta Convenção. Obras voluptuárias exigem dois terços dos \
condôminos.

CAPÍTULO VI — DA PRESTAÇÃO DE CONTAS
Art. 40. O síndico prestará contas mensalmente ao Conselho, com os comprovantes de todas \
as despesas, e anualmente à assembleia.
"""


def minutes_text(condo: Condominium, board: list[BoardMember]) -> str:
    names = {b.position: b.full_name for b in board}
    return f"""ATA DA ASSEMBLEIA GERAL ORDINÁRIA — {condo.name.upper()}
Documento fictício para demonstração do CondoOS.

Aos quinze dias do mês de março de 2026, às 19h30, em segunda convocação, reuniram-se os \
condôminos do {condo.name} no salão de festas, sob a presidência de {names.get("sindico", "")}.

Item 1 — Prestação de contas de 2025. As contas do exercício de 2025 foram aprovadas por \
maioria, com parecer favorável do Conselho Consultivo.

Item 2 — Orçamento de 2026. Aprovado o orçamento anual com reajuste de 6% (seis por cento) \
na taxa condominial ordinária a partir de abril de 2026.

Item 3 — Fachada. Aprovada a realização de três orçamentos para a pintura da fachada, a \
serem apresentados ao Conselho até junho de 2026. A obra só poderá ser contratada após \
nova aprovação em assembleia extraordinária.

Item 4 — Portaria. Os condôminos pediram que o síndico verifique se a ronda noturna \
prevista em contrato está sendo cumprida e que o tema volte à próxima assembleia.

Item 5 — Eleição. Foram reeleitos para o Conselho Consultivo \
{names.get("conselheiro", "")} e os demais membros, com mandato até março de 2027.

Nada mais havendo a tratar, a sessão foi encerrada e lavrada esta ata.
"""


def contract_text(condo: Condominium, contract: Contract, supplier: Supplier) -> str:
    fine_months, notice_days = _terms(contract.object)
    fine = brl(contract.monthly_value * fine_months)
    base_month = (
        MONTHS[contract.adjustment_base_month - 1] if contract.adjustment_base_month else "—"
    )
    index = INDEX_NAMES.get(contract.adjustment_index, contract.adjustment_index)
    scope = "; ".join(contract.scope_items) or contract.object
    end = f"{contract.end_date:%d/%m/%Y}" if contract.end_date else "prazo indeterminado"
    return f"""CONTRATO DE PRESTAÇÃO DE SERVIÇOS — {contract.object.upper()}
Documento fictício para demonstração do CondoOS.

CONTRATANTE: {condo.name}.
CONTRATADA: {supplier.legal_name}.

CLÁUSULA 1 — DO OBJETO. {contract.object}, compreendendo: {scope}.
CLÁUSULA 2 — DO PREÇO. Pelos serviços, o CONTRATANTE pagará o valor mensal de \
{brl(contract.monthly_value)}, mediante nota fiscal emitida até o dia 5 do mês \
seguinte ao da prestação.
CLÁUSULA 3 — DO REAJUSTE. O valor será reajustado anualmente, em {base_month}, pela \
variação acumulada do índice {index} nos doze meses anteriores.
CLÁUSULA 4 — DA VIGÊNCIA. Vigência de {contract.start_date:%d/%m/%Y} a {end}.
CLÁUSULA 5 — DA RESCISÃO. Qualquer das partes poderá rescindir este contrato mediante \
aviso prévio de {notice_days} dias. A rescisão sem o aviso prévio sujeita a parte que a \
der causa a multa de {fine}.
CLÁUSULA 6 — DOS SERVIÇOS EXTRAS. Serviços fora do escopo da Cláusula 1 só serão pagos \
mediante orçamento prévio aprovado por escrito pelo síndico.
CLÁUSULA 7 — DAS OBRIGAÇÕES TRABALHISTAS. A CONTRATADA é a única responsável pelos \
encargos trabalhistas e previdenciários de seus empregados.
"""


def _document(condo: Condominium, kind: DocumentType, name: str, content: str) -> Document:
    body = content.encode()
    digest = hashlib.sha256(body).hexdigest()
    doc_id = uuid.UUID(digest[:32])
    return Document(
        id=doc_id,
        condominium_id=condo.id,
        doc_type=kind.value,
        storage_key=f"cond/{condo.id}/seed/{name}",
        sha256=digest,
        original_filename=name,
        mime_type="text/plain",
        origin=DocumentOrigin.SEED.value,
        extraction_status=ExtractionStatus.DONE.value,
        text_content=content,
        page_count=1,
        classification_source="seed",
        extraction_source="seed",
        reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
    )


async def seed_documents(session: AsyncSession) -> int:
    """Create, store and index the governing documents of every seeded condominium."""
    docs: list[Document] = []
    links: list[tuple[Contract, uuid.UUID]] = []
    for condo in await session.scalars(select(Condominium).order_by(Condominium.slug)):
        board = list(
            await session.scalars(select(BoardMember).where(BoardMember.condominium_id == condo.id))
        )
        docs.append(
            _document(condo, DocumentType.CONVENCAO, "convencao.txt", convention_text(condo, board))
        )
        docs.append(
            _document(condo, DocumentType.ATA, "ata-ago-2026-03.txt", minutes_text(condo, board))
        )
        rows = await session.execute(
            select(Contract, Supplier)
            .join(Supplier, Supplier.id == Contract.supplier_id)
            .where(Contract.condominium_id == condo.id)
            .order_by(Contract.start_date, Contract.object)
        )
        for contract, supplier in rows:
            slug = (supplier.trade_name or supplier.legal_name).lower().split()[0]
            doc = _document(
                condo,
                DocumentType.CONTRATO,
                f"contrato-{slug}.txt",
                contract_text(condo, contract, supplier),
            )
            links.append((contract, doc.id))
            apply_clauses(contract, doc.text_content)  # notice period and penalty (CB-060)
            docs.append(doc)
    session.add_all(docs)
    await session.flush()
    for contract, doc_id in links:  # after the documents exist (no ORM relationship here)
        contract.source_document_id = doc_id
    storage = get_storage()
    for doc in docs:
        try:
            storage.put(doc.storage_key, (doc.text_content or "").encode(), doc.mime_type)
        except Exception:  # storage down: the text is in the database, search still works
            logger.warning("seed document not stored id=%s", doc.id)
        await index_document(session, doc)
    return len(docs)
