"""Launch instrumentation (LB-090, D92): how each condominium's implementation is going,
from records only (audit trail, documents, corrections, LLM calls). Counts and dates, never
personal data. Used by the CondoOS team's view of implementations in progress (LB-012).

- Time to first value: from the síndico's first access (``membership.accepted_at``) to the
  first ``launch.first_value_shown`` of the condominium, in hours.
- Days without activity: since the latest audit event written by a person on the
  condominium (``audit_log`` with an actor). An implementation that stops shows here.
- Steps put off: ``launch.step_postponed`` events.
- Per document (uploads and e-mails only, not the seed): fields corrected by people
  (``extraction_correction`` rows) and LLM cost (``llm_calls``).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.enums import DocumentOrigin, ExtractionStatus, Role
from app.db.models import (
    AuditLog,
    Condominium,
    Document,
    ExtractionCorrection,
    LlmCall,
    Membership,
)
from app.launch.journey import milestones
from app.launch.readiness import readiness


@dataclass(frozen=True)
class Implementation:
    condominium_id: uuid.UUID
    name: str
    milestones_done: int
    milestones_total: int
    next_milestone: str | None
    first_access_at: datetime | None
    first_value_at: datetime | None
    last_activity_at: datetime | None
    postponed_steps: int
    review_queue: int
    documents: int
    corrections: int
    llm_cost_usd: Decimal
    readiness: dict[str, str]

    @property
    def in_progress(self) -> bool:
        return self.milestones_done < self.milestones_total

    def as_dict(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or utcnow()
        hours_to_value = (
            round((self.first_value_at - self.first_access_at).total_seconds() / 3600, 1)
            if self.first_value_at and self.first_access_at
            else None
        )
        idle_days = (now - self.last_activity_at).days if self.last_activity_at else None
        per_doc = self.documents or None
        return {
            "id": str(self.condominium_id),
            "name": self.name,
            "in_progress": self.in_progress,
            "milestones_done": self.milestones_done,
            "milestones_total": self.milestones_total,
            "next_milestone": self.next_milestone,
            "first_access_at": self.first_access_at.isoformat() if self.first_access_at else None,
            "first_value_at": self.first_value_at.isoformat() if self.first_value_at else None,
            "hours_to_first_value": hours_to_value,
            "last_activity_at": (
                self.last_activity_at.isoformat() if self.last_activity_at else None
            ),
            "days_without_activity": idle_days,
            "postponed_steps": self.postponed_steps,
            "review_queue": self.review_queue,
            "documents": self.documents,
            "corrections_per_document": (round(self.corrections / per_doc, 2) if per_doc else None),
            "llm_cost_per_document_usd": (
                f"{self.llm_cost_usd / per_doc:.4f}" if per_doc else None
            ),
            "readiness": self.readiness,
        }


async def implementation(session: AsyncSession, condo: Condominium) -> Implementation:
    async def scalar(stmt: Any) -> Any:
        return await session.scalar(stmt)

    ms = await milestones(session, condo)
    caps = await readiness(session, condo)
    first_access = await scalar(
        select(func.min(Membership.accepted_at)).where(
            Membership.condominium_id == condo.id, Membership.role == Role.SINDICO.value
        )
    )
    first_value = await scalar(
        select(func.min(AuditLog.created_at)).where(
            AuditLog.condominium_id == condo.id,
            AuditLog.action == "launch.first_value_shown",
        )
    )
    last_activity = await scalar(
        select(func.max(AuditLog.created_at)).where(
            AuditLog.condominium_id == condo.id, AuditLog.actor_user_id.is_not(None)
        )
    )
    postponed = await scalar(
        select(func.count()).where(
            AuditLog.condominium_id == condo.id, AuditLog.action == "launch.step_postponed"
        )
    )
    queue = await scalar(
        select(func.count()).where(
            Document.condominium_id == condo.id,
            Document.needs_review.is_(True),
            Document.reviewed_at.is_(None),
        )
    )
    documents = await scalar(
        select(func.count()).where(
            Document.condominium_id == condo.id,
            Document.origin != DocumentOrigin.SEED.value,
            Document.extraction_status.in_(
                [ExtractionStatus.DONE.value, ExtractionStatus.NEEDS_REVIEW.value]
            ),
        )
    )
    corrections = await scalar(
        select(func.count()).where(ExtractionCorrection.condominium_id == condo.id)
    )
    cost = await scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(
            LlmCall.condominium_id == condo.id
        )
    )
    return Implementation(
        condominium_id=condo.id,
        name=condo.name,
        milestones_done=sum(m.done for m in ms),
        milestones_total=len(ms),
        next_milestone=next((m.name for m in ms if not m.done), None),
        first_access_at=first_access,
        first_value_at=first_value,
        last_activity_at=last_activity,
        postponed_steps=int(postponed or 0),
        review_queue=int(queue or 0),
        documents=int(documents or 0),
        corrections=int(corrections or 0),
        llm_cost_usd=Decimal(str(cost or 0)),
        readiness={r.capability: r.state for r in caps},
    )
