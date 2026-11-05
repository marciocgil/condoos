from datetime import UTC, date, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, months: int) -> date:
    """First day of the month ``months`` after ``d``'s month."""
    index = d.year * 12 + (d.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)
