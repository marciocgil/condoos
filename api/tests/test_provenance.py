"""CB-030 (FR-012, FR-016, DOC-01; D85): every extracted field records its source and, when
the text shows it, the page and excerpt; an absent field is "não disponível"; a person's
review turns every field into "confirmado" with the author."""

import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.enums import DocumentType
from app.db.models import Document
from app.db.session import sessionmaker_for
from app.extraction.provenance import NOT_AVAILABLE, build, confirmed, locate
from tests.helpers import ANALISTA, condo_id, login
from tests.test_queue import TRUTH, _upload_receipt

TEXT = (
    "RECIBO\nRecebi de Condomínio Jardim das Acácias a importância de R$ 1.250,00\f"
    "referente à manutenção do portão. São Paulo, 05/10/2026.\nCPF 123.456.789-09"
)


def test_locate_finds_page_and_excerpt_in_brazilian_formats() -> None:
    money = locate(TEXT, "money", "1250.00")
    assert money is not None and money["page"] == 1 and "R$ 1.250,00" in money["excerpt"]
    when = locate(TEXT, "date", "2026-10-05")
    assert when is not None and when["page"] == 2 and "05/10/2026" in when["excerpt"]
    doc = locate(TEXT, "doc", "12345678909")
    assert doc is not None and "123.456.789-09" in doc["excerpt"]
    assert locate(TEXT, "money", "999.00") is None  # never an invented excerpt


def test_build_marks_absent_fields_and_keeps_the_source() -> None:
    prov = build(
        DocumentType.RECIBO,
        {"valor": "1250.00", "data": "2026-10-05"},
        {"valor": "texto", "data": "ia"},
        TEXT,
    )
    assert prov["valor"]["source"] == "texto" and "excerpt" in prov["valor"]
    assert prov["data"]["source"] == "ia" and prov["data"]["page"] == 2
    absent = [k for k, v in prov.items() if v["source"] == NOT_AVAILABLE]
    assert absent and "valor" not in absent
    after = confirmed(
        prov, {"valor": "1250.00"}, {"valor": "1250.00", "data": "2026-10-06"}, "u", "t"
    )
    assert after["valor"]["status"] == "confirmado" and "excerpt" in after["valor"]
    assert "excerpt" not in after["data"]  # changed by the person: the old excerpt no longer fits
    assert after["data"]["extracted_from"] == "ia"


async def test_extraction_and_review_record_provenance(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    doc_id = await _upload_receipt(client, mailer, worker_engine, acacias)
    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.get(Document, uuid.UUID(doc_id))
        assert doc is not None
        prov = dict(doc.field_provenance)
    assert prov and all("source" in v for v in prov.values())
    located = [v for v in prov.values() if v.get("excerpt")]
    assert located and all(v["source"] in ("texto", "ia") for v in located)

    await login(client, mailer, ANALISTA)
    review = (await client.get(f"/condominiums/{acacias}/documents/{doc_id}/review")).json()
    assert review["provenance"] == prov
    truth = TRUTH["18_recibo.pdf"]["fields"]
    r = await client.put(
        f"/condominiums/{acacias}/documents/{doc_id}/review",
        json={"doc_type": "recibo", "values": truth},
    )
    assert r.status_code == 200, r.text
    after = r.json()["provenance"]
    assert all(v["status"] == "confirmado" and v["confirmed_by"] for v in after.values())


def test_values_filled_by_a_rule_are_inferred_never_read() -> None:
    """LB-036 (D94): without a start date the term starts on the signature date, and the
    adjustment month is the start month (D68). Both are "inferido", with the rule, and never
    get an excerpt — even though the signature date is in the text."""
    import random
    from datetime import date

    from app.core.br import format_cnpj, generate_cnpj
    from app.extraction.confidence import assess

    condo = generate_cnpj(random.Random("inf-condo"))
    supplier = generate_cnpj(random.Random("inf-supplier"))
    raw = {
        "cnpj_contratada": supplier,
        "razao_social_contratada": "Limpa Bem Serviços Ltda",
        "cnpj_contratante": condo,
        "objeto": "Limpeza das áreas comuns",
        "itens_escopo": ["limpeza"],
        "valor_mensal": "4800.00",
        "indice_reajuste": "IPCA",
        "data_assinatura": "2025-03-10",
    }
    result = assess(
        DocumentType.CONTRATO,
        raw,
        {k: 0.95 for k in raw},
        condominium_cnpj=condo,
        today=date(2026, 11, 7),
    )
    assert set(result.inferred) == {"data_inicio", "mes_base_reajuste"}
    text = f"CONTRATANTE CNPJ {format_cnpj(condo)}. São Paulo, 10/03/2025."
    prov = build(
        DocumentType.CONTRATO, result.values, {k: "texto" for k in raw}, text, result.inferred
    )
    assert (
        prov["data_inicio"]["source"] == "inferido" and "assinatura" in prov["data_inicio"]["rule"]
    )
    assert "excerpt" not in prov["data_inicio"]
    assert prov["mes_base_reajuste"]["source"] == "inferido"
    assert prov["data_assinatura"]["source"] == "texto"  # read, keeps its excerpt
    assert "excerpt" in prov["data_assinatura"]
