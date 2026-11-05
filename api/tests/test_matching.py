"""Matching: document → expense → contract, boleto → expense, expense ↔ bank debit."""

import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.br import generate_cnpj
from app.db.models import (
    BankTransaction,
    Condominium,
    Contract,
    Document,
    Expense,
    ExpenseDocument,
    Job,
    MatchIssue,
    Supplier,
)
from app.db.session import sessionmaker_for
from app.matching.bank import match_bank
from app.matching.documents import match_document


def _amount() -> Decimal:
    """A unique value per test, so tests never match each other's rows."""
    return Decimal(random.randint(100_000, 999_999)) / 100


async def _mirante(s: AsyncSession) -> tuple[Condominium, Supplier, Contract]:
    condo = await s.scalar(select(Condominium).where(Condominium.slug == "mirante-do-vale"))
    assert condo is not None
    supplier = await s.scalar(select(Supplier).where(Supplier.legal_name.like("Fixa Bem%")))
    assert supplier is not None
    contract = await s.scalar(
        select(Contract).where(
            Contract.condominium_id == condo.id, Contract.supplier_id == supplier.id
        )
    )
    assert contract is not None
    return condo, supplier, contract


def _doc(condo: Condominium, doc_type: str, extracted: dict[str, Any], **kw: Any) -> Document:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": condo.id,
        "doc_type": doc_type,
        "storage_key": f"cond/{condo.id}/x",
        "sha256": uuid.uuid4().hex * 2,
        "original_filename": f"{doc_type}.pdf",
        "mime_type": "application/pdf",
        "origin": "upload",
        "extraction_status": "done",
        "extracted": extracted,
        "field_confidence": {},
        "needs_review": False,
        "review_reasons": [],
    }
    base.update(kw)
    return Document(**base)


def _nfse(
    condo: Condominium, supplier: Supplier, amount: Decimal, number: str, text: str
) -> Document:
    return _doc(
        condo,
        "nfse",
        {
            "numero": number,
            "data_emissao": "2026-11-03",
            "competencia": "2026-11",
            "cnpj_prestador": supplier.cnpj,
            "razao_social_prestador": supplier.legal_name,
            "cnpj_tomador": condo.cnpj,
            "valor_servicos": str(amount),
            "valor_liquido": str(amount),
            "discriminacao": text,
        },
    )


async def test_note_boleto_and_bank_debit(worker_engine: AsyncEngine) -> None:
    amount = _amount()
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        condo, supplier, contract = await _mirante(s)
        note = _nfse(
            condo,
            supplier,
            amount,
            f"N{uuid.uuid4().hex[:6]}",
            "Manutenção elétrica predial de novembro",
        )
        s.add(note)
        await s.flush()
        first = await match_document(s, note)
        again = await match_document(s, note)  # idempotent
        assert first.created and again.expense_id == first.expense_id
        expense = await s.get(Expense, first.expense_id)
        assert expense is not None
        assert expense.contract_id == contract.id and expense.category == "manutencao"
        assert expense.origin == "documento" and expense.competence == date(2026, 11, 1)

        boleto = _doc(
            condo,
            "boleto",
            {
                "valor": str(amount),
                "vencimento": "2026-11-20",
                "cnpj_beneficiario": supplier.cnpj,
                "nome_beneficiario": supplier.legal_name,
            },
        )
        s.add(boleto)
        await s.flush()
        assert (await match_document(s, boleto)).expense_id == expense.id
        assert expense.due_date == date(2026, 11, 20)
        roles = set(
            await s.scalars(
                select(ExpenseDocument.role).where(ExpenseDocument.expense_id == expense.id)
            )
        )
        assert roles == {"fiscal", "cobranca"}

        debit = BankTransaction(
            condominium_id=condo.id,
            posted_at=date(2026, 11, 21),
            amount=-amount,
            payee_name=None,
            payee_document=supplier.cnpj,
            description="PAG BOLETO FIXA BEM",
            origin="ofx",
            external_id=f"t-{uuid.uuid4()}",
        )
        s.add(debit)
        await s.flush()
        assert expense in await match_bank(s, condo.id)
        assert debit.expense_id == expense.id


async def test_ambiguous_debit_goes_to_queue(worker_engine: AsyncEngine) -> None:
    amount = _amount()
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, supplier, _ = await _mirante(s)
        notes = [
            _nfse(condo, supplier, amount, f"A{i}{uuid.uuid4().hex[:5]}", "Reparo")
            for i in range(2)
        ]
        s.add_all(notes)
        await s.flush()
        for n in notes:
            await match_document(s, n)
        debit = BankTransaction(
            condominium_id=condo.id,
            posted_at=date(2026, 11, 5),
            amount=-amount,
            payee_name=None,
            payee_document=supplier.cnpj,
            description="PAGAMENTO",
            origin="ofx",
            external_id=f"t-{uuid.uuid4()}",
        )
        s.add(debit)
        await s.flush()
        await match_bank(s, condo.id)
        assert debit.expense_id is None  # never chosen at random
        issue = await s.scalar(select(MatchIssue).where(MatchIssue.subject_id == debit.id))
        assert (
            issue is not None and issue.kind == "pagamento_ambiguo" and len(issue.candidates) == 2
        )


async def test_pending_review_document_creates_nothing(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, supplier, _ = await _mirante(s)
        doc = _nfse(condo, supplier, _amount(), "P1", "Serviço")
        doc.needs_review, doc.extraction_status = True, "needs_review"
        s.add(doc)
        await s.flush()
        assert (await match_document(s, doc)).expense_id is None


async def test_new_supplier_is_created_and_queued_for_enrichment(
    worker_engine: AsyncEngine,
) -> None:
    cnpj = generate_cnpj(random.Random())
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, _, _ = await _mirante(s)
        doc = _doc(
            condo,
            "recibo",
            {
                "data": "2026-11-02",
                "valor": "350.00",
                "nome_recebedor": "Empresa Nova Fictícia",
                "documento_recebedor": cnpj,
                "descricao": "Conserto do portão",
            },
        )
        s.add(doc)
        await s.flush()
        out = await match_document(s, doc)
        supplier = await s.scalar(select(Supplier).where(Supplier.cnpj == cnpj))
        assert out.created and supplier is not None and supplier.enrichment_source == "documento"
        job = await s.scalar(select(Job).where(Job.dedupe_key == f"supplier:{cnpj}:enrich"))
        assert job is not None


async def test_analyst_resolves_ambiguous_debit(
    client: Any, mailer: Any, worker_engine: AsyncEngine
) -> None:
    from tests.helpers import ANALISTA, login

    amount = _amount()
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, supplier, _ = await _mirante(s)
        notes = [
            _nfse(condo, supplier, amount, f"R{i}{uuid.uuid4().hex[:5]}", "Reparo")
            for i in range(2)
        ]
        s.add_all(notes)
        await s.flush()
        expense_ids = [(await match_document(s, n)).expense_id for n in notes]
        debit = BankTransaction(
            condominium_id=condo.id,
            posted_at=date(2026, 11, 5),
            amount=-amount,
            payee_name=None,
            payee_document=supplier.cnpj,
            description="PAGAMENTO",
            origin="ofx",
            external_id=f"t-{uuid.uuid4()}",
        )
        s.add(debit)
        await s.flush()
        await match_bank(s, condo.id)
        condo_id, debit_id = condo.id, debit.id

    await login(client, mailer, ANALISTA)
    queue = (await client.get("/queue")).json()
    item = next(
        i
        for i in queue
        if i["kind"] == "casamento" and "Débito" in i["title"] and str(amount) in i["title"]
    )
    issue = (await client.get(f"/condominiums/{condo_id}/match-issues/{item['id']}")).json()
    assert {c["id"] for c in issue["candidates"]} == {str(e) for e in expense_ids}
    url = f"/condominiums/{condo_id}/match-issues/{item['id']}/resolve"
    assert (await client.post(url, json={"candidate_id": str(uuid.uuid4())})).status_code == 422
    assert (await client.post(url, json={"candidate_id": str(expense_ids[1])})).status_code == 200
    assert (await client.post(url, json={"candidate_id": None})).status_code == 409
    async with sessionmaker_for(worker_engine)() as s:
        trn = await s.get(BankTransaction, debit_id)
    assert trn is not None and trn.expense_id == expense_ids[1]


async def test_boleto_without_note_creates_expense_and_ambiguous_boleto(
    worker_engine: AsyncEngine,
) -> None:
    amount = _amount()
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, supplier, contract = await _mirante(s)
        boleto = _doc(
            condo,
            "boleto",
            {
                "valor": str(amount),
                "vencimento": "2026-11-25",
                "cnpj_beneficiario": supplier.cnpj,
                "nome_beneficiario": supplier.legal_name,
            },
        )
        s.add(boleto)
        await s.flush()
        out = await match_document(s, boleto)
        assert out.created
        expense = await s.get(Expense, out.expense_id)
        assert expense is not None and expense.due_date == date(2026, 11, 25)
        assert expense.contract_id == contract.id and expense.invoice_number is None

        # The note arriving later attaches to the expense created by the boleto.
        note = _nfse(condo, supplier, amount, f"L{uuid.uuid4().hex[:5]}", "Manutenção predial")
        s.add(note)
        await s.flush()
        assert (await match_document(s, note)).expense_id == expense.id
        assert expense.invoice_number == note.extracted["numero"]

        # Two open expenses compatible with one boleto: exception queue.
        amount2 = _amount()
        for i in range(2):
            n = _nfse(condo, supplier, amount2, f"B{i}{uuid.uuid4().hex[:5]}", "Reparo")
            s.add(n)
            await s.flush()
            await match_document(s, n)
        b2 = _doc(
            condo,
            "boleto",
            {
                "valor": str(amount2),
                "vencimento": "2026-11-12",
                "cnpj_beneficiario": supplier.cnpj,
            },
        )
        s.add(b2)
        await s.flush()
        assert (await match_document(s, b2)).issue == "boleto_ambiguo"
        issue = await s.scalar(select(MatchIssue).where(MatchIssue.subject_id == b2.id))
        assert issue is not None and len(issue.candidates) == 2


async def test_contract_choice_by_validity_and_ambiguity(worker_engine: AsyncEngine) -> None:
    from app.matching.documents import choose_contract

    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo, _, _ = await _mirante(s)
        supplier = Supplier(
            cnpj=generate_cnpj(random.Random()),
            legal_name="Dois Contratos Ltda",
            cnae_secondary=[],
            partners=[],
        )
        s.add(supplier)
        await s.flush()
        base: dict[str, Any] = {
            "condominium_id": condo.id,
            "supplier_id": supplier.id,
            "scope_items": [],
            "monthly_value": Decimal("100"),
            "adjustment_index": "FIXO",
            "adjustment_base_month": None,
        }
        old = Contract(
            object="Limpeza antiga",
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            **base,
        )
        a = Contract(object="Limpeza de vidros", start_date=date(2025, 1, 1), end_date=None, **base)
        b = Contract(object="Jardinagem e poda", start_date=date(2025, 1, 1), end_date=None, **base)
        s.add_all([old, a, b])
        await s.flush()
        chosen, amb = await choose_contract(
            s, condo.id, supplier.id, date(2026, 10, 1), "poda das árvores"
        )
        assert chosen is not None and chosen.id == b.id and amb == []
        chosen, amb = await choose_contract(
            s, condo.id, supplier.id, date(2026, 10, 1), "serviço geral"
        )
        assert chosen is None and {c.id for c in amb} == {a.id, b.id}
        chosen, _ = await choose_contract(s, condo.id, supplier.id, date(2024, 6, 1), "qualquer")
        assert chosen is not None and chosen.id == old.id


def test_categories_and_payee_rules() -> None:
    from app.matching.bank import payee_compatible
    from app.matching.categories import category_for, category_label, cnae_compatible

    s = Supplier(
        cnpj="45723174000110",
        legal_name="Fixa Bem Manutenção Predial Ltda",
        cnae_main={"code": "4321-5/00", "description": "x"},
        cnae_secondary=[],
        partners=[],
    )
    assert category_for(None, None, "Troca de lâmpadas e reparo elétrico") == "manutencao"
    assert category_for(None, s, "Serviço diverso") == "manutencao"  # from the CNAE
    assert category_for(None, None, "Serviço diverso") == "outros"
    assert cnae_compatible("outros", ["4321-5/00"]) is None
    assert category_label("agua") == "água e esgoto"
    t = BankTransaction(
        posted_at=date(2026, 10, 1),
        amount=Decimal("-1"),
        description="x",
        origin="ofx",
        external_id="x",
        payee_name="FIXA BEM MANUTENCAO",
        payee_document=None,
    )
    assert payee_compatible(t, s)
    t.payee_name = "OUTRA EMPRESA QUALQUER"
    assert not payee_compatible(t, s)
    t.payee_name = None
    assert payee_compatible(t, s)  # statement without payee: value and date decide
    t.payee_document = "11222333000181"
    assert not payee_compatible(t, s)
