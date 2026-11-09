"""D119: the "Novo condomínio" form checks the condominium's CNPJ at the Receita (BrasilAPI)
before saving: name, situation, legal nature and address. Nothing is stored."""

import random
from datetime import date
from typing import Any

import httpx
import pytest

from app.auth.mailer import MemoryMailer
from app.core.br import generate_cnpj
from app.enrichment import suppliers
from app.enrichment.suppliers import SupplierRecord, parse_brasilapi
from tests.helpers import ADMIN_CONDOOS, GERENTE, SINDICA_ACACIAS, login

CNPJ = generate_cnpj(random.Random("cnpj-lookup-condo"))


def test_registry_record_keeps_nature_and_address() -> None:
    record = parse_brasilapi(
        {
            "cnpj": CNPJ,
            "razao_social": "CONDOMINIO EDIFICIO FICTICIO",
            "descricao_situacao_cadastral": "ATIVA",
            "data_situacao_cadastral": "2005-03-10",
            "codigo_natureza_juridica": 3085,
            "natureza_juridica": "Condomínio Edilício",
            "descricao_tipo_de_logradouro": "RUA",
            "logradouro": "DAS FLORES",
            "numero": "100",
            "bairro": "CENTRO",
            "municipio": "SAO PAULO",
            "uf": "SP",
            "cep": "01001-000",
        }
    )
    assert record.legal_nature_code == 3085 and record.legal_nature == "Condomínio Edilício"
    assert record.address == {
        "street": "RUA DAS FLORES",
        "number": "100",
        "district": "CENTRO",
        "city": "SAO PAULO",
        "state": "SP",
        "zip": "01001000",
    }


class DownProvider:
    async def lookup(self, cnpj: str) -> SupplierRecord | None:
        raise suppliers.SupplierLookupUnavailable("HTTP 503")


class FakeProvider:
    def __init__(self, record: SupplierRecord | None) -> None:
        self.record = record

    async def lookup(self, cnpj: str) -> SupplierRecord | None:
        return self.record


async def test_lookup_before_registering(
    client: httpx.AsyncClient, mailer: MemoryMailer, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"/portfolio/cnpj/{CNPJ}"
    # Never call the real Receita from tests: a valid random CNPJ may belong to a real company.
    fake: dict[str, Any] = {"provider": DownProvider()}
    monkeypatch.setattr(suppliers, "get_provider", lambda: fake["provider"])
    # The síndica does not register condominiums.
    await login(client, mailer, SINDICA_ACACIAS)
    assert (await client.get(url)).status_code == 403

    await login(client, mailer, GERENTE)
    assert (await client.get("/portfolio/cnpj/11111111111111")).status_code == 422
    # The Receita is down: "unavailable", and saving still works.
    body = (await client.get(url)).json()
    assert body == {**body, "available": False, "found": False}

    record = SupplierRecord(
        cnpj=CNPJ,
        legal_name="CONDOMINIO EDIFICIO FICTICIO",
        trade_name=None,
        cnae_main=None,
        registration_status="ATIVA",
        registration_status_date=date(2005, 3, 10),
        legal_nature_code=3085,
        legal_nature="Condomínio Edilício",
        address={"street": "RUA DAS FLORES", "number": "100", "city": "SAO PAULO", "state": "SP"},
    )
    fake["provider"] = FakeProvider(record)
    body = (
        await client.get(f"/portfolio/cnpj/{CNPJ[:2]}.{CNPJ[2:5]}.{CNPJ[5:8]}{CNPJ[8:]}")
    ).json()
    assert body["available"] and body["found"] and body["is_condominium"] is True
    assert body["legal_name"] == "CONDOMINIO EDIFICIO FICTICIO" and body["status"] == "ATIVA"
    assert body["address"]["city"] == "SAO PAULO"

    # A company that is not a condominium is flagged, not refused.
    fake["provider"] = FakeProvider(
        SupplierRecord(
            cnpj=CNPJ,
            legal_name="LOJA FICTICIA LTDA",
            trade_name=None,
            cnae_main=None,
            registration_status="BAIXADA",
            legal_nature_code=2062,
        )
    )
    await login(client, mailer, ADMIN_CONDOOS)
    body = (await client.get(url)).json()
    assert body["is_condominium"] is False and body["status"] == "BAIXADA"

    fake["provider"] = FakeProvider(None)
    assert (await client.get(url)).json()["found"] is False
