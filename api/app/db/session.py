"""Database engines and sessions.

Three connection roles (see docs/decisions.md, D7):
- app: used by the API. Not a superuser, no BYPASSRLS: Row-Level Security applies.
- worker: used by the job worker. Has BYPASSRLS because jobs span tenants.
- admin: table owner. Used by migrations and the seed only.
"""

import uuid
from collections.abc import AsyncIterator, Iterable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def _make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


@lru_cache
def get_app_engine() -> AsyncEngine:
    return _make_engine(get_settings().database_url)


@lru_cache
def get_worker_engine() -> AsyncEngine:
    return _make_engine(get_settings().database_worker_url)


@lru_cache
def get_admin_engine() -> AsyncEngine:
    return _make_engine(get_settings().database_admin_url)


def sessionmaker_for(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One transaction per request, committed when the endpoint returns."""
    maker = sessionmaker_for(get_app_engine())
    async with maker() as session, session.begin():
        yield session


# Always depend on the database through this alias. scope="function" commits *before* the
# response is sent; with the default scope the commit could land after the client already
# received the response (e.g. a fresh session cookie used before its row was committed).
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]


async def set_tenant_scope(session: AsyncSession, condominium_ids: Iterable[uuid.UUID]) -> None:
    """Restrict every RLS-protected table to these condominiums for the current transaction."""
    csv = ",".join(str(c) for c in condominium_ids)
    await session.execute(
        text("SELECT set_config('app.condominium_ids', :ids, true)"), {"ids": csv}
    )


async def accessible_condominium_ids(session: AsyncSession, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Condominiums a user can reach, directly or through a management company.

    Uses a SECURITY DEFINER function so it works before the tenant scope is set.
    """
    result = await session.execute(
        text("SELECT unnest(app_accessible_condominium_ids(:uid))"), {"uid": user_id}
    )
    return [row[0] for row in result]
