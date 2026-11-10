"""Supplier enrichment from the CNPJ registry (BrasilAPI, which serves Receita Federal data).

Response format checked against the official BrasilAPI OpenAPI document (cnpj.json):
``razao_social``, ``nome_fantasia``, ``cnae_fiscal`` (int) + ``cnae_fiscal_descricao``,
``cnaes_secundarios`` [{codigo, descricao}], ``descricao_situacao_cadastral`` ("ATIVA"...),
``data_situacao_cadastral`` (AAAA-MM-DD), ``qsa`` [{nome_socio, cnpj_cpf_do_socio,
qualificacao_socio}]. 404 = CNPJ not found; 503 = upstream unavailable (do not cache).

Partners' CPFs are stored masked only (***.456.789-**). Cache: 30 days per supplier.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.br import is_valid_cnpj, mask_cpf, only_digits
from app.core.time import utcnow
from app.db.models import Supplier

logger = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


class SupplierLookupUnavailable(Exception):
    """Temporary failure (network, 429, 5xx): try again later, cache nothing."""


@dataclass(frozen=True)
class SupplierRecord:
    cnpj: str
    legal_name: str
    trade_name: str | None
    cnae_main: dict[str, str] | None
    cnae_secondary: list[dict[str, str]] = field(default_factory=list)
    registration_status: str | None = None
    registration_status_date: date | None = None
    partners: list[dict[str, str]] = field(default_factory=list)
    # Used to check a condominium's own CNPJ before registering it (D119); not stored.
    legal_nature_code: int | None = None
    legal_nature: str | None = None
    address: dict[str, str] | None = None


class SupplierDataProvider(Protocol):
    async def lookup(self, cnpj: str) -> SupplierRecord | None:
        """None when the CNPJ does not exist in the registry."""
        ...


def format_cnae(code: int | str) -> str:
    digits = str(code).zfill(7)
    return f"{digits[:4]}-{digits[4]}/{digits[5:]}"


def _mask_partner_doc(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = only_digits(raw)
    if len(digits) == 14 and is_valid_cnpj(digits):
        return digits  # a company partner: CNPJ is public
    return mask_cpf(raw)


def parse_brasilapi(payload: dict[str, Any]) -> SupplierRecord:
    situation_date = payload.get("data_situacao_cadastral")
    cnae = payload.get("cnae_fiscal")
    return SupplierRecord(
        cnpj=only_digits(str(payload.get("cnpj", ""))).zfill(14),
        legal_name=str(payload.get("razao_social") or "").strip(),
        trade_name=(payload.get("nome_fantasia") or "").strip() or None,
        cnae_main=(
            {
                "code": format_cnae(cnae),
                "description": str(payload.get("cnae_fiscal_descricao") or ""),
            }
            if cnae
            else None
        ),
        cnae_secondary=[
            {"code": format_cnae(c["codigo"]), "description": str(c.get("descricao") or "")}
            for c in payload.get("cnaes_secundarios") or []
            if c.get("codigo")
        ],
        registration_status=(payload.get("descricao_situacao_cadastral") or "").strip().upper()
        or None,
        registration_status_date=date.fromisoformat(situation_date) if situation_date else None,
        partners=[
            {
                "name": str(p.get("nome_socio") or "").strip(),
                "cpf_masked": _mask_partner_doc(p.get("cnpj_cpf_do_socio")) or "",
                "qualification": str(p.get("qualificacao_socio") or ""),
            }
            for p in payload.get("qsa") or []
            if p.get("nome_socio")
        ],
        legal_nature_code=_int(payload.get("codigo_natureza_juridica")),
        legal_nature=(payload.get("natureza_juridica") or "").strip() or None,
        address=_address(payload),
    )


def _int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _address(payload: dict[str, Any]) -> dict[str, str] | None:
    street = " ".join(
        str(payload.get(k) or "").strip()
        for k in ("descricao_tipo_de_logradouro", "logradouro")
        if payload.get(k)
    ).strip()
    if not street and not payload.get("municipio"):
        return None
    parts = {
        "street": street,
        "number": str(payload.get("numero") or "").strip(),
        "complement": str(payload.get("complemento") or "").strip(),
        "district": str(payload.get("bairro") or "").strip(),
        "city": str(payload.get("municipio") or "").strip(),
        "state": str(payload.get("uf") or "").strip(),
        "zip": only_digits(str(payload.get("cep") or "")),
    }
    return {k: v for k, v in parts.items() if v}


class BrasilApiProvider:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def lookup(self, cnpj: str) -> SupplierRecord | None:
        url = f"{get_settings().brasilapi_base_url}/cnpj/v1/{cnpj}"
        client = self._client or httpx.AsyncClient(timeout=15.0)
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    response = await client.get(url, headers={"Accept": "application/json"})
                except httpx.HTTPError as exc:
                    if attempt == MAX_ATTEMPTS:
                        raise SupplierLookupUnavailable(type(exc).__name__) from exc
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                if response.status_code == 404:
                    return None
                if response.status_code in RETRY_STATUSES:
                    if attempt == MAX_ATTEMPTS:
                        raise SupplierLookupUnavailable(f"HTTP {response.status_code}")
                    retry_after = response.headers.get("retry-after", "")
                    wait = float(retry_after) if retry_after.isdigit() else 2 ** (attempt - 1)
                    await asyncio.sleep(min(wait, 30))
                    continue
                if response.status_code == 400:
                    return None
                response.raise_for_status()
                return parse_brasilapi(response.json())
            raise SupplierLookupUnavailable("tentativas esgotadas")
        finally:
            if self._client is None:
                await client.aclose()


class OfflineProvider:
    """Never calls out: suppliers keep whatever data they already have."""

    async def lookup(self, cnpj: str) -> SupplierRecord | None:
        raise SupplierLookupUnavailable("consulta de CNPJ desligada (SUPPLIER_PROVIDER=offline)")


def get_provider() -> SupplierDataProvider:
    if get_settings().supplier_provider == "offline":
        return OfflineProvider()
    return BrasilApiProvider()


def is_fresh(supplier: Supplier) -> bool:
    if supplier.enriched_at is None:
        return False
    return utcnow() - supplier.enriched_at < timedelta(days=get_settings().supplier_cache_days)


async def enrich_supplier(
    session: AsyncSession,
    supplier: Supplier,
    provider: SupplierDataProvider,
    *,
    force: bool = False,
) -> bool:
    """Refresh a supplier from the registry. Returns True when data changed."""
    if not force and is_fresh(supplier):
        return False
    record = await provider.lookup(supplier.cnpj)  # may raise SupplierLookupUnavailable
    supplier.enriched_at = utcnow()
    if record is None:
        # Keep what we had (e.g. data read from the document) and remember the problem.
        supplier.enrichment_error = "nao_encontrado"
        return False
    apply_record(supplier, record)
    return True


def apply_record(supplier: Supplier, record: SupplierRecord) -> None:
    supplier.legal_name = record.legal_name or supplier.legal_name
    supplier.trade_name = record.trade_name
    supplier.cnae_main = record.cnae_main
    supplier.cnae_secondary = record.cnae_secondary
    supplier.registration_status = record.registration_status
    supplier.registration_status_date = record.registration_status_date
    supplier.partners = record.partners
    supplier.enrichment_source = "brasilapi"
    supplier.enrichment_error = None
    supplier.enriched_at = utcnow()


async def get_or_create_supplier(
    session: AsyncSession, cnpj: str, legal_name: str | None
) -> Supplier:
    """Supplier by CNPJ; a new one starts with what the document showed and is enriched later."""
    supplier = await session.scalar(select(Supplier).where(Supplier.cnpj == cnpj))
    if supplier is None:
        supplier = Supplier(
            cnpj=cnpj,
            legal_name=(legal_name or "Fornecedor sem razão social").strip()[:200],
            cnae_secondary=[],
            partners=[],
            enrichment_source="documento",
        )
        session.add(supplier)
        await session.flush()
    return supplier


async def enrich_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    """Job ``supplier.enrich``. Temporary failures raise so the queue retries with backoff."""
    supplier = await session.scalar(
        select(Supplier).where(Supplier.cnpj == payload["cnpj"]).with_for_update()
    )
    if supplier is None:
        return
    await enrich_supplier(session, supplier, get_provider(), force=bool(payload.get("force")))
