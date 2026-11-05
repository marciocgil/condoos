"""LLM client: modes, record/replay, cost logging and budget. The API is never called:
``_call_api`` is replaced by a fake, so these tests cost nothing and need no key."""

import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import get_settings
from app.db.models import LlmCall
from app.db.session import sessionmaker_for
from app.llm import client as llm
from app.llm.pricing import estimate_cost_usd
from app.llm.schema import strict_json_schema
from tests.helpers import condo_id


class Answer(BaseModel):
    value: str
    confidence: float
    note: str | None = None


def _req(**kw: Any) -> llm.LLMRequest[Answer]:
    base: dict[str, Any] = {
        "purpose": "test",
        "role": "extraction",
        "system": "sistema",
        "user_text": "pergunta",
        "output_model": Answer,
    }
    base.update(kw)
    return llm.LLMRequest(**base)


@pytest.fixture
def cassettes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "llm_cassette_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_api(monkeypatch: pytest.MonkeyPatch) -> list[llm.LLMRequest[Any]]:
    calls: list[llm.LLMRequest[Any]] = []

    async def fake(req: llm.LLMRequest[Any], model: str) -> tuple[dict[str, Any], Any, str]:
        calls.append(req)
        usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=0,
        )
        return {"value": "ok", "confidence": 0.97, "note": None}, usage, model

    monkeypatch.setattr(llm, "_call_api", fake)
    return calls


async def test_off_mode_never_calls(
    worker_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, fake_api: list[Any]
) -> None:
    monkeypatch.setattr(get_settings(), "llm_mode", "off")
    async with sessionmaker_for(worker_engine)() as s:
        with pytest.raises(llm.LLMUnavailable):
            await llm.call_structured(s, _req())
    assert fake_api == []


async def test_replay_without_cassette_is_unavailable(
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    cassettes: Path,
    fake_api: list[Any],
) -> None:
    monkeypatch.setattr(get_settings(), "llm_mode", "replay")
    async with sessionmaker_for(worker_engine)() as s:
        with pytest.raises(llm.LLMUnavailable, match="sem resposta gravada"):
            await llm.call_structured(s, _req())
    assert fake_api == []


async def test_record_then_replay(
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    cassettes: Path,
    fake_api: list[Any],
    admin_engine: AsyncEngine,
) -> None:
    condo = await condo_id(admin_engine, "mirante-do-vale")
    monkeypatch.setattr(get_settings(), "llm_mode", "record")
    purpose = f"record-{uuid.uuid4().hex[:6]}"
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        result = await llm.call_structured(s, _req(purpose=purpose, condominium_id=condo))
    assert result.output.value == "ok" and not result.replayed
    assert len(list(cassettes.glob("*.json"))) == 1

    async with sessionmaker_for(worker_engine)() as s:
        row = await s.scalar(select(LlmCall).where(LlmCall.purpose == purpose))
    assert row is not None and row.success
    assert row.input_tokens == 1000 and row.cache_read_tokens == 3000
    assert row.cost_usd == estimate_cost_usd(row.model, 1000, 200, 3000, 0)
    assert row.condominium_id == condo

    monkeypatch.setattr(get_settings(), "llm_mode", "replay")
    async with sessionmaker_for(worker_engine)() as s:
        again = await llm.call_structured(s, _req(purpose=purpose, condominium_id=condo))
    assert again.replayed and again.output == result.output
    assert len(fake_api) == 1  # replay did not call the API


async def test_budget_blocks_live_calls(
    worker_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    fake_api: list[Any],
    admin_engine: AsyncEngine,
) -> None:
    condo = await condo_id(admin_engine, "jardim-das-acacias")
    monkeypatch.setattr(get_settings(), "llm_mode", "live")
    monkeypatch.setattr(get_settings(), "llm_monthly_budget_usd_per_condominium", 0.0)
    async with sessionmaker_for(worker_engine)() as s:
        with pytest.raises(llm.LLMBudgetExceeded):
            await llm.call_structured(s, _req(condominium_id=condo))
    assert fake_api == []


async def test_invalid_output_is_logged_as_failure(
    worker_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def bad(req: llm.LLMRequest[Any], model: str) -> tuple[dict[str, Any], Any, str]:
        return {"value": "x"}, SimpleNamespace(input_tokens=5, output_tokens=5), model

    monkeypatch.setattr(llm, "_call_api", bad)
    monkeypatch.setattr(get_settings(), "llm_mode", "live")
    purpose = f"bad-{uuid.uuid4().hex[:6]}"
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        with pytest.raises(llm.LLMOutputInvalid):
            await llm.call_structured(s, _req(purpose=purpose))
    async with sessionmaker_for(worker_engine)() as s:
        row = await s.scalar(select(LlmCall).where(LlmCall.purpose == purpose))
    assert row is not None and not row.success


def test_digest_depends_on_inputs() -> None:
    a = llm.request_digest(_req(), "m")
    assert a == llm.request_digest(_req(), "m")
    assert a != llm.request_digest(_req(user_text="outra"), "m")
    assert a != llm.request_digest(_req(attachments=[llm.PdfInput(b"%PDF")]), "m")
    assert a != llm.request_digest(_req(), "outro-modelo")


def test_default_mode_depends_on_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "llm_mode", None)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    assert llm.resolve_mode() == "replay"
    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr("x"))
    assert llm.resolve_mode() == "live"


def test_strict_schema_requires_every_field() -> None:
    schema = strict_json_schema(Answer)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["confidence", "note", "value"]
    assert "default" not in str(schema)


def test_pricing() -> None:
    # 1M input + 1M output on Sonnet 5.5 = $2 + $10
    assert estimate_cost_usd("claude-sonnet-5-5", 1_000_000, 1_000_000) == Decimal("12.000000")
    # cache read at $0.20/M, cache write at 1.25x input
    assert estimate_cost_usd("claude-opus-5-5", 0, 0, 1_000_000, 1_000_000) == Decimal("5.200000")
