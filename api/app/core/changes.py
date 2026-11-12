"""Critical changes with what was before and after, the reason and the versions (FR-005,
D126).

Every critical change (access, board, contracts, review policy, approval limits, the audit
profile, accounts and funds) goes to ``audit_log`` (append only) with: who and when (the
row itself), what changed field by field, the reason a person gave (empty when the screen
does not ask for one), the version of the application and, when the change creates one, the
version of the setting. Personal data stays out: a CPF is masked, an e-mail is not stored in
the change (the membership already points to the person).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from importlib import metadata
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit

CHANGE_FORMAT = "mudanca_v1"


def app_version() -> str:
    try:
        return metadata.version("condoos-api")
    except metadata.PackageNotFoundError:  # pragma: no cover - source checkout without install
        return "dev"


def _plain(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """The listed attributes of a row, JSON-safe."""
    return {f: _plain(getattr(obj, f, None)) for f in fields}


def changed(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before, after = before or {}, after or {}
    return {
        k: {"antes": before.get(k), "depois": after.get(k)}
        for k in sorted(set(before) | set(after))
        if before.get(k) != after.get(k)
    }


async def record_change(
    session: AsyncSession,
    *,
    action: str,
    object_type: str,
    object_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    condominium_id: uuid.UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str | None = None,
    setting_version: int | str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    await record_audit(
        session,
        action=action,
        object_type=object_type,
        object_id=object_id,
        actor_user_id=actor_user_id,
        condominium_id=condominium_id,
        details={
            "formato": CHANGE_FORMAT,
            "antes": _plain(before),
            "depois": _plain(after),
            "mudou": changed(_plain(before), _plain(after)),
            "motivo": (reason or "").strip()[:500] or None,
            "versao_aplicacao": app_version(),
            "versao_configuracao": setting_version,
            **(_plain(extra) if extra else {}),
        },
    )
