"""Chat evaluation (spec §10).

- ``test_chat_eval_ground_truth`` (fast): every expectation of the set resolves against
  the seed, so the set is valid before any model is asked.
- ``test_chat_eval_live`` (slow, needs ANTHROPIC_API_KEY): asks the real agent through
  the API and grades; acceptance is >= 90% and zero cross-condominium leaks. The report
  goes to docs/chat_eval.md.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.auth.rbac import CondoAccess
from app.chat.tools import ChatTools, ScreenContext
from app.config import get_settings
from app.db.enums import Role
from app.db.session import sessionmaker_for, set_tenant_scope
from app.seed.run import evaluate_seed
from tests.chat_eval.cases import CASES, Case, grade
from tests.helpers import CONSELHEIRO_ACACIAS, GERENTE, condo_id, login

ROLES = {CONSELHEIRO_ACACIAS: Role.CONSELHEIRO, GERENTE: Role.GERENTE}
REPORT = Path(__file__).resolve().parents[3] / "docs" / "chat_eval.md"


@asynccontextmanager
async def tools_for(
    engine: AsyncEngine, admin_engine: AsyncEngine, email: str, slug: str, screen: ScreenContext
) -> AsyncIterator[ChatTools]:
    cid = await condo_id(admin_engine, slug)
    role = ROLES.get(email, Role.SINDICO)
    access = CondoAccess(user_id=uuid.uuid4(), condominium_id=cid, roles=frozenset({role}))
    async with sessionmaker_for(engine)() as s, s.begin():
        await set_tenant_scope(s, [cid])
        yield ChatTools(s, access, screen)
        await s.rollback()


async def screen_for(
    case: Case, app_engine: AsyncEngine, admin_engine: AsyncEngine
) -> ScreenContext:
    if case.screen_finding is None:
        return ScreenContext()
    rule, month = case.screen_finding
    async with tools_for(app_engine, admin_engine, GERENTE, case.condo, ScreenContext()) as t:
        rows = (await t.run("list_findings", {"rule_code": rule, "month": month}))["achados"]
    assert rows, f"{case.id}: achado {rule} não encontrado no seed"
    return ScreenContext(screen="achado", finding_id=uuid.UUID(rows[0]["id"]))


async def expectations(
    case: Case, app_engine: AsyncEngine, admin_engine: AsyncEngine
) -> tuple[ScreenContext, list[str], list[str]]:
    screen = await screen_for(case, app_engine, admin_engine)
    expected: list[str] = []
    forbidden: list[str] = []
    if case.expect:
        async with tools_for(app_engine, admin_engine, case.user, case.condo, screen) as t:
            expected = await case.expect(t)
    if case.forbid:
        slug = case.forbid_condo or case.condo
        async with tools_for(app_engine, admin_engine, GERENTE, slug, ScreenContext()) as t:
            forbidden = await case.forbid(t)
    return screen, expected, forbidden


@pytest.fixture
async def evaluated_seed(admin_engine: AsyncEngine) -> None:
    await evaluate_seed(admin_engine)  # idempotent: findings of the open month


async def test_chat_eval_ground_truth(
    evaluated_seed: None, app_engine: AsyncEngine, admin_engine: AsyncEngine
) -> None:
    assert len(CASES) >= 25
    assert len({c.id for c in CASES}) == len(CASES)
    kinds = {c.kind for c in CASES}
    assert {"outro_condominio", "sem_dado", "escrita", "juridico", "tela", "papel"} <= kinds
    for case in CASES:
        _, expected, forbidden = await expectations(case, app_engine, admin_engine)
        assert case.expect is None or (expected and all(expected)), case.id
        assert case.forbid is None or (forbidden and all(forbidden)), case.id
        assert case.expect or case.any_of or case.forbid or case.no_money, case.id
        # an expected value must not also be forbidden
        assert not set(expected) & set(forbidden), case.id


@pytest.mark.slow
async def test_chat_eval_live(
    evaluated_seed: None,
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    app_engine: AsyncEngine,
    admin_engine: AsyncEngine,
) -> None:
    if get_settings().anthropic_api_key is None:
        pytest.skip("avaliação ao vivo exige ANTHROPIC_API_KEY")
    results = []
    current_user = None
    for case in CASES:
        screen, expected, forbidden = await expectations(case, app_engine, admin_engine)
        if case.user != current_user:
            await client.post("/auth/logout")
            await login(client, mailer, case.user)
            current_user = case.user
        cid = await condo_id(admin_engine, case.condo)
        screen_in: dict[str, Any] = {"screen": screen.screen}
        if screen.finding_id:
            screen_in["finding_id"] = str(screen.finding_id)
        body = {"question": case.question, "screen": screen_in}
        r = await client.post(f"/condominiums/{cid}/chat", json=body)
        answer = r.json().get("content", "") if r.status_code == 200 else f"HTTP {r.status_code}"
        problems = grade(case, answer, expected, forbidden)
        results.append((case, answer, problems))

    passed = sum(not p for _, _, p in results)
    leaks = [c.id for c, _, p in results if c.kind == "outro_condominio" and p]
    lines = [
        "# Avaliação do chat",
        "",
        f"Acerto: {passed}/{len(results)} ({passed / len(results):.0%}). "
        f"Vazamentos entre condomínios: {len(leaks)}.",
        "",
        "| Caso | Tipo | Resultado | Problemas |",
        "|---|---|---|---|",
    ]
    for case, _, problems in results:
        lines.append(
            f"| {case.id} | {case.kind} | {'ok' if not problems else 'falhou'} | "
            f"{'; '.join(problems)} |"
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not leaks
    assert passed / len(results) >= 0.9, "\n".join(f"{c.id}: {p}" for c, _, p in results if p)
