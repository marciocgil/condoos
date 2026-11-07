"""Coverage and two-way reconciliation (LB-031, LB-037, D94), built on the month's pending
items (D70) and the exception queue that blocks closing (spec §7).

A month is "coberto" only when every contract that expects an invoice has one and nothing
of the month waits in the queue. Anything else is described as partial, with the numbers;
no text produced here ever says "completo".

The other direction of the reconciliation: a supplier charged without a contract in two or
more of the months looked at ("cobrança recorrente sem contrato"). It is a follow-up item,
not a finding: it may be a contract that was never sent, or an honest one-off.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months, month_start
from app.db.models import Condominium, Expense, Supplier
from app.pending import GRACE_DAYS, UTILITIES, month_end, month_pending

MONTHS_PT = (
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
)


def month_name(month: date) -> str:
    return f"{MONTHS_PT[month.month - 1]}/{month.year}"


@dataclass(frozen=True)
class MonthCoverage:
    month: date
    contracts_expected: int
    invoiced: int
    waiting: int  # still within the usual issue time: never counted as missing
    missing: int  # charged without invoice, or nothing at all
    queue: int  # exception-queue items that block closing this month

    @property
    def covered(self) -> bool:
        return self.missing == 0 and self.waiting == 0 and self.queue == 0

    @property
    def label(self) -> str:
        name = month_name(self.month)
        if self.covered:
            if self.contracts_expected == 0:
                return f"Cobertura de {name}: nenhum contrato com nota prevista e fila vazia."
            return (
                f"Cobertura de {name}: os {self.contracts_expected} contratos com nota "
                "prevista têm nota, e a fila do mês está vazia."
            )
        parts = [f"{self.invoiced} de {self.contracts_expected} contratos com nota"]
        if self.waiting:
            parts.append(f"{self.waiting} ainda no prazo de emissão")
        if self.queue:
            parts.append(f"{self.queue} {'item' if self.queue == 1 else 'itens'} na fila")
        return f"Cobertura parcial de {name}: " + "; ".join(parts) + "."

    def as_dict(self) -> dict[str, Any]:
        return {
            "month": self.month.isoformat(),
            "contracts_expected": self.contracts_expected,
            "invoiced": self.invoiced,
            "waiting": self.waiting,
            "missing": self.missing,
            "queue": self.queue,
            "covered": self.covered,
            "label": self.label,
        }


@dataclass
class Reconciliation:
    months: list[MonthCoverage]
    recurring_without_contract: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "months": [m.as_dict() for m in self.months],
            "recurring_without_contract": self.recurring_without_contract,
        }


async def month_coverage(
    session: AsyncSession, condominium_id: uuid.UUID, month: date, today: date
) -> MonthCoverage:
    # Imported here: reports.data imports the launch package for the report header.
    from app.reports.data import pending_for_month

    pending = await month_pending(session, condominium_id, month, today)
    statuses = [c.status for c in pending.contracts]
    queue = await pending_for_month(session, condominium_id, month)
    return MonthCoverage(
        month=month,
        contracts_expected=len(statuses),
        invoiced=statuses.count("faturado"),
        waiting=statuses.count("aguardando"),
        missing=statuses.count("sem_nf") + statuses.count("sem_faturamento"),
        queue=sum(queue.values()),
    )


def last_settled_month(today: date) -> date:
    """The latest month whose usual invoice window has already ended."""
    candidate = add_months(month_start(today), -1)
    if today <= month_end(candidate) + timedelta(days=GRACE_DAYS):
        candidate = add_months(candidate, -1)
    return candidate


async def reconcile(
    session: AsyncSession, condo: Condominium, months: int, today: date
) -> Reconciliation:
    """Coverage of the last ``months`` months (most recent first) and the suppliers charged
    without a contract in two or more of them."""
    first = add_months(month_start(today), -(months - 1))
    month_list = [add_months(month_start(today), -i) for i in range(months)]
    coverage = [await month_coverage(session, condo.id, m, today) for m in month_list]

    exempt = set(
        ((condo.rule_params or {}).get("R12", {}) or {}).get("exempt_categories", UTILITIES)
    )
    seen: dict[uuid.UUID, set[date]] = {}
    for e in await session.scalars(
        select(Expense).where(
            Expense.condominium_id == condo.id,
            Expense.contract_id.is_(None),
            Expense.supplier_id.is_not(None),
            Expense.competence >= first,
        )
    ):
        if e.category in exempt or e.supplier_id is None:
            continue
        seen.setdefault(e.supplier_id, set()).add(e.competence)
    recurring = {sid: ms for sid, ms in seen.items() if len(ms) >= 2}
    names = {
        s.id: s.legal_name
        for s in await session.scalars(select(Supplier).where(Supplier.id.in_(list(recurring))))
    }
    rows = [
        {
            "supplier_id": str(sid),
            "supplier": names.get(sid, ""),
            "months": sorted(m.isoformat() for m in ms),
            "label": (
                f"{names.get(sid, 'Fornecedor')}: cobrança sem contrato em {len(ms)} meses. "
                "Pode ser um contrato que ainda não chegou."
            ),
        }
        for sid, ms in sorted(recurring.items(), key=lambda kv: (-len(kv[1]), names.get(kv[0], "")))
    ]
    return Reconciliation(months=coverage, recurring_without_contract=rows)
