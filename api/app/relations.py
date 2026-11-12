"""Relations of a document, a contract or a supplier (FR-014, D126).

Everything is found through the links the product already keeps (expense ↔ document roles,
contract source and amendments, approvals, cases, compliance evidence, versions, the audit's
inputs); nothing is inferred and no link is created here. Each item says how it is related
and where to open it. Findings still under review are listed only for who sees them.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.money import brl
from app.db.enums import UNDER_REVIEW
from app.db.models import (
    AccountsApproval,
    Approval,
    Budget,
    CaseLink,
    CaseRecord,
    ComplianceEvidence,
    ComplianceObligation,
    Contract,
    ContractAmendment,
    Document,
    Expense,
    ExpenseDocument,
    Finding,
    FundBalance,
    Opportunity,
    Supplier,
)

ROLE_LABEL = {
    "fiscal": "nota ou boleto da despesa",
    "recibo": "recibo da despesa",
    "copia": "cópia da nota",
    "pagamento": "comprovante de pagamento",
}
KINDS = ("document", "contract", "supplier")


def _item(kind: str, id_: Any, label: str, relation: str, href: str | None) -> dict[str, Any]:
    return {"kind": kind, "id": str(id_), "label": label, "relation": relation, "href": href}


def _expense_label(e: Expense) -> str:
    return f"{e.description[:70]} · {brl(e.amount)} · {e.competence:%m/%Y}"


async def _cases(
    session: AsyncSession, condo_id: uuid.UUID, target_type: str, ids: Iterable[uuid.UUID]
) -> list[dict[str, Any]]:
    ids = list(ids)
    if not ids:
        return []
    rows = await session.execute(
        select(CaseRecord, CaseLink.target_id)
        .join(CaseLink, CaseLink.case_id == CaseRecord.id)
        .where(
            CaseLink.condominium_id == condo_id,
            CaseLink.target_type == target_type,
            CaseLink.target_id.in_(ids),
            CaseLink.unlinked_at.is_(None),
        )
    )
    seen: set[uuid.UUID] = set()
    out = []
    for case, _ in rows:
        if case.id in seen:
            continue
        seen.add(case.id)
        out.append(
            _item(
                "case",
                case.id,
                f"{case.number} · {case.title}",
                f"assunto ({case.status})",
                f"/admin/assuntos/{condo_id}/{case.id}",
            )
        )
    return out


async def _documents(session: AsyncSession, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Document]:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    return {
        d.id: d
        for d in await session.scalars(
            select(Document).options(defer(Document.text_content)).where(Document.id.in_(ids))
        )
    }


def _doc_item(condo_id: uuid.UUID, d: Document, relation: str) -> dict[str, Any]:
    return _item(
        "document",
        d.id,
        d.original_filename,
        relation,
        f"/admin/relacoes/{condo_id}/document/{d.id}",
    )


async def _findings(
    session: AsyncSession, condo_id: uuid.UUID, *, supplier_id: uuid.UUID | None, see_pending: bool
) -> list[dict[str, Any]]:
    if supplier_id is None:
        return []
    stmt = select(Finding).where(
        Finding.condominium_id == condo_id, Finding.supplier_id == supplier_id
    )
    if not see_pending:
        stmt = stmt.where(Finding.status.notin_([s.value for s in UNDER_REVIEW]))
    rows = list(await session.scalars(stmt.order_by(Finding.competence.desc()).limit(30)))
    return [
        _item(
            "finding",
            f.id,
            f"{f.rule_code} · {f.title[:70]} · {f.competence:%m/%Y}",
            f"achado ({f.status})",
            f"/admin/achados/{condo_id}/{f.id}",
        )
        for f in rows
    ]


async def _expenses_with_docs(
    session: AsyncSession, condo_id: uuid.UUID, expenses: list[Expense]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exp_items = [_item("expense", e.id, _expense_label(e), "despesa", None) for e in expenses]
    links = (
        await session.execute(
            select(ExpenseDocument.document_id, ExpenseDocument.role).where(
                ExpenseDocument.expense_id.in_([e.id for e in expenses] or [uuid.uuid4()])
            )
        )
    ).all()
    docs = await _documents(session, [d for d, _ in links])
    doc_items = []
    seen: set[uuid.UUID] = set()
    for did, role in links:
        if did in docs and did not in seen:
            seen.add(did)
            doc_items.append(_doc_item(condo_id, docs[did], ROLE_LABEL.get(role, role)))
    return exp_items, doc_items


async def document_relations(
    session: AsyncSession, condo_id: uuid.UUID, document_id: uuid.UUID, see_pending: bool
) -> dict[str, Any]:
    doc = await session.get(Document, document_id, options=[defer(Document.text_content)])
    if doc is None or doc.condominium_id != condo_id:
        raise LookupError("documento não encontrado")
    groups: dict[str, list[dict[str, Any]]] = {}
    links = (
        await session.execute(
            select(Expense, ExpenseDocument.role)
            .join(ExpenseDocument, ExpenseDocument.expense_id == Expense.id)
            .where(ExpenseDocument.document_id == doc.id, Expense.condominium_id == condo_id)
        )
    ).all()
    groups["Despesas"] = [
        _item("expense", e.id, _expense_label(e), ROLE_LABEL.get(role, role), None)
        for e, role in links
    ]
    contracts = list(
        await session.scalars(
            select(Contract).where(
                Contract.condominium_id == condo_id, Contract.source_document_id == doc.id
            )
        )
    )
    amendments = list(
        await session.scalars(
            select(ContractAmendment).where(
                ContractAmendment.condominium_id == condo_id,
                ContractAmendment.document_id == doc.id,
            )
        )
    )
    amended = {
        c.id: c
        for c in await session.scalars(
            select(Contract).where(
                Contract.id.in_([a.contract_id for a in amendments] or [uuid.uuid4()])
            )
        )
    }
    groups["Contratos"] = [
        _item(
            "contract",
            c.id,
            c.object[:80],
            "documento do contrato",
            f"/admin/contratos/{condo_id}/{c.id}",
        )
        for c in contracts
    ] + [
        _item(
            "contract",
            a.contract_id,
            amended[a.contract_id].object[:80] if a.contract_id in amended else "contrato",
            f"termo aditivo de {a.effective_date:%d/%m/%Y}",
            f"/admin/contratos/{condo_id}/{a.contract_id}",
        )
        for a in amendments
    ]
    approvals = list(
        await session.execute(
            select(Approval, Expense)
            .join(Expense, Expense.id == Approval.expense_id)
            .where(Approval.condominium_id == condo_id, Approval.source_document_id == doc.id)
        )
    )
    groups["Aprovações"] = [
        _item(
            "approval",
            a.id,
            f"{a.approved_by} · {_expense_label(e)}",
            "aceite" if a.kind == "aceite" else "autorização de despesa",
            None,
        )
        for a, e in approvals
    ]
    evidence = list(
        await session.execute(
            select(ComplianceEvidence, ComplianceObligation)
            .join(ComplianceObligation, ComplianceObligation.id == ComplianceEvidence.obligation_id)
            .where(
                ComplianceEvidence.condominium_id == condo_id,
                ComplianceEvidence.document_id == doc.id,
            )
        )
    )
    governance = [
        _item(
            "obligation",
            ob.id,
            ob.name,
            "documento da obrigação",
            f"/admin/conformidade?condominio={condo_id}",
        )
        for _, ob in evidence
    ]
    for a in await session.scalars(
        select(AccountsApproval).where(
            AccountsApproval.condominium_id == condo_id, AccountsApproval.document_id == doc.id
        )
    ):
        governance.append(
            _item(
                "accounts_approval",
                a.id,
                f"Aprovação das contas {a.period_start:%m/%Y} a {a.period_end:%m/%Y}",
                "documento da aprovação (DOC-03)",
                f"/admin/audit/governanca?condominio={condo_id}",
            )
        )
    for b in await session.scalars(
        select(Budget).where(Budget.condominium_id == condo_id, Budget.source_document_id == doc.id)
    ):
        governance.append(
            _item(
                "budget",
                b.id,
                f"Orçamento {b.year} (versão {b.version})",
                "ata do orçamento",
                f"/admin/audit/governanca?condominio={condo_id}",
            )
        )
    for fb in await session.scalars(
        select(FundBalance).where(
            FundBalance.condominium_id == condo_id, FundBalance.source_document_id == doc.id
        )
    ):
        governance.append(
            _item(
                "fund_balance",
                fb.id,
                f"Saldo de fundo de {fb.competence:%m/%Y}",
                "demonstrativo do fundo",
                f"/admin/audit/governanca?condominio={condo_id}",
            )
        )
    groups["Conformidade e governança"] = governance
    versions = list(
        await session.scalars(
            select(Document)
            .options(defer(Document.text_content))
            .where(
                Document.condominium_id == condo_id,
                or_(Document.id == doc.supersedes_id, Document.supersedes_id == doc.id),
            )
        )
    )
    groups["Versões"] = [
        _doc_item(
            condo_id, v, "versão anterior" if v.id == doc.supersedes_id else "versão mais nova"
        )
        for v in versions
    ]
    groups["Assuntos"] = await _cases(session, condo_id, "document", [doc.id])
    return {
        "object": {"kind": "document", "id": str(doc.id), "label": doc.original_filename},
        "groups": _non_empty(groups),
    }


async def contract_relations(
    session: AsyncSession, condo_id: uuid.UUID, contract_id: uuid.UUID, see_pending: bool
) -> dict[str, Any]:
    c = await session.get(Contract, contract_id)
    if c is None or c.condominium_id != condo_id:
        raise LookupError("contrato não encontrado")
    groups: dict[str, list[dict[str, Any]]] = {}
    amendments = list(
        await session.scalars(
            select(ContractAmendment)
            .where(ContractAmendment.contract_id == c.id)
            .order_by(ContractAmendment.effective_date)
        )
    )
    docs = await _documents(
        session, [c.source_document_id, *(a.document_id for a in amendments)]  # type: ignore[list-item]
    )
    own = []
    if c.source_document_id in docs:
        own.append(_doc_item(condo_id, docs[c.source_document_id], "documento do contrato"))
    for a in amendments:
        if a.document_id in docs:
            own.append(
                _doc_item(condo_id, docs[a.document_id], f"aditivo de {a.effective_date:%d/%m/%Y}")
            )
    expenses = list(
        await session.scalars(
            select(Expense)
            .where(Expense.condominium_id == condo_id, Expense.contract_id == c.id)
            .order_by(Expense.competence.desc())
            .limit(60)
        )
    )
    exp_items, exp_docs = await _expenses_with_docs(session, condo_id, expenses)
    groups["Documentos do contrato"] = own
    groups["Despesas cobradas"] = exp_items
    groups["Notas e comprovantes das despesas"] = exp_docs
    if c.supplier_id is not None:
        sup = await session.get(Supplier, c.supplier_id)
        if sup is not None:
            groups["Fornecedor"] = [
                _item(
                    "supplier",
                    sup.id,
                    sup.legal_name,
                    "contratada",
                    f"/admin/relacoes/{condo_id}/supplier/{sup.id}",
                )
            ]
    groups["Assuntos"] = await _cases(session, condo_id, "contract", [c.id])
    opp = select(Opportunity).where(
        Opportunity.condominium_id == condo_id, Opportunity.contract_id == c.id
    )
    groups["Oportunidades"] = [
        _item("opportunity", o.id, f"{o.number} · {o.title}", f"oportunidade ({o.status})", None)
        for o in await session.scalars(opp)
        if see_pending
        or o.status not in ("identificada", "em_revisao_interna", "devolvida", "rejeitada")
    ]
    return {
        "object": {"kind": "contract", "id": str(c.id), "label": c.object},
        "groups": _non_empty(groups),
    }


async def supplier_relations(
    session: AsyncSession, condo_id: uuid.UUID, supplier_id: uuid.UUID, see_pending: bool
) -> dict[str, Any]:
    sup = await session.get(Supplier, supplier_id)
    contracts = list(
        await session.scalars(
            select(Contract).where(
                Contract.condominium_id == condo_id, Contract.supplier_id == supplier_id
            )
        )
    )
    expenses = list(
        await session.scalars(
            select(Expense)
            .where(Expense.condominium_id == condo_id, Expense.supplier_id == supplier_id)
            .order_by(Expense.competence.desc())
            .limit(60)
        )
    )
    # A supplier is shared between condominiums: it is "found" here only through this
    # condominium's own records.
    if sup is None or not (contracts or expenses):
        raise LookupError("fornecedor não encontrado")
    exp_items, exp_docs = await _expenses_with_docs(session, condo_id, expenses)
    groups = {
        "Contratos": [
            _item(
                "contract", c.id, c.object[:80], "contrato", f"/admin/contratos/{condo_id}/{c.id}"
            )
            for c in contracts
        ],
        "Despesas": exp_items,
        "Documentos": exp_docs,
        "Achados": await _findings(
            session, condo_id, supplier_id=supplier_id, see_pending=see_pending
        ),
        "Assuntos": await _cases(session, condo_id, "supplier", [supplier_id]),
    }
    return {
        "object": {"kind": "supplier", "id": str(sup.id), "label": sup.legal_name},
        "groups": _non_empty(groups),
    }


def _non_empty(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"title": k, "items": v} for k, v in groups.items() if v]


RESOLVERS = {
    "document": document_relations,
    "contract": contract_relations,
    "supplier": supplier_relations,
}
