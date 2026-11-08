from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def utcnow() -> datetime:
    return datetime.now(UTC)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, months: int) -> date:
    """First day of the month ``months`` after ``d``'s month."""
    index = d.year * 12 + (d.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


DEFAULT_TIMEZONE = "America/Sao_Paulo"


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_today(timezone: str | None) -> date:
    """Today's date in a condominium's time zone (ADR-P07). The server runs in UTC: at 22h in
    São Paulo it is already tomorrow in UTC, so "overdue" and "today" must use this."""
    try:
        zone = ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(zone).date()


def local_date(moment: datetime, timezone: str | None) -> date:
    """The date of an instant in a condominium's time zone (an event at 23h in São Paulo is
    on that day, although it is already the next day in UTC)."""
    try:
        zone = ZoneInfo(timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo(DEFAULT_TIMEZONE)
    return moment.astimezone(zone).date()
