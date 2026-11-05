"""Price indices from the Banco Central SGS API, cached in ``index_value``.

Series codes (SGS): IPCA 433, IGP-M 189, INPC 188 — monthly % change. Checked against the
published history (e.g. IPCA jan/2023 = 0.53, INPC jan/2023 = 0.46).
Endpoint: {base}/bcdata.sgs.{code}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa
"""

import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.time import add_months
from app.db.enums import AdjustmentIndex
from app.db.models import IndexValue

SGS_CODES: dict[AdjustmentIndex, int] = {
    AdjustmentIndex.IPCA: 433,
    AdjustmentIndex.IGPM: 189,
    AdjustmentIndex.INPC: 188,
}
FIXTURE = Path(__file__).resolve().parents[1] / "seed" / "fixtures" / "bcb_indices.json"


class IndexUnavailable(Exception):
    pass


async def fetch_series(
    index: AdjustmentIndex, start: date, end: date, client: httpx.AsyncClient | None = None
) -> dict[date, Decimal]:
    code = SGS_CODES[index]
    url = (
        f"{get_settings().bcb_sgs_base_url}/bcdata.sgs.{code}/dados"
        f"?formato=json&dataInicial={start:%d/%m/%Y}&dataFinal={end:%d/%m/%Y}"
    )
    own = client is None
    http = client or httpx.AsyncClient(timeout=30.0)
    try:
        for attempt in range(1, 5):
            try:
                response = await http.get(url)
            except httpx.HTTPError as exc:
                if attempt == 4:
                    raise IndexUnavailable(type(exc).__name__) from exc
                await asyncio.sleep(2 ** (attempt - 1))
                continue
            if response.status_code >= 500 or response.status_code == 429:
                if attempt == 4:
                    raise IndexUnavailable(f"HTTP {response.status_code}")
                await asyncio.sleep(2 ** (attempt - 1))
                continue
            if response.status_code == 404:
                return {}  # BCB answers 404 when the range has no values yet
            response.raise_for_status()
            return {
                date(int(item["data"][6:10]), int(item["data"][3:5]), 1): Decimal(item["valor"])
                for item in response.json()
            }
        raise IndexUnavailable("tentativas esgotadas")
    finally:
        if own:
            await http.aclose()


async def store_values(
    session: AsyncSession, index: AdjustmentIndex, values: dict[date, Decimal], source: str
) -> int:
    for month, pct in values.items():
        await session.execute(
            insert(IndexValue)
            .values(index_name=index.value, month=month, pct_change=pct, source=source)
            .on_conflict_do_update(
                index_elements=["index_name", "month"],
                set_={"pct_change": pct, "source": source},
            )
        )
    return len(values)


async def refresh_indices_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``indices.refresh``: last ``months`` months of every index."""
    months = int(payload.get("months", 24))
    end = date.today()
    start = add_months(end.replace(day=1), -months)
    for index in SGS_CODES:
        values = await fetch_series(index, start, end)
        await store_values(session, index, values, "bcb_sgs")


def fixture_values() -> dict[AdjustmentIndex, dict[date, Decimal]]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["series"]
    out: dict[AdjustmentIndex, dict[date, Decimal]] = {}
    for name, series in data.items():
        out[AdjustmentIndex(name)] = {
            date(int(k[:4]), int(k[5:7]), 1): Decimal(v) for k, v in series["values"].items()
        }
    return out


async def load_index_table(session: AsyncSession) -> dict[str, dict[date, Decimal]]:
    rows = await session.execute(
        select(IndexValue.index_name, IndexValue.month, IndexValue.pct_change)
    )
    table: dict[str, dict[date, Decimal]] = {}
    for name, month, pct in rows:
        table.setdefault(name, {})[month] = pct
    return table


def accumulated_12m(
    table: dict[str, dict[date, Decimal]], index: str, base_month: date
) -> Decimal | None:
    """Accumulated % change over the 12 months before ``base_month`` (e.g. base 2026-03 →
    2025-03..2026-02). None when any month is missing."""
    if index in (AdjustmentIndex.FIXO.value, AdjustmentIndex.NENHUM.value):
        return Decimal("0")
    series = table.get(index, {})
    factor = Decimal("1")
    for i in range(12, 0, -1):
        month = add_months(base_month, -i)
        if month not in series:
            return None
        factor *= 1 + series[month] / 100
    return ((factor - 1) * 100).quantize(Decimal("0.0001"))
