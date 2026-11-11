"""Everything one audit run reads for one condominium and month, loaded once (D122).

The facts come from the shared registry (documents, extracted fields with provenance,
expenses, bank lines, statements, links): agents A5–A9 never read the PDFs again.
Bank lines are classified by a versioned deterministic rule; values stay ``Decimal`` (exact
cents), never ``float``.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.time import add_months
from app.db.models import (
    BankAccount,
    BankStatement,
    BankTransaction,
    Condominium,
    Document,
    Expense,
    ExpenseDocument,
    ManagementCompany,
    Supplier,
)

CLASSIFICATION_VERSION = "classificacao_v1"
ZERO = Decimal("0")
CENT = Decimal("0.01")
# A document with no month of its own (unreadable, unknown type) counts in the month it was
# received or up to this many days after its end.
UPLOAD_GRACE_DAYS = 45

# Debits that are not expenses, and credits by kind. Order matters: the first match wins.
DEBIT_RULES: list[tuple[str, str]] = [
    ("estorno", r"estorno|devolu"),
    ("tarifa", r"tarifa|cesta de servi|pacote de servi|manuten[cç][aã]o de conta"),
    ("tributo_bancario", r"\biof\b|\birrf\b s/ ?aplic"),
    ("juros_encargos", r"\bjuros\b|encargos|\bmulta\b"),
    ("aplicacao", r"aplica[cç][aã]o|\binvest"),
    ("transferencia", r"mesma titularidade|entre contas|transf\.? (?:p/|para) conta pr[oó]pria"),
]
CREDIT_RULES: list[tuple[str, str]] = [
    ("estorno", r"estorno|devolu"),
    ("rendimento", r"rendimento|rend\.? pago|remunera[cç][aã]o"),
    ("resgate", r"resgate"),
    ("emprestimo", r"empr[eé]stimo|m[uú]tuo"),
    ("transferencia", r"mesma titularidade|entre contas|transf|ted receb|doc receb"),
    ("arrecadacao", r"cobran|liquida[cç][aã]o|boleto|taxas? condom|cotas? condom|arrecada"),
]
# Credits that look like collection but may be anything (a PIX from a person): suggestion.
SUGGESTED_CREDIT = ("arrecadacao", r"\bpix\b|dep[oó]sito")
INTERMEDIARY = r"pjbank|administradora|repasse"

LABELS = {
    "despesa": "Pagamento de despesa",
    "estorno": "Estorno ou devolução",
    "tarifa": "Tarifa bancária",
    "tributo_bancario": "Tributo bancário (IOF/IR)",
    "juros_encargos": "Juros ou encargos",
    "aplicacao": "Aplicação",
    "transferencia": "Transferência entre contas",
    "rendimento": "Rendimento",
    "resgate": "Resgate de aplicação",
    "emprestimo": "Empréstimo",
    "arrecadacao": "Arrecadação (cotas e boletos)",
    "nao_identificado": "Não identificado",
}
NON_REVENUE = {"transferencia", "estorno", "resgate", "emprestimo"}


def _fold(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@dataclass
class Line:
    trn: BankTransaction
    kind: str  # one of LABELS
    strength: str  # "regra" (deterministic), "sugerido" (weak keyword) or "pendente"
    intermediary: bool = False
    paired_with: uuid.UUID | None = None

    @property
    def amount(self) -> Decimal:
        return self.trn.amount


def classify(trn: BankTransaction, intermediary_docs: set[str]) -> Line:
    text = _fold(f"{trn.description} {trn.payee_name or ''}")
    if trn.amount < 0:
        if trn.expense_id is not None:
            indirect = bool(
                (trn.payee_document and trn.payee_document in intermediary_docs)
                or re.search(INTERMEDIARY, text)
            )
            return Line(trn, "despesa", "regra", indirect)
        for kind, pattern in DEBIT_RULES:
            if re.search(pattern, text):
                return Line(trn, kind, "regra")
        return Line(trn, "nao_identificado", "pendente")
    for kind, pattern in CREDIT_RULES:
        if re.search(pattern, text):
            return Line(trn, kind, "regra")
    kind, pattern = SUGGESTED_CREDIT
    if re.search(pattern, text):
        return Line(trn, kind, "sugerido")
    return Line(trn, "nao_identificado", "pendente")


def pair_reversals(lines: list[Line], window_days: int = 10) -> None:
    """Pair each reversal credit with the debit it returns: same absolute amount, up to
    ``window_days`` before, same account. Each debit is paired at most once."""
    used: set[uuid.UUID] = set()
    debits = sorted((ln for ln in lines if ln.amount < 0), key=lambda ln: ln.trn.posted_at)
    for credit in (ln for ln in lines if ln.amount > 0 and ln.kind == "estorno"):
        for debit in reversed(debits):
            if (
                debit.trn.id not in used
                and debit.trn.bank_account_id == credit.trn.bank_account_id
                and -debit.amount == credit.amount
                and credit.trn.posted_at - timedelta(days=window_days)
                <= debit.trn.posted_at
                <= credit.trn.posted_at
            ):
                used.add(debit.trn.id)
                credit.paired_with, debit.paired_with = debit.trn.id, credit.trn.id
                break


@dataclass
class AccountView:
    account: BankAccount | None  # None: lines whose file did not name the account
    statement: BankStatement | None
    previous: BankStatement | None
    lines: list[Line] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.account.label if self.account else "Conta não identificada no arquivo"

    @property
    def key(self) -> str:
        return str(self.account.id) if self.account else "sem_conta"

    @property
    def movements(self) -> Decimal:
        if self.statement is None:
            return sum((ln.amount for ln in self.lines), ZERO)
        return sum(
            (ln.amount for ln in self.lines if ln.trn.statement_id == self.statement.id), ZERO
        )

    def balance_check(self) -> dict[str, Any]:
        """Opening + movements = closing, with the source of each number (D122)."""
        st = self.statement
        out: dict[str, Any] = {"movimentos": str(self.movements)}
        if st is None:
            return {**out, "situacao": "sem_extrato"}
        if st.closing_balance is None:
            return {**out, "situacao": "sem_saldo_final"}
        if st.opening_balance is not None:
            opening, source = st.opening_balance, "declarado no extrato"
        elif self.previous is not None and self.previous.closing_balance is not None:
            opening, source = self.previous.closing_balance, "fechamento do extrato anterior"
        else:
            return {**out, "situacao": "sem_saldo_inicial", "saldo_final": str(st.closing_balance)}
        expected = opening + self.movements
        diff = st.closing_balance - expected
        return {
            **out,
            "situacao": "confere" if diff == ZERO else "diverge",
            "saldo_inicial": str(opening),
            "origem_saldo_inicial": source,
            "saldo_final_declarado": str(st.closing_balance),
            "saldo_final_calculado": str(expected),
            "diferenca": str(diff),
        }

    def continuity(self) -> dict[str, Any]:
        st, prev = self.statement, self.previous
        if st is None:
            return {"situacao": "sem_extrato"}
        if prev is None or prev.closing_balance is None:
            return {"situacao": "sem_mes_anterior"}
        if st.opening_balance is not None:
            opening, method = st.opening_balance, "saldo inicial declarado"
        elif st.closing_balance is not None:
            opening, method = (
                st.closing_balance - self.movements,
                "abertura implícita (final − movimentos)",
            )
        else:
            return {"situacao": "sem_saldo"}
        diff = opening - prev.closing_balance
        return {
            "situacao": "confere" if diff == ZERO else "diverge",
            "fechamento_anterior": str(prev.closing_balance),
            "abertura": str(opening),
            "metodo": method,
            "diferenca": str(diff),
        }


@dataclass
class ExpenseView:
    expense: Expense
    roles: dict[str, list[uuid.UUID]]  # role -> document ids
    payments: list[BankTransaction]
    supplier: Supplier | None

    @property
    def has_document(self) -> bool:
        return bool(self.roles.get("fiscal") or self.roles.get("recibo"))


@dataclass
class AuditData:
    condo: Condominium
    competence: date
    today: date
    documents: list[Document]
    accounts: list[AccountView]
    expenses: list[ExpenseView]
    copies: int
    superseded: int
    intermediary_docs: set[str]

    @property
    def month_end(self) -> date:
        return add_months(self.competence, 1) - timedelta(days=1)

    @property
    def lines(self) -> list[Line]:
        return [ln for a in self.accounts for ln in a.lines]

    @property
    def has_statement(self) -> bool:
        return any(a.statement is not None for a in self.accounts)


def _doc_month(doc: Document) -> date | None:
    v = doc.extracted or {}
    for key in (
        "competencia",
        "data_emissao",
        "vencimento",
        "data",
        "data_pagamento",
        "data_inicio",
    ):
        raw = v.get(key)
        if not raw:
            continue
        try:
            text = str(raw)
            return date(int(text[:4]), int(text[5:7]), 1)
        except ValueError:
            continue
    return None


async def load(
    session: AsyncSession, condo: Condominium, competence: date, today: date
) -> AuditData:
    first = competence
    last = add_months(competence, 1) - timedelta(days=1)
    expenses = list(
        await session.scalars(
            select(Expense)
            .where(Expense.condominium_id == condo.id, Expense.competence == first)
            .order_by(Expense.issue_date, Expense.id)
        )
    )
    links = (
        await session.execute(
            select(
                ExpenseDocument.expense_id, ExpenseDocument.role, ExpenseDocument.document_id
            ).where(
                ExpenseDocument.condominium_id == condo.id,
                ExpenseDocument.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
            )
        )
    ).all()
    roles: dict[uuid.UUID, dict[str, list[uuid.UUID]]] = {}
    for eid, role, did in links:
        roles.setdefault(eid, {}).setdefault(role, []).append(did)
    transactions = list(
        await session.scalars(
            select(BankTransaction)
            .where(
                BankTransaction.condominium_id == condo.id,
                or_(
                    BankTransaction.posted_at.between(first, last),
                    BankTransaction.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()]),
                ),
            )
            .order_by(BankTransaction.posted_at, BankTransaction.id)
        )
    )
    paid: dict[uuid.UUID, list[BankTransaction]] = {}
    for t in transactions:
        if t.expense_id is not None:
            paid.setdefault(t.expense_id, []).append(t)
    suppliers = {
        s.id: s
        for s in await session.scalars(
            select(Supplier).where(
                Supplier.id.in_([e.supplier_id for e in expenses if e.supplier_id])
            )
        )
    }
    intermediary: set[str] = set()
    if condo.management_company_id is not None:
        company = await session.get(ManagementCompany, condo.management_company_id)
        if company is not None:
            intermediary.add(company.cnpj)

    in_month = [t for t in transactions if first <= t.posted_at <= last]
    lines = [classify(t, intermediary) for t in in_month]
    accounts = list(
        await session.scalars(
            select(BankAccount)
            .where(BankAccount.condominium_id == condo.id)
            .order_by(BankAccount.label)
        )
    )
    statements = list(
        await session.scalars(
            select(BankStatement)
            .where(BankStatement.condominium_id == condo.id, BankStatement.format != "cnab")
            .order_by(BankStatement.period_end)
        )
    )
    views: list[AccountView] = []
    for account in accounts:
        mine = [s for s in statements if s.bank_account_id == account.id]
        current = [
            s
            for s in mine
            if s.period_end is not None
            and first <= s.period_end
            and (s.period_start or s.period_end) <= last
        ]
        statement = current[-1] if current else None
        previous = [s for s in mine if s.closing_date is not None and s.closing_date < first]
        views.append(
            AccountView(
                account,
                statement,
                previous[-1] if previous else None,
                [ln for ln in lines if ln.trn.bank_account_id == account.id],
            )
        )
    loose = [ln for ln in lines if ln.trn.bank_account_id is None]
    if loose:
        views.append(AccountView(None, None, None, loose))
    for view in views:
        pair_reversals(view.lines)

    linked = {d for r in roles.values() for ds in r.values() for d in ds}
    linked |= {
        s.document_id
        for s in statements
        if s.document_id
        and s.period_end is not None
        and first <= s.period_end
        and (s.period_start or s.period_end) <= last
    }
    window_start = first - timedelta(days=120)
    candidates = await session.scalars(
        select(Document)
        .options(defer(Document.text_content))
        .where(
            Document.condominium_id == condo.id,
            or_(
                Document.id.in_(linked or {uuid.uuid4()}),
                Document.created_at >= datetime.combine(window_start, time.min, tzinfo=UTC),
            ),
        )
    )
    upload_end = last + timedelta(days=UPLOAD_GRACE_DAYS)
    docs = []
    for d in candidates:
        month = _doc_month(d)
        uploaded = d.created_at.date()
        if d.id in linked or month == first or (month is None and first <= uploaded <= upload_end):
            docs.append(d)
    superseded_ids = {d.supersedes_id for d in docs if d.supersedes_id}
    copies = sum(1 for r in roles.values() for d in r.get("copia", []))
    return AuditData(
        condo=condo,
        competence=first,
        today=today,
        documents=sorted(docs, key=lambda d: (d.created_at, str(d.id))),
        accounts=views,
        expenses=[
            ExpenseView(
                e,
                roles.get(e.id, {}),
                paid.get(e.id, []),
                suppliers.get(e.supplier_id) if e.supplier_id else None,
            )
            for e in expenses
        ],
        copies=copies,
        superseded=len(superseded_ids),
        intermediary_docs=intermediary,
    )
