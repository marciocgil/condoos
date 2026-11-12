"""Implantation of a condominium by the síndico (D127, D128).

Eight required items make a condominium "apto a operar". Each one is computed from records
on every read (nothing is stored as progress); the percentage is items done ÷ 8 and always
comes with the count and what is missing. The capabilities of the Launch (D89) keep working
underneath; this list never grants a permission.

The síndico (who is síndico of at least one condominium) or a CondoOS admin may start one:
the condominium is created with the Receita's name and address, the person becomes its
síndico and the rest is filled in by the conversation or later.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.changes import record_change
from app.core.time import utcnow
from app.db.enums import BoardPosition, ComplianceApplicability, ContractNature
from app.db.models import (
    AdhesionTerm,
    BankAccount,
    BankStatement,
    BoardMember,
    Budget,
    ComplianceEvidence,
    ComplianceObligation,
    Condominium,
    Contract,
    Document,
    Expense,
)

TERM_VERSION = "termo_adesao_v1"
TOTAL = 8


class ImplantationError(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    key: str
    title: str
    why: str
    done: bool
    detail: str
    action: str  # where to do it: "mandato", "termo", "alcada" (in place) or "enviar"

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "why": self.why,
            "done": self.done,
            "detail": self.detail,
            "action": self.action,
        }


async def _count(session: AsyncSession, stmt: Any) -> int:
    return int(await session.scalar(stmt) or 0)


async def _doc_count(session: AsyncSession, condo_id: uuid.UUID, doc_type: str) -> int:
    return await _count(
        session,
        select(func.count())
        .select_from(Document)
        .where(Document.condominium_id == condo_id, Document.doc_type == doc_type),
    )


async def essentials(session: AsyncSession, condo: Condominium, today: date) -> dict[str, Any]:
    cid = condo.id
    items: list[Item] = []
    items.append(
        Item(
            "dados",
            "Dados do condomínio",
            "Nome, endereço e situação vêm da Receita; unidades e cidade dizem o tamanho e o fuso.",
            bool(condo.cnpj and condo.units and condo.units > 0),
            (
                f"{condo.units} unidades · CNPJ conferido"
                if condo.units
                else "Falta o número de unidades."
            ),
            "enviar",
        )
    )
    sindico = await session.scalar(
        select(BoardMember).where(
            BoardMember.condominium_id == cid,
            BoardMember.position == BoardPosition.SINDICO.value,
            BoardMember.term_start <= today,
            (BoardMember.term_end.is_(None)) | (BoardMember.term_end >= today),
        )
    )
    atas = await _doc_count(session, cid, "ata")
    items.append(
        Item(
            "sindico",
            "Você como síndico",
            "O mandato diz até quando você responde pelo condomínio; a ata da eleição prova.",
            sindico is not None and atas > 0,
            (
                "Mandato e ata registrados."
                if sindico is not None and atas > 0
                else "Falta o mandato." if sindico is None else "Falta a ata da eleição."
            ),
            "mandato",
        )
    )
    term = await session.scalar(
        select(AdhesionTerm)
        .where(AdhesionTerm.condominium_id == cid)
        .order_by(AdhesionTerm.accepted_at.desc())
        .limit(1)
    )
    items.append(
        Item(
            "autorizacao",
            "Autorização de uso dos dados",
            "O termo de adesão assinado pelo condomínio diz o que o CondoOS faz com os dados.",
            term is not None,
            (
                f"Termo registrado em {term.accepted_at:%d/%m/%Y}."
                if term
                else "Falta o termo assinado."
            ),
            "termo",
        )
    )
    conv = await _doc_count(session, cid, "convencao")
    items.append(
        Item(
            "convencao",
            "Convenção do condomínio",
            "Com ela eu respondo sobre regras, quóruns e alçadas.",
            conv > 0,
            "Recebida." if conv else "Envie a convenção.",
            "enviar",
        )
    )
    accounts = await _count(
        session,
        select(func.count()).select_from(BankAccount).where(BankAccount.condominium_id == cid),
    )
    recent = await _count(
        session,
        select(func.count())
        .select_from(BankStatement)
        .where(BankStatement.condominium_id == cid, BankStatement.format != "cnab"),
    )
    items.append(
        Item(
            "contas",
            "Contas bancárias",
            "O extrato OFX identifica cada conta e o saldo; sem ele não há conciliação.",
            accounts > 0 and recent > 0,
            (
                f"{accounts} conta(s) com extrato."
                if accounts and recent
                else "Envie o extrato do último mês (OFX) de cada conta."
            ),
            "enviar",
        )
    )
    contracts = await _count(
        session,
        select(func.count())
        .select_from(Contract)
        .where(Contract.condominium_id == cid, Contract.nature == ContractNature.CONTINUO.value),
    )
    items.append(
        Item(
            "contratos",
            "Contratos contínuos",
            "Portaria, limpeza, elevadores: eu leio valor, reajuste e prazo de cada um.",
            contracts > 0,
            (
                f"{contracts} contrato(s)."
                if contracts
                else "Envie os contratos de serviços contínuos."
            ),
            "enviar",
        )
    )
    # The first month sent is what matters: from then on the day to day keeps it current.
    latest = await session.scalar(
        select(func.max(Expense.competence)).where(Expense.condominium_id == cid)
    )
    items.append(
        Item(
            "contas_mes",
            "Contas do último mês",
            "Notas e boletos pagos no último mês: o primeiro farol sai daqui.",
            latest is not None,
            (
                f"Contas de {latest:%m/%Y} recebidas."
                if latest
                else "Envie as notas e boletos do último mês."
            ),
            "enviar",
        )
    )
    limit = (condo.approval_limits or {}).get("default")
    items.append(
        Item(
            "alcada",
            "Alçada de aprovação",
            "Até quanto o síndico aprova sozinho, como diz a convenção ou a ata.",
            limit is not None,
            f"Até R$ {limit}." if limit is not None else "Uma pergunta: até quanto você aprova.",
            "alcada",
        )
    )
    done = sum(1 for i in items if i.done)
    year_budget = await session.scalar(
        select(Budget.id).where(Budget.condominium_id == cid, Budget.year == today.year)
    )
    insurance = await session.scalar(
        select(ComplianceObligation.id)
        .join(ComplianceEvidence, ComplianceEvidence.obligation_id == ComplianceObligation.id)
        .where(
            ComplianceObligation.condominium_id == cid,
            ComplianceObligation.category == "seguro",
            ComplianceObligation.applicability == ComplianceApplicability.APLICAVEL.value,
        )
    )
    pending = [i for i in items if not i.done]
    return {
        "condominium": {"id": str(cid), "name": condo.name},
        "items": [i.as_dict() for i in items],
        "done": done,
        "total": TOTAL,
        "percent": round(done * 100 / TOTAL),
        "complete": done == TOTAL,
        "next": pending[0].as_dict() if pending else None,
        "recommended": [
            {"key": "orcamento", "title": "Orçamento do ano", "done": year_budget is not None},
            {"key": "seguro", "title": "Seguro da edificação", "done": insurance is not None},
        ],
    }


async def set_mandate(
    session: AsyncSession,
    condo: Condominium,
    *,
    name: str,
    term_start: date,
    term_end: date | None,
    user_id: uuid.UUID,
) -> BoardMember:
    if term_end is not None and term_end < term_start:
        raise ImplantationError("O fim do mandato é anterior ao início.")
    member = await session.scalar(
        select(BoardMember).where(
            BoardMember.condominium_id == condo.id,
            BoardMember.position == BoardPosition.SINDICO.value,
            BoardMember.user_id == user_id,
        )
    )
    before = {"term_start": member.term_start, "term_end": member.term_end} if member else None
    if member is None:
        member = BoardMember(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            full_name=name,
            position=BoardPosition.SINDICO.value,
            term_start=term_start,
            term_end=term_end,
            user_id=user_id,
        )
        session.add(member)
    else:
        member.term_start, member.term_end = term_start, term_end
    await session.flush()
    await record_change(
        session,
        action="implantation.mandate",
        object_type="board_member",
        object_id=member.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        before=before,
        after={"term_start": term_start, "term_end": term_end},
    )
    return member


async def record_term(
    session: AsyncSession, condo: Condominium, document_id: uuid.UUID, user_id: uuid.UUID
) -> AdhesionTerm:
    doc = await session.scalar(
        select(Document.id).where(Document.id == document_id, Document.condominium_id == condo.id)
    )
    if doc is None:
        raise LookupError("documento não encontrado")
    row = AdhesionTerm(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        version=TERM_VERSION,
        document_id=document_id,
        accepted_by=user_id,
        accepted_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    await record_change(
        session,
        action="implantation.term",
        object_type="adhesion_term",
        object_id=row.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        before=None,
        after={"version": TERM_VERSION, "document_id": document_id},
    )
    return row


async def set_limit(
    session: AsyncSession, condo: Condominium, value: str, source: str, user_id: uuid.UUID
) -> None:
    """The approval limit as the convention or minutes say (where it is written is required).
    Only while it is not set yet: changing a limit in force stays with who configures."""
    from app.condo_settings import ensure_baseline, record_version

    if (condo.approval_limits or {}).get("default") is not None:
        raise ImplantationError("A alçada já está definida; mudanças passam pela administração.")
    clean = source.strip()
    if len(clean) < 10:
        raise ImplantationError("Diga onde a alçada está escrita (convenção ou ata).")
    try:
        amount = (
            Decimal(value.replace(".", "").replace(",", ".")) if "," in value else Decimal(value)
        )
    except InvalidOperation as exc:
        raise ImplantationError("Valor inválido.") from exc
    if amount <= 0:
        raise ImplantationError("A alçada deve ser maior que zero.")
    await ensure_baseline(session, condo)
    condo.approval_limits = {**(condo.approval_limits or {}), "default": f"{amount:.2f}"}
    version = await record_version(
        session, condo, actor_user_id=user_id, reason=f"Implantação: {clean}"
    )
    await record_change(
        session,
        action="implantation.limit",
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        before={"default": None},
        after={"default": f"{amount:.2f}"},
        reason=clean,
        setting_version=version.version,
    )
