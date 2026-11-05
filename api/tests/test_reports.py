"""Milestone 5: monthly report (PDF and XLSX) for both seeded condominiums, the decision
trail export and closing a competence only with an empty exception queue."""

import io
from datetime import date

import httpx
import pypdfium2 as pdfium
import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import AuditLog, Competence
from app.db.session import sessionmaker_for
from app.reports.data import FOOTER, build_month_report
from app.reports.pdf import month_report_pdf
from app.reports.xlsx import month_report_xlsx
from app.seed.run import evaluate_seed
from tests.helpers import GERENTE, SINDICA_ACACIAS, SINDICA_MIRANTE, condo_id, login

OCT = date(2026, 10, 1)


def pdf_pages(body: bytes) -> list[str]:
    doc = pdfium.PdfDocument(body)
    pages = [" ".join(doc[i].get_textpage().get_text_range().split()) for i in range(len(doc))]
    doc.close()
    return pages


@pytest.fixture
async def evaluated(admin_engine: AsyncEngine) -> None:
    await evaluate_seed(admin_engine)


@pytest.mark.parametrize("slug", ["jardim-das-acacias", "mirante-do-vale"])
async def test_report_for_each_seeded_condominium(
    evaluated: None, admin_engine: AsyncEngine, slug: str
) -> None:
    cid = await condo_id(admin_engine, slug)
    async with sessionmaker_for(admin_engine)() as s:
        report = await build_month_report(s, cid, OCT)
    assert report.expenses and report.contracts and report.findings
    # board view: nothing awaiting validation
    assert all(f.status != "aguardando_validacao" for f in report.findings)

    pages = pdf_pages(month_report_pdf(report))
    assert len(pages) >= 3  # summary, findings, annex
    assert all(FOOTER in page for page in pages), "rodapé ausente em alguma página"
    assert report.condominium in pages[0] and "Principais achados" in pages[0]
    for f in report.findings:
        assert any(f.title[:40] in p for p in pages[1:]), f.title
    joined = " ".join(pages).lower()
    assert "fraude" not in joined and "desvio" not in joined

    wb = load_workbook(io.BytesIO(month_report_xlsx(report)))
    assert wb.sheetnames == ["Achados", "Despesas", "Fornecedores", "Contratos"]
    for ws in wb.worksheets:
        assert ws["A1"].value == FOOTER
        assert ws.oddFooter is not None and ws.oddFooter.center.text == FOOTER
    assert wb["Achados"].max_row == 3 + len(report.findings)
    assert wb["Despesas"].max_row == 3 + len(report.expenses) + 1  # + total row


async def test_report_endpoints_and_isolation(
    evaluated: None, client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.get(f"/condominiums/{acacias}/reports/2026-10.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "previa-relatorio-jardim-das-acacias-2026-10.pdf" in r.headers["content-disposition"]
    r = await client.get(f"/condominiums/{acacias}/reports/2026-10.xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    listed = (await client.get(f"/condominiums/{acacias}/reports")).json()
    assert listed[0]["competence"] == "2026-10-01" and listed[0]["status"] == "aberta"
    trail = await client.get(f"/condominiums/{acacias}/decisions.pdf")
    assert trail.status_code == 200 and all(FOOTER in p for p in pdf_pages(trail.content))
    # the síndica cannot close
    assert (
        await client.post(f"/condominiums/{acacias}/competences/2026-10/close")
    ).status_code == 403

    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{acacias}/reports/2026-10.pdf")).status_code == 404
    assert (await client.get(f"/condominiums/{acacias}/decisions.pdf")).status_code == 404


async def test_close_requires_empty_queue_then_stores_report(
    evaluated: None, client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, GERENTE)

    # Acácias has serious findings awaiting validation in October: closing is refused.
    status_ = (await client.get(f"/condominiums/{acacias}/competences/2026-10/closing")).json()
    assert status_["pending"]["achados_graves"] >= 1 and not status_["can_close"]
    r = await client.post(f"/condominiums/{acacias}/competences/2026-10/close")
    assert r.status_code == 409 and "fila de exceções" in r.json()["detail"]

    # Mirante's October queue is empty: closing stores both files and publishes.
    status_ = (await client.get(f"/condominiums/{mirante}/competences/2026-10/closing")).json()
    assert status_["can_close"], status_
    r = await client.post(f"/condominiums/{mirante}/competences/2026-10/close")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "fechada" and r.json()["published_at"]
    assert (
        await client.post(f"/condominiums/{mirante}/competences/2026-10/close")
    ).status_code == 409

    r = await client.get(f"/condominiums/{mirante}/reports/2026-10.pdf")
    assert "relatorio-mirante-do-vale-2026-10.pdf" in r.headers["content-disposition"]
    assert "previa" not in r.headers["content-disposition"]
    pages = pdf_pages(r.content)
    assert "fechada" in pages[0] and all(FOOTER in p for p in pages)

    async with sessionmaker_for(admin_engine)() as s:
        comp = await s.scalar(
            select(Competence).where(Competence.condominium_id == mirante, Competence.month == OCT)
        )
        audit = await s.scalar(
            select(AuditLog).where(
                AuditLog.action == "competence.closed", AuditLog.condominium_id == mirante
            )
        )
    assert comp is not None and comp.report_pdf_key and comp.report_xlsx_key
    assert comp.report_pdf_key.startswith(f"cond/{mirante}/")
    assert audit is not None
