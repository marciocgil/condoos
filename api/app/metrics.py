"""Internal pilot metrics (spec §13, milestone 6), per condominium and month (D60).

- Precision of findings = confirmed / reviewed. A finding is reviewed when the board's
  latest decision on it is confirmar, contestar or ignorar; it counts as confirmed when that
  latest decision is confirmar. Month = the finding's competence.
- Automatic extraction = processed documents that never needed a person / processed
  documents. Counts uploads and e-mails of the fiscal types (not bank files, governing
  documents or the seed). Month = when the document was received.
- Síndico review time = from the moment the board could see the finding (created, or
  validated by the manager for serious ones) to the board's first decision; median in hours.
- LLM cost = sum of ``llm_calls.cost_usd`` of the condominium. Month = call date.
"""

import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import add_months
from app.db.enums import DocumentOrigin, DocumentType, ExtractionStatus
from app.db.models import Decision, Document, Finding, LlmCall

BOARD_ACTIONS = {"confirmar", "contestar", "ignorar"}
EXTRACTED_TYPES = {
    DocumentType.NFSE.value,
    DocumentType.NFE.value,
    DocumentType.BOLETO.value,
    DocumentType.RECIBO.value,
    DocumentType.CONTRATO.value,
    DocumentType.OUTRO.value,
}


@dataclass
class Bucket:
    findings_reviewed: int = 0
    findings_confirmed: int = 0
    docs_processed: int = 0
    docs_automatic: int = 0
    review_hours: list[float] = field(default_factory=list)
    llm_cost_usd: Decimal = Decimal("0")
    llm_calls: int = 0

    def add(self, other: "Bucket") -> None:
        self.findings_reviewed += other.findings_reviewed
        self.findings_confirmed += other.findings_confirmed
        self.docs_processed += other.docs_processed
        self.docs_automatic += other.docs_automatic
        self.review_hours += other.review_hours
        self.llm_cost_usd += other.llm_cost_usd
        self.llm_calls += other.llm_calls

    def summary(self) -> dict[str, object]:
        return {
            "findings_reviewed": self.findings_reviewed,
            "findings_confirmed": self.findings_confirmed,
            "precision": (
                round(self.findings_confirmed / self.findings_reviewed, 4)
                if self.findings_reviewed
                else None
            ),
            "docs_processed": self.docs_processed,
            "docs_automatic": self.docs_automatic,
            "automatic_rate": (
                round(self.docs_automatic / self.docs_processed, 4) if self.docs_processed else None
            ),
            "review_count": len(self.review_hours),
            "review_hours_median": (
                round(statistics.median(self.review_hours), 1) if self.review_hours else None
            ),
            "llm_cost_usd": f"{self.llm_cost_usd:.4f}",
            "llm_calls": self.llm_calls,
        }


def _month(d: date | datetime) -> date:
    return date(d.year, d.month, 1)


async def compute(
    session: AsyncSession, condominium_ids: list[uuid.UUID], first: date, last: date
) -> dict[uuid.UUID, dict[date, Bucket]]:
    """Buckets per condominium and month for months in [first, last] (first days)."""
    out: dict[uuid.UUID, dict[date, Bucket]] = {c: defaultdict(Bucket) for c in condominium_ids}
    if not condominium_ids:
        return out
    end = add_months(last, 1)

    findings = {
        f.id: f
        for f in await session.scalars(
            select(Finding).where(
                Finding.condominium_id.in_(condominium_ids),
                Finding.competence >= first,
                Finding.competence < end,
            )
        )
    }
    decisions: dict[uuid.UUID, list[Decision]] = defaultdict(list)
    if findings:
        for d in await session.scalars(
            select(Decision)
            .where(Decision.finding_id.in_(list(findings)))
            .order_by(Decision.decided_at)
        ):
            decisions[d.finding_id].append(d)
    for fid, f in findings.items():
        bucket = out[f.condominium_id][f.competence]
        board = [d for d in decisions[fid] if d.action in BOARD_ACTIONS]
        if board:
            bucket.findings_reviewed += 1
            bucket.findings_confirmed += board[-1].action == "confirmar"
            validated = next((d.decided_at for d in decisions[fid] if d.action == "validar"), None)
            visible_since = validated or f.created_at
            hours = (board[0].decided_at - visible_since).total_seconds() / 3600
            bucket.review_hours.append(max(hours, 0.0))

    received_from = datetime.combine(first, time.min, tzinfo=UTC)
    for doc in await session.scalars(
        select(Document).where(
            Document.condominium_id.in_(condominium_ids),
            Document.origin != DocumentOrigin.SEED.value,
            Document.doc_type.in_(EXTRACTED_TYPES),
            Document.extraction_status.in_(
                [ExtractionStatus.DONE.value, ExtractionStatus.NEEDS_REVIEW.value]
            ),
            Document.created_at >= received_from,
        )
    ):
        month = _month(doc.created_at)
        if month > last:
            continue
        bucket = out[doc.condominium_id][month]
        bucket.docs_processed += 1
        bucket.docs_automatic += not doc.needs_review and doc.reviewed_at is None

    for call in await session.scalars(
        select(LlmCall).where(
            LlmCall.condominium_id.in_(condominium_ids), LlmCall.created_at >= received_from
        )
    ):
        month = _month(call.created_at)
        if month > last or call.condominium_id is None:
            continue
        bucket = out[call.condominium_id][month]
        bucket.llm_cost_usd += call.cost_usd
        bucket.llm_calls += 1
    return out
