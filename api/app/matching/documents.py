"""Document → expense → contract (spec §5.5).

A validated document (no review pending) becomes, or is attached to, an expense:
- fiscal document (NFS-e, NF-e) or receipt: creates the expense, or attaches to an existing
  expense of the same supplier with the same invoice number (idempotent);
- boleto: attaches to the single open expense of the same supplier with the same value and a
  compatible date; with no candidate it creates the expense; with several, it goes to the
  exception queue (never chosen at random). A copy of a boleto already received (same
  digitable line) joins that boleto's expense.
The contract is chosen by supplier CNPJ, then validity at the issue date, then object/scope
similarity. An expired contract is still linked when it is the only one (rule R05 flags it).
- contract document: registers the contract (D59) when the contracting party is this
  condominium (otherwise back to the extraction queue); the same supplier and start date
  links to the existing contract instead. A termo aditivo is linked to the supplier's
  contract as an amendment (D66).
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.jobs import enqueue
from app.core.time import utcnow
from app.db.enums import AdjustmentIndex, ContractNature, DocumentType, ExtractionStatus
from app.db.models import (
    Condominium,
    Contract,
    ContractAmendment,
    Document,
    Expense,
    ExpenseDocument,
    MatchIssue,
    Supplier,
)
from app.enrichment.suppliers import get_or_create_supplier
from app.extraction.clauses import apply_clauses
from app.matching.categories import category_for
from app.matching.text import overlap

MATCH_JOB = "document.match"
BOLETO_WINDOW_BEFORE = timedelta(days=60)
BOLETO_WINDOW_AFTER = timedelta(days=10)
CENT = Decimal("0.01")
# A second file of a note already received (D120): linked to the same expense, no new expense.
COPY_ROLE = "copia"
MIN_FINGERPRINT_CHARS = 200
RECEIPT_ROLE = "pagamento"
RECEIPT_WINDOW = timedelta(days=60)  # a payment up to 60 days after the note or boleto
TAX_CATEGORY = "tributos"


@dataclass(frozen=True)
class MatchOutcome:
    expense_id: uuid.UUID | None
    created: bool = False
    issue: str | None = None


def _d(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def _money(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value not in (None, "") else None


async def choose_contract(
    session: AsyncSession, condominium_id: uuid.UUID, supplier_id: uuid.UUID, when: date, text: str
) -> tuple[Contract | None, list[Contract]]:
    """(chosen contract, ambiguous candidates). Never picks at random."""
    contracts = list(
        await session.scalars(
            select(Contract).where(
                Contract.condominium_id == condominium_id, Contract.supplier_id == supplier_id
            )
        )
    )
    if not contracts:
        return None, []
    valid = [
        c for c in contracts if c.start_date <= when and (c.end_date is None or when <= c.end_date)
    ]
    pool = valid or [max(contracts, key=lambda c: c.end_date or date.max)]
    if len(pool) == 1:
        return pool[0], []
    scored = sorted(
        (
            (max(overlap(text, c.object), *(overlap(text, s) for s in c.scope_items or [""])), c)
            for c in pool
        ),
        key=lambda x: x[0],
        reverse=True,
    )
    if scored[0][0] > 0 and scored[0][0] > scored[1][0]:
        return scored[0][1], []
    return None, pool


async def _attach(session: AsyncSession, expense: Expense, doc: Document, role: str) -> None:
    exists = await session.scalar(
        select(ExpenseDocument.id).where(ExpenseDocument.document_id == doc.id)
    )
    if exists is None:
        session.add(
            ExpenseDocument(
                condominium_id=expense.condominium_id,
                expense_id=expense.id,
                document_id=doc.id,
                role=role,
            )
        )


async def match_document(session: AsyncSession, doc: Document) -> MatchOutcome:
    if doc.needs_review or doc.extraction_status != ExtractionStatus.DONE.value:
        return MatchOutcome(None)  # a document with pending review produces nothing
    linked = await session.scalar(
        select(ExpenseDocument.expense_id).where(ExpenseDocument.document_id == doc.id)
    )
    if linked is not None:
        return MatchOutcome(linked)
    v = doc.extracted
    doc_type = DocumentType(doc.doc_type)

    if doc_type in (DocumentType.NFSE, DocumentType.NFE):
        cnpj = v.get("cnpj_prestador") or v.get("cnpj_emitente")
        name = v.get("razao_social_prestador") or v.get("razao_social_emitente")
        amount = _money(v.get("valor_liquido") or v.get("valor_total"))
        issue = _d(v.get("data_emissao"))
        competence = (
            date.fromisoformat(v["competencia"] + "-01") if v.get("competencia") else None
        ) or (issue.replace(day=1) if issue else None)
        text = v.get("discriminacao") or " ".join(v.get("itens") or [])
        number = v.get("numero")
        role = "fiscal"
    elif doc_type == DocumentType.RECIBO:
        cnpj = (
            v.get("documento_recebedor") if len(v.get("documento_recebedor") or "") == 14 else None
        )
        name = v.get("nome_recebedor")
        amount, issue = _money(v.get("valor")), _d(v.get("data"))
        competence = issue.replace(day=1) if issue else None
        text, number, role = v.get("descricao") or "", None, "recibo"
    elif doc_type == DocumentType.BOLETO:
        return await _match_boleto(session, doc)
    elif doc_type == DocumentType.COMPROVANTE:
        return await _match_receipt(session, doc)
    elif doc_type == DocumentType.GUIA_TRIBUTO:
        return await _match_tax_slip(session, doc)
    elif doc_type == DocumentType.CONTRATO:
        await register_contract(session, doc)
        from app.data_issues import detect  # conflicts between documents (D93)

        await detect(session, doc.condominium_id)
        from app.data_issues.contracts import detect_contracts  # contract alerts (D120)

        await detect_contracts(session, doc.condominium_id)
        return MatchOutcome(None)
    else:
        return MatchOutcome(None)
    if amount is None or issue is None or competence is None:
        return MatchOutcome(None)

    supplier = await get_or_create_supplier(session, cnpj, name) if cnpj else None
    if supplier is not None and role == "fiscal":
        await fill_contract_supplier(session, doc.condominium_id, supplier)
    # The same note in another file (downloaded twice, a photo of the PDF): it joins the
    # expense of the first one as a copy, never a new expense (D120, A4).
    if role == "fiscal":
        original = await _same_note(session, doc, supplier, number, amount, issue)
        if original is not None:
            fiscal = await session.scalar(
                select(ExpenseDocument.id).where(
                    ExpenseDocument.expense_id == original.id, ExpenseDocument.role == "fiscal"
                )
            )
            await _attach(session, original, doc, COPY_ROLE if fiscal else role)
            return MatchOutcome(original.id)

    # A boleto received earlier may already have created the expense: attach the note to it.
    if supplier is not None:
        pending = list(
            await session.scalars(
                select(Expense).where(
                    Expense.condominium_id == doc.condominium_id,
                    Expense.supplier_id == supplier.id,
                    Expense.invoice_number.is_(None),
                    Expense.amount.between(amount - CENT, amount + CENT),
                    Expense.competence == competence,
                )
            )
        )
        if len(pending) == 1:
            pending[0].invoice_number = str(number) if number else None
            pending[0].document_id = doc.id
            await _attach(session, pending[0], doc, role)
            return MatchOutcome(pending[0].id)

    contract: Contract | None = None
    ambiguous: list[Contract] = []
    if supplier is not None:
        contract, ambiguous = await choose_contract(
            session, doc.condominium_id, supplier.id, issue, text
        )
    expense = Expense(
        id=uuid.uuid4(),
        condominium_id=doc.condominium_id,
        supplier_id=supplier.id if supplier else None,
        contract_id=contract.id if contract else None,
        document_id=doc.id,
        competence=competence,
        issue_date=issue,
        due_date=None,
        amount=amount,
        category=category_for(contract, supplier, text),
        description=(text or name or "Despesa")[:500],
        invoice_number=str(number) if number else None,
        origin="documento",
    )
    session.add(expense)
    await session.flush()
    await _attach(session, expense, doc, role)
    if ambiguous:
        await open_issue(
            session,
            doc.condominium_id,
            "contrato_ambiguo",
            "expense",
            expense.id,
            [{"type": "contract", "id": str(c.id), "label": c.object} for c in ambiguous],
            "Mais de um contrato possível para a despesa",
        )
    if supplier is not None and supplier.enriched_at is None:
        await enqueue(
            session,
            "supplier.enrich",
            {"cnpj": supplier.cnpj},
            dedupe_key=f"supplier:{supplier.cnpj}:enrich",
        )
    return MatchOutcome(expense.id, created=True)


def invoice_key(number: Any) -> str | None:
    """A note number without series and leading zeros: "Série 1 - 000123", "2024/123" and
    "123" are the same note number 123. None when there is no number."""
    raw = str(number or "").strip()
    if not raw:
        return None
    bare = re.sub(r"(?i)\b(s[eé]rie|n[ºo°]?|num(ero)?|nota)\b\.?", " ", raw)
    if re.search(r"[A-Za-z]", bare):
        # Letters in the number itself: compared as written, without leading zeros only.
        return re.sub(r"[^0-9A-Za-z]", "", bare).upper().lstrip("0") or "0"
    groups = re.findall(r"\d+", bare)
    if not groups:
        return None
    return groups[-1].lstrip("0") or "0"


def text_fingerprint(text: str | None) -> str | None:
    """Same text read from two files is the same document. Short texts prove nothing."""
    compact = re.sub(r"\s+", "", text or "").lower()
    return compact if len(compact) >= MIN_FINGERPRINT_CHARS else None


async def _same_note(
    session: AsyncSession,
    doc: Document,
    supplier: Supplier | None,
    number: Any,
    amount: Decimal,
    issue: date,
) -> Expense | None:
    """The expense of a note already received, when ``doc`` is another file of it:
    1. the same text; 2. the same supplier and note number (no series, no leading zeros);
    3. a number missing in one of the copies: same supplier, amount and issue date."""
    fingerprint = text_fingerprint(doc.text_content)
    if fingerprint is not None:
        same_text = await session.scalar(
            select(ExpenseDocument.expense_id)
            .join(Document, Document.id == ExpenseDocument.document_id)
            .where(
                ExpenseDocument.condominium_id == doc.condominium_id,
                Document.id != doc.id,
                Document.doc_type == doc.doc_type,
                func.lower(func.regexp_replace(Document.text_content, r"\s+", "", "g"))
                == fingerprint,
            )
            .limit(1)
        )
        if same_text is not None:
            return await _expense(session, same_text)
    if supplier is None:
        return None
    same_supplier = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == doc.condominium_id,
                Expense.supplier_id == supplier.id,
            )
        )
    )
    key = invoice_key(number)
    if key is not None:
        by_number = [e for e in same_supplier if invoice_key(e.invoice_number) == key]
        if by_number:
            return by_number[0]
    candidates = [
        e
        for e in same_supplier
        if (key is None or e.invoice_number is None)
        and e.issue_date == issue
        and abs(e.amount - amount) <= CENT
    ]
    if len(candidates) != 1:
        return None
    # Only an expense created from a note: a boleto-first expense keeps its own path below.
    has_note = await session.scalar(
        select(ExpenseDocument.id).where(
            ExpenseDocument.expense_id == candidates[0].id, ExpenseDocument.role == "fiscal"
        )
    )
    return candidates[0] if has_note else None


def _digits(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


async def _match_receipt(session: AsyncSession, doc: Document) -> MatchOutcome:
    """A payment receipt is the proof of an expense already known, never a new expense
    (D120): by the bar code paid, else by the final beneficiary, amount and date."""
    v = doc.extracted
    amount, paid = _money(v.get("valor")), _d(v.get("data_pagamento"))
    if amount is None or paid is None:
        return MatchOutcome(None)
    code = _digits(v.get("linha_digitavel"))
    if code:
        for field_name in ("linha_digitavel", "codigo_barras"):
            same = await session.scalar(
                select(ExpenseDocument.expense_id)
                .join(Document, Document.id == ExpenseDocument.document_id)
                .where(
                    ExpenseDocument.condominium_id == doc.condominium_id,
                    Document.id != doc.id,
                    func.regexp_replace(
                        Document.extracted[field_name].as_string(), "[^0-9]", "", "g"
                    )
                    == code,
                )
                .limit(1)
            )
            if same is not None:
                await _attach(session, await _expense(session, same), doc, RECEIPT_ROLE)
                return MatchOutcome(same)
    beneficiary = _digits(v.get("documento_beneficiario"))
    if len(beneficiary) != 14:
        return MatchOutcome(None)
    supplier = await session.scalar(select(Supplier).where(Supplier.cnpj == beneficiary))
    if supplier is None:
        return MatchOutcome(None)
    candidates = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == doc.condominium_id,
                Expense.supplier_id == supplier.id,
                Expense.amount.between(amount - CENT, amount + CENT),
                Expense.issue_date.between(paid - RECEIPT_WINDOW, paid + timedelta(days=10)),
            )
        )
    )
    if len(candidates) != 1:
        return MatchOutcome(None)  # none or several: the receipt stays as a document
    await _attach(session, candidates[0], doc, RECEIPT_ROLE)
    return MatchOutcome(candidates[0].id)


async def _match_tax_slip(session: AsyncSession, doc: Document) -> MatchOutcome:
    """A tax slip is an expense of the "tributos" category without supplier (D120), so a
    tax paid in the bank statement is not "paid without a document". The same slip sent
    again (same bar code) joins the first one."""
    v = doc.extracted
    amount, due = _money(v.get("valor")), _d(v.get("vencimento"))
    month = v.get("competencia")
    if amount is None or due is None or not month:
        return MatchOutcome(None)
    code = _digits(v.get("codigo_barras"))
    if code:
        same = await session.scalar(
            select(ExpenseDocument.expense_id)
            .join(Document, Document.id == ExpenseDocument.document_id)
            .where(
                ExpenseDocument.condominium_id == doc.condominium_id,
                Document.id != doc.id,
                Document.doc_type == DocumentType.GUIA_TRIBUTO.value,
                func.regexp_replace(
                    Document.extracted["codigo_barras"].as_string(), "[^0-9]", "", "g"
                )
                == code,
            )
            .limit(1)
        )
        if same is not None:
            await _attach(session, await _expense(session, same), doc, COPY_ROLE)
            return MatchOutcome(same)
    tax = str(v.get("tributo") or "Tributo").strip()
    expense = Expense(
        id=uuid.uuid4(),
        condominium_id=doc.condominium_id,
        supplier_id=None,
        contract_id=None,
        document_id=doc.id,
        competence=date.fromisoformat(f"{month}-01"),
        issue_date=due,
        due_date=due,
        amount=amount,
        category=TAX_CATEGORY,
        description=f"Guia de tributo: {tax} ({month[5:]}/{month[:4]})"[:500],
        invoice_number=None,
        origin="documento",
    )
    session.add(expense)
    await session.flush()
    await _attach(session, expense, doc, "fiscal")
    return MatchOutcome(expense.id, created=True)


async def _expense(session: AsyncSession, expense_id: uuid.UUID) -> Expense:
    expense = await session.get(Expense, expense_id)
    assert expense is not None
    return expense


async def _match_boleto(session: AsyncSession, doc: Document) -> MatchOutcome:
    v = doc.extracted
    amount, due = _money(v.get("valor")), _d(v.get("vencimento"))
    cnpj = v.get("cnpj_beneficiario")
    if amount is None or due is None or not cnpj:
        return MatchOutcome(None)
    # The same boleto sent again (e.g. a photo of the PDF): the digitable line identifies the
    # charge, so the copy joins the expense of the first one instead of creating another.
    line = "".join(ch for ch in str(v.get("linha_digitavel") or "") if ch.isdigit())
    if line:
        same = await session.scalar(
            select(ExpenseDocument.expense_id)
            .join(Document, Document.id == ExpenseDocument.document_id)
            .where(
                ExpenseDocument.condominium_id == doc.condominium_id,
                Document.id != doc.id,
                Document.doc_type == DocumentType.BOLETO.value,
                func.regexp_replace(
                    Document.extracted["linha_digitavel"].as_string(), "[^0-9]", "", "g"
                )
                == line,
            )
            .limit(1)
        )
        if same is not None:
            await _attach(session, await _expense(session, same), doc, "cobranca")
            return MatchOutcome(same)
    supplier = await get_or_create_supplier(session, cnpj, v.get("nome_beneficiario"))
    candidates = list(
        await session.scalars(
            select(Expense).where(
                Expense.condominium_id == doc.condominium_id,
                Expense.supplier_id == supplier.id,
                Expense.amount.between(amount - CENT, amount + CENT),
                Expense.issue_date.between(due - BOLETO_WINDOW_BEFORE, due + BOLETO_WINDOW_AFTER),
            )
        )
    )
    # Drop expenses that already have a boleto.
    with_boleto = (
        set(
            await session.scalars(
                select(ExpenseDocument.expense_id).where(
                    ExpenseDocument.expense_id.in_([c.id for c in candidates]),
                    ExpenseDocument.role == "cobranca",
                )
            )
        )
        if candidates
        else set()
    )
    open_candidates = [c for c in candidates if c.id not in with_boleto]
    if len(open_candidates) == 1:
        expense = open_candidates[0]
        expense.due_date = due
        await _attach(session, expense, doc, "cobranca")
        return MatchOutcome(expense.id)
    if len(open_candidates) > 1:
        await open_issue(
            session,
            doc.condominium_id,
            "boleto_ambiguo",
            "document",
            doc.id,
            [
                {
                    "type": "expense",
                    "id": str(c.id),
                    "label": f"{c.description} · {c.issue_date:%d/%m/%Y}",
                }
                for c in open_candidates
            ],
            "Boleto compatível com mais de uma despesa",
        )
        return MatchOutcome(None, issue="boleto_ambiguo")
    contract, _ = await choose_contract(
        session, doc.condominium_id, supplier.id, due, supplier.legal_name
    )
    expense = Expense(
        id=uuid.uuid4(),
        condominium_id=doc.condominium_id,
        supplier_id=supplier.id,
        contract_id=contract.id if contract else None,
        document_id=doc.id,
        competence=due.replace(day=1),
        issue_date=due,
        due_date=due,
        amount=amount,
        category=category_for(contract, supplier, supplier.legal_name),
        description=f"Boleto {supplier.legal_name}"[:500],
        invoice_number=None,
        origin="documento",
    )
    session.add(expense)
    await session.flush()
    await _attach(session, expense, doc, "cobranca")
    return MatchOutcome(expense.id, created=True)


async def register_contract(session: AsyncSession, doc: Document) -> Contract | None:
    """A validated contract document becomes a contract of the condominium (idempotent).

    D120: a one-off contract keeps its total value and installments (no index, no monthly
    note); a contract without the contracted party's CNPJ is registered by its legal name
    and the gap becomes an alert (and, when needed, a case to adjust the contract)."""
    v = doc.extracted
    condo = await session.get(Condominium, doc.condominium_id)
    cnpj, name = v.get("cnpj_contratada"), str(v.get("razao_social_contratada") or "").strip()
    start = _d(v.get("data_inicio"))
    nature = v.get("natureza") or ContractNature.CONTINUO.value
    monthly, total = _money(v.get("valor_mensal")), _money(v.get("valor_total"))
    value_ok = total is not None if nature == ContractNature.PONTUAL.value else monthly is not None
    if condo is None or not (cnpj or name) or start is None or not value_ok:
        return None
    if v.get("cnpj_contratante") and v["cnpj_contratante"] != condo.cnpj:
        # Back to the extraction queue: the analyst corrects the CNPJ or discards the file.
        doc.needs_review = True
        doc.extraction_status = ExtractionStatus.NEEDS_REVIEW.value
        doc.review_reasons = [
            "Contrato em nome de outro CNPJ: confira se o documento é deste condomínio."
        ]
        return None
    supplier = await get_or_create_supplier(session, cnpj, name) if cnpj else None
    if is_amendment(doc) and supplier is not None:
        await register_amendment(session, doc, supplier.id, start, monthly)
        return None
    same_party = (
        Contract.supplier_id == supplier.id
        if supplier is not None
        else (Contract.supplier_id.is_(None) & (Contract.supplier_name == name[:200]))
    )
    existing = await session.scalar(
        select(Contract).where(
            Contract.condominium_id == doc.condominium_id,
            same_party,
            Contract.start_date == start,
        )
    )
    if existing is not None:
        existing.source_document_id = existing.source_document_id or doc.id
        apply_clauses(existing, doc.text_content)
        return existing
    one_off = nature == ContractNature.PONTUAL.value
    index = str(v.get("indice_reajuste") or AdjustmentIndex.NENHUM.value)
    if index not in {i.value for i in AdjustmentIndex} or (one_off and index == "OUTRO"):
        index = AdjustmentIndex.NENHUM.value if one_off else AdjustmentIndex.OUTRO.value
    base = v.get("mes_base_reajuste")
    base_month = int(base) if base and 1 <= int(base) <= 12 else None
    if base_month is None and index not in (AdjustmentIndex.FIXO, AdjustmentIndex.NENHUM):
        base_month = start.month  # D68: the adjustment happens in the month the term started
    installments = v.get("parcelas")
    contract = Contract(
        id=uuid.uuid4(),
        condominium_id=doc.condominium_id,
        supplier_id=supplier.id if supplier is not None else None,
        supplier_name=None if supplier is not None else name[:200],
        nature=nature,
        object=str(v.get("objeto") or "Contrato")[:300],
        scope_items=[str(x) for x in (v.get("itens_escopo") or [])],
        monthly_value=None if one_off else monthly,
        total_value=total,
        installments=int(installments) if installments and int(installments) >= 1 else None,
        adjustment_index=index,
        adjustment_index_other=(
            str(v.get("indice_reajuste_outro") or "")[:120] or None
            if index == AdjustmentIndex.OUTRO
            else None
        ),
        adjustment_base_month=None if one_off else base_month,
        # A one-off contract expects no note every month (D120): on demand.
        billing_frequency_months=0 if one_off else billing_frequency(str(v.get("objeto") or "")),
        start_date=start,
        end_date=_d(v.get("data_fim")),
        source_document_id=doc.id,
    )
    apply_clauses(contract, doc.text_content)  # notice period, renewal, penalty (CB-060)
    session.add(contract)
    await session.flush()
    if supplier is None:
        from app.data_issues.contracts import open_adjust_case  # B2 (D120)

        await open_adjust_case(session, condo, contract)
    elif supplier.enriched_at is None:
        await enqueue(
            session,
            "supplier.enrich",
            {"cnpj": supplier.cnpj},
            dedupe_key=f"supplier:{supplier.cnpj}:enrich",
        )
    return contract


async def fill_contract_supplier(
    session: AsyncSession, condominium_id: uuid.UUID, supplier: Supplier
) -> list[Contract]:
    """The first note of a supplier fills the CNPJ of its contracts registered by legal name
    only (D120, B2): same legal name, ignoring accents and the legal suffix."""
    from app.extraction.evidence import same_legal_name

    filled = []
    for contract in await session.scalars(
        select(Contract).where(
            Contract.condominium_id == condominium_id, Contract.supplier_id.is_(None)
        )
    ):
        if same_legal_name(contract.supplier_name, supplier.legal_name):
            contract.supplier_id = supplier.id
            filled.append(contract)
    return filled


AMENDMENT = re.compile(r"\b(termo\s+)?aditivo\b", re.IGNORECASE)


def billing_frequency(text: str) -> int:
    """Expected invoice every N months, from the contract object (monthly by default, D70)."""
    t = text.lower()
    for word, months in (("bimestral", 2), ("trimestral", 3), ("semestral", 6), ("anual", 12)):
        if word in t:
            return months
    return 1


def is_amendment(doc: Document) -> bool:
    """A contract document that amends another one (termo aditivo): told by its title."""
    head = f"{doc.extracted.get('objeto') or ''} {(doc.text_content or '')[:600]}"
    return bool(AMENDMENT.search(head))


def _review(doc: Document, reason: str) -> None:
    doc.needs_review = True
    doc.extraction_status = ExtractionStatus.NEEDS_REVIEW.value
    doc.review_reasons = [reason]


async def register_amendment(
    session: AsyncSession,
    doc: Document,
    supplier_id: uuid.UUID,
    effective: date,
    value: Decimal | None,
) -> ContractAmendment | None:
    """Link an amendment to the supplier's contract and apply its end date and scope (D66).
    Without a single base contract, back to the queue: never chosen at random."""
    existing = await session.scalar(
        select(ContractAmendment).where(ContractAmendment.document_id == doc.id)
    )
    if existing is not None:
        return existing
    v = doc.extracted
    contracts = list(
        await session.scalars(
            select(Contract).where(
                Contract.condominium_id == doc.condominium_id,
                Contract.supplier_id == supplier_id,
                Contract.start_date <= effective,
            )
        )
    )
    if len(contracts) > 1:
        chosen, _ = await choose_contract(
            session, doc.condominium_id, supplier_id, effective, str(v.get("objeto") or "")
        )
        contracts = [chosen] if chosen is not None else contracts
    if not contracts:
        _review(
            doc,
            "Termo aditivo sem o contrato original cadastrado: envie o contrato primeiro e "
            "salve este documento de novo.",
        )
        return None
    if len(contracts) > 1:
        _review(
            doc,
            "Termo aditivo com mais de um contrato possível do mesmo fornecedor: confira o "
            "objeto e a data de início.",
        )
        return None
    contract = contracts[0]
    scope = [str(x) for x in (v.get("itens_escopo") or [])]
    amendment = ContractAmendment(
        id=uuid.uuid4(),
        condominium_id=doc.condominium_id,
        contract_id=contract.id,
        document_id=doc.id,
        effective_date=effective,
        monthly_value=value,
        end_date=_d(v.get("data_fim")),
        scope_items=scope,
        description=str(v.get("objeto") or "Termo aditivo")[:500],
    )
    session.add(amendment)
    if amendment.end_date is not None:
        contract.end_date = amendment.end_date  # extension (or earlier end) from the amendment
    new_scope = [x for x in scope if x not in contract.scope_items]
    if new_scope:
        contract.scope_items = [*contract.scope_items, *new_scope]
    await session.flush()
    return amendment


async def open_issue(
    session: AsyncSession,
    condominium_id: uuid.UUID,
    kind: str,
    subject_type: str,
    subject_id: uuid.UUID,
    candidates: list[dict[str, Any]],
    description: str,
) -> None:
    existing = await session.scalar(
        select(MatchIssue).where(
            MatchIssue.condominium_id == condominium_id,
            MatchIssue.kind == kind,
            MatchIssue.subject_id == subject_id,
        )
    )
    if existing is None:
        session.add(
            MatchIssue(
                condominium_id=condominium_id,
                kind=kind,
                subject_type=subject_type,
                subject_id=subject_id,
                candidates=candidates,
                description=description,
                status="aberto",
                resolution={},
            )
        )
    elif existing.status == "aberto":
        existing.candidates = candidates


async def match_document_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    doc = await session.get(Document, uuid.UUID(payload["document_id"]), with_for_update=True)
    if doc is None:
        return
    outcome = await match_document(session, doc)
    if outcome.expense_id is None:
        return
    expense = await session.get(Expense, outcome.expense_id)
    await enqueue(
        session,
        "bank.match",
        {"condominium_id": str(doc.condominium_id)},
        condominium_id=doc.condominium_id,
        dedupe_key=f"bank-match:{doc.condominium_id}:{outcome.expense_id}:{doc.id}",
    )
    if expense is not None:
        await enqueue_rules(session, doc.condominium_id, expense.competence)


async def enqueue_rules(session: AsyncSession, condominium_id: uuid.UUID, competence: date) -> None:
    """Re-evaluate a month a little later, after bank matching had its turn.
    The engine is idempotent, so a repeated evaluation is harmless."""
    await enqueue(
        session,
        "rules.evaluate",
        {"condominium_id": str(condominium_id), "competence": f"{competence:%Y-%m}"},
        condominium_id=condominium_id,
        run_after=utcnow() + timedelta(seconds=20),
    )
