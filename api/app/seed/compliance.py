"""Compliance obligations of the fictitious seed (D112): Jardim das Acácias has the catalogue
on, three obligations validated by the síndica and the rest still "a validar". Dates are
relative to today so the demo always shows one document expiring soon."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import compliance as svc
from app.db.models import AppUser, ComplianceObligation, Condominium

SINDICA = "ana.sindica@acacias.example.com"


async def seed_compliance(session: AsyncSession, today: date | None = None) -> None:
    today = today or date.today()
    condo = await session.scalar(
        select(Condominium).where(Condominium.slug == "jardim-das-acacias")
    )
    sindica = await session.scalar(select(AppUser).where(AppUser.email == SINDICA))
    if condo is None or sindica is None:
        return
    # D113: what the building has (fictitious), so the catalogue shows suggestions.
    condo.building_profile = {
        "elevadores": 4,
        "reservatorios": True,
        "gerador": True,
        "piscina": False,
    }
    await svc.activate_catalog(session, condo.id, sindica.id)
    by_key = {
        o.catalog_key: o
        for o in await session.scalars(
            select(ComplianceObligation).where(ComplianceObligation.condominium_id == condo.id)
        )
    }
    plan = {
        "seguro": (12, today - timedelta(days=320), today + timedelta(days=45)),
        "avcb": (None, today - timedelta(days=700), today + timedelta(days=400)),
        "extintores": (12, None, None),
    }
    for key, (months, issued, until) in plan.items():
        ob = by_key[key]
        await svc.validate(
            session,
            ob,
            sindica.id,
            applies=True,
            reason="Confirmado com a administradora (dado fictício do seed).",
            periodicity_months=months,
        )
        if until is not None:
            await svc.add_evidence(
                session, ob, sindica.id, document_id=None, issued_on=issued, valid_until=until
            )
