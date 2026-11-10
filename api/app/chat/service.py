"""One chat turn: history → agent → checks by code → persistence.

The checks enforce the chat rules that code can verify (spec §10), whatever the model
wrote:
- every number in the answer appears in a tool output of this turn (or the question);
- citations are refs that a tool returned in this turn (others are dropped);
- the suggested action is on the allowlist and points to a ref of the right kind;
- no forbidden wording.
An answer that fails is retried once with the problems listed; if it fails again, the
user gets a safe "could not confirm" message instead of unverified numbers.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess
from app.chat.agent import AgentReply, ChatUnavailable, get_runner
from app.chat.tools import ChatTools, ScreenContext
from app.config import get_settings
from app.db.enums import ChatRole
from app.db.models import ChatMessage, LlmCall
from app.findings.explain import _MACHINE, _cnpj_as_digits, invalid_numbers, numbers_in
from app.llm.client import month_spend_usd
from app.llm.prompts import load_prompt, prompt_fingerprint
from app.rules.engine import FORBIDDEN_WORDS

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 6
ACTIONS = {"abrir_achado": "achado", "ver_contrato": "contrato", "ver_despesas": None}
# Small integers (days, months, counts written in a list) are always allowed.
ALWAYS_ALLOWED = {Decimal(n) for n in range(0, 32)}
FALLBACK = (
    "Não consegui confirmar esta resposta com os dados do condomínio. "
    "Tente perguntar de outro jeito ou abra a tela correspondente."
)


@dataclass
class ChatAnswer:
    message_id: str
    content: str
    citations: list[dict[str, Any]]
    suggested_action: dict[str, Any] | None
    created_at: str
    verified: bool = True
    problems: list[str] = field(default_factory=list)


def allowed_numbers(tools: ChatTools, question: str) -> set[Decimal]:
    allowed = set(ALWAYS_ALLOWED)
    for text in [*tools.outputs, question, f"{date.today():%Y-%m-%d}"]:
        for match in _MACHINE.finditer(_cnpj_as_digits(text)):
            allowed.add(Decimal(match.group(0)))
    # Document passages come back as Brazilian text ("multa de R$ 9.250,00"): a number written
    # that way in a tool output is a number from the data too (D98).
    for text in tools.outputs:
        allowed |= {value for value, _ in numbers_in(_cnpj_as_digits(text))}
    # pt-BR numbers the user typed (e.g. "R$ 1.234,56") are fair to repeat
    allowed |= {value for value, _ in numbers_in(question)}
    return allowed


def check_output(
    output: dict[str, Any], tools: ChatTools, question: str
) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None, list[str]]:
    """Validate one structured answer. Returns (text, citations, action, problems)."""
    problems: list[str] = []
    text = str(output.get("resposta") or "").strip()
    if not text:
        problems.append("resposta vazia")
    if bad := invalid_numbers(text, allowed_numbers(tools, question)):
        problems.append(f"números que não estão nos dados consultados: {', '.join(bad[:5])}")
    lowered = text.lower()
    if any(w in lowered for w in (*FORBIDDEN_WORDS, "irregularidade")):
        problems.append("linguagem proibida (use indício, divergência ou ponto de atenção)")

    citations: list[dict[str, Any]] = []
    for ref in output.get("citacoes") or []:
        c = tools.seen.get(str(ref))
        if c is not None and c.ref not in {x["ref"] for x in citations}:
            citations.append({"ref": c.ref, "kind": c.kind, "id": c.id, "label": c.label})

    action = None
    raw = output.get("acao_sugerida") or {}
    kind = raw.get("tipo")
    if kind in ACTIONS:
        needed = ACTIONS[kind]
        ref = raw.get("ref")
        target = tools.seen.get(str(ref)) if ref else None
        if needed is None or (target is not None and target.kind == needed):
            action = {
                "tipo": kind,
                "ref": target.ref if target else None,
                "id": target.id if target else None,
                "rotulo": str(raw.get("rotulo") or "").strip()[:60] or None,
            }
    return text, citations, action, problems


def _history_prompt(history: list[ChatMessage], question: str) -> str:
    lines = []
    for m in history:
        who = "Usuário" if m.role == ChatRole.USER.value else "Assistente"
        lines.append(f"{who}: {m.content}")
    past = "\n".join(lines)
    intro = (
        f"Conversa anterior (para contexto; os dados devem ser consultados de novo):\n{past}\n\n"
    )
    return f"{intro if lines else ''}Pergunta atual: {question}"


async def _log(session: AsyncSession, access: CondoAccess, reply: AgentReply | None) -> None:
    session.add(
        LlmCall(
            purpose="chat",
            prompt_sha256=prompt_fingerprint(load_prompt("chat_system")),
            model=reply.model if reply else get_settings().claude_model_reasoning,
            input_tokens=reply.input_tokens if reply else 0,
            output_tokens=reply.output_tokens if reply else 0,
            cache_read_tokens=reply.cache_read_tokens if reply else 0,
            cache_write_tokens=reply.cache_write_tokens if reply else 0,
            cost_usd=reply.cost_usd if reply else Decimal("0"),
            latency_ms=reply.latency_ms if reply else 0,
            success=reply is not None,
            condominium_id=access.condominium_id,
        )
    )
    await session.flush()


async def history(session: AsyncSession, access: CondoAccess, limit: int = 50) -> list[ChatMessage]:
    rows = await session.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.condominium_id == access.condominium_id,
            ChatMessage.user_id == access.user_id,
        )
        # same transaction = same now(): within one turn the question comes before the answer
        .order_by(ChatMessage.created_at.desc(), ChatMessage.role.asc())
        .limit(limit)
    )
    return list(reversed(list(rows)))


async def answer(
    session: AsyncSession, access: CondoAccess, question: str, screen: ScreenContext
) -> ChatAnswer:
    question = question.strip()
    limit = Decimal(str(get_settings().llm_monthly_budget_usd_per_condominium))
    if await month_spend_usd(session, access.condominium_id) >= limit:
        raise ChatUnavailable("O limite mensal de uso de IA deste condomínio foi atingido.")

    past = (await history(session, access, HISTORY_MESSAGES))[-HISTORY_MESSAGES:]
    session.add(
        ChatMessage(
            condominium_id=access.condominium_id,
            user_id=access.user_id,
            role=ChatRole.USER.value,
            content=question,
            citations=[],
        )
    )
    await session.flush()

    tools = ChatTools(session=session, access=access, screen=screen)
    system = load_prompt("chat_system")
    prompt = _history_prompt(past, question)
    runner = get_runner()
    text, action, problems = FALLBACK, None, ["sem resposta"]
    citations: list[dict[str, Any]] = []
    for attempt in range(2):
        started = time.monotonic()
        try:
            reply = await runner(system=system, prompt=prompt, tools=tools)
        except ChatUnavailable:
            await _log(session, access, None)
            logger.warning("chat agent unavailable condominium=%s", access.condominium_id)
            raise
        await _log(session, access, reply)
        text, citations, action, problems = check_output(reply.output, tools, question)
        logger.info(
            "chat turn condominium=%s attempt=%s tools=%s problems=%s ms=%s",
            access.condominium_id,
            attempt,
            len(tools.calls),
            len(problems),
            int((time.monotonic() - started) * 1000),
        )
        if not problems:
            break
        prompt = (
            f"{_history_prompt(past, question)}\n\nSua resposta anterior foi recusada pela "
            f"verificação: {'; '.join(problems)}. Consulte as ferramentas e responda de novo, "
            "usando só números que elas devolveram."
        )
    verified = not problems
    if not verified:
        text, citations, action = FALLBACK, [], None

    msg = ChatMessage(
        condominium_id=access.condominium_id,
        user_id=access.user_id,
        role=ChatRole.ASSISTANT.value,
        content=text,
        citations=citations,
        suggested_action=action,
    )
    session.add(msg)
    await session.flush()
    await session.refresh(msg, ["created_at"])
    return ChatAnswer(
        message_id=str(msg.id),
        content=text,
        citations=citations,
        suggested_action=action,
        created_at=msg.created_at.isoformat(),
        verified=verified,
        problems=problems,
    )
