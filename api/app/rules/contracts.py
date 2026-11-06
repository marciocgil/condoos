"""Contract value over time: shared by rules R02/R03 and by the seed generator."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from app.core.time import add_months
from app.db.enums import AdjustmentIndex
from app.enrichment.indices import accumulated_12m

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models import Contract, ContractAmendment

CENT = Decimal("0.01")
INDEXED = {AdjustmentIndex.IPCA.value, AdjustmentIndex.IGPM.value, AdjustmentIndex.INPC.value}


def anniversaries(start: date, base_month: int | None, until: date) -> list[date]:
    """Adjustment months: the base month of each year, starting 12+ months after the start."""
    if base_month is None:
        return []
    month = add_months(start.replace(day=1), 12)
    while month.month != base_month:
        month = add_months(month, 1)
    out: list[date] = []
    while month <= until:
        out.append(month)
        month = add_months(month, 12)
    return out


def is_anniversary(start: date, base_month: int | None, month: date) -> bool:
    return month in anniversaries(start, base_month, month)


def value_at(
    monthly_value: Decimal,
    index: str,
    base_month: int | None,
    start: date,
    month: date,
    index_table: dict[str, dict[date, Decimal]],
    since: date | None = None,
) -> Decimal | None:
    """Monthly value due in ``month`` after every contractual adjustment. None if an index
    value needed for an adjustment is missing.

    ``since``: the value was set by an amendment effective that month, so only the
    adjustments after it apply (the amendment value already includes the earlier ones)."""
    value = monthly_value
    if index not in INDEXED:
        return value
    for anniversary in anniversaries(start, base_month, month):
        if since is not None and anniversary <= since.replace(day=1):
            continue
        acc = accumulated_12m(index_table, index, anniversary)
        if acc is None:
            return None
        value = (value * (1 + acc / 100)).quantize(CENT, rounding=ROUND_HALF_UP)
    return value


def terms_at(
    contract: "Contract", amendments: list["ContractAmendment"], month: date
) -> tuple[Decimal, date | None]:
    """(monthly value, since) in force in ``month``: the latest amendment with a value
    effective on or before the month, else the original contract value (D66)."""
    valued = [
        a
        for a in amendments
        if a.monthly_value is not None and a.effective_date.replace(day=1) <= month
    ]
    if not valued:
        return contract.monthly_value, None
    latest = max(valued, key=lambda a: (a.effective_date, a.created_at or a.effective_date))
    assert latest.monthly_value is not None
    return latest.monthly_value, latest.effective_date


def contract_value_at(
    contract: "Contract",
    amendments: list["ContractAmendment"],
    month: date,
    index_table: dict[str, dict[date, Decimal]],
) -> Decimal | None:
    base, since = terms_at(contract, amendments, month)
    return value_at(
        base,
        contract.adjustment_index,
        contract.adjustment_base_month,
        contract.start_date,
        month,
        index_table,
        since,
    )


async def amendments_by_contract(
    session: "AsyncSession", contract_ids: list["uuid.UUID"]
) -> dict["uuid.UUID", list["ContractAmendment"]]:
    """Amendments of these contracts, oldest first (callers filter by tenant already)."""
    from sqlalchemy import select

    from app.db.models import ContractAmendment

    out: dict[uuid.UUID, list[ContractAmendment]] = {}
    if not contract_ids:
        return out
    for a in await session.scalars(
        select(ContractAmendment)
        .where(ContractAmendment.contract_id.in_(contract_ids))
        .order_by(ContractAmendment.effective_date)
    ):
        out.setdefault(a.contract_id, []).append(a)
    return out
