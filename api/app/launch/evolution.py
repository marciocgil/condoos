"""Centro de Evolução (LB-063, D110): after the implementation, suggest the next adjustment
only when the data already shows the demand. Computed on every read from records, nothing
stored; "Agora não" uses ``launch_state.postponed`` (key ``evo:<signal>``), like the guide.

Each suggestion says what was observed, what changes if it is done, and where to do it. At
most three at a time (Q-L14). Nothing here changes a permission or turns anything on.
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.config import get_settings
from app.core.time import add_months
from app.db.enums import DelegationEventKind
from app.db.models import (
    ActionRequest,
    BankTransaction,
    Condominium,
    Contract,
    DelegationEvent,
    Document,
    Expense,
    Supplier,
)
from app.policy import approval_limit

MAX_SUGGESTIONS = 3
PREFIX = "evo:"
SIGNALS = ("contrato_faltando", "usar_email", "enviar_pedido", "extrato", "alcada")


def _item(
    key: str, observed: str, gain: str, label: str | None, href: str | None
) -> dict[str, Any]:
    return {
        "key": key,
        "observed": observed,
        "gain": gain,
        "action": {"label": label, "href": href} if label and href else None,
    }


async def _missing_contract(
    session: AsyncSession, condo_id: uuid.UUID, today: date
) -> dict[str, Any] | None:
    since = add_months(today.replace(day=1), -6)
    with_contract = select(Contract.supplier_id).where(Contract.condominium_id == condo_id)
    row = (
        await session.execute(
            select(Supplier.legal_name, func.count(distinct(Expense.competence)).label("months"))
            .join(Supplier, Supplier.id == Expense.supplier_id)
            .where(
                Expense.condominium_id == condo_id,
                Expense.competence >= since,
                Expense.supplier_id.not_in(with_contract),
            )
            .group_by(Supplier.legal_name)
            .having(func.count(distinct(Expense.competence)) >= 2)
            .order_by(func.count(distinct(Expense.competence)).desc(), Supplier.legal_name)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    name, months = row
    return _item(
        "contrato_faltando",
        f"{name} cobrou em {months} meses e não há contrato cadastrado com esse fornecedor.",
        "Com o contrato eu confiro valor, reajuste e prazos de aviso das cobranças.",
        "Enviar o contrato",
        "enviar?passo=enviar_contrato",
    )


async def _use_email(session: AsyncSession, condo_id: uuid.UUID) -> dict[str, Any] | None:
    since = func.now() - timedelta(days=60)
    rows = dict(
        (
            await session.execute(
                select(Document.origin, func.count())
                .where(Document.condominium_id == condo_id, Document.created_at >= since)
                .group_by(Document.origin)
            )
        ).all()
    )
    uploads = int(rows.get("upload", 0))
    if uploads < 3 or rows.get("email"):
        return None
    return _item(
        "usar_email",
        f"Nos últimos 60 dias, {uploads} documentos foram enviados à mão e nenhum por e-mail.",
        "Encaminhando as notas para o e-mail do condomínio, elas chegam sozinhas e eu aviso "
        "quando alguma faltar.",
        "Ver o e-mail do condomínio",
        "ajustes",
    )


async def _send_request(session: AsyncSession, condo_id: uuid.UUID) -> dict[str, Any] | None:
    if get_settings().mailer != "smtp":  # the option only exists with a mail server (D103)
        return None
    shared, emailed = (
        await session.execute(
            select(
                func.count().filter(DelegationEvent.kind == DelegationEventKind.COMPARTILHADO),
                func.count().filter(DelegationEvent.kind == DelegationEventKind.EMAIL_ENVIADO),
            ).where(DelegationEvent.condominium_id == condo_id)
        )
    ).one()
    if shared < 3 or emailed:
        return None
    return _item(
        "enviar_pedido",
        f"{shared} pedidos de documento foram compartilhados à mão.",
        "O CondoOS pode enviar o e-mail do pedido depois da sua aprovação, e você acompanha "
        "a entrega pela tela.",
        "Ver os pedidos",
        "pedidos",
    )


async def _bank_statement(
    session: AsyncSession, condo_id: uuid.UUID, today: date
) -> dict[str, Any] | None:
    first = add_months(today.replace(day=1), -2)
    end = today.replace(day=1)
    expenses = await session.scalar(
        select(func.count())
        .select_from(Expense)
        .where(
            Expense.condominium_id == condo_id,
            Expense.competence >= first,
            Expense.competence < end,
        )
    )
    if not expenses:
        return None
    bank = await session.scalar(
        select(func.count())
        .select_from(BankTransaction)
        .where(
            BankTransaction.condominium_id == condo_id,
            BankTransaction.posted_at >= first,
            BankTransaction.posted_at < end,
        )
    )
    if bank:
        return None
    return _item(
        "extrato",
        "Há despesas dos dois últimos meses e nenhum extrato bancário desse período.",
        "Com o extrato eu confiro se cada pagamento tem nota e se nada foi pago duas vezes.",
        "Enviar o extrato",
        "enviar?passo=enviar_extrato",
    )


async def _limit(session: AsyncSession, condo: Condominium, team: bool) -> dict[str, Any] | None:
    if approval_limit(condo) is not None:
        return None
    asked = await session.scalar(
        select(ActionRequest.id)
        .where(ActionRequest.condominium_id == condo.id, ActionRequest.cost_cap > 0)
        .limit(1)
    )
    if asked is None:
        return None
    return _item(
        "alcada",
        "Foi pedida uma ação com custo e a alçada do síndico não está configurada.",
        "Com a alçada, as ações com custo podem ser aprovadas pelo síndico dentro do limite.",
        "Configurar a alçada" if team else None,
        f"/admin/configuracoes?condominio={condo.id}" if team else None,
    )


async def suggestions(
    session: AsyncSession,
    condo: Condominium,
    access: CondoAccess,
    postponed: dict[str, Any],
    today: date,
) -> list[dict[str, Any]]:
    hidden = set()
    for key, until in (postponed or {}).items():
        if not key.startswith(PREFIX):
            continue
        try:
            if date.fromisoformat(str(until)) > today:
                hidden.add(key[len(PREFIX) :])
        except ValueError:
            continue
    team = access.can(Permission.CONFIGURE)
    found = [
        await _missing_contract(session, condo.id, today),
        await _use_email(session, condo.id),
        await _send_request(session, condo.id),
        await _bank_statement(session, condo.id, today),
        await _limit(session, condo, team),
    ]
    return [s for s in found if s is not None and s["key"] not in hidden][:MAX_SUGGESTIONS]
