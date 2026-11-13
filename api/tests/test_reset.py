"""Data reset for a new test from zero (D131): every table of condominium data is emptied,
people and platform settings stay, files under cond/ go, one trail line records it. Runs in
a transaction that is rolled back, so the seed of the other tests stays."""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base
from app.db.models import AppUser, AuditLog, Condominium, Document, Membership
from app.db.session import sessionmaker_for
from app.platform import PlatformError
from app.platform.__main__ import run
from app.platform.reset import KEEP_TABLES, reset_data, tables_to_empty
from app.storage.base import MemoryStorage


async def _count(s: object, model: type) -> int:
    return int(await s.scalar(select(func.count()).select_from(model)) or 0)  # type: ignore[attr-defined]


async def test_reset_empties_condominium_data_and_keeps_people(admin_engine: AsyncEngine) -> None:
    storage = MemoryStorage()
    storage.put("cond/x/docs/a.pdf", b"a", "application/pdf")
    storage.put("outro/b.txt", b"b", "text/plain")
    async with sessionmaker_for(admin_engine)() as s:
        await s.begin()
        users = await _count(s, AppUser)
        assert await _count(s, Condominium) > 0 and await _count(s, Document) > 0
        summary = await reset_data(s, storage)
        assert summary["condominios"] > 0 and summary["arquivos"] == 1
        assert list(storage.objects) == ["outro/b.txt"]
        for model in (Condominium, Document, Membership):
            assert await _count(s, model) == 0
        assert await _count(s, AppUser) == users  # accounts stay
        trail = list(await s.scalars(select(AuditLog.action)))
        assert trail == ["platform.data_reset"]
        # Every table not kept is empty (a new table is emptied unless it is kept on purpose).
        for name in tables_to_empty():
            # Names come from the models' metadata, not from input.
            n = await s.scalar(text(f'SELECT count(*) FROM "{name}"'))  # noqa: S608
            assert n == (1 if name == "audit_log" else 0), name
        await s.rollback()
    async with sessionmaker_for(admin_engine)() as s:
        assert await _count(s, Condominium) > 0  # rolled back: the seed is intact


def test_kept_tables_hold_no_condominium_data() -> None:
    names = {t.name for t in Base.metadata.sorted_tables}
    assert names >= KEEP_TABLES
    for t in Base.metadata.sorted_tables:
        if t.name in KEEP_TABLES:
            assert "condominium_id" not in t.c, t.name
            assert "management_company_id" not in t.c, t.name


async def test_reset_command_requires_the_site_domain() -> None:
    with pytest.raises(PlatformError, match=r"web\.test"):
        await run(["reset-data", "app.condoos.ia.br"])
