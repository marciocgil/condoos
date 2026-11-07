"""LF3-c (LB-032, LB-033; D96): the validation centre and the batch upload's follow-up.

The exception queue becomes the validation centre: documents to confirm, ambiguous matches,
findings under review and, now, open data conflicts, each with the money it is about,
most money first. Each person sees only what they may act on. The batch upload follows each
file in words: reading, read, for review, could not read.
"""

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.enums import PlatformRole
from app.db.models import AppUser, CondoAssignment, Condominium, Document
from app.db.session import sessionmaker_for
from app.extraction.pipeline import process_document
from app.routers.documents import _status
from tests.helpers import ADMIN_CONDOOS, GERENTE, SINDICA_MIRANTE, login
from tests.test_data_issues import _conflicted, _scan
from tests.test_launch import _client, _contract_doc


async def _assign_admin(admin_engine: AsyncEngine, cid: uuid.UUID) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        fabio = await s.scalar(select(AppUser.id).where(AppUser.email == ADMIN_CONDOOS))
        assert fabio is not None
        s.add(
            CondoAssignment(
                condominium_id=cid,
                user_id=fabio,
                platform_role=PlatformRole.CONDOOS_ADMIN.value,
                reason="Teste da Central de Validação",
            )
        )


async def test_queue_has_conflicts_and_is_sorted_by_money(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, email, _, _ = await _conflicted(admin_engine)
    [issue] = await _scan(admin_engine, condo.id)
    big = await _contract_doc(admin_engine, condo.id, needs_review=True)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        doc = await s.get(Document, big)
        assert doc is not None
        doc.extracted = {"valor_mensal": "12480.00"}
    await _assign_admin(admin_engine, condo.id)

    async with _client() as c:
        await login(c, mailer, ADMIN_CONDOOS)
        items = (await c.get("/queue")).json()
        counts = (await c.get("/queue/count")).json()
    mine = [i for i in items if i["condominium_id"] == str(condo.id)]
    assert [(i["kind"], Decimal(i["value_at_stake"])) for i in mine] == [
        ("extracao", Decimal("12480.00")),
        ("conflito", Decimal("500.00")),  # 4.500,00 in the document × 4.000,00 registered
    ]
    assert mine[1]["id"] == str(issue.id)
    assert "Documento do contrato: 4500.00" in mine[1]["detail"]
    values = [Decimal(i["value_at_stake"]) for i in items]
    assert values == sorted(values, reverse=True)  # most money first, across condominiums
    assert counts["conflito"] >= 1 and counts["total"] == len(items)

    # The síndica of this condominium resolves conflicts: she sees them, and nothing else
    # of the queue (she does not correct extractions).
    async with _client() as c:
        await login(c, mailer, email)
        kinds = {i["kind"] for i in (await c.get("/queue")).json()}
    assert kinds == {"conflito"}


async def test_who_does_not_resolve_does_not_see_conflicts(
    mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    condo, _, _, _ = await _conflicted(admin_engine)
    await _scan(admin_engine, condo.id)

    async def sees(email: str) -> bool:
        async with _client() as c:
            await login(c, mailer, email)
            items = (await c.get("/queue")).json()
        return any(i["condominium_id"] == str(condo.id) and i["kind"] == "conflito" for i in items)

    # Onboarded with a management company, which reviews by default: the manager sees it.
    assert await sees(GERENTE)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        stored = await s.get(Condominium, condo.id)
        assert stored is not None
        stored.management_company_reviews = False  # the condominium takes it back (D74)
    assert not await sees(GERENTE)
    assert not await sees(SINDICA_MIRANTE)  # another condominium's síndica


async def test_batch_upload_follow_up(
    mailer: MemoryMailer, admin_engine: AsyncEngine, worker_engine: AsyncEngine
) -> None:
    condo, email, _, _ = await _conflicted(admin_engine)
    base = f"/condominiums/{condo.id}/documents"
    corrupt = b"%PDF-1.7\n" + b"\x00not a real pdf\x00" * 30
    async with _client() as c:
        await login(c, mailer, email)
        sent = (
            await c.post(
                base,
                files=[
                    ("files", ("ilegivel.pdf", corrupt, "application/pdf")),
                    ("files", ("vazio.pdf", b"", "application/pdf")),
                ],
            )
        ).json()
        doc_id = sent[0]["document_id"]
        assert sent[1]["document_id"] is None  # nothing to follow: refused at the door
        other = uuid.uuid4()  # unknown or another condominium's: simply not returned
        r = await c.get(f"{base}/status", params={"ids": f"{doc_id},{other}"})
        assert r.status_code == 200, r.text
        assert [(d["filename"], d["status"]) for d in r.json()] == [("ilegivel.pdf", "lendo")]
        assert (await c.get(f"{base}/status", params={"ids": "nao-e-id"})).status_code == 422

    async with sessionmaker_for(worker_engine)() as s, s.begin():
        await process_document(s, {"document_id": doc_id})
    async with _client() as c:
        await login(c, mailer, email)
        [after] = (await c.get(f"{base}/status", params={"ids": doc_id})).json()
    assert after["status"] == "revisao" and after["detail"].startswith("Para revisão:")


def test_status_words() -> None:
    def doc(**over: object) -> Document:
        base: dict[str, object] = {
            "id": uuid.uuid4(),
            "original_filename": "nota.pdf",
            "doc_type": "nfse",
            "extraction_status": "done",
            "needs_review": False,
            "review_reasons": [],
            "reviewed_at": None,
        }
        base.update(over)
        return Document(**base)

    assert _status(doc(extraction_status="processing")).status == "lendo"
    assert _status(doc(extraction_status="failed")).status == "falhou"
    assert _status(doc()).status == "lido"
    review = _status(
        doc(extraction_status="needs_review", needs_review=True, review_reasons=["Valor ilegível"])
    )
    assert (review.status, review.detail) == ("revisao", "Para revisão: Valor ilegível")
