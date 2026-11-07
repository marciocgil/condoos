"""Gate LG3 (Launch LF3, D94): one scenario with contradictory, absent, duplicated and
unreadable documents. Nothing partial is presented as complete:

- contradictory: a contract and an amendment that takes effect after the contract's end,
  both entering through the real matching step → a data conflict, C2 partial, the policy
  refuses actions with the supplier;
- duplicated: the same file sent twice is one document;
- unreadable: a blank image is never "read" on the first-value card;
- absent: the month's invoice of the contract did not arrive → C8 says "not received" and
  the report's coverage says so, with no bank statement either.
"""

import io
import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.br import format_cnpj, generate_cnpj
from app.data_issues import open_issues
from app.db.enums import DocumentOrigin, PolicyDecision
from app.db.models import Condominium, Document
from app.db.session import sessionmaker_for
from app.extraction.pipeline import process_document
from app.ingestion.documents import ingest_file
from app.launch.first_value import first_value
from app.launch.readiness import readiness
from app.matching.documents import match_document
from app.onboarding import onboard
from app.policy import evaluate as policy_evaluate
from app.reports.data import month_coverage
from tests.test_onboarding import _spec

TODAY = date(2026, 11, 20)


def _contract_doc(condo: Condominium, extracted: dict[str, Any], text: str) -> Document:
    return Document(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        doc_type="contrato",
        storage_key=f"cond/{condo.id}/x",
        sha256=uuid.uuid4().hex * 2,
        original_filename="contrato.pdf",
        mime_type="application/pdf",
        origin="upload",
        extraction_status="done",
        extracted=extracted,
        field_confidence={k: 0.95 for k in extracted},
        needs_review=False,
        review_reasons=[],
        text_content=text,
    )


def _blank_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buf, format="PNG")
    return buf.getvalue()


async def test_contradictory_absent_duplicated_and_unreadable(
    admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec(management_company_name=None))
        supplier_cnpj = generate_cnpj(random.Random(f"lg3-{condo.id}"))
        base = {
            "cnpj_contratada": supplier_cnpj,
            "razao_social_contratada": "Portaria Fictícia Ltda",
            "cnpj_contratante": condo.cnpj,
            "itens_escopo": ["portaria"],
            "valor_mensal": "9000.00",
            "indice_reajuste": "IPCA",
        }
        contract_doc = _contract_doc(
            condo,
            {
                **base,
                "objeto": "Portaria 24 horas",
                "data_inicio": "2026-01-01",
                "data_fim": "2026-06-30",
            },
            f"CONTRATO DE PORTARIA. CONTRATANTE CNPJ {format_cnpj(condo.cnpj)}. "
            "Vigência de 01/01/2026 a 30/06/2026.",
        )
        s.add(contract_doc)
        await s.flush()
        await match_document(s, contract_doc)
        amendment_doc = _contract_doc(
            condo,
            {
                **base,
                "objeto": "Primeiro termo aditivo — portaria 24 horas",
                "data_inicio": "2026-08-01",
                "valor_mensal": "9500.00",
            },
            "PRIMEIRO TERMO ADITIVO ao contrato de portaria, a partir de 01/08/2026.",
        )
        s.add(amendment_doc)
        await s.flush()
        await match_document(s, amendment_doc)

        # Contradictory → a conflict, C2 partial, actions with the supplier refused.
        [issue] = await open_issues(s, condo.id)
        assert issue.detector == "aditivo_fora_da_vigencia_v1"
        ready = {r.key: r for r in await readiness(s, condo.id, TODAY)}
        assert ready["C2"].state == "analise_parcial"
        denied = await policy_evaluate(
            s,
            condo,
            action_type="fornecedor.cobrar",
            cost_cap=Decimal("0"),
            supplier_id=issue.supplier_id,
        )
        assert denied.decision == PolicyDecision.DENY

        # Absent → "not received", never "not issued"; the report states its coverage.
        # (In July the contract, in force until June, expected June's invoice.)
        c8 = {r.key: r for r in await readiness(s, condo.id, date(2026, 7, 20))}["C8"]
        assert c8.state == "analise_parcial"
        assert "ainda não recebida" in c8.missing[0]
        coverage = await month_coverage(s, condo.id, date(2026, 6, 1))
        assert coverage[0].startswith("Notas fiscais dos contratos: 0 de 1 recebidas")
        assert any(line.startswith("Sem extrato bancário") for line in coverage)
        condo_id = condo.id

    # Duplicated → one document.
    png = _blank_png()
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        first = await ingest_file(
            s,
            condominium_id=condo_id,
            filename="foto.png",
            data=png,
            origin=DocumentOrigin.UPLOAD,
            actor_user_id=None,
        )
    async with maker() as s, s.begin():
        again = await ingest_file(
            s,
            condominium_id=condo_id,
            filename="foto-de-novo.png",
            data=png,
            origin=DocumentOrigin.UPLOAD,
            actor_user_id=None,
        )
    assert first.document_id is not None and not first.duplicate
    assert again.duplicate and again.document_id == first.document_id

    # Unreadable → processed, but never shown as read.
    async with maker() as s, s.begin():
        await process_document(s, {"document_id": str(first.document_id)})
    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.get(Document, first.document_id)
        assert doc is not None
        card = await first_value(s, doc)
        assert card["state"] in ("falhou", "outro_tipo", "parcial")
        assert card["state"] != "lido"
