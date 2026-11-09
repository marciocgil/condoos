"""The síndico's month (LB-082, D108): at most three things to do about the previous month,
built by code only from records, shown on "Hoje" once the implementation reached LM3.

An item appears only while something is missing; a month with nothing pending has no items.
Nothing here grants a permission or closes anything: closing stays with whoever may close
(D77), and the síndico only sees where it stands.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.core.money import brl
from app.core.time import add_months
from app.db.enums import CompetenceStatus, FindingStatus
from app.db.models import Competence, Finding
from app.launch.journey import milestones
from app.reports.data import pending_for_month


def _action(label: str, href: str, primary: bool = False) -> dict[str, Any]:
    return {"label": label, "href": href, "primary": primary}


async def _documents(
    session: AsyncSession, condo_id: uuid.UUID, month: date, today: date
) -> dict[str, Any] | None:
    from app.pending import month_pending  # pending imports rules; keep launch light

    pending = await month_pending(session, condo_id, month, today)
    expected = [c for c in pending.contracts if c.status != "aguardando"]
    if not expected:
        return None
    received = sum(c.status == "faturado" for c in expected)
    in_review = sum(c.status == "em_conferencia" for c in expected)
    if received + in_review >= len(expected):
        return None
    detail = f"{received} de {len(expected)} contratos com nota recebida"
    if in_review:
        detail += f"; {in_review} em conferência"
    return {
        "key": "documentos",
        "title": "Documentos do mês",
        "detail": detail + ".",
        "actions": [
            _action("Enviar notas", "enviar?passo=enviar_faturas", primary=True),
            _action("Pedir a quem tem", "pedidos/novo"),
        ],
    }


async def _decisions(
    session: AsyncSession, condo_id: uuid.UUID, access: CondoAccess
) -> dict[str, Any] | None:
    if not access.can(Permission.DECIDE_FINDING):
        return None
    waiting = (
        Finding.condominium_id == condo_id,
        Finding.status == FindingStatus.PUBLICADO.value,
    )
    count, total = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Finding.amount_at_risk), 0)).where(*waiting)
        )
    ).one()
    if not count:
        return None
    first = await session.scalar(
        select(Finding.id)
        .where(*waiting)
        .order_by(Finding.amount_at_risk.desc(), Finding.id)
        .limit(1)
    )
    noun = "ponto de atenção aguarda" if count == 1 else "pontos de atenção aguardam"
    return {
        "key": "decisoes",
        "title": "Suas decisões",
        "detail": f"{count} {noun} você · {brl(Decimal(total))} em risco.",
        "actions": [_action("Decidir o primeiro", f"achados/{first}", primary=True)],
    }


async def _closing(
    session: AsyncSession, condo_id: uuid.UUID, month: date
) -> dict[str, Any] | None:
    comp = await session.scalar(
        select(Competence).where(Competence.condominium_id == condo_id, Competence.month == month)
    )
    if comp is None or comp.status == CompetenceStatus.FECHADA.value:
        return None
    queue = await pending_for_month(session, condo_id, month)
    waiting = sum(queue.values())
    detail = (
        f"Aguardando a conferência de {waiting} {'item' if waiting == 1 else 'itens'}."
        if waiting
        else "Pronto para fechar. Quem fecha o mês é a equipe responsável."
    )
    return {"key": "fechamento", "title": "Fechamento", "detail": detail, "actions": []}


async def month_routine(
    session: AsyncSession, condo_id: uuid.UUID, access: CondoAccess, today: date
) -> dict[str, Any]:
    """``active`` only after LM3 (the assessor already evaluated a month); before that the
    implementation guide is what leads. The month is the previous one, whose invoices arrive
    in the current month (the same default as the coverage, LB-055)."""
    ms = {m.key: m.done for m in await milestones(session, condo_id)}
    month = add_months(today.replace(day=1), -1)
    out: dict[str, Any] = {"active": ms.get("LM3", False), "month": f"{month:%Y-%m}", "items": []}
    if not out["active"]:
        return out
    for item in (
        await _documents(session, condo_id, month, today),
        await _decisions(session, condo_id, access),
        await _closing(session, condo_id, month),
    ):
        if item is not None:
            out["items"].append(item)
    return out
