"""D95 (LF4): delegated document requests — the síndico asks, the CondoOS makes a link and a
text (nothing is sent by the system), the recipient uploads without a login. Covers the
whole flow, permissions, tenant isolation, unusable links, limits, triage and the automatic
attendance of an invoice item."""

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.core.time import utcnow
from app.db.models import (
    AppUser,
    Contract,
    DelegationLink,
    DelegationRequest,
    Document,
    Expense,
)
from app.db.session import sessionmaker_for
from app.delegation import create, issue_link, refresh
from app.enrichment.suppliers import get_or_create_supplier
from app.onboarding import onboard
from tests.helpers import (
    ADMIN_CONDOOS,
    CONSELHEIRO_ACACIAS,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)
from tests.test_onboarding import _spec

CORPUS = Path(__file__).parent / "fixtures" / "corpus"


def _pdf(tag: str) -> bytes:
    return (CORPUS / "17_recibo.pdf").read_bytes() + f"\n% {tag}\n".encode()


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "recipient_name": "Atlântida Gestão (fictícia)",
        "recipient_role": "administradora",
        "items": [
            {"key": "balancete", "kind": "balancete", "label": "Balancete do último mês"},
            {"label": "Recibo da limpeza da caixa de gordura"},
        ],
        "scope": "Documentos para a implantação do CondoOS.",
        "due_date": (date.today() + timedelta(days=5)).isoformat(),
    }
    body.update(over)
    return body


async def _upload(client: httpx.AsyncClient, token: str, *files: tuple[str, bytes]) -> Any:
    return await client.post(
        f"/public/delegations/{token}/files",
        files=[("files", (name, data, "application/pdf")) for name, data in files],
    )


async def test_full_flow_nothing_sent_by_the_system(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    base = f"/condominiums/{acacias}/delegations"
    await login(client, mailer, SINDICA_ACACIAS)
    suggestions = (await client.get(f"{base}/suggestions")).json()
    assert any(s["key"] == "balancete" for s in suggestions)

    r = await client.post(base, json=_body())
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "autorizado"  # the síndico prepared it: authorised at once
    mailer.sent.clear()
    r = await client.post(f"{base}/{req['id']}/link", json={"days": 7})
    assert r.status_code == 200
    link = r.json()
    assert mailer.sent == []  # nothing leaves the system
    assert link["url"] in link["text"] and "Balancete do último mês" in link["text"]
    token = link["url"].rsplit("/", 1)[1]
    assert link["request"]["status"] == "aguardando_envio"

    async with sessionmaker_for(admin_engine)() as s:
        stored = await s.scalar(
            select(DelegationLink).where(DelegationLink.request_id == uuid.UUID(req["id"]))
        )
        assert stored is not None and token not in stored.token_hash  # only the hash
        row = await s.get(DelegationRequest, uuid.UUID(req["id"]))
        assert row is not None and not hasattr(row, "recipient_email")

    await client.post("/auth/logout")  # the recipient has no session
    view = (await client.get(f"/public/delegations/{token}")).json()
    assert view["condominium"].endswith("Jardim das Acácias")
    assert view["items"][0]["label"] == "Balancete do último mês"
    assert set(view) == {
        "condominium",
        "recipient_name",
        "items",
        "due_date",
        "expires_at",
        "remaining_files",
    }

    pdf = _pdf(f"pedido-{uuid.uuid4()}")
    active = (
        (CORPUS / "17_recibo.pdf")
        .read_bytes()
        .replace(b"%%EOF", b"9 0 obj << /S /JavaScript /JS (x) >> endobj\n%%EOF")
    )
    r = await _upload(client, token, ("recibo.pdf", pdf), ("ativo.pdf", active))
    assert r.status_code == 200
    first, refused = r.json()
    assert first["error"] is None and not first["duplicate"]
    assert "conteúdo ativo" in refused["error"]
    again = (await _upload(client, token, ("de-novo.pdf", pdf))).json()[0]
    assert again["duplicate"] is True

    await login(client, mailer, SINDICA_ACACIAS)
    detail = (await client.get(f"{base}/{req['id']}")).json()
    assert detail["status"] == "recebendo"
    assert [d["filename"] for d in detail["documents"]] == ["recibo.pdf"]
    kinds = [e["kind"] for e in detail["events"]]
    assert kinds[:3] == ["criado", "autorizado", "link_gerado"]
    assert "arquivo_recusado" in kinds and kinds.count("arquivo_recebido") == 2
    async with sessionmaker_for(admin_engine)() as s:
        doc = await s.scalar(
            select(Document).where(Document.delegation_request_id == uuid.UUID(req["id"]))
        )
        assert doc is not None and doc.origin == "pedido" and doc.condominium_id == acacias

    assert (await client.post(f"{base}/{req['id']}/shared")).status_code == 200
    for item in detail["items"]:
        r = await client.post(f"{base}/{req['id']}/items/{item['key']}/attend")
        assert r.status_code == 200
    final = r.json()
    assert final["status"] == "concluido" and final["progress"] == {"attended": 2, "total": 2}
    await client.post("/auth/logout")
    assert (await client.get(f"/public/delegations/{token}")).status_code == 404


async def test_permissions_and_isolation(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    base = f"/condominiums/{acacias}/delegations"

    await login(client, mailer, CONSELHEIRO_ACACIAS)
    assert (await client.post(base, json=_body())).status_code == 403

    await login(client, mailer, ADMIN_CONDOOS)  # the CondoOS team only drafts
    draft = (await client.post(base, json=_body())).json()
    assert draft["status"] == "rascunho" and draft["can"]["authorize"] is False
    assert (await client.post(f"{base}/{draft['id']}/link", json={})).status_code == 403

    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"{base}/{draft['id']}")).status_code == 404

    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.post(f"{base}/{draft['id']}/link", json={})).status_code == 409
    assert (await client.post(f"{base}/{draft['id']}/authorize")).status_code == 200
    token = (
        (await client.post(f"{base}/{draft['id']}/link", json={})).json()["url"].rsplit("/", 1)[1]
    )

    # The link writes only into its own condominium.
    await client.post("/auth/logout")
    r = await _upload(client, token, ("a.pdf", _pdf(f"iso-{uuid.uuid4()}")))
    assert r.status_code == 200 and r.json()[0]["error"] is None
    async with sessionmaker_for(admin_engine)() as s:
        docs = list(
            await s.scalars(
                select(Document.condominium_id).where(
                    Document.delegation_request_id == uuid.UUID(draft["id"])
                )
            )
        )
    assert docs == [acacias] and mirante not in docs

    # Unknown, limited, paused, expired and revoked links: the same 404 or a refusal.
    assert (await client.get("/public/delegations/nao-existe")).status_code == 404
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(DelegationLink)
            .where(DelegationLink.request_id == uuid.UUID(draft["id"]))
            .values(max_files=1)
        )
    r = await _upload(client, token, ("b.pdf", _pdf(f"lim-{uuid.uuid4()}")))
    assert r.json()[0]["error"] == "Limite de arquivos deste link atingido."

    await login(client, mailer, SINDICA_ACACIAS)
    pauses = f"/condominiums/{acacias}/automation-pauses"
    r = await client.post(
        pauses, json={"automation_type": "delegation.link", "reason": "Teste de pausa do link"}
    )
    assert r.status_code == 201, r.text
    assert (await client.get(f"/public/delegations/{token}")).status_code == 404
    pause_id = next(
        p["id"] for p in r.json()["active"] if p["automation_type"] == "delegation.link"
    )
    await client.post(f"{pauses}/{pause_id}/resume")
    assert (await client.get(f"/public/delegations/{token}")).status_code == 200

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        await s.execute(
            update(DelegationLink)
            .where(DelegationLink.request_id == uuid.UUID(draft["id"]))
            .values(expires_at=utcnow() - timedelta(minutes=1))
        )
    assert (await client.get(f"/public/delegations/{token}")).status_code == 404
    detail = (await client.get(f"{base}/{draft['id']}")).json()
    assert detail["status"] == "expirado"  # nothing deleted: the file received stays
    assert len(detail["documents"]) == 1

    other = (await client.post(base, json=_body())).json()
    token2 = (
        (await client.post(f"{base}/{other['id']}/link", json={})).json()["url"].rsplit("/", 1)[1]
    )
    assert (await client.post(f"{base}/{other['id']}/revoke")).status_code == 200
    assert (await client.get(f"/public/delegations/{token2}")).status_code == 404


async def test_invoice_item_attended_when_it_arrives(admin_engine: AsyncEngine) -> None:
    today = date(2026, 11, 20)
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await onboard(s, _spec(management_company_name=None))
        user = await s.scalar(select(AppUser).limit(1))
        assert user is not None
        supplier = await get_or_create_supplier(
            s, generate_cnpj(random.Random(f"del-{condo.id}")), "Limpeza Fictícia Ltda"
        )
        contract = Contract(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            supplier_id=supplier.id,
            object="Limpeza das áreas comuns",
            scope_items=[],
            monthly_value=Decimal("4800.00"),
            adjustment_index="IPCA",
            billing_frequency_months=1,
            start_date=date(2026, 1, 1),
        )
        s.add(contract)
        await s.flush()
        req = await create(
            s,
            condominium_id=condo.id,
            user_id=user.id,
            recipient_name="Limpeza Fictícia",
            recipient_role="fornecedor",
            items=[
                {
                    "key": f"nf:{contract.id}:2026-10",
                    "kind": "nota_fiscal",
                    "label": "Nota fiscal de 10/2026",
                    "contract_id": str(contract.id),
                    "competence": "2026-10",
                }
            ],
            scope="",
            due_date=today + timedelta(days=3),
            today=today,
            authorize_now=True,
        )
        await issue_link(s, req, user.id)
        await refresh(s, req, today)
        assert req.status == "aguardando_envio"  # not arrived yet: nothing assumed

        s.add(
            Expense(
                id=uuid.uuid4(),
                condominium_id=condo.id,
                supplier_id=supplier.id,
                contract_id=contract.id,
                competence=date(2026, 10, 1),
                issue_date=date(2026, 10, 5),
                amount=Decimal("4800.00"),
                category="limpeza",
                description="Limpeza 10/2026",
                invoice_number="901",
            )
        )
        await s.flush()
        await refresh(s, req, today)
        assert req.items[0]["attended_by"] == "automatico"
        assert req.status == "concluido"
        await s.rollback()
