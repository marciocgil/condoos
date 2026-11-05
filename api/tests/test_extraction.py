"""Extraction: deterministic readers, confidence rules and the document.process job."""

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.enums import DocumentOrigin, DocumentType
from app.db.models import BankTransaction, Condominium, Document
from app.db.session import sessionmaker_for
from app.extraction import boleto
from app.extraction.confidence import assess
from app.extraction.fields import InvalidValue, normalize
from app.extraction.heuristics import classify_text, valid_cnpjs
from app.extraction.pipeline import process_document
from app.extraction.xml_fiscal import NotFiscalXml, parse_fiscal_xml
from app.ingestion.documents import ingest_file
from app.llm import client as llm
from tests.bankfiles import Payment, cnab240

CORPUS = Path(__file__).parent / "fixtures" / "corpus"
TRUTH = json.loads((CORPUS / "ground_truth.json").read_text(encoding="utf-8"))
CONDO_CNPJ = TRUTH["condominium_cnpj"]
TODAY = date(2026, 11, 5)


# --------------------------------------------------------------------------- boleto


def test_bancario_roundtrip_and_check_digits() -> None:
    code = boleto.build_bancario("341", Decimal("1234.56"), date(2026, 10, 20), "1" * 25)
    parsed = boleto.parse_linha_digitavel(boleto.format_bancario(code), TODAY)
    assert parsed is not None
    assert parsed.amount == Decimal("1234.56") and parsed.due_date == date(2026, 10, 20)
    assert parsed.bank_code == "341" and len(parsed.barcode) == 44
    # Any single-digit change must be caught by a check digit.
    for pos in (2, 15, 27, 40):
        broken = code[:pos] + str((int(code[pos]) + 1) % 10) + code[pos + 1 :]
        assert boleto.parse_linha_digitavel(broken, TODAY) is None


def test_due_date_factor_new_cycle() -> None:
    # Factor 1000 = 22/02/2025 (restart); the old cycle would give a 2000 date.
    assert boleto.due_date_from_factor(1000, TODAY) == date(2025, 2, 22)
    assert boleto.due_date_from_factor(9999, date(2025, 2, 1)) == date(2025, 2, 21)
    assert boleto.due_date_from_factor(0, TODAY) is None


def test_arrecadacao_roundtrip() -> None:
    code = boleto.build_arrecadacao("3", Decimal("8143.27"), "1234", "9" * 25)
    parsed = boleto.parse_linha_digitavel(code, TODAY)
    assert parsed is not None and parsed.kind == "arrecadacao"
    assert parsed.amount == Decimal("8143.27") and parsed.due_date is None
    assert boleto.parse_linha_digitavel(code[:-1] + str((int(code[-1]) + 1) % 10), TODAY) is None


def test_find_linha_in_text() -> None:
    code = boleto.build_bancario("237", Decimal("99.90"), date(2026, 11, 10), "2" * 25)
    text = f"Bradesco 237-2   {boleto.format_bancario(code)}\nVencimento 10/11/2026"
    found = boleto.find_in_text(text, TODAY)
    assert found is not None and found.digits == code


# --------------------------------------------------------------------------- XML


@pytest.mark.parametrize("name", ["21_nfe.xml", "24_nfse_nacional.xml", "25_nfse_abrasf.xml"])
def test_fiscal_xml_matches_ground_truth(name: str) -> None:
    result = parse_fiscal_xml((CORPUS / name).read_bytes())
    expected = TRUTH["documents"][name]
    assert result.doc_type.value == expected["doc_type"]
    for field, value in expected["fields"].items():
        got = result.values.get(field)
        if isinstance(value, list):
            assert got == value, field
        else:
            # Dates come as ISO prefixes in XML (2026-10-05T08:00:00-03:00 / competência 2026-10).
            assert got is not None and str(value).startswith(str(got)[:10]), field


def test_xml_rejects_entities_and_other_xml() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(NotFiscalXml):
        parse_fiscal_xml(bomb)
    with pytest.raises(NotFiscalXml):
        parse_fiscal_xml(b"<rss><channel/></rss>")


# --------------------------------------------------------------------------- normalisation / heuristics


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        ("date", "05/10/2026", "2026-10-05"),
        ("date", "2026-10-05T10:00:00-03:00", "2026-10-05"),
        ("month", "10/2026", "2026-10"),
        ("money", "R$ 1.234,56", "1234.56"),
        ("money", 99.9, "99.90"),
        ("cnpj", "11.222.333/0001-81", "11222333000181"),
        ("index", "IGP-M", "IGPM"),
        ("list", "a; b;\nc", ["a", "b", "c"]),
    ],
)
def test_normalize(kind: Any, raw: Any, expected: Any) -> None:
    assert normalize(kind, raw) == expected


def test_normalize_rejects_garbage() -> None:
    with pytest.raises(InvalidValue):
        normalize("date", "31/02/2026")
    with pytest.raises(InvalidValue):
        normalize("cnpj", "123")


def test_bare_digits_inside_boleto_code_are_not_cnpj() -> None:
    code = boleto.build_bancario("341", Decimal("147.00"), date(2026, 10, 20), "3" * 25)
    assert valid_cnpjs(code) == []
    assert valid_cnpjs("CNPJ: 11222333000181") == ["11222333000181"]


def test_classify_text() -> None:
    assert (
        classify_text("PREFEITURA ... NOTA FISCAL DE SERVIÇOS ELETRÔNICA", TODAY).doc_type
        == DocumentType.NFSE
    )
    assert classify_text("RECIBO\nRecebi de Fulano", TODAY).doc_type == DocumentType.RECIBO
    assert classify_text("texto qualquer", TODAY).doc_type is None


# --------------------------------------------------------------------------- confidence


def _nfse_values(**over: Any) -> dict[str, Any]:
    base = dict(TRUTH["documents"]["24_nfse_nacional.xml"]["fields"])
    base.update(over)
    return base


def test_assess_accepts_consistent_certain_values() -> None:
    values = _nfse_values()
    result = assess(
        DocumentType.NFSE,
        values,
        dict.fromkeys(values, 1.0),
        condominium_cnpj=CONDO_CNPJ,
        today=TODAY,
    )
    assert not result.needs_review


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"cnpj_tomador": "11222333000181"}, "não é o CNPJ do condomínio"),
        ({"cnpj_prestador": "11222333000182"}, "dígito verificador inválido"),
        ({"valor_liquido": "100.00"}, "não confere"),
        ({"data_emissao": "2019-01-01"}, "fora do período"),
        ({"numero": None}, "não encontrado"),
    ],
)
def test_assess_flags_problems(override: dict[str, Any], fragment: str) -> None:
    values = _nfse_values(**override)
    result = assess(
        DocumentType.NFSE,
        values,
        dict.fromkeys(values, 1.0),
        condominium_cnpj=CONDO_CNPJ,
        today=TODAY,
    )
    assert result.needs_review
    assert any(fragment in r for r in result.reasons), result.reasons


def test_model_self_confidence_below_threshold_goes_to_review() -> None:
    values = _nfse_values()
    conf = dict.fromkeys(values, 0.97)
    conf["valor_servicos"] = 0.6
    result = assess(DocumentType.NFSE, values, conf, condominium_cnpj=CONDO_CNPJ, today=TODAY)
    assert result.needs_review and any("Valor dos serviços" in r for r in result.reasons)


def test_low_confidence_optional_fields_are_dropped_when_automatic() -> None:
    values = dict(TRUTH["documents"]["09_boleto.pdf"]["fields"])
    conf = dict.fromkeys(values, 1.0)
    conf["numero_documento"] = 0.75
    result = assess(DocumentType.BOLETO, values, conf, condominium_cnpj=CONDO_CNPJ, today=TODAY)
    assert not result.needs_review
    assert result.values["numero_documento"] is None


# --------------------------------------------------------------------------- job document.process


async def _acacias(admin_engine: AsyncEngine) -> Condominium:
    async with sessionmaker_for(admin_engine)() as s:
        condo = await s.scalar(select(Condominium).where(Condominium.slug == "jardim-das-acacias"))
    assert condo is not None and condo.cnpj == CONDO_CNPJ
    return condo


async def _ingest_and_process(
    engine: AsyncEngine, condo: Condominium, name: str, data: bytes
) -> Document:
    maker = sessionmaker_for(engine)
    async with maker() as s, s.begin():
        out = await ingest_file(
            s,
            condominium_id=condo.id,
            filename=name,
            data=data,
            origin=DocumentOrigin.UPLOAD,
            actor_user_id=None,
        )
    assert out.document_id is not None, out.error
    async with maker() as s, s.begin():
        await process_document(s, {"document_id": str(out.document_id)})
    async with maker() as s:
        doc = await s.get(Document, out.document_id)
    assert doc is not None
    return doc


async def test_job_xml_is_automatic(worker_engine: AsyncEngine, admin_engine: AsyncEngine) -> None:
    condo = await _acacias(admin_engine)
    doc = await _ingest_and_process(
        worker_engine, condo, "nf.xml", (CORPUS / "25_nfse_abrasf.xml").read_bytes()
    )
    assert doc.doc_type == "nfse" and doc.extraction_status == "done" and not doc.needs_review
    assert doc.extracted["valor_liquido"] == "1470.00"
    assert doc.field_confidence["cnpj_prestador"] == 1.0


async def test_job_boleto_pdf_is_automatic(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    condo = await _acacias(admin_engine)
    doc = await _ingest_and_process(
        worker_engine, condo, "b.pdf", (CORPUS / "11_boleto.pdf").read_bytes()
    )
    truth = TRUTH["documents"]["11_boleto.pdf"]["fields"]
    assert doc.doc_type == "boleto" and not doc.needs_review, doc.review_reasons
    assert (
        doc.extracted["valor"] == truth["valor"]
        and doc.extracted["vencimento"] == truth["vencimento"]
    )
    assert doc.text_content and doc.page_count == 1


async def test_job_without_model_sends_receipt_to_queue(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    condo = await _acacias(admin_engine)
    doc = await _ingest_and_process(
        worker_engine, condo, "r.pdf", (CORPUS / "19_recibo.pdf").read_bytes()
    )
    assert doc.doc_type == "recibo" and doc.needs_review and doc.extraction_status == "needs_review"
    assert doc.review_reasons


async def test_job_photo_without_ocr_goes_to_queue(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    condo = await _acacias(admin_engine)
    doc = await _ingest_and_process(
        worker_engine, condo, "f.jpg", (CORPUS / "30_foto_recibo.jpg").read_bytes()
    )
    assert doc.needs_review and "sem texto legível" in doc.review_reasons[0]


async def test_job_with_model_output_completes_receipt(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model path, with the API replaced by a fake that returns the ground truth."""
    truth = TRUTH["documents"]["17_recibo.pdf"]["fields"]

    async def fake(req: llm.LLMRequest[Any], model: str) -> tuple[dict[str, Any], Any, str]:
        assert req.purpose == "document.extract.recibo"
        assert "Recebi de" in req.user_text and not req.attachments  # text, not the file
        out = {k: {"value": str(v), "confidence": 0.97} for k, v in truth.items()}
        return (
            {**out, "observacoes": ""},
            SimpleNamespace(input_tokens=900, output_tokens=150),
            model,
        )

    from app.config import get_settings

    monkeypatch.setattr(llm, "_call_api", fake)
    monkeypatch.setattr(get_settings(), "llm_mode", "live")
    condo = await _acacias(admin_engine)
    doc = await _ingest_and_process(
        worker_engine, condo, "r17.pdf", (CORPUS / "17_recibo.pdf").read_bytes()
    )
    assert not doc.needs_review, doc.review_reasons
    assert doc.extracted["valor"] == truth["valor"] and doc.extraction_source == "texto+ia"


async def test_job_imports_cnab_and_reviewed_documents_are_kept(
    worker_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    condo = await _acacias(admin_engine)
    data = cnab240(
        "237",
        condo.cnpj,
        payments=[
            Payment(
                "A",
                "VERDE VIVO PAISAGISMO",
                Decimal("1470.00"),
                date(2026, 10, 15),
                "45723174000110",
                f"JOB{uuid.uuid4().hex[:6]}",
            ),
        ],
    )
    doc = await _ingest_and_process(worker_engine, condo, "retorno.ret", data)
    assert doc.doc_type == "cnab_retorno" and doc.extracted["lancamentos_novos"] == 1
    async with sessionmaker_for(worker_engine)() as s:
        assert await s.scalar(
            select(BankTransaction.id).where(
                BankTransaction.condominium_id == condo.id,
                BankTransaction.amount == Decimal("-1470.00"),
            )
        )

    # A document already reviewed by a person is never re-extracted.
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        d = await s.get(Document, doc.id)
        assert d is not None
        d.reviewed_at, d.extracted = date(2026, 11, 1), {"marcado": True}  # type: ignore[assignment]
    async with maker() as s, s.begin():
        await process_document(s, {"document_id": str(doc.id)})
    async with maker() as s:
        d = await s.get(Document, doc.id)
        assert d is not None and d.extracted == {"marcado": True}
