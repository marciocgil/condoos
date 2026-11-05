"""The single entry point for every LLM call in CondoOS.

Responsibilities (spec §14): structured output validated by a Pydantic schema, timeout,
retries, prompt caching of the (long, stable) system prompt, one ``llm_calls`` row per real
API call with tokens, cost and latency, and a monthly cost ceiling per condominium.

Modes (``LLM_MODE``):
- ``live``: call the Anthropic API.
- ``record``: call the API and save each response as a cassette for replay in tests.
- ``replay``: never call the API; answer only from cassettes, else ``LLMUnavailable``.
- ``off``: never call; always ``LLMUnavailable``.
Without ``LLM_MODE``, the mode is ``live`` when ``ANTHROPIC_API_KEY`` is set, ``replay`` otherwise.

Callers must treat ``LLMUnavailable`` as a normal outcome: the document goes to the human
exception queue instead of being guessed.
"""

import base64
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import LlmCall
from app.llm.pricing import estimate_cost_usd
from app.llm.schema import strict_json_schema

logger = logging.getLogger(__name__)

ModelRole = Literal["extraction", "reasoning", "fast"]
Effort = Literal["low", "medium", "high"]

# Server-side refusal fallback (routes by refusal category; no model list to maintain).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MODELS_WITH_SERVER_FALLBACK = ("claude-opus-5-5", "claude-sonnet-5-5")


class LLMUnavailable(Exception):
    """No answer can be obtained (no key, mode off, no cassette, budget, API failure)."""


class LLMBudgetExceeded(LLMUnavailable):
    pass


class LLMOutputInvalid(LLMUnavailable):
    pass


@dataclass(frozen=True)
class ImageInput:
    media_type: str  # image/jpeg, image/png, image/webp, image/gif
    data: bytes


@dataclass(frozen=True)
class PdfInput:
    data: bytes


@dataclass
class LLMRequest[T: BaseModel]:
    purpose: str
    role: ModelRole
    system: str
    user_text: str
    output_model: type[T]
    attachments: list[ImageInput | PdfInput] = field(default_factory=list)
    condominium_id: uuid.UUID | None = None
    max_tokens: int = 8000
    effort: Effort = "medium"


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    output: T
    model: str
    replayed: bool


def resolve_mode() -> Literal["live", "replay", "record", "off"]:
    s = get_settings()
    if s.llm_mode is not None:
        return s.llm_mode
    return "live" if s.anthropic_api_key else "replay"


def model_for(role: ModelRole) -> str:
    s = get_settings()
    return {
        "extraction": s.claude_model_extraction,
        "reasoning": s.claude_model_reasoning,
        "fast": s.claude_model_fast,
    }[role]


# --------------------------------------------------------------------------- cassettes


def _attachment_digest(item: ImageInput | PdfInput) -> dict[str, str]:
    kind = "pdf" if isinstance(item, PdfInput) else item.media_type
    return {"kind": kind, "sha256": hashlib.sha256(item.data).hexdigest()}


def request_digest(req: LLMRequest[Any], model: str) -> str:
    """Stable key of a request: same inputs and schema => same cassette."""
    payload = {
        "purpose": req.purpose,
        "model": model,
        "system": req.system,
        "user_text": req.user_text,
        "attachments": [_attachment_digest(a) for a in req.attachments],
        "schema": strict_json_schema(req.output_model),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _cassette_path(digest: str) -> Path:
    return Path(get_settings().llm_cassette_dir) / f"{digest}.json"


def _load_cassette(digest: str) -> dict[str, Any] | None:
    path = _cassette_path(digest)
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _save_cassette(digest: str, purpose: str, model: str, output: dict[str, Any]) -> None:
    path = _cassette_path(digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"digest": digest, "purpose": purpose, "model": model, "output": output},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- budget


async def month_spend_usd(session: AsyncSession, condominium_id: uuid.UUID) -> Decimal:
    first_day = date.today().replace(day=1)
    total = await session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0)).where(
            LlmCall.condominium_id == condominium_id,
            LlmCall.created_at >= first_day,
        )
    )
    return Decimal(str(total or 0))


# --------------------------------------------------------------------------- live call


def _content_blocks(req: LLMRequest[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in req.attachments:
        encoded = base64.standard_b64encode(item.data).decode()
        if isinstance(item, PdfInput):
            blocks.append(
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": encoded},
                }
            )
        else:
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": item.media_type, "data": encoded},
                }
            )
    blocks.append({"type": "text", "text": req.user_text})
    return blocks


_client: anthropic.AsyncAnthropic | None = None


def _anthropic() -> anthropic.AsyncAnthropic:
    global _client
    s = get_settings()
    if s.anthropic_api_key is None:
        raise LLMUnavailable("ANTHROPIC_API_KEY não configurada")
    if _client is None:
        _client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key.get_secret_value(),
            timeout=s.llm_timeout_seconds,
            max_retries=s.llm_max_retries,
        )
    return _client


async def _call_api(req: LLMRequest[Any], model: str) -> tuple[dict[str, Any], Any, str]:
    """Returns (parsed JSON output, usage, model that served the answer)."""
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": req.max_tokens,
        # The system prompt is long and identical across calls of the same purpose: cache it.
        "system": [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": _content_blocks(req)}],
        "output_config": {
            "effort": req.effort,
            "format": {"type": "json_schema", "schema": strict_json_schema(req.output_model)},
        },
    }
    if model in MODELS_WITH_SERVER_FALLBACK:
        kwargs["betas"] = [FALLBACK_BETA]
        kwargs["fallbacks"] = "default"
    response = await _anthropic().beta.messages.create(**kwargs)
    if response.stop_reason == "refusal":
        raise LLMUnavailable("o modelo recusou a solicitação")
    if response.stop_reason == "max_tokens":
        raise LLMOutputInvalid("resposta truncada (max_tokens)")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LLMOutputInvalid("resposta sem bloco de texto")
    return json.loads(text), response.usage, str(response.model)


async def _log_call(
    session: AsyncSession,
    req: LLMRequest[Any],
    model: str,
    usage: Any,
    latency_ms: int,
    success: bool,
) -> None:
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    session.add(
        LlmCall(
            purpose=req.purpose,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=estimate_cost_usd(model, input_tokens, output_tokens, cache_read, cache_write),
            latency_ms=latency_ms,
            success=success,
            condominium_id=req.condominium_id,
        )
    )
    await session.flush()


# --------------------------------------------------------------------------- public API


async def call_structured[T: BaseModel](
    session: AsyncSession | None, req: LLMRequest[T]
) -> LLMResult[T]:
    """``session`` may be None only in replay/off modes (nothing is logged there)."""
    mode = resolve_mode()
    model = model_for(req.role)
    digest = request_digest(req, model)

    if mode == "off":
        raise LLMUnavailable("LLM desativado (LLM_MODE=off)")

    if mode == "replay":
        cassette = _load_cassette(digest)
        if cassette is None:
            raise LLMUnavailable(f"sem resposta gravada para {req.purpose} ({digest[:12]})")
        try:
            return LLMResult(
                output=req.output_model.model_validate(cassette["output"]),
                model=str(cassette.get("model", model)),
                replayed=True,
            )
        except ValidationError as exc:
            raise LLMOutputInvalid(f"resposta gravada inválida: {exc.error_count()} erros") from exc

    # live / record
    if session is None:
        raise LLMUnavailable("chamada real exige sessão de banco para registrar o custo")
    if req.condominium_id is not None:
        spent = await month_spend_usd(session, req.condominium_id)
        limit = Decimal(str(get_settings().llm_monthly_budget_usd_per_condominium))
        if spent >= limit:
            logger.warning("llm budget exceeded condominium=%s", req.condominium_id)
            raise LLMBudgetExceeded("limite mensal de custo de IA atingido para o condomínio")

    started = time.monotonic()
    try:
        raw, usage, served_by = await _call_api(req, model)
    except anthropic.APIError as exc:
        await _log_call(session, req, model, None, int((time.monotonic() - started) * 1000), False)
        logger.warning("llm call failed purpose=%s error=%s", req.purpose, type(exc).__name__)
        raise LLMUnavailable(f"falha na API: {type(exc).__name__}") from exc
    latency = int((time.monotonic() - started) * 1000)

    try:
        output = req.output_model.model_validate(raw)
    except ValidationError as exc:
        await _log_call(session, req, served_by, usage, latency, False)
        raise LLMOutputInvalid(f"saída fora do esquema: {exc.error_count()} erros") from exc

    await _log_call(session, req, served_by, usage, latency, True)
    if mode == "record":
        _save_cassette(digest, req.purpose, served_by, raw)
    return LLMResult(output=output, model=served_by, replayed=False)
