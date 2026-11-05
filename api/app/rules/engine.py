"""Rules engine: build the context of one condominium and month, run the 12 rules, persist.

Persistence is idempotent: a finding is keyed by (condominium, subject_key). Re-running
updates numbers and evidence but never resets a status set by a person. Routing (spec §7):
severity "alta" starts as ``aguardando_validacao`` (manager validates first); "media" and
"baixa" start as ``publicado``.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jobs import enqueue
from app.db.enums import FindingStatus, Severity
from app.db.models import (
    Approval,
    BankTransaction,
    BoardMember,
    Condominium,
    Contract,
    Document,
    Expense,
    ExpenseDocument,
    Finding,
    Supplier,
)
from app.enrichment.indices import load_index_table
from app.rules.base import FindingDraft, Rule, RuleContext
from app.rules.r01_duplicate import DuplicatePayment
from app.rules.r02_above_contract import AboveContract
from app.rules.r03_adjustment import AdjustmentAboveIndex
from app.rules.r04_scope import OutOfScope
from app.rules.r05_expired_contract import ExpiredContract
from app.rules.r06_irregular_supplier import IrregularSupplier
from app.rules.r07_cnae import IncompatibleCnae
from app.rules.r08_conflict import ConflictOfInterest
from app.rules.r09_paid_without_document import PaidWithoutDocument
from app.rules.r10_unpaid_document import UnpaidDocument
from app.rules.r11_anomaly import AnomalousVariation
from app.rules.r12_approval import ApprovalLimit

ALL_RULES: list[Rule] = [
    DuplicatePayment(),
    AboveContract(),
    AdjustmentAboveIndex(),
    OutOfScope(),
    ExpiredContract(),
    IrregularSupplier(),
    IncompatibleCnae(),
    ConflictOfInterest(),
    PaidWithoutDocument(),
    UnpaidDocument(),
    AnomalousVariation(),
    ApprovalLimit(),
]
RULES_BY_CODE = {r.code: r for r in ALL_RULES}
FORBIDDEN_WORDS = ("fraude", "desvio", "irregularidade comprovada")


@dataclass
class RunSummary:
    drafts: list[FindingDraft]
    created: int = 0
    updated: int = 0
    not_evaluated: dict[str, str] = field(default_factory=dict)


async def build_context(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    competence: date,
    reference_date: date,
    llm_session: AsyncSession | None = None,
) -> RuleContext:
    condo = await session.get(Condominium, condominium_id)
    if condo is None:
        raise ValueError("condomínio não encontrado")
    expenses = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == condominium_id, Expense.competence <= competence
            )
        )
    )
    supplier_ids = {e.supplier_id for e in expenses if e.supplier_id}
    suppliers = {
        s.id: s
        for s in await session.scalars(select(Supplier).where(Supplier.id.in_(supplier_ids)))
    }
    contracts = {
        c.id: c
        for c in await session.scalars(
            select(Contract).where(Contract.condominium_id == condominium_id)
        )
    }
    transactions = list(
        await session.scalars(
            select(BankTransaction).where(BankTransaction.condominium_id == condominium_id)
        )
    )
    docs: dict[uuid.UUID, list[tuple[str, Document]]] = defaultdict(list)
    rows = await session.execute(
        select(ExpenseDocument.expense_id, ExpenseDocument.role, Document)
        .join(Document, Document.id == ExpenseDocument.document_id)
        .where(ExpenseDocument.condominium_id == condominium_id)
    )
    for expense_id, role, doc in rows:
        docs[expense_id].append((role, doc))
    board = list(
        await session.scalars(
            select(BoardMember).where(BoardMember.condominium_id == condominium_id)
        )
    )
    approvals: dict[uuid.UUID, list[Approval]] = defaultdict(list)
    for a in await session.scalars(
        select(Approval).where(Approval.condominium_id == condominium_id)
    ):
        approvals[a.expense_id].append(a)
    return RuleContext(
        session=llm_session if llm_session is not None else session,
        condominium=condo,
        competence=competence,
        reference_date=reference_date,
        expenses=expenses,
        suppliers=suppliers,
        contracts=contracts,
        transactions=transactions,
        documents=dict(docs),
        board=board,
        approvals=dict(approvals),
        index_table=await load_index_table(session),
    )


async def run_rules(ctx: RuleContext, rules: list[Rule] | None = None) -> list[FindingDraft]:
    drafts: list[FindingDraft] = []
    for rule in rules or ALL_RULES:
        for draft in await rule.evaluate(ctx):
            lowered = (draft.title + " " + draft.explanation).lower()
            if any(word in lowered for word in FORBIDDEN_WORDS):
                raise AssertionError(f"{draft.rule_code}: linguagem proibida no achado")
            drafts.append(draft)
    return drafts


def initial_status(severity: Severity) -> FindingStatus:
    return (
        FindingStatus.AGUARDANDO_VALIDACAO if severity == Severity.ALTA else FindingStatus.PUBLICADO
    )


async def persist(
    session: AsyncSession, ctx: RuleContext, drafts: list[FindingDraft]
) -> tuple[int, int]:
    created = updated = 0
    to_explain: list[uuid.UUID] = []
    for d in drafts:
        existing = await session.scalar(
            select(Finding).where(
                Finding.condominium_id == ctx.condominium.id, Finding.dedupe_key == d.subject_key
            )
        )
        values: dict[str, Any] = {
            "rule_code": d.rule_code,
            "severity": d.severity.value,
            "title": d.title,
            "explanation": d.explanation,
            "amount_at_risk": d.amount_at_risk,
            "evidence": [e.as_dict() for e in d.evidence],
            "rule_inputs": d.rule_inputs,
            "competence": ctx.competence,
            "ai_assisted": d.ai_assisted,
            "supplier_id": d.supplier_id,
        }
        if existing is None:
            finding = Finding(
                id=uuid.uuid4(),
                condominium_id=ctx.condominium.id,
                dedupe_key=d.subject_key,
                status=initial_status(d.severity).value,
                explanation_source="regra",
                **values,
            )
            session.add(finding)
            created += 1
            to_explain.append(finding.id)
        else:
            if existing.rule_inputs == d.rule_inputs and existing.explanation_source == "ia":
                # Same numbers: keep the validated plain-language text already written.
                values.pop("title")
                values.pop("explanation")
            elif existing.rule_inputs != d.rule_inputs:
                existing.explanation_source = "regra"
                to_explain.append(existing.id)
            for key, value in values.items():
                setattr(existing, key, value)
            updated += 1
    await session.flush()
    for finding_id in to_explain:
        await enqueue(
            session,
            "finding.explain",
            {"finding_id": str(finding_id)},
            condominium_id=ctx.condominium.id,
        )
    return created, updated


async def evaluate(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    competence: date,
    reference_date: date,
    *,
    save: bool = True,
) -> RunSummary:
    ctx = await build_context(session, condominium_id, competence, reference_date)
    drafts = await run_rules(ctx)
    summary = RunSummary(drafts=drafts, not_evaluated=dict(ctx.not_evaluated))
    if save:
        summary.created, summary.updated = await persist(session, ctx, drafts)
    return summary


async def evaluate_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``rules.evaluate``: {"condominium_id", "competence": "AAAA-MM"}."""
    competence = date.fromisoformat(payload["competence"] + "-01")
    await evaluate(session, uuid.UUID(payload["condominium_id"]), competence, date.today())
