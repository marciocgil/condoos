"""The síndico leaves a condominium (D129): only the síndico, for themself; today ends the
access and pauses the automations; a later date can be undone and is applied by the daily
check; nothing is deleted; the period dossier is audited."""

import random
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app import exit as ex
from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.core.time import local_today
from app.db.enums import Role
from app.db.models import AppUser, AuditLog, AutomationPause, Membership
from app.db.session import sessionmaker_for
from app.main import create_app
from app.policy import ALL_AUTOMATIONS
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_ACACIAS, condo_id, login
from tests.test_audit import _new_condo


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def _active_pause(s: object, cid: uuid.UUID) -> AutomationPause | None:
    return await s.scalar(  # type: ignore[attr-defined, no-any-return]
        select(AutomationPause).where(
            AutomationPause.condominium_id == cid,
            AutomationPause.automation_type == ALL_AUTOMATIONS,
            AutomationPause.resumed_at.is_(None),
        )
    )


async def test_only_the_sindico_leaves(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    async with _client() as bruno:
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        info = (await bruno.get(f"/condominiums/{acacias}/exit")).json()
        assert info["can_exit"] is False and info["pending"] is None
        body = {"reason": "renuncia", "on": info["today"]}
        assert (await bruno.post(f"/condominiums/{acacias}/exit", json=body)).status_code == 403
        assert (await bruno.get(f"/condominiums/{acacias}/exit/dossier.pdf")).status_code == 403


async def test_sindico_schedules_undoes_and_leaves_today(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    cnpj = generate_cnpj(random.Random(uuid.uuid4().hex))
    async with _client() as ana:
        await login(ana, mailer, SINDICA_ACACIAS)
        r = await ana.post(
            "/implantation",
            json={
                "cnpj": cnpj,
                "name": "Condomínio Saída",
                "address": "Rua Fictícia, 5",
                "units": 8,
            },
        )
        assert r.status_code == 201, r.text
        new = r.json()["id"]
        base = f"/condominiums/{new}/exit"
        info = (await ana.get(base)).json()
        assert info["can_exit"] and info["pending"] is None
        today = local_today(None)

        pdf = await ana.get(f"{base}/dossier.pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

        bad = await ana.post(base, json={"reason": "outro", "on": today.isoformat()})
        assert bad.status_code == 422  # "outro" needs a few words
        far = await ana.post(
            base, json={"reason": "fim_mandato", "on": (today + timedelta(days=200)).isoformat()}
        )
        assert far.status_code == 422

        later = (today + timedelta(days=10)).isoformat()
        r = await ana.post(base, json={"reason": "fim_mandato", "on": later})
        assert r.status_code == 200, r.text
        assert r.json() == {"applied": False, "pending": {"on": later, "reason": "Fim do mandato"}}
        assert (await ana.post(base, json={"reason": "renuncia", "on": later})).status_code == 422
        assert (await ana.get(base)).json()["pending"]["on"] == later  # still has access

        assert (await ana.post(f"{base}/cancel")).status_code == 200
        async with sessionmaker_for(admin_engine)() as s:
            m = await s.scalar(
                select(Membership).where(
                    Membership.condominium_id == uuid.UUID(new),
                    Membership.role == Role.SINDICO.value,
                )
            )
            assert m is not None and m.expires_at is None and m.revoked_at is None
        assert (await ana.get(base)).json()["pending"] is None

        r = await ana.post(base, json={"reason": "renuncia", "on": today.isoformat()})
        assert r.json() == {"applied": True, "pending": None}
        assert (await ana.get(base)).status_code == 404  # the access ended now

    async with sessionmaker_for(admin_engine)() as s:
        cid = uuid.UUID(new)
        assert await _active_pause(s, cid) is not None
        actions = list(
            await s.scalars(
                select(AuditLog.action)
                .where(AuditLog.condominium_id == cid, AuditLog.action.like("condominium.exit%"))
                .order_by(AuditLog.created_at)
            )
        )
        assert sorted(actions) == sorted(
            [
                "condominium.exit_dossier_exported",
                ex.SCHEDULED,
                ex.CANCELLED,
                ex.SCHEDULED,
                ex.APPLIED,
            ]
        )  # one transaction shares a timestamp: compare without order


async def test_later_exit_is_applied_by_the_daily_check(
    admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        user = await s.scalar(select(AppUser).where(AppUser.email == SINDICA_ACACIAS))
        assert user is not None
        s.add(
            Membership(
                id=uuid.uuid4(), user_id=user.id, condominium_id=condo.id, role=Role.SINDICO.value
            )
        )
        await s.flush()
        today = local_today(condo.timezone)
        on = today + timedelta(days=3)
        pending = await ex.schedule_exit(
            s, condo, user.id, reason_code="fim_mandato", note="", on=on
        )
        assert pending is not None and pending.on == on
        assert not await ex.apply_due_exits(s, condo)  # not yet
        assert await _active_pause(s, condo.id) is None

        monkeypatch.setattr(ex, "local_today", lambda tz: on + timedelta(days=1))
        assert await ex.apply_due_exits(s, condo)
        assert await _active_pause(s, condo.id) is not None
        assert await ex.pending_exit(s, condo.id) is None
        assert not await ex.apply_due_exits(s, condo)  # applied once
        await s.rollback()


async def test_exit_on_the_mandate_end_beyond_ninety_days(admin_engine: AsyncEngine) -> None:
    from app.db.enums import BoardPosition
    from app.db.models import BoardMember

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        user = await s.scalar(select(AppUser).where(AppUser.email == SINDICA_ACACIAS))
        assert user is not None
        today = local_today(condo.timezone)
        end = today + timedelta(days=200)
        s.add_all(
            [
                Membership(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    condominium_id=condo.id,
                    role=Role.SINDICO.value,
                ),
                BoardMember(
                    id=uuid.uuid4(),
                    condominium_id=condo.id,
                    full_name=user.name,
                    position=BoardPosition.SINDICO.value,
                    term_start=today - timedelta(days=30),
                    term_end=end,
                    user_id=user.id,
                ),
            ]
        )
        await s.flush()
        with pytest.raises(ex.ExitError):
            await ex.schedule_exit(
                s, condo, user.id, reason_code="renuncia", note="", on=end - timedelta(days=1)
            )
        pending = await ex.schedule_exit(
            s, condo, user.id, reason_code="fim_mandato", note="", on=end
        )
        assert pending is not None and pending.on == end
        dossier = await ex.period_dossier(s, condo, user.id, user.name)
        assert dossier["start"] == today - timedelta(days=30) and dossier["end"] == today
        await s.rollback()
