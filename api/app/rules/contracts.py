"""Contract value over time: shared by rules R02/R03 and by the seed generator."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.core.time import add_months
from app.db.enums import AdjustmentIndex
from app.enrichment.indices import accumulated_12m

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
) -> Decimal | None:
    """Monthly value due in ``month`` after every contractual adjustment. None if an index
    value needed for an adjustment is missing."""
    value = monthly_value
    if index not in INDEXED:
        return value
    for anniversary in anniversaries(start, base_month, month):
        acc = accumulated_12m(index_table, index, anniversary)
        if acc is None:
            return None
        value = (value * (1 + acc / 100)).quantize(CENT, rounding=ROUND_HALF_UP)
    return value
