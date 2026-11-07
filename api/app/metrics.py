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

Pilot protocol baseline (CB-070, ``docs/pilot-protocol.md`` §4), counts only, no personal data:
- Expenses per month (by competence) and findings contested or ignored by the board (proxy of
  false positives; the real rate needs a human sample).
- Divergences confirmed (R$): amount at risk of confirmed findings. Not realised savings.
- Cross-tenant attempts (``security.access_denied`` aimed at the condominium) and actions
  denied by the policy (``action.denied_by_policy``). Target: zero and visible.
- Board sessions: sessions opened in the month by people on the condominium's board.
- Savings per stage (D76): annualised value of the latest row per opportunity, separately
  for "estimada validada" and "realizada"; never added across stages.
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
from app.db.enums import DocumentOrigin, DocumentType, ExtractionStatus, Role, SavingsStage
from app.db.models import (
    AuditLog,
    Decision,
    Document,
    Expense,
    Finding,
    LlmCall,
    Membership,
    SavingsRecord,
    UserSession,
)

BOARD_ROLES = {Role.SINDICO.value, Role.SUBSINDICO.value, Role.CONSELHEIRO.value}

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
    expenses: int = 0
    findings_disputed: int = 0
    confirmed_at_risk: Decimal = Decimal("0")
    cross_tenant_attempts: int = 0
    denied_by_policy: int = 0
    board_sessions: int = 0
    savings_validated_annual: Decimal = Decimal("0")
    savings_realized_annual: Decimal = Decimal("0")

    def add(self, other: "Bucket") -> None:
        self.findings_reviewed += other.findings_reviewed
        self.findings_confirmed += other.findings_confirmed
        self.docs_processed += other.docs_processed
        self.docs_automatic += other.docs_automatic
        self.review_hours += other.review_hours
        self.llm_cost_usd += other.llm_cost_usd
        self.llm_calls += other.llm_calls
        self.expenses += other.expenses
        self.findings_disputed += other.findings_disputed
        self.confirmed_at_risk += other.confirmed_at_risk
        self.cross_tenant_attempts += other.cross_tenant_attempts
        self.denied_by_policy += other.denied_by_policy
        self.board_sessions += other.board_sessions
        self.savings_validated_annual += other.savings_validated_annual
        self.savings_realized_annual += other.savings_realized_annual

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
            "expenses": self.expenses,
            "findings_disputed": self.findings_disputed,
            "disputed_rate": (
                round(self.findings_disputed / self.findings_reviewed, 4)
                if self.findings_reviewed
                else None
            ),
            "confirmed_at_risk": f"{self.confirmed_at_risk:.2f}",
            "cross_tenant_attempts": self.cross_tenant_attempts,
            "denied_by_policy": self.denied_by_policy,
            "board_sessions": self.board_sessions,
            "savings_validated_annual": f"{self.savings_validated_annual:.2f}",
            "savings_realized_annual": f"{self.savings_realized_annual:.2f}",
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
            bucket.findings_disputed += board[-1].action in ("contestar", "ignorar")
            if board[-1].action == "confirmar":
                bucket.confirmed_at_risk += f.amount_at_risk
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

    for e in await session.scalars(
        select(Expense).where(
            Expense.condominium_id.in_(condominium_ids),
            Expense.competence >= first,
            Expense.competence < end,
        )
    ):
        out[e.condominium_id][e.competence].expenses += 1

    wanted = {str(c) for c in condominium_ids}
    for log in await session.scalars(
        select(AuditLog).where(
            AuditLog.action.in_(["security.access_denied", "action.denied_by_policy"]),
            AuditLog.created_at >= received_from,
        )
    ):
        month = _month(log.created_at)
        if month > last:
            continue
        if log.action == "action.denied_by_policy":
            if log.condominium_id in out:
                out[log.condominium_id][month].denied_by_policy += 1
        else:
            target = str((log.details or {}).get("requested_condominium_id", ""))
            if target in wanted:
                out[uuid.UUID(target)][month].cross_tenant_attempts += 1

    members: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for m in await session.scalars(
        select(Membership).where(
            Membership.condominium_id.in_(condominium_ids), Membership.role.in_(BOARD_ROLES)
        )
    ):
        if m.condominium_id is not None:
            members[m.user_id].add(m.condominium_id)
    if members:
        for s in await session.scalars(
            select(UserSession).where(
                UserSession.user_id.in_(list(members)), UserSession.created_at >= received_from
            )
        ):
            month = _month(s.created_at)
            if month > last:
                continue
            for cid in members[s.user_id]:
                out[cid][month].board_sessions += 1

    latest: dict[tuple[uuid.UUID, str], SavingsRecord] = {}
    for r in await session.scalars(
        select(SavingsRecord)
        .where(
            SavingsRecord.condominium_id.in_(condominium_ids),
            SavingsRecord.stage.in_(
                [SavingsStage.ESTIMADA_VALIDADA.value, SavingsStage.REALIZADA.value]
            ),
            SavingsRecord.created_at >= received_from,
        )
        .order_by(SavingsRecord.created_at)
    ):
        latest[(r.opportunity_id, r.stage)] = r  # the latest row per opportunity and stage
    for (_, stage), r in latest.items():
        month = _month(r.created_at)
        if month > last:
            continue
        bucket = out[r.condominium_id][month]
        if stage == SavingsStage.ESTIMADA_VALIDADA.value:
            bucket.savings_validated_annual += r.annualized_amount
        else:
            bucket.savings_realized_annual += r.annualized_amount
    return out
