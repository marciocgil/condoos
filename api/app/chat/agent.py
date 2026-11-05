"""The chat agent runner (Claude Agent SDK).

The SDK drives the tool loop; our read-only tools run in-process as an SDK MCP server.
Every built-in Claude Code tool (files, shell, web) is disabled: the agent can only call
the tools in ``ChatTools``. No project settings or CLAUDE.md are loaded, and it runs in an
empty temporary directory.

``AgentRunner`` is a protocol so tests and the evaluation can swap the backend.
"""

import json
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from app.chat.tools import ChatTools
from app.config import get_settings

SERVER = "condoos"

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resposta": {"type": "string"},
        "citacoes": {"type": "array", "items": {"type": "string"}},
        "acao_sugerida": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["abrir_achado", "ver_contrato", "ver_despesas", "nenhuma"],
                },
                "ref": {"type": "string"},
                "rotulo": {"type": "string"},
            },
            "required": ["tipo"],
            "additionalProperties": False,
        },
    },
    "required": ["resposta", "citacoes", "acao_sugerida"],
    "additionalProperties": False,
}


class ChatUnavailable(Exception):
    """The agent cannot answer now (no API key, budget, API failure). Message is pt-BR."""


@dataclass
class AgentReply:
    output: dict[str, Any]
    model: str
    cost_usd: Decimal
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    latency_ms: int
    turns: int


class AgentRunner(Protocol):
    async def __call__(self, *, system: str, prompt: str, tools: ChatTools) -> AgentReply: ...


class ClaudeAgentRunner:
    async def __call__(self, *, system: str, prompt: str, tools: ChatTools) -> AgentReply:
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            ClaudeSDKError,
            ResultMessage,
            SdkMcpTool,
            create_sdk_mcp_server,
            query,
        )

        settings = get_settings()
        key = (
            settings.anthropic_api_key.get_secret_value().strip()
            if settings.anthropic_api_key
            else ""
        )
        if not key:  # unset or empty (compose passes ANTHROPIC_API_KEY="" by default)
            raise ChatUnavailable("O assistente precisa de uma chave de API configurada.")

        def wrap(name: str) -> Any:
            async def handler(args: dict[str, Any]) -> dict[str, Any]:
                result = await tools.run(name, args)
                text = json.dumps(result, ensure_ascii=False, default=str)
                return {"content": [{"type": "text", "text": text}]}

            return handler

        sdk_tools = [
            SdkMcpTool(
                name=spec.name,
                description=spec.description,
                input_schema=spec.schema,
                handler=wrap(spec.name),
            )
            for spec in tools.specs()
        ]
        server = create_sdk_mcp_server(SERVER, tools=sdk_tools)
        allowed = [f"mcp__{SERVER}__{spec.name}" for spec in tools.specs()]
        started = time.monotonic()
        result: ResultMessage | None = None
        with tempfile.TemporaryDirectory(prefix="condoos-chat-") as workdir:
            options = ClaudeAgentOptions(
                tools=[],  # no built-in tools at all
                allowed_tools=allowed,
                mcp_servers={SERVER: server},
                strict_mcp_config=True,
                setting_sources=[],
                system_prompt=system,
                model=settings.claude_model_reasoning,
                max_turns=settings.chat_max_turns,
                max_budget_usd=settings.chat_max_budget_usd,
                output_format={"type": "json_schema", "schema": OUTPUT_SCHEMA},
                permission_mode="dontAsk",
                cwd=workdir,
                env={"ANTHROPIC_API_KEY": key},
            )
            try:
                async for message in query(prompt=prompt, options=options):
                    if isinstance(message, ResultMessage):
                        result = message
            except ClaudeSDKError as exc:
                raise ChatUnavailable("O assistente não respondeu agora. Tente de novo.") from exc
        if result is None or result.is_error or not isinstance(result.structured_output, dict):
            raise ChatUnavailable("O assistente não conseguiu concluir a resposta. Tente de novo.")
        usage = result.usage or {}
        model = next(iter(result.model_usage or {}), settings.claude_model_reasoning)
        return AgentReply(
            output=result.structured_output,
            model=str(model),
            cost_usd=Decimal(str(result.total_cost_usd or 0)),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
            latency_ms=int((time.monotonic() - started) * 1000),
            turns=result.num_turns,
        )


_runner: AgentRunner = ClaudeAgentRunner()


def get_runner() -> AgentRunner:
    return _runner


def set_runner(runner: AgentRunner) -> None:
    """For tests and the evaluation harness."""
    global _runner
    _runner = runner
