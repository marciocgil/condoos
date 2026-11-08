"""Milestone 5 chat: read-only tools bound to one condominium, checks by code, endpoint.

The agent itself is simulated here (no API key in tests); the live evaluation is in
tests/chat_eval (slow).
"""

import uuid
from collections.abc import Awaitable, Callable, Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.auth.rbac import CondoAccess
from app.chat import agent as agent_mod
from app.chat.agent import AgentReply, ChatUnavailable
from app.chat.tools import ChatTools, ScreenContext
from app.db.enums import Role
from app.db.models import ChatMessage, Expense, Finding, LlmCall
from app.db.session import sessionmaker_for, set_tenant_scope
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    GERENTE,
    SINDICA_ACACIAS,
    SINDICA_MIRANTE,
    condo_id,
    login,
)

READ_ONLY_TOOLS = {
    "get_month_summary",
    "list_findings",
    "get_finding",
    "search_expenses",
    "get_contract",
    "get_supplier",
    "compare_periods",
    "search_documents",
    "get_screen_context",
}
MONTH = date(2026, 4, 1)  # a month no other test adds findings to


async def _finding(admin_engine: AsyncEngine, slug: str, status: str, amount: str) -> uuid.UUID:
    cid = await condo_id(admin_engine, slug)
    fid = uuid.uuid4()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        s.add(
            Finding(
                id=fid,
                condominium_id=cid,
                rule_code="R03",
                severity="alta" if status == "aguardando_validacao" else "media",
                title="Reajuste acima do índice",
                explanation=f"Divergência de R$ {amount}.",
                amount_at_risk=Decimal(amount),
                status=status,
                evidence=[],
                rule_inputs={"diferenca": amount, "categoria": "portaria"},
                competence=MONTH,
                dedupe_key=f"chat-{fid}",
            )
        )
    return fid


def _access(cid: uuid.UUID, *roles: Role) -> CondoAccess:
    return CondoAccess(user_id=uuid.uuid4(), condominium_id=cid, roles=frozenset(roles))


async def test_tools_are_read_only_and_bound_to_the_condominium(
    admin_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    published = await _finding(admin_engine, "jardim-das-acacias", "publicado", "321.00")
    pending = await _finding(admin_engine, "jardim-das-acacias", "aguardando_validacao", "999.00")
    other = await _finding(admin_engine, "mirante-do-vale", "publicado", "555.00")

    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [acacias])
        tools = ChatTools(s, _access(acacias, Role.SINDICO))
        assert {t.name for t in tools.specs()} == READ_ONLY_TOOLS
        for spec in tools.specs():  # the model never picks the condominium
            assert "condominium" not in str(spec.schema).lower()

        listed = await tools.run("list_findings", {"month": "2026-04"})
        ids = {f["id"] for f in listed["achados"]}
        assert str(published) in ids and str(pending) not in ids and str(other) not in ids
        assert (await tools.run("get_finding", {"id": str(other)}))["encontrado"] is False
        assert (await tools.run("get_finding", {"id": str(pending)}))["encontrado"] is False

        summary = await tools.run("get_month_summary", {"month": "2026-04"})
        assert summary["achados"] == 1 and summary["valor_em_risco"] == "321.00"

        expenses = await tools.run("search_expenses", {"category": "portaria"})
        assert expenses["total_encontrado"] > 0
        # The total is the sum of the matching expenses only (it used to multiply them, D98).
        energy = await tools.run(
            "search_expenses",
            {"category": "energia", "month_from": "2026-09", "month_to": "2026-09"},
        )
        real_sum, real_count = (
            await s.execute(
                select(func.coalesce(func.sum(Expense.amount), 0), func.count()).where(
                    Expense.condominium_id == acacias,
                    Expense.category == "energia",
                    Expense.competence == date(2026, 9, 1),
                )
            )
        ).one()
        assert energy["total_encontrado"] == real_count == 1
        assert Decimal(energy["soma"]) == real_sum
        assert all(r["ref"].startswith("despesa:") for r in expenses["despesas"])

        contract = await tools.run("get_contract", {"supplier": "Vigilare"})
        assert contract["encontrado"] and contract["contratos"][0]["objeto"] == "Portaria 24 horas"
        assert "CLÁUSULA 5" in contract["contratos"][0]["clausulas"]

        docs = await tools.run("search_documents", {"query": "multa rescisão portaria"})
        assert docs["trechos"] and docs["trechos"][0]["ref"].startswith("documento:")

        cmp = await tools.run(
            "compare_periods",
            {"period_a": "2026-01", "period_b": "2026-02", "category": "energia"},
        )
        assert cmp["total_a"] and cmp["variacao_percentual"] is not None

        sup = await tools.run("get_supplier", {"name": "Vigilare"})
        assert sup["encontrado"]
        for partner in sup["fornecedores"][0]["socios"]:
            assert partner["cpf"].startswith("***")

    # The manager sees findings awaiting validation, still only in this condominium.
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [acacias])
        tools = ChatTools(s, _access(acacias, Role.GERENTE))
        ids = {f["id"] for f in (await tools.run("list_findings", {"month": "2026-04"}))["achados"]}
        assert str(pending) in ids and str(other) not in ids


async def test_screen_context_brings_the_open_finding(
    admin_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = await _finding(admin_engine, "jardim-das-acacias", "publicado", "123.45")
    async with sessionmaker_for(app_engine)() as s, s.begin():
        await set_tenant_scope(s, [acacias])
        tools = ChatTools(
            s, _access(acacias, Role.SINDICO), ScreenContext(screen="achado", finding_id=fid)
        )
        ctx = await tools.run("get_screen_context", {})
        assert ctx["achado_aberto"]["id"] == str(fid)
        assert (await tools.run("get_finding", {}))["valor_em_risco"] == "123.45"


# --------------------------------------------------------------------------- endpoint

Script = Callable[[ChatTools], Awaitable[dict[str, Any]]]


class FakeRunner:
    """Plays a scripted agent: each call runs the next script against the real tools."""

    def __init__(self, *scripts: Script) -> None:
        self.scripts = list(scripts)
        self.prompts: list[str] = []

    async def __call__(self, *, system: str, prompt: str, tools: ChatTools) -> AgentReply:
        assert "Nunca use" in system
        self.prompts.append(prompt)
        output = await self.scripts.pop(0)(tools)
        return AgentReply(output, "modelo-simulado", Decimal("0.01"), 10, 5, 0, 0, 3, 2)


@pytest.fixture
def runner() -> Iterator[Callable[..., FakeRunner]]:
    previous = agent_mod.get_runner()

    def install(*scripts: Script) -> FakeRunner:
        fake = FakeRunner(*scripts)
        agent_mod.set_runner(fake)
        return fake

    yield install
    agent_mod.set_runner(previous)


async def _summary_answer(tools: ChatTools) -> dict[str, Any]:
    s = await tools.run("get_month_summary", {"month": "2026-04"})
    top = s["principais_achados"][0]["ref"]
    return {
        "resposta": f"Em 04/2026 há {s['achados']} achado(s), com R$ "
        f"{Decimal(s['valor_em_risco']):.2f}".replace(".", ",") + " em risco.",
        "citacoes": [s["ref"], top, "despesa:inventada"],
        "acao_sugerida": {"tipo": "abrir_achado", "ref": top, "rotulo": "Abrir achado"},
    }


async def test_chat_answers_with_checked_citations_and_action(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    runner: Callable[..., FakeRunner],
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    fid = await _finding(admin_engine, "jardim-das-acacias", "publicado", "321.00")
    runner(_summary_answer)
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(
        f"/condominiums/{acacias}/chat", json={"question": "Quanto há em risco em abril?"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "R$" in body["content"]
    refs = [c["ref"] for c in body["citations"]]
    assert "despesa:inventada" not in refs and any(ref.startswith("achado:") for ref in refs)
    assert body["suggested_action"]["tipo"] == "abrir_achado"
    assert body["suggested_action"]["id"] in {str(fid)} | {
        c["id"] for c in body["citations"] if c["kind"] == "achado"
    }

    hist = (await client.get(f"/condominiums/{acacias}/chat")).json()
    assert [m["role"] for m in hist[-2:]] == ["user", "assistant"]
    async with sessionmaker_for(admin_engine)() as s:
        calls = (
            await s.scalars(
                select(LlmCall).where(LlmCall.purpose == "chat", LlmCall.condominium_id == acacias)
            )
        ).all()
    assert calls


async def test_invented_numbers_are_retried_then_replaced(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    runner: Callable[..., FakeRunner],
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")

    async def invented(tools: ChatTools) -> dict[str, Any]:
        await tools.run("get_month_summary", {"month": "2026-04"})
        return {
            "resposta": "A estimativa é de R$ 98.765,43 em risco; isso indica fraude.",
            "citacoes": [],
            "acao_sugerida": {"tipo": "nenhuma"},
        }

    fake = runner(invented, invented)
    await login(client, mailer, SINDICA_ACACIAS)
    r = await client.post(f"/condominiums/{acacias}/chat", json={"question": "Quanto em risco?"})
    body = r.json()
    assert body["content"].startswith("Não consegui confirmar")
    assert body["citations"] == [] and body["suggested_action"] is None
    assert len(fake.prompts) == 2 and "recusada pela verificação" in fake.prompts[1]


async def test_chat_without_agent_returns_503_and_other_condo_404(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    runner: Callable[..., FakeRunner],
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")

    async def down(_: ChatTools) -> dict[str, Any]:
        raise ChatUnavailable("O assistente precisa de uma chave de API configurada.")

    runner(down)
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    r = await client.post(f"/condominiums/{acacias}/chat", json={"question": "Oi?"})
    assert r.status_code == 503 and "chave" in r.json()["detail"]

    await client.post("/auth/logout")
    await login(client, mailer, SINDICA_MIRANTE)
    r = await client.post(f"/condominiums/{acacias}/chat", json={"question": "Oi?"})
    assert r.status_code == 404
    assert (await client.get(f"/condominiums/{acacias}/chat")).status_code == 404


async def test_manager_turn_is_scoped_to_one_condominium(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    runner: Callable[..., FakeRunner],
) -> None:
    """The manager reaches both condominiums, but a chat turn only sees the one asked."""
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    mirante_finding = await _finding(admin_engine, "mirante-do-vale", "publicado", "777.00")
    seen: dict[str, Any] = {}

    async def probe(tools: ChatTools) -> dict[str, Any]:
        seen["other"] = await tools.run("get_finding", {"id": str(mirante_finding)})
        from sqlalchemy import func

        seen["rows"] = await tools.session.scalar(
            select(func.count()).select_from(Finding).where(Finding.id == mirante_finding)
        )
        return {"resposta": "Não encontrei.", "citacoes": [], "acao_sugerida": {"tipo": "nenhuma"}}

    runner(probe)
    await login(client, mailer, GERENTE)
    r = await client.post(f"/condominiums/{acacias}/chat", json={"question": "E o Mirante?"})
    assert r.status_code == 200
    assert seen["other"]["encontrado"] is False
    assert seen["rows"] == 0  # RLS hides the other condominium even to a raw query
    async with sessionmaker_for(admin_engine)() as s:
        msgs = (
            await s.scalars(select(ChatMessage).where(ChatMessage.content == "E o Mirante?"))
        ).all()
    assert len(msgs) == 1 and msgs[0].condominium_id == acacias


@pytest.mark.parametrize("key", [None, "", "   "])
async def test_runner_without_key_is_unavailable(
    key: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic import SecretStr

    from app.chat.agent import ClaudeAgentRunner
    from app.config import get_settings

    monkeypatch.setattr(
        get_settings(), "anthropic_api_key", SecretStr(key) if key is not None else None
    )
    with pytest.raises(ChatUnavailable, match="chave de API"):
        await ClaudeAgentRunner()(system="", prompt="oi", tools=None)  # type: ignore[arg-type]


def test_numbers_from_document_passages_are_accepted_invented_ones_are_not() -> None:
    """D98: passages come back as Brazilian text; a value quoted from them is from the data.
    A value the tools did not return is still refused."""
    from types import SimpleNamespace
    from typing import cast

    from app.chat.service import allowed_numbers
    from app.findings.explain import invalid_numbers

    passage = (
        '{"trechos": [{"texto": "CLÁUSULA 9 - Rescisão antecipada: multa de R$ 9.250,00 e '
        'aviso prévio de 30 (trinta) dias. Obras acima de R$ 5.000,00 exigem 3 orçamentos."}]}'
    )
    tools = cast(ChatTools, SimpleNamespace(outputs=[passage]))
    allowed = allowed_numbers(tools, "Qual a multa de rescisão da portaria?")
    assert invalid_numbers("A multa é de R$ 9.250,00, com aviso de 30 dias.", allowed) == []
    assert invalid_numbers("Acima de R$ 5.000,00 são 3 orçamentos.", allowed) == []
    assert invalid_numbers("A multa é de R$ 9.300,00.", allowed) == ["9.300,00"]
