"""D68: contract reading calibrated with real documents — contracts that cite "nota fiscal"
are contracts, the contracted party's CNPJ, signature date as start, adjustment month from
the start, indeterminate term, and an "OUTRO" index with its description."""

import random
from datetime import date
from decimal import Decimal

from app.core.br import format_cnpj, generate_cnpj
from app.db.enums import DocumentType
from app.extraction.confidence import assess
from app.extraction.heuristics import classify_text, prefill, signature_date
from app.rules.contracts import value_at

REF = date(2026, 11, 5)
CONDO = generate_cnpj(random.Random("condo"))
SUPPLIER = generate_cnpj(random.Random("supplier"))
WITNESS = generate_cnpj(random.Random("witness"))

CONTRACT = f"""CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE LIMPEZA
CONTRATANTE: Condomínio Fictício, inscrito no CNPJ {format_cnpj(CONDO)}.
CONTRATADA: Limpa Bem Serviços Ltda, inscrita no CNPJ sob o nº {SUPPLIER[:2]}.{SUPPLIER[2:5]}.{SUPPLIER[5:8]} / {SUPPLIER[8:12]} - {SUPPLIER[12:]}.
CLÁUSULA PRIMEIRA — DO OBJETO. Limpeza das áreas comuns.
CLÁUSULA SEGUNDA — DO PAGAMENTO. O pagamento será feito mediante apresentação de nota fiscal de serviço eletrônica (NFS-e).
CLÁUSULA TERCEIRA — DO REAJUSTE. Anualmente, pelo IGP-DI/FGV.
CLÁUSULA QUARTA — DO PRAZO. Prazo indeterminado.
Interveniente: Garantias Fictícias S.A., CNPJ {format_cnpj(WITNESS)}.
São Paulo, 10 de março de 2025.
"""


def test_contract_citing_nfse_is_a_contract() -> None:
    c = classify_text(CONTRACT, REF)
    assert c.doc_type == DocumentType.CONTRATO
    nfse = "NFS-e — Nota Fiscal de Serviço Eletrônica\nPrestador: X\nTomador: Y\nContrato nº 12"
    assert classify_text(nfse, REF).doc_type == DocumentType.NFSE


def test_contracted_cnpj_and_signature_date() -> None:
    pf = prefill(DocumentType.CONTRATO, CONTRACT, CONDO, REF)
    values = pf.values
    assert values["cnpj_contratada"] == SUPPLIER  # spaced OCR form, not the guarantor's
    assert signature_date(CONTRACT) == "2025-03-10"
    assert values["data_assinatura"] == "2025-03-10"


def _assess(raw: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    base: dict[str, object] = {
        "cnpj_contratada": SUPPLIER,
        "razao_social_contratada": "Limpa Bem Serviços Ltda",
        "cnpj_contratante": CONDO,
        "objeto": "Limpeza das áreas comuns",
        "itens_escopo": ["limpeza"],
        "valor_mensal": "4800.00",
        "indice_reajuste": "IPCA",
    }
    base.update(raw)
    conf = {k: 0.95 for k in base}
    a = assess(DocumentType.CONTRATO, base, conf, condominium_cnpj=CONDO, today=REF)
    return a.values, a.reasons


def test_start_falls_back_to_signature_and_month_to_start() -> None:
    values, reasons = _assess({"data_assinatura": "2025-03-10"})
    assert values["data_inicio"] == "2025-03-10" and values["mes_base_reajuste"] == 3
    assert values["data_fim"] is None  # indeterminate term is a valid answer
    assert reasons == []
    values, _ = _assess({"data_inicio": "2025-06-01", "mes_base_reajuste": 1})
    assert values["mes_base_reajuste"] == 1  # an explicit month in the contract wins
    values, _ = _assess({"data_inicio": "2025-06-01", "indice_reajuste": "FIXO"})
    assert values["mes_base_reajuste"] is None


def test_other_index_keeps_its_name() -> None:
    values, reasons = _assess({"data_inicio": "2025-03-01", "indice_reajuste": "IGP-DI"})
    assert values["indice_reajuste"] == "OUTRO"
    assert values["indice_reajuste_outro"] == "IGP-DI"
    assert reasons == []
    _, reasons = _assess({"data_inicio": "2025-03-01", "indice_reajuste": "OUTRO"})
    assert any("informe qual" in r for r in reasons)


def test_other_index_value_known_until_first_adjustment() -> None:
    start = date(2025, 3, 1)
    assert value_at(Decimal(1000), "OUTRO", 3, start, date(2026, 2, 1), {}) == 1000
    assert value_at(Decimal(1000), "OUTRO", 3, start, date(2026, 3, 1), {}) is None
