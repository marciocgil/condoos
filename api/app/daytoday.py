"""The síndico's day to day of one condominium (D127): the month to send, what already
arrived, the farol and the points of attention, all on one screen.

Built by code only from records the product already keeps (expenses, the month's pending
contracts and one-off services, bank statements, payment receipts, the farol the síndico
approved, published findings). It decides nothing and grants nothing: an item says what is
there and what is missing, with one place to send the files.
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.enums import FindingStatus, PublicationStatus
from app.db.models import (
    AuditPeriod,
    AuditPublication,
    BankStatement,
    BankTransaction,
    Condominium,
    Expense,
    ExpenseDocument,
    Finding,
)

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


def month_label(month: date) -> str:
    return MONTHS[month.month - 1]


def _item(key: str, title: str, status: str, detail: str) -> dict[str, Any]:
    return {"key": key, "title": title, "status": status, "detail": detail}


async def _checklist(
    session: AsyncSession, condo_id: uuid.UUID, month: date, today: date
) -> list[dict[str, Any]]:
    from app.pending import month_pending  # pending imports the rules: keep this light

    last = add_months(month, 1) - timedelta(days=1)
    pending = await month_pending(session, condo_id, month, today)
    items: list[dict[str, Any]] = []

    expenses = int(
        await session.scalar(
            select(func.count())
            .select_from(Expense)
            .where(Expense.condominium_id == condo_id, Expense.competence == month)
        )
        or 0
    )
    expected = [c for c in pending.contracts if c.status != "aguardando"]
    missing = [c for c in expected if c.status in ("sem_nf", "sem_faturamento")]
    if missing:
        # One name per contract object (two contracts of the same service read as one).
        unique = list(dict.fromkeys(c.object.strip() for c in missing))
        shown = [n if len(n) <= 40 else n[:39].rstrip() + "…" for n in unique[:2]]
        names = ", ".join(shown)
        more = f" e mais {len(unique) - 2}" if len(unique) > 2 else ""
        items.append(
            _item(
                "notas",
                "Notas e boletos",
                "falta",
                f"{expenses} recebida(s); faltam as de {names}{more}.",
            )
        )
    elif expenses:
        items.append(_item("notas", "Notas e boletos", "ok", f"{expenses} recebida(s)."))
    else:
        items.append(_item("notas", "Notas e boletos", "falta", "Nenhuma recebida ainda."))

    statements = list(
        await session.scalars(
            select(BankStatement).where(
                BankStatement.condominium_id == condo_id,
                BankStatement.format != "cnab",
                BankStatement.period_end.between(month, last + timedelta(days=10)),
            )
        )
    )
    lines = int(
        await session.scalar(
            select(func.count())
            .select_from(BankTransaction)
            .where(
                BankTransaction.condominium_id == condo_id,
                BankTransaction.posted_at.between(month, last),
                BankTransaction.origin != "cnab",
            )
        )
        or 0
    )
    if statements or lines:
        until = max((s.period_end for s in statements if s.period_end), default=None)
        detail = f"Até {until:%d/%m}." if until else f"{lines} lançamento(s) do mês."
        items.append(_item("extrato", "Extrato bancário", "ok", detail))
    else:
        items.append(
            _item("extrato", "Extrato bancário", "falta", "Envie o extrato do mês (OFX ou CSV).")
        )

    waiting = [s for s in pending.one_off if s.pending]
    if waiting:
        first = waiting[0].description[:40]
        items.append(
            _item(
                "propostas",
                "Propostas aprovadas",
                "falta",
                f"{len(waiting)} despesa(s) acima da sua alçada sem aprovação registrada, "
                f"como {first}.",
            )
        )
    elif pending.one_off:
        items.append(_item("propostas", "Propostas aprovadas", "ok", "Despesas avulsas aprovadas."))

    receipts = int(
        await session.scalar(
            select(func.count())
            .select_from(ExpenseDocument)
            .join(Expense, Expense.id == ExpenseDocument.expense_id)
            .where(
                Expense.condominium_id == condo_id,
                Expense.competence == month,
                ExpenseDocument.role == "pagamento",
            )
        )
        or 0
    )
    if receipts:
        items.append(
            _item("comprovantes", "Comprovantes de pagamento", "ok", f"{receipts} recebido(s).")
        )
    return items


async def _farol(session: AsyncSession, condo_id: uuid.UUID, month: date) -> dict[str, Any]:
    approved = await session.scalar(
        select(AuditPublication)
        .where(
            AuditPublication.condominium_id == condo_id,
            AuditPublication.status == PublicationStatus.APROVADA.value,
        )
        .order_by(AuditPublication.submitted_at.desc())
        .limit(1)
    )
    waiting = await session.scalar(
        select(AuditPublication.id).where(
            AuditPublication.condominium_id == condo_id,
            AuditPublication.status == PublicationStatus.AGUARDANDO.value,
        )
    )
    audited = await session.scalar(
        select(AuditPeriod.id).where(
            AuditPeriod.condominium_id == condo_id, AuditPeriod.competence == month
        )
    )
    last: dict[str, Any] | None = None
    if approved is not None:
        counts = approved.snapshot.get("contagem", {})
        last = {
            "id": str(approved.id),
            "competencia": approved.snapshot.get("competencia"),
            "validados": counts.get("VALIDADO", 0),
            "ressalvas": counts.get("COM_RESSALVA", 0),
            "pendentes": counts.get("PENDENTE", 0),
            "divergentes": counts.get("DIVERGENTE", 0),
        }
    approved_month = last["competencia"] if last else None
    return {
        "last_approved": last,
        "waiting_for_you": waiting is not None,
        # The month was audited and not yet approved: the team is still checking it.
        "in_review": audited is not None and approved_month != f"{month:%Y-%m}",
    }


async def _attention(session: AsyncSession, condo_id: uuid.UUID) -> dict[str, Any]:
    rows = list(
        await session.scalars(
            select(Finding)
            .where(
                Finding.condominium_id == condo_id,
                Finding.status == FindingStatus.PUBLICADO.value,
            )
            .order_by(Finding.amount_at_risk.desc(), Finding.created_at)
        )
    )
    return {
        "count": len(rows),
        "items": [{"id": str(f.id), "title": f.title} for f in rows[:2]],
    }


async def day_to_day(
    session: AsyncSession, condo: Condominium, today: date, month: date | None = None
) -> dict[str, Any]:
    """The month to send is the previous one: bills of a month arrive in the next."""
    month = month or add_months(today.replace(day=1), -1)
    from app.implantation import essentials

    ess = await essentials(session, condo, today)
    return {
        "condominium": {"id": str(condo.id), "name": condo.name},
        "month": f"{month:%Y-%m}",
        "month_label": month_label(month),
        # "Apto a operar" = the eight implantation items done (D127, D128).
        "implemented": ess["complete"],
        "implantation": {"done": ess["done"], "total": ess["total"], "percent": ess["percent"]},
        "checklist": await _checklist(session, condo.id, month, today),
        "farol": await _farol(session, condo.id, month),
        "attention": await _attention(session, condo.id),
    }
