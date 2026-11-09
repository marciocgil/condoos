"""Weekly compliance e-mail to the síndico (D109), the second thing the system sends out.

Rules: off until the síndico turns it on; only to the condominium's own síndicos (active
membership); only when a document of an applicable obligation expired or expires within 30
days; obligation names and dates only (no amounts); a link to the app; at most one per
síndico per week (``compliance_reminder``, append only); paused by the kill switch
``conformidade.lembrete_email``. "Enviado" means accepted by the mail server, never delivered.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance import Row, rows_for
from app.config import get_settings
from app.core.time import DEFAULT_TIMEZONE, utcnow
from app.db.enums import ReminderStatus, Role
from app.db.models import AppUser, ComplianceReminder, Condominium, Membership

logger = logging.getLogger(__name__)

REMINDER_JOB = "compliance.reminders"
PAUSE_TYPE = "conformidade.lembrete_email"
SOON_DAYS = 30
SEND_WEEKDAY = 0  # Monday
SEND_FROM_HOUR = 8  # local time


@dataclass
class Outcome:
    sent: int = 0
    failed: int = 0
    skipped: int = 0


def due_rows(rows: list[Row]) -> list[Row]:
    out = []
    for r in rows:
        s = r.situation
        if s.code == "vencido" or (s.code == "vence_em_breve" and (s.days_left or 0) <= SOON_DAYS):
            out.append(r)
    return out


def compose(condo: Condominium, name: str, rows: list[Row]) -> tuple[str, str]:
    base = get_settings().web_base_url.rstrip("/")
    lines = []
    for r in rows:
        s = r.situation
        extra = f" ({s.to_confirm})" if s.to_confirm else ""
        lines.append(f"- {r.obligation.name}: {s.text}{extra}")
    subject = f"CondoOS · Vencimentos da semana · {condo.name}"
    body = (
        f"Olá, {name.split()[0] if name else 'síndico(a)'}.\n\n"
        f"Documentos registrados no CondoOS para {condo.name} que venceram ou vencem nos "
        f"próximos {SOON_DAYS} dias:\n\n" + "\n".join(lines) + "\n\n"
        f"Ver no CondoOS: {base}/condominio/{condo.id}/conformidade\n\n"
        "Este resumo mostra só o que está registrado no CondoOS. Não é laudo nem parecer "
        "técnico ou jurídico.\n"
        "Para parar de receber, desligue o resumo semanal em Ajustes → Conformidade e "
        "vencimentos.\n"
    )
    return subject, body


async def _recipients(session: AsyncSession, condominium_id: uuid.UUID) -> list[AppUser]:
    from app.auth.deps import active_membership

    return list(
        await session.scalars(
            select(AppUser)
            .join(Membership, Membership.user_id == AppUser.id)
            .where(
                Membership.condominium_id == condominium_id,
                Membership.role == Role.SINDICO.value,
                AppUser.is_active.is_(True),
                *active_membership(),
            )
            .distinct()
        )
    )


async def send_reminders(session: AsyncSession, now: datetime | None = None) -> Outcome:
    """Send what is due at ``now`` (Monday from 8h, condominium's time zone)."""
    from app.auth.mailer import OutgoingEmail, get_mailer
    from app.policy import active_pause

    now = now or utcnow()
    outcome = Outcome()
    condos = await session.scalars(
        select(Condominium).where(Condominium.compliance_email_enabled.is_(True))
    )
    for condo in list(condos):
        local = now.astimezone(ZoneInfo(condo.timezone or DEFAULT_TIMEZONE))
        if local.weekday() != SEND_WEEKDAY or local.hour < SEND_FROM_HOUR:
            continue
        if await active_pause(session, condo.id, PAUSE_TYPE) is not None:
            outcome.skipped += 1
            continue
        today: date = local.date()
        week = today - timedelta(days=today.weekday())
        rows = due_rows(await rows_for(session, condo.id, today))
        if not rows:
            continue
        for user in await _recipients(session, condo.id):
            done = await session.scalar(
                select(ComplianceReminder.id).where(
                    ComplianceReminder.condominium_id == condo.id,
                    ComplianceReminder.user_id == user.id,
                    ComplianceReminder.week == week,
                )
            )
            if done is not None:
                continue
            subject, body = compose(condo, user.name, rows)
            status, message_id = ReminderStatus.ENVIADO, None
            try:
                async with session.begin_nested():
                    message_id = await get_mailer().send(
                        OutgoingEmail(
                            to=user.email, subject=subject, body=body, from_name="CondoOS"
                        )
                    )
            except Exception:  # the server refused: recorded, tried again next week
                logger.warning("compliance reminder refused condo=%s", condo.id)
                status = ReminderStatus.FALHOU
            session.add(
                ComplianceReminder(
                    id=uuid.uuid4(),
                    condominium_id=condo.id,
                    user_id=user.id,
                    week=week,
                    status=status.value,
                    items=len(rows),
                    message_id=(message_id or None) and str(message_id)[:300],
                )
            )
            if status is ReminderStatus.ENVIADO:
                outcome.sent += 1
            else:
                outcome.failed += 1
    return outcome


async def reminders_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    result = await send_reminders(session)
    if result.sent or result.failed:
        logger.info("compliance reminders sent=%s failed=%s", result.sent, result.failed)
