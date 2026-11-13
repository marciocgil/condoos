"""Data reset for a new test from zero (D131). Operator only: run by ``deploy/reset.sh`` with
the owner database role, never from the API.

Empties every table except the people and the platform's own settings: accounts, CondoOS
roles, sessions and login links, the Banco Central index series and the versions of the
agents' prompts. Everything of condominiums (registry, documents, analyses, audit, trail)
and of management companies goes, and the files under ``cond/`` are deleted. People keep
their accounts with no access until invited again. One line in the trail records the reset.

This is the one sanctioned exception to "append only" (decision, audit_log and the other
append-only tables): it exists for test data and is never offered in the product.
"""

import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.db.base import Base
from app.db.models import Condominium, Document
from app.storage.base import ObjectStorage

# Kept on purpose. A new table is emptied unless it is added here (and here only when it is
# not data of a condominium).
KEEP_TABLES = frozenset(
    {
        "app_user",
        "platform_role",
        "user_session",
        "magic_link_token",
        "index_value",
        "agent_prompt_version",
        "agent_prompt_event",
        "prompt_test_run",
    }
)
FILES_PREFIX = "cond/"


def tables_to_empty() -> list[str]:
    return [t.name for t in Base.metadata.sorted_tables if t.name not in KEEP_TABLES]


async def reset_data(
    session: AsyncSession, storage: ObjectStorage, *, actor_user_id: uuid.UUID | None = None
) -> dict[str, Any]:
    """Truncates in one statement (all or nothing, inside the caller's transaction) and then
    deletes the files. Rerunning is safe."""
    condos = int(await session.scalar(select(func.count()).select_from(Condominium)) or 0)
    docs = int(await session.scalar(select(func.count()).select_from(Document)) or 0)
    names = ", ".join(f'"{n}"' for n in tables_to_empty())
    await session.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    summary: dict[str, Any] = {"condominios": condos, "documentos": docs}
    await record_audit(
        session,
        action="platform.data_reset",
        object_type="platform",
        object_id=None,
        actor_user_id=actor_user_id,
        condominium_id=None,
        details=summary,
    )
    await session.flush()
    summary["arquivos"] = storage.delete_prefix(FILES_PREFIX)
    return summary
