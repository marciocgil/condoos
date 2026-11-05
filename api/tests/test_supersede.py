"""D61: a finding the rules no longer detect, untouched by people, becomes "superado";
one that a person decided or commented stays as it is."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import AppUser, AuditLog, Decision, Finding, FindingComment
from app.db.session import sessionmaker_for
from app.onboarding import onboard
from app.rules.engine import evaluate
from tests.test_onboarding import _spec

MONTH = date(2026, 10, 1)


def _finding(condo_id: uuid.UUID, rule: str, status: str = "publicado") -> Finding:
    fid = uuid.uuid4()
    return Finding(
        id=fid,
        condominium_id=condo_id,
        rule_code=rule,
        severity="media",
        title="Débito sem nota fiscal",
        explanation="e",
        amount_at_risk=Decimal("100"),
        status=status,
        evidence=[],
        rule_inputs={},
        competence=MONTH,
        dedupe_key=f"{rule}:{fid}",
    )


async def test_stale_untouched_findings_are_superseded(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec())
        user = AppUser(id=uuid.uuid4(), name="Pessoa", email=f"{uuid.uuid4().hex}@s.example.com")
        stale = _finding(condo.id, "R09")
        serious = _finding(condo.id, "R01", "aguardando_validacao")
        decided = _finding(condo.id, "R10", "confirmado")
        commented = _finding(condo.id, "R10")
        s.add_all([user, stale, serious, decided, commented])
        await s.flush()
        s.add(
            Decision(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                finding_id=decided.id,
                user_id=user.id,
                action="confirmar",
            )
        )
        s.add(
            FindingComment(
                condominium_id=condo.id, finding_id=commented.id, user_id=user.id, body="Ver."
            )
        )

    # The month has no data at all now: no rule detects anything.
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        summary = await evaluate(s, condo.id, MONTH, date(2026, 11, 5))
    assert summary.drafts == []

    async with sessionmaker_for(admin_engine)() as s:
        status = {
            f.id: f.status
            for f in await s.scalars(select(Finding).where(Finding.condominium_id == condo.id))
        }
        audits = (
            await s.scalars(
                select(AuditLog).where(
                    AuditLog.action == "finding.superseded", AuditLog.condominium_id == condo.id
                )
            )
        ).all()
    assert status[stale.id] == "superado" and status[serious.id] == "superado"
    assert status[decided.id] == "confirmado" and status[commented.id] == "publicado"
    assert len(audits) == 2
