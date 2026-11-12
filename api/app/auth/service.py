"""Magic-link login and server-side sessions."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mailer import Mailer, OutgoingEmail
from app.auth.tokens import hash_token, new_token
from app.config import get_settings
from app.core.audit import record_audit
from app.core.jobs import enqueue
from app.core.time import utcnow
from app.db.enums import Role
from app.db.models import AppUser, MagicLinkToken, Membership, UserSession


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def request_magic_link(session: AsyncSession, email: str, mailer: Mailer) -> None:
    """Send a login link if the e-mail belongs to an active user.

    Always behaves the same from the outside, so the endpoint cannot be used to discover
    which e-mails are registered.
    """
    s = get_settings()
    user = await session.scalar(
        select(AppUser).where(AppUser.email == normalize_email(email), AppUser.is_active)
    )
    if user is None:
        return

    recent = await session.scalar(
        select(func.count())
        .select_from(MagicLinkToken)
        .where(
            MagicLinkToken.user_id == user.id,
            MagicLinkToken.created_at > utcnow() - timedelta(hours=1),
        )
    )
    if (recent or 0) >= s.magic_link_max_per_hour:
        return

    raw, hashed = new_token()
    session.add(
        MagicLinkToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=utcnow() + timedelta(minutes=s.magic_link_ttl_minutes),
        )
    )
    await record_audit(
        session,
        action="auth.magic_link_requested",
        object_type="app_user",
        object_id=user.id,
        actor_user_id=user.id,
    )
    link = f"{s.web_base_url}/auth/verify?token={raw}"
    await mailer.send(
        OutgoingEmail(
            to=user.email,
            subject="Seu link de acesso ao CondoOS",
            body=(
                f"Olá, {user.name}.\n\n"
                f"Para entrar no CondoOS, abra o link abaixo. Ele vale por "
                f"{s.magic_link_ttl_minutes} minutos e só pode ser usado uma vez.\n\n"
                f"{link}\n\n"
                "Se você não pediu este acesso, ignore este e-mail."
            ),
        )
    )


@dataclass(frozen=True)
class NewSession:
    user_id: uuid.UUID
    raw_token: str


async def consume_magic_link(session: AsyncSession, raw_token: str) -> NewSession | None:
    now = utcnow()
    # Atomic single use: only one request can flip used_at from NULL.
    user_id = await session.scalar(
        update(MagicLinkToken)
        .where(
            MagicLinkToken.token_hash == hash_token(raw_token),
            MagicLinkToken.used_at.is_(None),
            MagicLinkToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(MagicLinkToken.user_id)
    )
    if user_id is None:
        return None
    user = await session.get(AppUser, user_id)
    if user is None or not user.is_active:
        return None

    raw, hashed = new_token()
    session.add(
        UserSession(
            user_id=user_id,
            token_hash=hashed,
            expires_at=now + timedelta(days=get_settings().session_ttl_days),
            last_seen_at=now,
        )
    )
    # The first login accepts pending invitations (D77).
    accepted = (
        await session.execute(
            update(Membership)
            .where(
                Membership.user_id == user_id,
                Membership.accepted_at.is_(None),
                Membership.revoked_at.is_(None),
                # FR-002 (D126): an expired invitation is not accepted; it must be sent again.
                or_(
                    Membership.invited_at.is_(None),
                    Membership.invited_at > now - timedelta(days=get_settings().invite_valid_days),
                ),
            )
            .values(accepted_at=now)
            .returning(Membership.id, Membership.condominium_id, Membership.role)
        )
    ).all()
    # A síndico entering can bring a capability back (C7 after a change of síndico, D109):
    # the history is checked for that condominium by the worker, right away.
    for membership_id, condominium_id, role in accepted:
        if role == Role.SINDICO.value and condominium_id is not None:
            await enqueue(
                session,
                "launch.health",
                {"condominium_id": str(condominium_id), "reason": "acesso"},
                condominium_id=condominium_id,
                dedupe_key=f"health:acesso:{membership_id}:{now.isoformat()}",
                priority=True,
            )
    await record_audit(
        session,
        action="auth.login",
        object_type="app_user",
        object_id=user_id,
        actor_user_id=user_id,
    )
    return NewSession(user_id=user_id, raw_token=raw)


async def user_from_session_token(session: AsyncSession, raw_token: str) -> AppUser | None:
    now = utcnow()
    row = await session.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(raw_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    if row is None:
        return None
    user = await session.get(AppUser, row.user_id)
    if user is None or not user.is_active:
        return None
    row.last_seen_at = now
    return user


async def revoke_session(session: AsyncSession, raw_token: str) -> uuid.UUID | None:
    return await session.scalar(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(raw_token), UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
        .returning(UserSession.user_id)
    )
