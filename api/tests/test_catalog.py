"""D121: the "Regras e prompts" screen — read only, CondoOS team only, built from the code,
with the prompt version of each model call."""

import re
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app import catalog
from app.auth.mailer import MemoryMailer
from app.db.models import LlmCall
from app.db.session import sessionmaker_for
from app.llm.prompts import load_prompt, prompt_fingerprint
from app.rules.engine import ALL_RULES
from tests.helpers import ADMIN_CONDOOS, GERENTE, SINDICA_MIRANTE, login

APP = Path(__file__).resolve().parents[1] / "app"


def test_every_prompt_file_has_a_purpose() -> None:
    assert catalog.unused_prompt_files() == []


def test_every_rule_has_a_description() -> None:
    assert all(r.description for r in ALL_RULES)


def test_every_detector_in_the_code_is_described() -> None:
    found = set()
    for path in (APP / "data_issues").glob("*.py"):
        found |= set(re.findall(r'"([a-z_]+_v\d+)"', path.read_text(encoding="utf-8")))
    assert found <= {d["code"] for d in catalog.DETECTORS}


async def test_only_the_condoos_team_sees_it(
    client: httpx.AsyncClient, mailer: MemoryMailer
) -> None:
    for email in (SINDICA_MIRANTE, GERENTE):
        await login(client, mailer, email)
        assert (await client.get("/catalog")).status_code == 403
        client.cookies.clear()
    await login(client, mailer, ADMIN_CONDOOS)
    r = await client.get("/catalog")
    assert r.status_code == 200
    body = r.json()
    assert [x["code"] for x in body["rules"]] == [r.code for r in ALL_RULES]
    chat = next(p for p in body["prompts"] if p["code"] == "chat")
    assert chat["text"] == load_prompt("chat_system")
    contract = next(p for p in body["prompts"] if p["code"] == "document.extract.contrato")
    assert contract["files"] == ["extract_common.md", "extract_contrato.md"]
    assert {a["code"] for a in body["policy"]["actions"] if a["always_denied"]} == {
        "pagamento.aprovar",
        "contrato.contratar",
        "multa.aplicar",
        "dados_bancarios.alterar",
    }


async def test_prompt_versions_come_from_the_calls(
    client: httpx.AsyncClient, mailer: MemoryMailer, worker_engine: AsyncEngine
) -> None:
    current = prompt_fingerprint(load_prompt("rule_scope"))
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        for sha in ("0" * 64, current):
            s.add(LlmCall(purpose="rule.R04.scope", prompt_sha256=sha, model="m", success=True))
    await login(client, mailer, ADMIN_CONDOOS)
    body = (await client.get("/catalog")).json()
    scope = next(p for p in body["prompts"] if p["code"] == "rule.R04.scope")
    assert scope["sha256"] == current
    versions = {v["sha256"]: v["current"] for v in scope["versions"]}
    assert versions[current] is True and versions["0" * 64] is False
    assert scope["calls_this_month"] >= 2
