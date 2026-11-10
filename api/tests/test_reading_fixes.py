"""D120: reading fixes from the pilot tests, with fictitious documents that reproduce the
reported cases — the same note in two files (A4), signature after the start (A5/B1), the
management company as contracting party and a wrong condominium CNPJ (B1), a contract
without the contracted party's CNPJ (B2), a one-off contract (B3), payment receipt and tax
slip (B4) and the debtor list (B5)."""

import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.br import format_cnpj, generate_cnpj
from app.data_issues.contracts import detect_contracts, essential_service
from app.db.enums import DataIssueKind, DataIssueStatus, DocumentType
from app.db.models import (
    AppUser,
    CaseLink,
    CaseRecord,
    Condominium,
    Contract,
    DataIssue,
    Document,
    Expense,
    ExpenseDocument,
    ExtractionCorrection,
    ManagementCompany,
    Supplier,
)
from app.db.session import sessionmaker_for
from app.extraction.confidence import assess
from app.extraction.heuristics import classify_text
from app.extraction.pipeline import analyze
from app.matching.documents import invoice_key, match_document
from corpus.generate import Pdf

REF = date(2026, 11, 10)


def _amount() -> Decimal:
    return Decimal(random.randint(100_000, 999_999)) / 100


async def _condo(s: AsyncSession) -> Condominium:
    condo = await s.scalar(select(Condominium).where(Condominium.slug == "mirante-do-vale"))
    assert condo is not None
    return condo


def _doc(condo: Condominium, doc_type: str, extracted: dict[str, Any], **kw: Any) -> Document:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": condo.id,
        "doc_type": doc_type,
        "storage_key": f"cond/{condo.id}/x",
        "sha256": uuid.uuid4().hex * 2,
        "original_filename": f"{doc_type}-{uuid.uuid4().hex[:4]}.pdf",
        "mime_type": "application/pdf",
        "origin": "upload",
        "extraction_status": "done",
        "extracted": extracted,
        "field_confidence": {},
        "field_provenance": {},
        "needs_review": False,
        "review_reasons": [],
    }
    base.update(kw)
    return Document(**base)


async def _supplier(s: AsyncSession, name: str) -> Supplier:
    supplier = Supplier(
        cnpj=generate_cnpj(random.Random(uuid.uuid4().hex)),
        legal_name=name,
        cnae_secondary=[],
        partners=[],
        enrichment_source="seed",
    )
    s.add(supplier)
    await s.flush()
    return supplier


def _note(
    condo: Condominium, sup: Supplier, amount: Decimal, number: str | None, **kw: Any
) -> Document:
    return _doc(
        condo,
        "nfse",
        {
            "numero": number,
            "data_emissao": "2026-11-03",
            "competencia": "2026-11",
            "cnpj_prestador": sup.cnpj,
            "razao_social_prestador": sup.legal_name,
            "cnpj_tomador": condo.cnpj,
            "valor_servicos": str(amount),
            "valor_liquido": str(amount),
            "discriminacao": "Serviço de jardinagem",
        },
        **kw,
    )


async def _roles(s: AsyncSession, expense_id: uuid.UUID | None) -> list[str]:
    return sorted(
        await s.scalars(
            select(ExpenseDocument.role).where(ExpenseDocument.expense_id == expense_id)
        )
    )


# --------------------------------------------------------------------------- A4


def test_invoice_key() -> None:
    assert invoice_key("000123") == invoice_key("Série 1 - 123") == invoice_key("2024/0123")
    assert invoice_key("123") != invoice_key("124")
    assert invoice_key("A-12") != invoice_key("12")  # letters are part of the number
    assert invoice_key(None) is None


async def test_same_note_in_another_file_is_a_copy(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        sup = await _supplier(s, "Verde Fictício Jardins Ltda")
        amount = _amount()
        first = _note(condo, sup, amount, "000123")
        s.add(first)
        await s.flush()
        out = await match_document(s, first)
        assert out.created
        # Downloaded again: zeros and series differ.
        again = _note(condo, sup, amount, "Série 1 - 123")
        # And a copy where the number was not read: same supplier, amount and issue date.
        no_number = _note(condo, sup, amount, None)
        for copy in (again, no_number):
            s.add(copy)
            await s.flush()
            assert (await match_document(s, copy)).expense_id == out.expense_id
        assert await _roles(s, out.expense_id) == ["copia", "copia", "fiscal"]
        count = len(list(await s.scalars(select(Expense).where(Expense.supplier_id == sup.id))))
        assert count == 1  # no second expense, so no duplicate alert (R01)

        # Negative: another note of the same supplier and amount on another date.
        other = _note(condo, sup, amount, None)
        other.extracted = {**other.extracted, "data_emissao": "2026-11-20"}
        s.add(other)
        await s.flush()
        assert (await match_document(s, other)).created


async def test_same_text_is_the_same_note(worker_engine: AsyncEngine) -> None:
    text = "NFS-e fictícia. " + "Prestação de serviço de jardinagem nas áreas comuns. " * 6
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        sup = await _supplier(s, "Folha Fictícia Paisagismo Ltda")
        amount = _amount()
        first = _note(condo, sup, amount, "77", text_content=text)
        s.add(first)
        await s.flush()
        out = await match_document(s, first)
        # The second reading took another number and amount, but the text is the same.
        second = _note(condo, sup, amount + 1, "78", text_content=text.replace(" ", "  "))
        s.add(second)
        await s.flush()
        assert (await match_document(s, second)).expense_id == out.expense_id


# --------------------------------------------------------------------------- A5, B3


def _contract_raw(condo_cnpj: str, **over: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "cnpj_contratada": generate_cnpj(random.Random("rf-sup")),
        "razao_social_contratada": "Reforma Fictícia Ltda",
        "cnpj_contratante": condo_cnpj,
        "objeto": "Reforma da fachada",
        "itens_escopo": ["pintura"],
        "data_inicio": "2026-02-01",
    }
    raw.update(over)
    return raw


def test_one_off_contract_needs_total_not_index() -> None:
    condo = generate_cnpj(random.Random("rf-condo"))
    raw = _contract_raw(condo, natureza="pontual", valor_total="30000.00", parcelas="3")
    a = assess(
        DocumentType.CONTRATO, raw, {k: 0.95 for k in raw}, condominium_cnpj=condo, today=REF
    )
    assert a.reasons == [] and a.values["natureza"] == "pontual"
    assert a.values["indice_reajuste"] is None and a.values["mes_base_reajuste"] is None
    # Negative: a one-off contract without the total goes to review.
    raw.pop("valor_total")
    a = assess(
        DocumentType.CONTRATO, raw, {k: 0.95 for k in raw}, condominium_cnpj=condo, today=REF
    )
    assert any("Valor total" in r for r in a.reasons)
    # A continuous contract still needs the monthly value and the index.
    raw = _contract_raw(condo)
    a = assess(
        DocumentType.CONTRATO, raw, {k: 0.95 for k in raw}, condominium_cnpj=condo, today=REF
    )
    assert any("Valor mensal" in r for r in a.reasons)
    assert a.values["natureza"] == "continuo"  # presumed: no total value


def test_signature_after_start_is_an_observation() -> None:
    condo = generate_cnpj(random.Random("rf-condo"))
    raw = _contract_raw(
        condo, valor_mensal="900.00", indice_reajuste="IPCA", data_assinatura="2026-05-09"
    )
    a = assess(
        DocumentType.CONTRATO, raw, {k: 0.95 for k in raw}, condominium_cnpj=condo, today=REF
    )
    assert a.reasons == []  # it does not block
    assert a.observations["data_assinatura"].startswith("Assinado em 09/05/2026, depois")
    raw["data_assinatura"] = "2026-01-20"
    a = assess(
        DocumentType.CONTRATO, raw, {k: 0.95 for k in raw}, condominium_cnpj=condo, today=REF
    )
    assert a.observations == {}


def test_contract_without_cnpj_is_not_blocked_only_when_the_text_shows_none() -> None:
    condo = generate_cnpj(random.Random("rf-condo"))
    raw = _contract_raw(condo, valor_mensal="400.00", indice_reajuste="IPCA")
    raw.pop("cnpj_contratada")
    conf = {k: 0.95 for k in raw}
    a = assess(DocumentType.CONTRATO, raw, conf, condominium_cnpj=condo, today=REF)
    assert any("CNPJ da contratada" in r for r in a.reasons)
    a = assess(
        DocumentType.CONTRATO,
        raw,
        conf,
        condominium_cnpj=condo,
        today=REF,
        counterparty_absent=True,
    )
    assert a.reasons == []


async def test_one_off_contract_is_registered_without_monthly_note(
    worker_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        sup = await _supplier(s, "Pintura Fictícia Ltda")
        doc = _doc(
            condo,
            "contrato",
            _contract_raw(
                condo.cnpj,
                cnpj_contratada=sup.cnpj,
                natureza="pontual",
                valor_total="30000.00",
                parcelas=3,
            ),
        )
        s.add(doc)
        await s.flush()
        await match_document(s, doc)
        c = await s.scalar(select(Contract).where(Contract.source_document_id == doc.id))
        assert c is not None and c.nature == "pontual"
        assert c.monthly_value is None and c.total_value == Decimal("30000.00")
        assert c.installments == 3 and c.billing_frequency_months == 0  # no "NF não recebida"
        assert c.adjustment_index == "NENHUM" and c.adjustment_base_month is None


# --------------------------------------------------------------------------- B1, B2


async def _contract_doc(
    s: AsyncSession, condo: Condominium, **over: Any
) -> tuple[Document, Contract]:
    raw = _contract_raw(condo.cnpj, valor_mensal="400.00", indice_reajuste="IPCA", **over)
    if raw.get("cnpj_contratada") is None:
        raw.pop("cnpj_contratada")
    doc = _doc(condo, "contrato", raw)
    s.add(doc)
    await s.flush()
    await match_document(s, doc)
    c = await s.scalar(select(Contract).where(Contract.source_document_id == doc.id))
    assert c is not None
    return doc, c


async def _alerts(s: AsyncSession, contract: Contract) -> dict[str, str]:
    return {
        i.kind: i.status
        for i in await s.scalars(select(DataIssue).where(DataIssue.subject_id == contract.id))
    }


async def test_contract_without_cnpj_small_and_not_essential(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        name = f"Jardins Sem CNPJ {uuid.uuid4().hex[:6]} Ltda"
        _, c = await _contract_doc(
            s, condo, cnpj_contratada=None, razao_social_contratada=name, objeto="Jardinagem"
        )
        assert c.supplier_id is None and c.supplier_name == name
        assert await _alerts(s, c) == {DataIssueKind.CONTRATO_SEM_CNPJ.value: "aberto"}
        linked = await s.scalar(select(CaseLink.id).where(CaseLink.target_id == c.id))
        assert linked is None  # within the alçada and not essential: observation only

        # The first note of that supplier fills the CNPJ; the alert is superseded.
        sup = await _supplier(s, name.upper().replace(" LTDA", " LTDA."))
        note = _note(condo, sup, _amount(), "5501")
        s.add(note)
        await s.flush()
        await match_document(s, note)
        assert c.supplier_id == sup.id
        await detect_contracts(s, condo.id)
        assert await _alerts(s, c) == {
            DataIssueKind.CONTRATO_SEM_CNPJ.value: DataIssueStatus.DESCARTADO.value
        }


async def test_contract_without_cnpj_essential_opens_a_case(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        _, c = await _contract_doc(
            s,
            condo,
            cnpj_contratada=None,
            razao_social_contratada=f"Limpeza Sem CNPJ {uuid.uuid4().hex[:6]}",
            objeto="Limpeza das áreas comuns",
        )
        assert essential_service(c) == "limpeza"
        case = await s.scalar(
            select(CaseRecord)
            .join(CaseLink, CaseLink.case_id == CaseRecord.id)
            .where(CaseLink.target_id == c.id)
        )
        assert case is not None and case.title.startswith("Ajustar contrato")
        sindico = await s.scalar(
            select(AppUser.id).where(AppUser.email == "carla.sindica@mirante.example.com")
        )
        assert case.owner_user_id == sindico and case.next_action_due_at is not None
        # Matching again never duplicates the case.
        from app.data_issues.contracts import open_adjust_case

        assert await open_adjust_case(s, condo, c) is None


async def test_signed_after_start_alert(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        sup = await _supplier(s, "Assina Depois Ltda")
        _, late = await _contract_doc(
            s, condo, cnpj_contratada=sup.cnpj, data_assinatura="2026-05-09"
        )
        assert DataIssueKind.CONTRATO_ASSINADO_DEPOIS.value in await _alerts(s, late)
        sup2 = await _supplier(s, "Assina Antes Ltda")
        _, early = await _contract_doc(
            s, condo, cnpj_contratada=sup2.cnpj, data_assinatura="2026-01-20"
        )
        assert await _alerts(s, early) == {}


async def test_contracting_party_alerts_keep_what_was_written(worker_engine: AsyncEngine) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        assert condo.management_company_id is not None
        manager = await s.get(ManagementCompany, condo.management_company_id)
        assert manager is not None
        user = await s.scalar(select(AppUser.id).limit(1))
        assert user is not None
        wrong = generate_cnpj(random.Random(uuid.uuid4().hex))
        kinds = {}
        for written in (manager.cnpj, wrong):
            sup = await _supplier(s, f"Parte {uuid.uuid4().hex[:6]} Ltda")
            doc, c = await _contract_doc(s, condo, cnpj_contratada=sup.cnpj)
            # A person corrected the contracting party's CNPJ to let the contract in.
            s.add(
                ExtractionCorrection(
                    condominium_id=condo.id,
                    document_id=doc.id,
                    user_id=user,
                    doc_type="contrato",
                    field_name="cnpj_contratante",
                    extracted_value=written,
                    corrected_value=condo.cnpj,
                )
            )
            await s.flush()
            await detect_contracts(s, condo.id)
            issue = await s.scalar(
                select(DataIssue).where(
                    DataIssue.subject_id == c.id, DataIssue.kind.like("contrato_c%")
                )
            )
            assert issue is not None and format_cnpj(written) in issue.detail
            assert issue.capabilities == []  # an alert never blocks
            kinds[written] = issue.kind
        assert kinds[manager.cnpj] == DataIssueKind.CONTRATO_CONTRATANTE.value
        assert kinds[wrong] == DataIssueKind.CONTRATO_CNPJ_CONDOMINIO.value


# --------------------------------------------------------------------------- B4, B5

LINE = "34191790010104351004791020150008291070026000"


def test_new_types_are_classified() -> None:
    receipt = (
        "COMPROVANTE DE PAGAMENTO DE BOLETO\nBeneficiário: Banco Fictício S.A.\n"
        "Beneficiário final: Jardins Fictícios Ltda\nAutenticação: A1B2C3D4"
    )
    assert classify_text(receipt, REF).doc_type == DocumentType.COMPROVANTE
    assert classify_text("DARF - Documento de Arrecadação de Receitas Federais", REF).doc_type == (
        DocumentType.GUIA_TRIBUTO
    )
    assert classify_text("RELATÓRIO DE GESTÃO - outubro", REF).doc_type == (
        DocumentType.RELATORIO_ADM
    )
    assert classify_text("INFORME DE RENDIMENTOS 2025", REF).doc_type == (
        DocumentType.EXTRATO_RENDIMENTO
    )


def test_debtor_list_is_refused_but_not_a_balance_sheet() -> None:
    rows = "\n".join(f"Apto {n} - R$ 850,00" for n in range(101, 108))
    c = classify_text("RELAÇÃO DE DEVEDORES - OUTUBRO\n" + rows, REF)
    assert c.refused and "moradores" in c.refused
    c = classify_text("Inadimplência do mês\n" + rows, REF)
    assert c.refused
    balance = "BALANCETE MENSAL\nInadimplência: R$ 4.300,00\nUnidade administrativa: sede"
    assert classify_text(balance, REF).refused is None


async def test_debtor_list_reading_refuses() -> None:
    pdf = Pdf()
    pdf.text("RELAÇÃO DE DEVEDORES - OUTUBRO DE 2026")
    for n in range(101, 108):
        pdf.text(f"Apto {n} - Fulano Fictício - R$ 850,00")
    analysis = await analyze(
        None,
        data=pdf.bytes(),
        mime="application/pdf",
        filename="devedores.pdf",
        condominium_id=None,
        condominium_cnpj="00000000000000",
        today=REF,
    )
    assert analysis.refused and analysis.text is None and analysis.values == {}


async def test_receipt_proves_the_expense_and_tax_slip_is_an_expense(
    worker_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        condo = await _condo(s)
        sup = await _supplier(s, "Recebe Fictício Ltda")
        amount = _amount()
        boleto = _doc(
            condo,
            "boleto",
            {
                "valor": str(amount),
                "vencimento": "2026-11-25",
                "cnpj_beneficiario": sup.cnpj,
                "nome_beneficiario": sup.legal_name,
                "linha_digitavel": LINE,
            },
        )
        s.add(boleto)
        await s.flush()
        out = await match_document(s, boleto)
        receipt = _doc(
            condo,
            "comprovante",
            {
                "data_pagamento": "2026-11-24",
                "valor": str(amount),
                "nome_beneficiario": sup.legal_name,
                "linha_digitavel": LINE,
            },
        )
        s.add(receipt)
        await s.flush()
        assert (await match_document(s, receipt)).expense_id == out.expense_id
        assert await _roles(s, out.expense_id) == ["cobranca", "pagamento"]
        # Negative: a receipt that matches nothing creates nothing.
        lost = _doc(
            condo,
            "comprovante",
            {"data_pagamento": "2026-11-24", "valor": "12.34", "nome_beneficiario": "X"},
        )
        s.add(lost)
        await s.flush()
        assert (await match_document(s, lost)).expense_id is None

        code = "85890000" + uuid.uuid4().hex[:8].translate(str.maketrans("abcdef", "123456"))
        slip = {
            "tributo": "IRRF",
            "competencia": "2026-10",
            "vencimento": "2026-11-20",
            "valor": "321.00",
            "codigo_barras": code,
        }
        tax = _doc(condo, "guia_tributo", slip)
        s.add(tax)
        await s.flush()
        made = await match_document(s, tax)
        expense = await s.get(Expense, made.expense_id)
        assert expense is not None and expense.category == "tributos"
        assert expense.supplier_id is None and expense.competence == date(2026, 10, 1)
        again = _doc(condo, "guia_tributo", dict(slip))
        s.add(again)
        await s.flush()
        assert (await match_document(s, again)).expense_id == expense.id
