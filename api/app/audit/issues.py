"""Persistent audit issues (D123): one issue per condominium, control and subject, kept
across months. What a control says is missing becomes an open issue; when a later run of the
same month no longer finds it, it is resolved; if it comes back, it is reopened with the same
id and the whole history (``audit_issue_event``, append only)."""

import hashlib
import re
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.enums import AuditIssueStatus
from app.db.models import AuditIssue, AuditIssueEvent


def subject_key(control_id: str, text: str) -> str:
    """Stable key of an issue: the control and the text without amounts or dates, so the same
    gap in another month is the same issue."""
    norm = re.sub(r"\d", "#", text.lower())
    norm = " ".join(norm.split())
    return f"{control_id}:{hashlib.sha256(norm.encode()).hexdigest()[:40]}"


async def sync_issues(
    session: AsyncSession,
    condo_id: uuid.UUID,
    competence: date,
    run_id: uuid.UUID,
    outcomes: dict[str, Any],
) -> dict[str, int]:
    found: dict[str, tuple[str, str]] = {}
    for control_id, outcome in outcomes.items():
        for text in outcome.missing:
            found[subject_key(control_id, text)] = (control_id, text[:300])
    existing = {
        i.subject_key: i
        for i in await session.scalars(
            select(AuditIssue).where(AuditIssue.condominium_id == condo_id)
        )
    }
    out = {"abertas": 0, "reabertas": 0, "resolvidas": 0, "mantidas": 0}

    def event(issue: AuditIssue, kind: str) -> None:
        session.add(
            AuditIssueEvent(
                condominium_id=condo_id,
                issue_id=issue.id,
                kind=kind,
                competence=competence,
                run_id=run_id,
                detail={"titulo": issue.title},
            )
        )

    for key, (control_id, text) in found.items():
        issue = existing.get(key)
        if issue is None:
            issue = AuditIssue(
                id=uuid.uuid4(),
                condominium_id=condo_id,
                control_id=control_id,
                subject_key=key,
                title=text,
                status=AuditIssueStatus.ABERTA.value,
                first_competence=competence,
                last_competence=competence,
            )
            session.add(issue)
            await session.flush()
            event(issue, "aberta")
            out["abertas"] += 1
            continue
        if issue.status == AuditIssueStatus.RESOLVIDA.value:
            issue.status, issue.resolved_at = AuditIssueStatus.ABERTA.value, None
            event(issue, "reaberta")
            out["reabertas"] += 1
        else:
            out["mantidas"] += 1
        issue.title = text
        issue.last_competence = max(issue.last_competence, competence)
    for key, issue in existing.items():
        if (
            key not in found
            and issue.status == AuditIssueStatus.ABERTA.value
            and issue.last_competence == competence
        ):
            issue.status, issue.resolved_at = AuditIssueStatus.RESOLVIDA.value, utcnow()
            event(issue, "resolvida")
            out["resolvidas"] += 1
    await session.flush()
    return out
