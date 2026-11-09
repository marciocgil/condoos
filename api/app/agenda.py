"""Agenda of a condominium (D71): what is due, expected or ending, by date.

A follow-up view over data the system already has — it creates nothing and decides nothing:
- ``vencimento``: due date of each expense (from the boleto or bill), with ``pago`` (a debit
  matched in the bank statement), ``vencido`` (past due, unpaid) or ``a_vencer``;
- ``nf_prevista``: when a contract's invoice is expected (billing frequency, D70), on the
  usual issue day seen in its past invoices — always marked as predicted; ``em_conferencia``
  when a document of the supplier for the month already arrived by any channel (LB-052);
- ``reajuste``: the adjustment month of indexed contracts;
- ``fim_contrato``: end of the term (contracts with an indeterminate term never appear).

It never suggests or schedules a payment: the system does not move money.
"""

import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.enums import AdjustmentIndex
from app.db.models import (
    BankTransaction,
    Contract,
    ContractAmendment,
    Expense,
    ExpenseDocument,
    Supplier,
)
from app.enrichment.indices import load_index_table
from app.pending import GRACE_DAYS, arrivals, billing_expected, month_end
from app.rules.contracts import anniversaries, contract_value_at, terms_at

KINDS = ("vencimento", "nf_prevista", "reajuste", "aviso_previo", "fim_contrato", "validade")
ADJUSTING = {
    AdjustmentIndex.IPCA.value,
    AdjustmentIndex.IGPM.value,
    AdjustmentIndex.INPC.value,
    AdjustmentIndex.OUTRO.value,
}
INDEX_NAME = {"IPCA": "IPCA", "IGPM": "IGP-M", "INPC": "INPC"}


@dataclass
class Event:
    date: date
    kind: str
    title: str
    detail: str
    status: str
    predicted: bool = False
    amount: Decimal | None = None
    contract_id: uuid.UUID | None = None
    expense_id: uuid.UUID | None = None
    obligation_id: uuid.UUID | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["amount"] = None if self.amount is None else f"{self.amount:.2f}"
        d["contract_id"] = str(self.contract_id) if self.contract_id else None
        d["expense_id"] = str(self.expense_id) if self.expense_id else None
        d["obligation_id"] = str(self.obligation_id) if self.obligation_id else None
        return d


def _months(start: date, end: date) -> list[date]:
    out, m = [], start.replace(day=1)
    while m <= end:
        out.append(m)
        m = add_months(m, 1)
    return out


def _on_day(month: date, day: int) -> date:
    return month.replace(day=min(day, month_end(month).day))


async def condominium_agenda(
    session: AsyncSession, condominium_id: uuid.UUID, start: date, end: date, today: date
) -> list[Event]:
    contracts = list(
        await session.scalars(select(Contract).where(Contract.condominium_id == condominium_id))
    )
    supplier_ids = {c.supplier_id for c in contracts}
    expenses = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condominium_id,
                # the window plus a year of history for the usual issue day of contracts
                Expense.competence >= add_months(start.replace(day=1), -12),
                Expense.competence <= end,
            )
        )
    )
    supplier_ids |= {e.supplier_id for e in expenses if e.supplier_id}
    suppliers = list(await session.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids))))
    names = {s.id: s.trade_name or s.legal_name for s in suppliers}
    cnpjs = {s.id: s.cnpj for s in suppliers}
    arrived_cache: dict[date, dict[str, list[dict[str, str]]]] = {}

    async def arrived(month: date) -> dict[str, list[dict[str, str]]]:
        """Documents that arrived by any channel and are still in review (LB-052)."""
        if month not in arrived_cache:
            arrived_cache[month] = (await arrivals(session, condominium_id, month))[0]
        return arrived_cache[month]

    paid = {
        r[0]: r[1]
        for r in await session.execute(
            select(BankTransaction.expense_id, BankTransaction.posted_at).where(
                BankTransaction.condominium_id == condominium_id,
                BankTransaction.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
            )
        )
    }
    fiscal = set(
        await session.scalars(
            select(ExpenseDocument.expense_id).where(
                ExpenseDocument.condominium_id == condominium_id,
                ExpenseDocument.role == "fiscal",
            )
        )
    )
    amendments: dict[uuid.UUID, list[ContractAmendment]] = {}
    for amendment in await session.scalars(
        select(ContractAmendment).where(ContractAmendment.condominium_id == condominium_id)
    ):
        amendments.setdefault(amendment.contract_id, []).append(amendment)

    table = await load_index_table(session)

    def expected(c: Contract, month: date) -> Decimal:
        """Value due in the month: amendments and index adjustments applied (D66, D68)."""
        mine = amendments.get(c.id, [])
        return contract_value_at(c, mine, month, table) or terms_at(c, mine, month)[0]

    events: list[Event] = []

    # Due dates of expenses.
    for e in expenses:
        if e.due_date is None or not (start <= e.due_date <= end):
            continue
        if e.id in paid:
            status = "pago"
        elif e.due_date < today:
            status = "vencido"
        else:
            status = "a_vencer"
        who = (
            names.get(e.supplier_id, "Fornecedor não identificado")
            if e.supplier_id
            else ("Fornecedor não identificado")
        )
        events.append(
            Event(
                date=e.due_date,
                kind="vencimento",
                title=f"Vencimento · {who}",
                detail=e.description,
                status=status,
                amount=e.amount,
                contract_id=e.contract_id,
                expense_id=e.id,
            )
        )

    for c in contracts:
        name = names.get(c.supplier_id, "")
        history = sorted((e for e in expenses if e.contract_id == c.id), key=lambda e: e.competence)
        usual_day = int(statistics.median(e.issue_date.day for e in history[-6:])) if history else 1
        # Expected invoices.
        for month in _months(start, end):
            if not billing_expected(c, month):
                continue
            when = _on_day(month, usual_day)
            if not (start <= when <= end):
                continue
            mine = [e for e in history if e.competence == month]
            invoiced = next((e for e in mine if e.invoice_number or e.id in fiscal), None)
            if invoiced is not None:
                status = "recebida"
            elif (await arrived(month)).get(cnpjs.get(c.supplier_id, "")):
                status = "em_conferencia"
            elif today > month_end(month) + timedelta(days=GRACE_DAYS):
                status = "nao_chegou"
            else:
                status = "prevista"
            events.append(
                Event(
                    date=invoiced.issue_date if invoiced else when,
                    kind="nf_prevista",
                    title=f"NF do contrato · {name}",
                    detail=c.object
                    + (
                        f" · NF {invoiced.invoice_number}"
                        if invoiced and invoiced.invoice_number
                        else ""
                    ),
                    status=status,
                    predicted=invoiced is None,
                    amount=invoiced.amount if invoiced else expected(c, month),
                    contract_id=c.id,
                    expense_id=invoiced.id if invoiced else None,
                )
            )
        # Adjustments.
        if c.adjustment_index in ADJUSTING:
            index = INDEX_NAME.get(c.adjustment_index) or c.adjustment_index_other or "outro índice"
            for anniversary in anniversaries(c.start_date, c.adjustment_base_month, end):
                if start <= anniversary <= end or (anniversary < start <= month_end(anniversary)):
                    events.append(
                        Event(
                            date=max(anniversary, start),
                            kind="reajuste",
                            title=f"Reajuste · {name}",
                            detail=f"{c.object} · {index}",
                            status="previsto" if anniversary > today else "conferir",
                            predicted=anniversary > today,
                            contract_id=c.id,
                        )
                    )
        # Last day to give notice before the end of the term (CB-060), read from the contract.
        if c.end_date is not None and c.notice_days:
            deadline = c.end_date - timedelta(days=c.notice_days)
            if start <= deadline <= end:
                events.append(
                    Event(
                        date=deadline,
                        kind="aviso_previo",
                        title=f"Prazo do aviso prévio · {name}",
                        detail=(
                            f"{c.notice_days} dias antes do fim; renova automaticamente se "
                            "ninguém avisar"
                            if c.auto_renewal
                            else f"{c.notice_days} dias antes do fim do contrato"
                        ),
                        status="previsto" if deadline >= today else "vencido",
                        predicted=deadline >= today,
                        contract_id=c.id,
                    )
                )
        # End of the term.
        if c.end_date is not None and start <= c.end_date <= end:
            events.append(
                Event(
                    date=c.end_date,
                    kind="fim_contrato",
                    title=f"Fim do contrato · {name}",
                    detail=c.object,
                    status="vence" if c.end_date >= today else "vencido",
                    contract_id=c.id,
                )
            )

    events.extend(await _compliance_events(session, condominium_id, start, end, today))

    order = {k: i for i, k in enumerate(KINDS)}
    events.sort(key=lambda ev: (ev.date, order[ev.kind], ev.title))
    return events


async def _compliance_events(
    session: AsyncSession, condominium_id: uuid.UUID, start: date, end: date, today: date
) -> list[Event]:
    """Validity of documents registered for compliance obligations (D112): the expiry day
    and the day to start renewing (the obligation's lead time). Only applicable ones."""
    from app.compliance import rows_for
    from app.compliance.status import UNCONFIRMED

    out: list[Event] = []
    for row in await rows_for(session, condominium_id, today):
        until = row.situation.valid_until
        if until is None or row.situation.code not in ("em_dia", "vence_em_breve", "vencido"):
            continue
        ob = row.obligation
        note = (
            UNCONFIRMED.get(row.evidence.source, "")
            if row.evidence and not row.evidence.confirmed
            else ""
        )
        detail = "Validade do documento registrado" + (f" ({note})" if note else "")
        if start <= until <= end:
            out.append(
                Event(
                    date=until,
                    kind="validade",
                    title=f"Vence · {ob.name}",
                    detail=detail,
                    status="vencido" if until < today else "vence",
                    obligation_id=ob.id,
                )
            )
        warn = until - timedelta(days=ob.lead_days)
        if start <= warn <= end and warn < until:
            out.append(
                Event(
                    date=warn,
                    kind="validade",
                    title=f"Começar a renovação · {ob.name}",
                    detail=f"{ob.lead_days} dias antes do vencimento",
                    status="renovar",
                    obligation_id=ob.id,
                )
            )
    return out
