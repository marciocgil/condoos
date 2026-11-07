"""LF4 (F02, ADR-L04, ADR-L06; D97): a request for documents with a send-only link.

Gate LG4: the síndico and a management company simulated end to end; revocation is
immediate; a link of condominium A never writes in B; nothing is sent by the system (the
síndico gets a ready text); files from a link always go to a person before use.
"""

import hashlib
import random
import uuid
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

import app.delegation as delegation
from app.auth.mailer import MemoryMailer
from app.core.time import utcnow
from app.db.models import AuditLog, DelegationRequest, DelegationUploadToken, Document
from app.db.session import sessionmaker_for
from app.extraction.pipeline import process_document
from app.main import create_app
from corpus.generate import Pdf
from tests.helpers import ADMIN_CONDOOS, CONSELHEIRO_ACACIAS, SINDICA_MIRANTE, condo_id, login
from tests.test_launch import _new_condo

BODY = {
    "recipient_name": "Administradora Fictícia",
    "recipient_email": "contato@administradora.example.com",
    "scope": "Contratos vigentes e notas de outubro de 2026",
    "items": ["Contrato da portaria", "Contrato da limpeza", "Notas de outubro"],
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


def _pdf(tag: str) -> bytes:
    p = Pdf()
    p.text("CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE PORTARIA", 11, True, gap=22)
    p.text(f"Documento enviado pelo link de teste {tag}.", 9)
    return p.bytes()


async def _authorized(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> tuple[uuid.UUID, str, str, dict[str, Any]]:
    """A new condominium, its síndica, a request and an authorized link."""
    condo, email = await _new_condo(admin_engine)
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(f"/condominiums/{condo.id}/delegations", json=BODY)
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "rascunho"
        rid = r.json()["id"]
        r = await c.post(f"/condominiums/{condo.id}/delegations/{rid}/authorize")
        assert r.status_code == 200, r.text
        out = r.json()
    token = out["link"].rsplit("/", 1)[1]
    return condo.id, email, token, out


async def test_sindica_delegates_and_the_administradora_sends(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    cid, email, token, out = await _authorized(mailer, admin_engine)
    rid = out["request"]["id"]
    assert out["request"]["status"] == "link_gerado"
    # Nothing is sent: the síndica gets the text to send through her own channel.
    assert out["link"] in out["message"] and "Contrato da portaria" in out["message"]
    assert "não mostra nenhum dado" in out["message"]
    assert not [m for m in mailer.sent if "enviar-documentos" in m.body]
    async with sessionmaker_for(admin_engine)() as s:  # only the hash is stored
        hashes = (
            await s.scalars(
                select(DelegationUploadToken.token_hash).where(
                    DelegationUploadToken.request_id == uuid.UUID(rid)
                )
            )
        ).all()
    assert hashes == [hashlib.sha256(token.encode()).hexdigest()]

    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(f"/condominiums/{cid}/delegations/{rid}/shared")
        assert r.json()["status"] == "compartilhado"

    # The administradora, without an account.
    async with _client() as anon:
        info = (await anon.get(f"/submit/{token}")).json()
        assert info["items"] == BODY["items"] and info["files_received"] == 0
        assert "recipient_email" not in info
        r = await anon.post(
            f"/submit/{token}",
            files=[
                ("files", ("contrato-portaria.pdf", _pdf("a"), "application/pdf")),
                ("files", ("extrato.ofx", b"OFXHEADER:100\nDATA:OFXSGML\n", "text/plain")),
                ("files", ("vazio.pdf", b"", "application/pdf")),
            ],
        )
        assert r.status_code == 201, r.text
        sent = r.json()
        assert [x["accepted"] for x in sent] == [True, False, False]
        assert "Tipo não aceito por este link" in sent[1]["error"]  # no bank files (ADR-L06)
        again = (
            await anon.post(
                f"/submit/{token}",
                files=[("files", ("copia.pdf", _pdf("a"), "application/pdf"))],
            )
        ).json()
        assert again[0]["duplicate"] is True

    async with sessionmaker_for(admin_engine)() as s:
        docs = (
            await s.scalars(
                select(Document).where(Document.delegation_request_id == uuid.UUID(rid))
            )
        ).all()
    assert len(docs) == 1 and docs[0].origin == "pedido" and docs[0].condominium_id == cid
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await process_document(s, {"document_id": str(docs[0].id)})
    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.get(Document, docs[0].id)
    assert doc is not None and doc.needs_review  # always a person before use
    assert doc.review_reasons[0] == "Recebido por link de envio: confira antes de usar."

    async with _client() as c:
        await login(c, mailer, email)
        view = (await c.get(f"/condominiums/{cid}/delegations/{rid}")).json()
        assert view["status"] == "arquivo_recebido" and view["files_received"] == 1
        assert [d["status"] for d in view["documents"]] == ["revisao"]
        r = await c.post(
            f"/condominiums/{cid}/delegations/{rid}/items", json={"done": [True, False, False]}
        )
        assert [i["done"] for i in r.json()["items"]] == [True, False, False]
        r = await c.post(f"/condominiums/{cid}/delegations/{rid}/conclude")
        assert r.json()["status"] == "concluido"
    async with _client() as anon:  # concluded: the link is gone
        assert (await anon.get(f"/submit/{token}")).status_code == 404

    async with sessionmaker_for(admin_engine)() as s:
        trail = (
            await s.scalars(
                select(AuditLog)
                .where(AuditLog.object_id == uuid.UUID(rid))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert [a.action for a in trail] == [
        "delegation.created",
        "delegation.link_created",
        "delegation.shared",
        "delegation.file_received",
        "delegation.items",
        "delegation.concluded",
    ]
    assert all("@" not in str(a.details) for a in trail)  # ids only


async def test_revocation_is_immediate_and_a_new_link_replaces_the_old(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    cid, email, first, out = await _authorized(mailer, admin_engine)
    rid = out["request"]["id"]
    async with _client() as c:
        await login(c, mailer, email)
        second = (
            (await c.post(f"/condominiums/{cid}/delegations/{rid}/authorize"))
            .json()["link"]
            .rsplit("/", 1)[1]
        )
    async with _client() as anon:
        assert (await anon.get(f"/submit/{first}")).status_code == 404  # replaced
        assert (await anon.get(f"/submit/{second}")).status_code == 200
    async with _client() as c:
        await login(c, mailer, email)
        r = await c.post(f"/condominiums/{cid}/delegations/{rid}/revoke")
        assert r.json()["status"] == "revogado"
    async with _client() as anon:
        r = await anon.post(
            f"/submit/{second}", files=[("files", ("x.pdf", _pdf("rev"), "application/pdf"))]
        )
        assert r.status_code == 404 and r.json()["detail"] == "Link inválido, vencido ou revogado."
        assert (await anon.get("/submit/nao-existe")).status_code == 404  # same answer


async def test_a_link_of_a_never_writes_in_b(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    cid_a, _, token_a, _ = await _authorized(mailer, admin_engine)
    cid_b, _, _, _ = await _authorized(mailer, admin_engine)
    async with _client() as anon:
        r = await anon.post(
            f"/submit/{token_a}", files=[("files", ("a.pdf", _pdf("ab"), "application/pdf"))]
        )
        assert r.json()[0]["accepted"]
    async with sessionmaker_for(admin_engine)() as s:
        where = (
            await s.scalars(select(Document.condominium_id).where(Document.origin == "pedido"))
        ).all()
    assert cid_a in where and cid_b not in where


async def test_expired_link(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    cid, email, token, out = await _authorized(mailer, admin_engine)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(DelegationUploadToken)
            .where(DelegationUploadToken.request_id == uuid.UUID(out["request"]["id"]))
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
    async with _client() as anon:
        assert (await anon.get(f"/submit/{token}")).status_code == 404
    async with _client() as c:
        await login(c, mailer, email)
        listed = (await c.get(f"/condominiums/{cid}/delegations")).json()
    assert listed[0]["status"] == "expirado"


async def test_limits_per_link_and_per_hour(
    mailer: MemoryMailer, admin_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, token, out = await _authorized(mailer, admin_engine)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(DelegationUploadToken)
            .where(DelegationUploadToken.request_id == uuid.UUID(out["request"]["id"]))
            .values(max_files=2)
        )
    monkeypatch.setattr(delegation, "MAX_FILES_PER_HOUR", 1)
    tag = str(random.random())
    async with _client() as anon:
        r = await anon.post(
            f"/submit/{token}",
            files=[
                ("files", ("1.pdf", _pdf(tag + "1"), "application/pdf")),
                ("files", ("2.pdf", _pdf(tag + "2"), "application/pdf")),
            ],
        )
    assert [x["accepted"] for x in r.json()] == [True, False]
    assert r.json()[1]["error"] == "Muitos envios agora. Tente em uma hora."
    monkeypatch.setattr(delegation, "MAX_FILES_PER_HOUR", 100)
    async with _client() as anon:
        r = await anon.post(
            f"/submit/{token}",
            files=[
                ("files", ("2.pdf", _pdf(tag + "2"), "application/pdf")),
                ("files", ("3.pdf", _pdf(tag + "3"), "application/pdf")),
            ],
        )
    assert [x["accepted"] for x in r.json()] == [True, False]
    assert r.json()[1]["error"] == "Este link já recebeu o máximo de arquivos."


async def test_who_may_do_what(mailer: MemoryMailer, admin_engine: AsyncEngine) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    url = f"/condominiums/{acacias}/delegations"
    async with _client() as c:  # the CondoOS admin drafts, but only the síndico authorizes
        await login(c, mailer, ADMIN_CONDOOS)
        r = await c.post(url, json=BODY)
        assert r.status_code == 201
        rid = r.json()["id"]
        assert (await c.post(f"{url}/{rid}/authorize")).status_code == 403
        assert (await c.post(f"{url}/{rid}/revoke")).status_code == 200  # tidy the seed
    async with _client() as c:
        await login(c, mailer, CONSELHEIRO_ACACIAS)
        assert (await c.get(url)).status_code == 200
        assert (await c.post(url, json=BODY)).status_code == 403
    async with _client() as c:
        await login(c, mailer, SINDICA_MIRANTE)
        assert (await c.get(url)).status_code == 404
    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.get(DelegationRequest, uuid.UUID(rid))
    assert stored is not None and stored.status == "revogado"  # kept, never deleted
