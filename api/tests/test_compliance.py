"""Compliance and expiry dates (D108, FR-057): the catalogue only suggests, a person decides
whether an obligation applies, the situation is computed on read with careful words, the
model reads a document's dates "a confirmar" (never invented), and the alerts reach the
agenda, the briefing and the chat. Nothing leaves the system."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app import compliance as svc
from app.auth.mailer import MemoryMailer
from app.compliance.status import situation
from app.db.enums import DocumentType
from app.db.models import ComplianceEvidence, ComplianceObligation, Document
from app.db.session import sessionmaker_for
from app.llm.client import LLMResult
from tests.helpers import (
    ADMIN_CONDOOS,
    ANALISTA,
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

TODAY = date(2026, 11, 9)
FORBIDDEN = ("irregular", "conformidade", "conforme", "não cumprida", "nao cumprida")


def _ob(**kw: Any) -> ComplianceObligation:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": uuid.uuid4(),
        "name": "Seguro",
        "category": "seguro",
        "lead_days": 60,
        "applicability": "aplicavel",
        "periodicity_months": None,
        "archived_at": None,
    }
    base.update(kw)
    return ComplianceObligation(**base)


def _ev(**kw: Any) -> ComplianceEvidence:
    base: dict[str, Any] = {"source": "pessoa", "confirmed": True}
    base.update(kw)
    return ComplianceEvidence(**base)


def test_situation_codes_and_words() -> None:
    cases = [
        (_ob(applicability="a_validar"), None, "a_validar"),
        (_ob(applicability="nao_aplicavel"), None, "nao_aplicavel"),
        (_ob(archived_at=datetime.now(UTC)), None, "arquivada"),
        (_ob(), None, "sem_documento"),
        (_ob(), _ev(source="lendo", confirmed=False), "lendo"),
        (_ob(), _ev(issued_on=TODAY), "sem_validade"),
        (_ob(), _ev(valid_until=TODAY - timedelta(days=1)), "vencido"),
        (_ob(), _ev(valid_until=TODAY), "vence_em_breve"),
        (_ob(), _ev(valid_until=TODAY + timedelta(days=60)), "vence_em_breve"),
        (_ob(), _ev(valid_until=TODAY + timedelta(days=61)), "em_dia"),
    ]
    for ob, ev, code in cases:
        sit = situation(ob, ev, TODAY)
        assert sit.code == code, (code, sit)
        text = f"{sit.label} {sit.text}".lower()
        assert not any(w in text for w in FORBIDDEN), text
    assert situation(_ob(), None, TODAY).text == "Nenhum documento registrado no CondoOS"
    assert situation(_ob(), _ev(valid_until=TODAY), TODAY).text.startswith("Vence hoje")
    # Issue date + the periodicity a person validated = computed validity.
    sit = situation(_ob(periodicity_months=12), _ev(issued_on=date(2026, 1, 15)), TODAY)
    assert (sit.code, sit.valid_until, sit.computed) == ("em_dia", date(2027, 1, 15), True)
    # A date read by the model says so until a person confirms it.
    sit = situation(_ob(), _ev(source="ia", confirmed=False, valid_until=date(2027, 6, 1)), TODAY)
    assert sit.to_confirm == "data lida pela IA, a confirmar"


def test_dates_are_read_only_when_written() -> None:
    issued, until, quote = svc.read_dates_from_text(
        "APÓLICE Nº 123\nVigência: das 24h de 10/03/2026 às 24h de 10/03/2027.\n"
    )
    assert (issued, until) == (date(2026, 3, 10), date(2027, 3, 10))
    assert quote and "10/03/2027" in quote
    assert svc.read_dates_from_text("Certificado válido até 31/12/2027.")[1] == date(2027, 12, 31)
    assert svc.read_dates_from_text("Data de emissão: 02/01/2026")[:2] == (date(2026, 1, 2), None)
    assert svc.read_dates_from_text("Relatório de visita técnica sem datas.") == (None, None, None)


async def test_seed_catalogue_and_who_does_what(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/compliance"
    await login(client, mailer, SINDICA_ACACIAS)
    body = (await client.get(base)).json()
    assert body["can_manage"] and body["can_validate"] and body["catalog_missing"] == 0
    by_name = {o["name"]: o for o in body["obligations"]}
    assert by_name["Seguro obrigatório da edificação"]["situation"]["code"] == "vence_em_breve"
    assert by_name["AVCB ou CLCB (Corpo de Bombeiros)"]["situation"]["code"] == "em_dia"
    assert by_name["Recarga e inspeção dos extintores"]["situation"]["code"] == "sem_documento"
    assert by_name["Inspeção predial"]["situation"]["code"] == "a_validar"
    assert by_name["Inspeção predial"]["suggested_months"] is None  # varies too much to suggest
    codes = [o["situation"]["code"] for o in body["obligations"]]
    assert codes.index("vence_em_breve") < codes.index("a_validar")  # most urgent first
    assert (await client.post(f"{base}/catalog")).json() == {"created": 0}  # idempotent
    predial = by_name["Inspeção predial"]["id"]

    # The board member sees, never changes.
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    seen = (await client.get(base)).json()
    assert not seen["can_manage"] and not seen["can_validate"]
    assert (await client.post(f"{base}/catalog")).status_code == 403
    assert (
        await client.post(f"{base}/{predial}/evidence", json={"valid_until": "2027-01-01"})
    ).status_code == 403

    # The analyst and the CondoOS admin register documents but do not decide applicability.
    for who in (ANALISTA, ADMIN_CONDOOS):
        await login(client, mailer, who)
        r = await client.post(
            f"{base}/{predial}/validation", json={"applies": True, "reason": "Achei que sim"}
        )
        assert r.status_code == 403, who
    await login(client, mailer, ANALISTA)
    assert (await client.get(f"{base}/{predial}")).json()["can_manage"] is True

    # Another condominium: 404, never 403.
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"{base}/{predial}")).status_code == 404


async def test_validation_evidence_and_where_alerts_show(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/compliance"
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(
        base, json={"name": "Laudo da fachada (fictício)", "category": "estrutura"}
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert (await client.get(f"{base}/{oid}")).json()["situation"]["code"] == "a_validar"

    # A reason is required; the periodicity is the person's.
    short = await client.post(f"{base}/{oid}/validation", json={"applies": True, "reason": "ok"})
    assert short.status_code == 422
    r = await client.post(
        f"{base}/{oid}/validation",
        json={
            "applies": True,
            "reason": "Exigido pela prefeitura, conforme o engenheiro",
            "periodicity_months": 12,
        },
    )
    assert r.status_code == 200
    detail = (await client.get(f"{base}/{oid}")).json()
    assert detail["applicability"] == "aplicavel" and detail["validated_by"]
    assert detail["situation"]["code"] == "sem_documento"

    # Dates typed by a person: expired. It shows in the briefing and the agenda.
    expired = (date.today() - timedelta(days=3)).isoformat()
    bad = await client.post(
        f"{base}/{oid}/evidence", json={"issued_on": "2026-05-01", "valid_until": "2026-04-01"}
    )
    assert bad.status_code == 422
    assert (
        await client.post(f"{base}/{oid}/evidence", json={"valid_until": expired})
    ).status_code == 201
    detail = (await client.get(f"{base}/{oid}")).json()
    assert detail["situation"]["code"] == "vencido" and detail["evidence"][0]["confirmed"]
    briefing = (await client.post(f"/condominiums/{acacias}/briefing/refresh")).json()
    risks = next(s for s in briefing["sections"] if s["key"] == "riscos")
    assert any(i["kind"] == "compliance" and "fachada" in i["title"] for i in risks["items"])
    start = (date.today() - timedelta(days=10)).isoformat()
    agenda = (
        await client.get(f"/condominiums/{acacias}/agenda?start={start}&kind=validade")
    ).json()
    assert any(e["obligation_id"] == oid and e["status"] == "vencido" for e in agenda["events"])

    # Not applicable: no alert anywhere.
    await client.post(
        f"{base}/{oid}/validation",
        json={"applies": False, "reason": "Prédio sem fachada ventilada"},
    )
    assert (await client.get(f"{base}/{oid}")).json()["situation"]["code"] == "nao_aplicavel"
    briefing = (await client.post(f"/condominiums/{acacias}/briefing/refresh")).json()
    risks = next(s for s in briefing["sections"] if s["key"] == "riscos")
    assert not any("fachada" in i["title"] for i in risks["items"])

    # Archived: out of the list, kept with its history.
    assert (await client.post(f"{base}/{oid}/archive", json={"archived": True})).status_code == 200
    listing = (await client.get(base)).json()
    assert oid not in {o["id"] for o in listing["obligations"]}
    assert oid in {o["id"] for o in listing["archived"]}
    kinds = [e["kind"] for e in (await client.get(f"{base}/{oid}")).json()["events"]]
    assert {"criada", "validada", "evidencia", "arquivada"} <= set(kinds)


async def _document(admin_engine: AsyncEngine, condo: uuid.UUID, text: str) -> uuid.UUID:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        doc = Document(
            id=uuid.uuid4(),
            condominium_id=condo,
            doc_type=DocumentType.APOLICE.value,
            storage_key=f"cond/{condo}/apolice-{uuid.uuid4().hex[:6]}",
            sha256=uuid.uuid4().hex * 2,
            original_filename="apolice.pdf",
            mime_type="application/pdf",
            origin="upload",
            extraction_status="done",
            extracted={},
            field_confidence={},
            needs_review=False,
            review_reasons=[],
            text_content=text,
            page_count=1,
        )
        s.add(doc)
        return doc.id


async def _read(worker_engine: AsyncEngine, evidence_id: str) -> None:
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await svc.read_validity_job(s, {"evidence_id": evidence_id})


async def test_document_dates_are_read_and_confirmed_by_a_person(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/compliance"
    await login(client, mailer, SINDICA_ACACIAS)
    oid = (
        await client.post(base, json={"name": "Seguro do gerador (fictício)", "category": "seguro"})
    ).json()["id"]
    await client.post(
        f"{base}/{oid}/validation",
        json={"applies": True, "reason": "Exigência da apólice principal"},
    )
    text = "APÓLICE 77\nVigência: das 24h de 10/03/2026 às 24h de 10/03/2027."
    doc = await _document(admin_engine, acacias, text)

    # Without the model (replay without a recording): the dates written in the text.
    ev = (await client.post(f"{base}/{oid}/evidence", json={"document_id": str(doc)})).json()
    assert ev["source"] == "lendo"
    assert (await client.get(f"{base}/{oid}")).json()["situation"]["code"] == "lendo"
    await _read(worker_engine, ev["id"])
    detail = (await client.get(f"{base}/{oid}")).json()
    latest = detail["evidence"][0]
    assert (latest["source"], latest["confirmed"], latest["valid_until"]) == (
        "texto",
        False,
        "2027-03-10",
    )
    assert detail["situation"]["to_confirm"] and detail["pending_confirmation"] == latest["id"]
    r = await client.post(
        f"{base}/{oid}/evidence/{latest['id']}/confirm", json={"valid_until": "2027-03-10"}
    )
    assert r.status_code == 200
    detail = (await client.get(f"{base}/{oid}")).json()
    assert detail["evidence"][0]["confirmed"] and detail["pending_confirmation"] is None
    assert detail["situation"]["to_confirm"] is None

    # With the model: a date it returns must be written in the document.
    replies = iter(
        [
            svc.ValidityReading(
                validade="2027-03-10", emissao="2026-03-10", trecho="Vigência", confidence=0.9
            ),
            svc.ValidityReading(validade="2028-01-01", confidence=0.9),  # not in the text
        ]
    )

    async def fake_call(_session: Any, _req: Any) -> LLMResult[svc.ValidityReading]:
        return LLMResult(output=next(replies), model="fake", replayed=True)

    monkeypatch.setattr("app.llm.client.call_structured", fake_call)
    for expected in ("ia", "texto"):
        ev = (await client.post(f"{base}/{oid}/evidence", json={"document_id": str(doc)})).json()
        await _read(worker_engine, ev["id"])
        latest = (await client.get(f"{base}/{oid}")).json()["evidence"][0]
        assert latest["source"] == expected
        assert latest["valid_until"] == "2027-03-10"  # never 2028-01-01

    # A person typed the dates while the reading waited: the reading changes nothing.
    ev = (await client.post(f"{base}/{oid}/evidence", json={"document_id": str(doc)})).json()
    await client.post(f"{base}/{oid}/evidence", json={"valid_until": "2027-04-01"})
    await _read(worker_engine, ev["id"])
    latest = (await client.get(f"{base}/{oid}")).json()["evidence"][0]
    assert (latest["source"], latest["valid_until"]) == ("pessoa", "2027-04-01")

    # A document from another condominium cannot be linked.
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    other = await _document(admin_engine, mirante, text)
    r = await client.post(f"{base}/{oid}/evidence", json={"document_id": str(other)})
    assert r.status_code == 422

    async with sessionmaker_for(admin_engine)() as s:
        n = await s.scalar(
            select(ComplianceEvidence.id)
            .where(ComplianceEvidence.obligation_id == uuid.UUID(oid))
            .limit(1)
        )
        assert n is not None
