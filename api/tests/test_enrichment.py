"""Supplier and index enrichment, with the HTTP APIs replaced by an in-process transport."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.time import utcnow
from app.db.enums import AdjustmentIndex
from app.db.models import Supplier
from app.db.session import sessionmaker_for
from app.enrichment import indices
from app.enrichment.suppliers import (
    BrasilApiProvider,
    SupplierLookupUnavailable,
    enrich_supplier,
    format_cnae,
    parse_brasilapi,
)

CNPJ = "45723174000110"  # fictitious

# Shape from the official BrasilAPI OpenAPI (cnpj.json); values are invented.
PAYLOAD: dict[str, Any] = {
    "cnpj": CNPJ,
    "razao_social": "EMPRESA FICTICIA DE LIMPEZA LTDA",
    "nome_fantasia": "LIMPA FICTICIA",
    "cnae_fiscal": 8121400,
    "cnae_fiscal_descricao": "Limpeza em prédios e em domicílios",
    "cnaes_secundarios": [
        {"codigo": 8129000, "descricao": "Atividades de limpeza não especificadas"}
    ],
    "situacao_cadastral": 8,
    "descricao_situacao_cadastral": "BAIXADA",
    "data_situacao_cadastral": "2026-05-10",
    "qsa": [
        {
            "nome_socio": "FULANA DE TAL FICTICIA",
            "cnpj_cpf_do_socio": "***123456**",
            "qualificacao_socio": "Sócio-Administrador",
        },
        {
            "nome_socio": "HOLDING FICTICIA SA",
            "cnpj_cpf_do_socio": "11222333000181",
            "qualificacao_socio": "Sócio",
        },
    ],
}


def test_parse_brasilapi_masks_cpf_and_formats_cnae() -> None:
    record = parse_brasilapi(PAYLOAD)
    assert record.cnae_main == {
        "code": "8121-4/00",
        "description": "Limpeza em prédios e em domicílios",
    }
    assert record.cnae_secondary[0]["code"] == "8129-0/00"
    assert record.registration_status == "BAIXADA"
    assert record.registration_status_date == date(2026, 5, 10)
    assert record.partners[0]["cpf_masked"] == "***.123.456-**"
    assert record.partners[1]["cpf_masked"] == "11222333000181"  # company partner: public CNPJ
    assert format_cnae(4329103) == "4329-1/03"


def _client(responses: list[httpx.Response]) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return responses.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), seen


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def instant(_: float) -> None:
        return None

    monkeypatch.setattr("app.enrichment.suppliers.asyncio.sleep", instant)
    monkeypatch.setattr("app.enrichment.indices.asyncio.sleep", instant)


async def test_brasilapi_retries_then_succeeds() -> None:
    client, seen = _client(
        [httpx.Response(503), httpx.Response(429), httpx.Response(200, json=PAYLOAD)]
    )
    record = await BrasilApiProvider(client).lookup(CNPJ)
    assert record is not None and record.legal_name == "EMPRESA FICTICIA DE LIMPEZA LTDA"
    assert len(seen) == 3 and seen[0].url.path.endswith(f"/cnpj/v1/{CNPJ}")


async def test_brasilapi_gives_up_and_404_is_not_found() -> None:
    client, _ = _client([httpx.Response(503)] * 4)
    with pytest.raises(SupplierLookupUnavailable):
        await BrasilApiProvider(client).lookup(CNPJ)
    client, _ = _client([httpx.Response(404, json={"message": "não encontrado"})])
    assert await BrasilApiProvider(client).lookup(CNPJ) is None


async def test_enrich_supplier_cache_and_not_found(worker_engine: AsyncEngine) -> None:
    supplier = Supplier(cnpj=CNPJ, legal_name="Nome lido na nota", cnae_secondary=[], partners=[])
    client, seen = _client([httpx.Response(200, json=PAYLOAD)])
    assert await enrich_supplier(None, supplier, BrasilApiProvider(client))  # type: ignore[arg-type]
    assert supplier.registration_status == "BAIXADA" and supplier.enrichment_source == "brasilapi"
    # Fresh for 30 days: no new call.
    assert not await enrich_supplier(None, supplier, BrasilApiProvider(client))  # type: ignore[arg-type]
    assert len(seen) == 1
    # Stale + not found: data is kept and the problem recorded.
    supplier.enriched_at = utcnow() - timedelta(days=31)
    client, _ = _client([httpx.Response(404)])
    assert not await enrich_supplier(None, supplier, BrasilApiProvider(client))  # type: ignore[arg-type]
    assert supplier.legal_name == "EMPRESA FICTICIA DE LIMPEZA LTDA"
    assert supplier.enrichment_error == "nao_encontrado"


async def test_bcb_series_fetch_and_store(worker_engine: AsyncEngine) -> None:
    body = [{"data": "01/08/2026", "valor": "-0.32"}, {"data": "01/09/2026", "valor": "0.82"}]
    client, seen = _client([httpx.Response(500), httpx.Response(200, json=body)])
    values = await indices.fetch_series(
        AdjustmentIndex.IPCA, date(2026, 8, 1), date(2026, 9, 30), client
    )
    assert values == {date(2026, 8, 1): Decimal("-0.32"), date(2026, 9, 1): Decimal("0.82")}
    assert "bcdata.sgs.433" in str(seen[-1].url) and "dataInicial=01/08/2026" in str(seen[-1].url)
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        assert await indices.store_values(s, AdjustmentIndex.IPCA, values, "teste") == 2
        table = await indices.load_index_table(s)
    assert table["IPCA"][date(2026, 9, 1)] == Decimal("0.82")
