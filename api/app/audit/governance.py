"""Inputs of the cycle-3 controls (D124): funds and their backing accounts, fund balances of
the statement of accounts, the approved budget, variance notes and the formal approval of the
accounts. Every change is recorded in ``audit_log``; notes and approvals are append only.

Nothing here decides a status: the controls read these records like any other source.
"""

import csv
import hashlib
import io
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.imports import ImportFileError, _money, _month
from app.core.audit import record_audit
from app.db.enums import AccountKind, AccountsApprovalBody, FundKind
from app.db.models import (
    AccountsApproval,
    BankAccount,
    BoardMember,
    Budget,
    BudgetLine,
    BudgetNote,
    Condominium,
    Document,
    Fund,
    FundAccount,
    FundBalance,
)
from app.matching.categories import CATEGORY_LABEL

FUND_COLUMNS = {
    "fundo": "fundo",
    "competencia": "competencia",
    "saldo inicial": "saldo_inicial",
    "entradas": "entradas",
    "saidas": "saidas",
    "rendimentos": "rendimentos",
    "saldo final": "saldo_final",
}
BUDGET_COLUMNS = {"categoria": "categoria", "mes": "mes", "competencia": "mes", "valor": "valor"}
CENT = Decimal("0.01")


class GovernanceError(ValueError):
    pass


@dataclass
class TableResult:
    created: int = 0
    updated: int = 0
    errors: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "criados": self.created,
            "atualizados": self.updated,
            "erros": self.errors[:50],
            **self.extra,
        }


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[_\-./]", " ", text).split())


def _table(data: bytes, allowed: dict[str, str], required: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    sample = text[:2000]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    lines = [
        r for r in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in r)
    ]
    if not lines:
        raise ImportFileError("Arquivo vazio.")
    keep = {i: allowed[_fold(h)] for i, h in enumerate(lines[0]) if _fold(h) in allowed}
    for col in required:
        if col not in keep.values():
            raise ImportFileError(f"A planilha precisa da coluna “{col.replace('_', ' ')}”.")
    return [
        {name: (r[i].strip() if i < len(r) else "") for i, name in keep.items()} for r in lines[1:]
    ]


def fund_kind(name: str) -> FundKind:
    folded = _fold(name)
    if "reserva" in folded:
        return FundKind.RESERVA
    if "obra" in folded:
        return FundKind.OBRAS
    return FundKind.OUTRO


async def _audit(
    session: AsyncSession,
    condo_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    **details: Any,
) -> None:
    await record_audit(
        session,
        action=action,
        object_type="condominium",
        object_id=condo_id,
        actor_user_id=user_id,
        condominium_id=condo_id,
        details=details,
    )


async def _document(
    session: AsyncSession, condo_id: uuid.UUID, document_id: uuid.UUID | None
) -> None:
    if document_id is None:
        return
    found = await session.scalar(
        select(Document.id).where(Document.id == document_id, Document.condominium_id == condo_id)
    )
    if found is None:
        raise LookupError("documento não encontrado")


# --------------------------------------------------------------------------- funds


async def get_or_create_fund(
    session: AsyncSession, condo: Condominium, name: str, kind: FundKind | None = None
) -> tuple[Fund, bool]:
    clean = " ".join(name.split())[:120]
    if not clean:
        raise GovernanceError("Nome do fundo vazio.")
    fund = await session.scalar(
        select(Fund).where(Fund.condominium_id == condo.id, Fund.name == clean)
    )
    if fund is not None:
        return fund, False
    fund = Fund(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        name=clean,
        kind=(kind or fund_kind(clean)).value,
    )
    session.add(fund)
    await session.flush()
    return fund, True


async def update_fund(
    session: AsyncSession,
    condo: Condominium,
    fund_id: uuid.UUID,
    *,
    kind: FundKind | None,
    purpose: str | None,
    account_ids: list[uuid.UUID] | None,
    user_id: uuid.UUID,
) -> Fund:
    fund = await session.get(Fund, fund_id)
    if fund is None or fund.condominium_id != condo.id:
        raise LookupError("fundo não encontrado")
    if kind is not None:
        fund.kind = kind.value
    if purpose is not None:
        fund.purpose = purpose.strip()[:300] or None
    if account_ids is not None:
        valid = set(
            await session.scalars(
                select(BankAccount.id).where(
                    BankAccount.condominium_id == condo.id,
                    BankAccount.id.in_(account_ids or [uuid.uuid4()]),
                )
            )
        )
        if valid != set(account_ids):
            raise LookupError("conta não encontrada")
        current = {
            fa.bank_account_id: fa
            for fa in await session.scalars(
                select(FundAccount).where(FundAccount.fund_id == fund.id)
            )
        }
        for acc, fa in current.items():
            if acc not in valid:
                await session.delete(fa)
        for acc in valid - set(current):
            session.add(
                FundAccount(
                    id=uuid.uuid4(), condominium_id=condo.id, fund_id=fund.id, bank_account_id=acc
                )
            )
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.fund.updated",
        fund_id=str(fund.id),
        kind=fund.kind,
        accounts=len(account_ids) if account_ids is not None else None,
    )
    return fund


async def set_account_kind(
    session: AsyncSession,
    condo: Condominium,
    account_id: uuid.UUID,
    kind: AccountKind,
    label: str | None,
    user_id: uuid.UUID,
) -> BankAccount:
    account = await session.get(BankAccount, account_id)
    if account is None or account.condominium_id != condo.id:
        raise LookupError("conta não encontrada")
    account.kind = kind.value
    if label and label.strip():
        account.label = label.strip()[:120]
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.account.updated",
        account_id=str(account.id),
        kind=kind.value,
    )
    return account


async def import_fund_balances(
    session: AsyncSession, condo: Condominium, data: bytes, user_id: uuid.UUID | None
) -> TableResult:
    """Fund balances of the statement of accounts: one line per fund and month. A blank cell
    stays empty (never zero); importing again updates the same fund and month."""
    rows = _table(data, FUND_COLUMNS, ("fundo", "competencia", "saldo_final"))
    result = TableResult(extra={"fundos_criados": 0})
    for n, r in enumerate(rows, start=2):
        try:
            month = _month(r.get("competencia", ""))
            closing = _money(r.get("saldo_final", ""))
            if month is None or closing is None:
                raise ValueError("competência e saldo final são obrigatórios")
            values = {
                "opening": _money(r.get("saldo_inicial", "")),
                "inflows": _money(r.get("entradas", "")),
                "outflows": _money(r.get("saidas", "")),
                "yield_amount": _money(r.get("rendimentos", "")),
            }
            for key in ("inflows", "outflows"):
                if values[key] is not None:
                    values[key] = abs(values[key])  # type: ignore[arg-type]
        except ValueError as exc:
            result.errors.append(f"linha {n}: {exc}")
            continue
        fund, created = await get_or_create_fund(session, condo, r.get("fundo", ""))
        result.extra["fundos_criados"] += int(created)
        existing = await session.scalar(
            select(FundBalance).where(
                FundBalance.fund_id == fund.id, FundBalance.competence == month
            )
        )
        if existing is None:
            session.add(
                FundBalance(
                    id=uuid.uuid4(),
                    condominium_id=condo.id,
                    fund_id=fund.id,
                    competence=month,
                    closing=closing,
                    **values,
                )
            )
            result.created += 1
        else:
            existing.closing = closing
            for key, value in values.items():
                setattr(existing, key, value)
            result.updated += 1
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.import.fund_balances",
        created=result.created,
        updated=result.updated,
        errors=len(result.errors),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    return result


# --------------------------------------------------------------------------- budget


def _category(raw: str) -> str:
    folded = _fold(raw)
    for key, label in CATEGORY_LABEL.items():
        if folded in (_fold(key), _fold(label)):
            return key
    raise ValueError(f"categoria desconhecida “{raw}”")


def _budget_month(raw: str, year: int) -> date | None:
    raw = raw.strip()
    if not raw or _fold(raw) in ("anual", "ano"):
        return None
    if raw.isdigit() and 1 <= int(raw) <= 12:
        return date(year, int(raw), 1)
    month = _month(raw)
    if month is None or month.year != year:
        raise ValueError(f"mês fora de {year}")
    return month


async def import_budget(
    session: AsyncSession,
    condo: Condominium,
    data: bytes,
    *,
    year: int,
    approved_on: date | None,
    source_document_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
) -> TableResult:
    """A new version of the year's budget. A line without month is annual and is split into
    twelve equal months (the last one absorbs the cents)."""
    await _document(session, condo.id, source_document_id)
    rows = _table(data, BUDGET_COLUMNS, ("categoria", "valor"))
    amounts: dict[tuple[str, date], Decimal] = {}
    result = TableResult()
    for n, r in enumerate(rows, start=2):
        try:
            category = _category(r.get("categoria", ""))
            value = _money(r.get("valor", ""))
            if value is None:
                raise ValueError("valor obrigatório")
            month = _budget_month(r.get("mes", ""), year)
        except ValueError as exc:
            result.errors.append(f"linha {n}: {exc}")
            continue
        if month is None:
            part = (value / 12).quantize(CENT, ROUND_HALF_UP)
            for m in range(1, 13):
                share = value - part * 11 if m == 12 else part
                key = (category, date(year, m, 1))
                amounts[key] = amounts.get(key, Decimal("0")) + share
        else:
            amounts[(category, month)] = amounts.get((category, month), Decimal("0")) + value
    if not amounts:
        raise ImportFileError("Nenhuma linha válida no orçamento.")
    latest = await session.scalar(
        select(func.max(Budget.version)).where(
            Budget.condominium_id == condo.id, Budget.year == year
        )
    )
    budget = Budget(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        year=year,
        version=(latest or 0) + 1,
        approved_on=approved_on,
        source_document_id=source_document_id,
        file_sha256=hashlib.sha256(data).hexdigest(),
        created_by=user_id,
    )
    session.add(budget)
    await session.flush()
    for (category, month), amount in sorted(amounts.items()):
        session.add(
            BudgetLine(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                budget_id=budget.id,
                category=category,
                month=month,
                amount=amount,
            )
        )
    result.created = len(amounts)
    result.extra = {"versao": budget.version, "orcamento_id": str(budget.id)}
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.import.budget",
        year=year,
        version=budget.version,
        lines=len(amounts),
        errors=len(result.errors),
    )
    return result


async def add_budget_note(
    session: AsyncSession,
    condo: Condominium,
    competence: date,
    category: str,
    text: str,
    user_id: uuid.UUID,
) -> BudgetNote:
    if category not in CATEGORY_LABEL:
        raise GovernanceError("Categoria desconhecida.")
    clean = text.strip()
    if len(clean) < 10:
        raise GovernanceError("Explique o desvio em pelo menos 10 caracteres.")
    note = BudgetNote(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        competence=competence,
        category=category,
        text=clean[:2000],
        user_id=user_id,
    )
    session.add(note)
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.budget.note",
        competence=competence.isoformat(),
        category=category,
    )
    return note


# --------------------------------------------------------------------------- DOC-03


async def record_accounts_approval(
    session: AsyncSession,
    condo: Condominium,
    *,
    body: AccountsApprovalBody,
    period_start: date,
    period_end: date,
    approved_on: date,
    document_id: uuid.UUID,
    signatories: list[dict[str, Any]],
    with_reservations: bool,
    notes: str | None,
    user_id: uuid.UUID,
    today: date,
) -> AccountsApproval:
    """The approval of the accounts of a period, always with its document. Board signatories
    are kept by id (their name comes from the board); an assembly's chair and secretary by
    name and role. Residents' data never enters here."""
    await _document(session, condo.id, document_id)
    start, end = period_start.replace(day=1), period_end.replace(day=1)
    if start > end:
        raise GovernanceError("O período começa depois de terminar.")
    if approved_on > today:
        raise GovernanceError("A data da aprovação não pode estar no futuro.")
    if not signatories:
        raise GovernanceError("Informe quem assinou a aprovação.")
    board = {
        str(m.id): m
        for m in await session.scalars(
            select(BoardMember).where(BoardMember.condominium_id == condo.id)
        )
    }
    clean: list[dict[str, Any]] = []
    for s in signatories[:20]:
        if s.get("board_member_id"):
            m = board.get(str(s["board_member_id"]))
            if m is None:
                raise LookupError("membro do corpo diretivo não encontrado")
            clean.append({"board_member_id": str(m.id), "nome": m.full_name, "cargo": m.position})
        else:
            name = " ".join(str(s.get("nome", "")).split())[:120]
            role = " ".join(str(s.get("papel", "")).split())[:60]
            if not name or not role:
                raise GovernanceError("Signatário sem nome e papel na mesa.")
            if body != AccountsApprovalBody.ASSEMBLEIA:
                raise GovernanceError("No conselho, escolha os signatários do corpo diretivo.")
            clean.append({"nome": name, "papel": role})
    row = AccountsApproval(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        body=body.value,
        period_start=start,
        period_end=end,
        approved_on=approved_on,
        document_id=document_id,
        signatories=clean,
        with_reservations=with_reservations,
        notes=(notes or "").strip()[:2000] or None,
        recorded_by=user_id,
    )
    session.add(row)
    await session.flush()
    await _audit(
        session,
        condo.id,
        user_id,
        "audit.accounts_approval.recorded",
        approval_id=str(row.id),
        body=body.value,
        period=f"{start:%Y-%m}..{end:%Y-%m}",
        signatories=len(clean),
    )
    return row


def parse_month(raw: str) -> date:
    try:
        month = _month(raw)
    except ValueError as exc:
        raise GovernanceError(str(exc)) from exc
    if month is None:
        raise GovernanceError("Informe a competência (AAAA-MM).")
    return month


__all__ = [
    "GovernanceError",
    "TableResult",
    "add_budget_note",
    "get_or_create_fund",
    "import_budget",
    "import_fund_balances",
    "parse_month",
    "record_accounts_approval",
    "set_account_kind",
    "update_fund",
]
