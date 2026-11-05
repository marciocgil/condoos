"""Rule framework: context, finding draft and the base class every rule extends."""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import Severity
from app.db.models import (
    Approval,
    BankTransaction,
    BoardMember,
    Condominium,
    Contract,
    Document,
    Expense,
    Supplier,
)


@dataclass(frozen=True)
class Evidence:
    kind: str  # expense | document | bank_transaction | contract | supplier | board_member
    id: str
    label: str
    excerpt: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.id, "label": self.label, "excerpt": self.excerpt}


@dataclass
class FindingDraft:
    rule_code: str
    severity: Severity
    title: str
    explanation: str
    amount_at_risk: Decimal
    subject_key: str  # stable: same rule + same subject = same finding on re-runs
    evidence: list[Evidence] = field(default_factory=list)
    rule_inputs: dict[str, Any] = field(default_factory=dict)
    supplier_id: uuid.UUID | None = None
    ai_assisted: bool = False


@dataclass
class RuleContext:
    session: AsyncSession | None
    condominium: Condominium
    competence: date  # day 1 of the month being audited
    reference_date: date  # "today" for grace periods
    expenses: list[Expense]  # every expense of the condominium (history included)
    suppliers: dict[uuid.UUID, Supplier]
    contracts: dict[uuid.UUID, Contract]
    transactions: list[BankTransaction]
    documents: dict[uuid.UUID, list[tuple[str, Document]]]  # expense id -> (role, document)
    board: list[BoardMember]
    approvals: dict[uuid.UUID, list[Approval]]
    index_table: dict[str, dict[date, Decimal]]
    not_evaluated: dict[str, str] = field(default_factory=dict)

    @property
    def month_expenses(self) -> list[Expense]:
        return [e for e in self.expenses if e.competence == self.competence]

    @property
    def month_end(self) -> date:
        nxt = (self.competence.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1)

    def payment_of(self, expense: Expense) -> BankTransaction | None:
        return next((t for t in self.transactions if t.expense_id == expense.id), None)

    def payment_date(self, expense: Expense) -> date:
        trn = self.payment_of(expense)
        if trn is not None:
            return trn.posted_at
        return expense.due_date or expense.issue_date

    def supplier_name(self, expense: Expense) -> str:
        supplier = self.suppliers.get(expense.supplier_id) if expense.supplier_id else None
        return supplier.legal_name if supplier else "fornecedor não identificado"

    def fiscal_text(self, expense: Expense) -> str:
        for role, doc in self.documents.get(expense.id, []):
            if role == "fiscal" and doc.extracted.get("discriminacao"):
                return str(doc.extracted["discriminacao"])
        return expense.description


def expense_evidence(ctx: RuleContext, e: Expense) -> list[Evidence]:
    out = [
        Evidence(
            "expense",
            str(e.id),
            f"{'NF ' + e.invoice_number if e.invoice_number else 'Despesa'} · "
            f"{e.issue_date:%d/%m/%Y} · R$ {e.amount}",
            e.description[:200],
        )
    ]
    for role, doc in ctx.documents.get(e.id, []):
        out.append(Evidence("document", str(doc.id), f"{role}: {doc.original_filename}"))
    trn = ctx.payment_of(e)
    if trn is not None:
        out.append(
            Evidence(
                "bank_transaction",
                str(trn.id),
                f"Extrato · {trn.posted_at:%d/%m/%Y} · R$ {-trn.amount}",
                trn.description[:200],
            )
        )
    return out


class Rule:
    code: ClassVar[str]
    name: ClassVar[str]
    default_severity: ClassVar[Severity]
    default_params: ClassVar[dict[str, Any]] = {}
    ai_assisted: ClassVar[bool] = False

    def params(self, ctx: RuleContext) -> dict[str, Any]:
        overrides = (ctx.condominium.rule_params or {}).get(self.code, {})
        return {**self.default_params, **overrides}

    async def evaluate(self, ctx: RuleContext) -> list[FindingDraft]:
        raise NotImplementedError


def contract_evidence(c: Contract) -> Evidence:
    end = f"{c.end_date:%d/%m/%Y}" if c.end_date else "indeterminado"
    return Evidence(
        "contract",
        str(c.id),
        f"Contrato · {c.object}",
        f"Valor mensal original R$ {c.monthly_value} · índice {c.adjustment_index} · "
        f"vigência {c.start_date:%d/%m/%Y} a {end}",
    )
