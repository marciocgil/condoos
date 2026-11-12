"""Implantation by the síndico (D128): who may start, the eight items computed from records,
the mandate, the adhesion term (append only) and the approval limit with its source."""

import random
import uuid

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.core.time import local_today, utcnow
from app.db.models import AdhesionTerm, AppUser, AuditLog, Document, Membership
from app.db.session import sessionmaker_for
from app.implantation import TOTAL, essentials
from app.main import create_app
from tests.helpers import CONSELHEIRO_ACACIAS, SINDICA_ACACIAS, condo_id, login
from tests.test_audit import _new_condo


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://t")


async def test_new_condominium_starts_with_only_its_data(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        out = await essentials(s, condo, local_today(condo.timezone))
        done = {i["key"] for i in out["items"] if i["done"]}
        assert done == {"dados", "alcada"}  # the test condominium has a limit already
        assert out["total"] == TOTAL and out["percent"] == 25 and not out["complete"]
        assert out["next"]["key"] == "sindico"
        await s.rollback()


async def test_seed_acacias_is_ready_and_mirante_is_implanting(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s:
        from app.db.models import Condominium

        for slug, complete in (("jardim-das-acacias", True), ("mirante-do-vale", False)):
            condo = await s.scalar(select(Condominium).where(Condominium.slug == slug))
            assert condo is not None
            out = await essentials(s, condo, local_today(condo.timezone))
            assert out["complete"] is complete, (slug, out["items"])


async def test_sindico_implants_a_condominium_step_by_step(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    cnpj = generate_cnpj(random.Random(uuid.uuid4().hex))
    async with _client() as ana, _client() as bruno:
        await login(bruno, mailer, CONSELHEIRO_ACACIAS)
        assert (await bruno.get("/implantation/eligibility")).json() == {"can_implant": False}
        body = {
            "cnpj": cnpj,
            "name": "Condomínio Teste Implantação",
            "address": "Rua Fictícia, 10",
            "units": 32,
        }
        assert (await bruno.post("/implantation", json=body)).status_code == 403

        await login(ana, mailer, SINDICA_ACACIAS)
        assert (await ana.get("/implantation/eligibility")).json() == {"can_implant": True}
        r = await ana.post("/implantation", json=body)
        assert r.status_code == 201, r.text
        new = r.json()["id"]
        assert (await ana.post("/implantation", json=body)).status_code == 422  # same CNPJ
        base = f"/condominiums/{new}/implantation"
        imp = (await ana.get(base)).json()
        assert imp["done"] == 1 and imp["next"]["key"] == "sindico" and imp["can_manage"]

        r = await ana.put(
            f"{base}/mandate", json={"term_start": "2026-03-01", "term_end": "2028-02-29"}
        )
        assert r.status_code == 200, r.text
        bad = await ana.put(
            f"{base}/mandate", json={"term_start": "2026-03-01", "term_end": "2025-01-01"}
        )
        assert bad.status_code == 422
        assert (
            await ana.put(f"{base}/limit", json={"value": "3000", "source": "curta"})
        ).status_code == 422
        ok = await ana.put(
            f"{base}/limit", json={"value": "3.000,00", "source": "Convenção, artigo 25"}
        )
        assert ok.status_code == 200 and ok.json()["default"] == "3000.00"
        again = await ana.put(
            f"{base}/limit", json={"value": "9000", "source": "Convenção, artigo 25"}
        )
        assert again.status_code == 422  # a limit in force changes elsewhere

        async with sessionmaker_for(admin_engine)() as s, s.begin():
            doc = Document(
                id=uuid.uuid4(),
                condominium_id=uuid.UUID(new),
                doc_type="outro",
                storage_key=f"cond/{new}/termo.pdf",
                sha256=uuid.uuid4().hex * 2,
                original_filename="termo.pdf",
                mime_type="application/pdf",
                origin="upload",
                extraction_status="done",
                extracted={},
                field_confidence={},
                needs_review=False,
                review_reasons=[],
            )
            s.add(doc)
        r = await ana.post(f"{base}/term", json={"document_id": str(doc.id)})
        assert r.status_code == 201 and r.json()["version"] == "termo_adesao_v1"
        other = await condo_id(admin_engine, "mirante-do-vale")
        assert (await ana.get(f"/condominiums/{other}/implantation")).status_code == 404

        imp = (await ana.get(base)).json()
        done = {i["key"] for i in imp["items"] if i["done"]}
        assert {"dados", "autorizacao", "alcada"} <= done and "sindico" not in done  # no ata yet
        day = (await ana.get(f"/condominiums/{new}/day")).json()
        assert day["implemented"] is False and day["implantation"]["done"] == imp["done"]

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        assert await s.scalar(
            select(AdhesionTerm.id).where(AdhesionTerm.condominium_id == uuid.UUID(new))
        )
        assert await s.scalar(
            select(AuditLog.id).where(
                AuditLog.action == "implantation.limit", AuditLog.condominium_id == uuid.UUID(new)
            )
        )
        # Shared seed: Ana goes back to one condominium.
        ana_id = await s.scalar(select(AppUser.id).where(AppUser.email == SINDICA_ACACIAS))
        await s.execute(
            update(Membership)
            .where(Membership.user_id == ana_id, Membership.condominium_id == uuid.UUID(new))
            .values(revoked_at=utcnow())
        )
