"""Test setup: a fresh PostgreSQL database, migrated and seeded once per session.

Requires a PostgreSQL 16 server with pgvector. Configure the owner connection with
TEST_DATABASE_ADMIN_URL (default: postgres/postgres on localhost:5432).
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

ADMIN_BASE = os.environ.get(
    "TEST_DATABASE_ADMIN_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
)
TEST_DB = os.environ.get("TEST_DATABASE_NAME", "condoos_test")
_base = make_url(ADMIN_BASE)


def _url(user: str, password: str) -> str:
    return str(
        _base.set(username=user, password=password, database=TEST_DB).render_as_string(
            hide_password=False
        )
    )


os.environ.update(
    {
        "ENVIRONMENT": "test",
        "MAILER": "memory",
        "DATABASE_ADMIN_URL": _url(_base.username or "postgres", _base.password or ""),
        "DATABASE_URL": _url("condoos_app_test", "condoos_app_test"),
        "DATABASE_WORKER_URL": _url("condoos_worker_test", "condoos_worker_test"),
        "WEB_BASE_URL": "http://web.test",
        "STORAGE_BACKEND": "memory",
        "LLM_MODE": "replay",
        "DOCUMENT_CONVERTER": "pdfium",
        "LLM_CASSETTE_DIR": str(Path(__file__).resolve().parent / "fixtures" / "llm"),
    }
)

# Imports below read the environment above.
import httpx  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402

from app.auth.mailer import MemoryMailer, get_mailer  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.session import get_admin_engine, get_app_engine, get_worker_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed.run import load_seed  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]


async def _recreate_database() -> None:
    engine = create_async_engine(ADMIN_BASE, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        await conn.exec_driver_sql(f'CREATE DATABASE "{TEST_DB}"')
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def database() -> AsyncIterator[None]:
    get_settings.cache_clear()
    await _recreate_database()
    subprocess.run(  # noqa: ASYNC221  (one-off, before any test runs)
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        check=True,
        env=os.environ.copy(),
    )
    await load_seed(get_admin_engine())
    yield
    for engine in (get_app_engine(), get_worker_engine(), get_admin_engine()):
        await engine.dispose()


@pytest.fixture
def admin_engine() -> AsyncEngine:
    return get_admin_engine()


@pytest.fixture
def app_engine() -> AsyncEngine:
    return get_app_engine()


@pytest.fixture
def worker_engine() -> AsyncEngine:
    return get_worker_engine()


@pytest.fixture
def mailer() -> MemoryMailer:
    m = get_mailer()
    assert isinstance(m, MemoryMailer)
    m.sent.clear()
    return m


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as c:
        yield c


@pytest.fixture(autouse=True)
async def _reset_magic_link_rate_limit(database: None) -> None:
    """Each test starts with a clean per-hour magic-link budget."""
    from sqlalchemy import text

    async with get_admin_engine().begin() as conn:
        await conn.execute(
            text("UPDATE magic_link_token SET created_at = created_at - interval '2 hours'")
        )
