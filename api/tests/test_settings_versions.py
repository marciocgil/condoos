"""CB-012 (FR-006, D85): approval limits and rule parameters are versioned; a change has an
author, a reason and a start; rules evaluate a month with the version in force then."""

from datetime import date

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import Condominium
from app.db.session import sessionmaker_for
from app.main import create_app
from app.rules.engine import build_context
from tests.helpers import GERENTE, condo_id, login

ACACIAS = "jardim-das-acacias"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def test_limits_are_versioned_and_rules_use_the_version_in_force(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, ACACIAS)
    url = f"/condominiums/{acacias}/settings"
    async with _client() as diego:
        await login(diego, mailer, GERENTE)
        original = (await diego.get(url)).json()["approval_limits"]
        try:
            r = await diego.put(
                url,
                json={
                    "approval_limits": {**original, "default": "9500.00"},
                    "reason": "Assembleia de novembro aprovou nova alçada",
                },
            )
            assert r.status_code == 200, r.text
            hist = r.json()["history"]
            newest = hist[0]
            assert newest["approval_limits"]["default"] == "9500.00"
            assert newest["reason"] == "Assembleia de novembro aprovou nova alçada"
            assert newest["changed_by"] == "Diego Fontes Arruda"
            first = hist[-1]
            assert first["version"] == 1 and first["approval_limits"] == original
            assert newest["version"] == first["version"] + len(hist) - 1

            # Saving the same values again creates no version.
            same = await diego.put(url, json={"approval_limits": {**original, "default": "9500"}})
            assert len(same.json()["history"]) == len(hist)

            async with sessionmaker_for(admin_engine)() as s:
                condo = await s.get(Condominium, acacias)
                assert condo is not None
                past = await build_context(s, acacias, date(2026, 3, 1), date.today())
                now = await build_context(s, acacias, date.today().replace(day=1), date.today())
            assert past.limits["default"] == original["default"]  # the month's own version
            assert now.limits["default"] == "9500.00"
            assert now.settings_version == newest["version"]
        finally:
            r = await diego.put(
                url, json={"approval_limits": original, "reason": "Teste: volta ao valor"}
            )
            assert r.status_code == 200
