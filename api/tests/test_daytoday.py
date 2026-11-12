"""The síndico's day to day (D127): one screen built from records, for whoever sees the
condominium; only who may upload gets the upload."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.time import local_today
from app.daytoday import day_to_day
from app.db.session import sessionmaker_for
from app.main import create_app
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_ACACIAS, condo_id, login
from tests.test_audit import _new_condo


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def test_empty_condominium_is_still_being_implemented(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        out = await day_to_day(s, condo, local_today(condo.timezone))
        assert out["implemented"] is False
        status = {i["key"]: i["status"] for i in out["checklist"]}
        assert status["notas"] == "falta" and status["extrato"] == "falta"
        assert out["farol"]["last_approved"] is None and out["attention"]["count"] == 0
        await s.rollback()


async def test_day_to_day_of_the_seed_and_access(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    async with _client() as ana, _client() as bruno:
        await login(ana, mailer, SINDICA_ACACIAS)
        day = (await ana.get(f"/condominiums/{acacias}/day?competencia=2026-10")).json()
        assert day["month"] == "2026-10" and day["month_label"] == "outubro"
        assert day["can_upload"] is True
        assert {"notas", "extrato"} <= {i["key"] for i in day["checklist"]}
        assert all(i["status"] in ("ok", "falta") for i in day["checklist"])
        assert (await ana.get(f"/condominiums/{mirante}/day")).status_code == 404
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        seen = await bruno.get(f"/condominiums/{acacias}/day")
        assert seen.status_code == 200 and seen.json()["can_upload"] is False
