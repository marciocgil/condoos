"""Milestone 3 acceptance: the seed has a planted positive and negative case for every rule.

The engine, run over October 2026 for both condominiums (reference date 05/11/2026), must
find every planted positive and nothing else (no false positive on the negatives).

Runs on a dedicated database holding only the seed, so other tests cannot interfere.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.db.models import Condominium
from app.db.session import sessionmaker_for
from app.rules import r04_scope
from app.rules.engine import RunSummary, evaluate
from app.rules.judge import ScopeJudgement
from app.seed.data import ExpectedFinding, build_seed
from app.seed.run import load_seed

OCT = date(2026, 10, 1)
REF = date(2026, 11, 5)
DB = "condoos_test_seed_only"
API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
async def seed_engine() -> AsyncIterator[AsyncEngine]:
    admin = make_url(os.environ["DATABASE_ADMIN_URL"])
    server = create_async_engine(admin.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with server.connect() as conn:
        await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
        await conn.exec_driver_sql(f'CREATE DATABASE "{DB}"')
    await server.dispose()
    url = admin.set(database=DB).render_as_string(hide_password=False)
    subprocess.run(  # noqa: ASYNC221  (one-off, before the tests of this module)
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        check=True,
        env={**os.environ, "DATABASE_ADMIN_URL": url},
    )
    engine = create_async_engine(url)
    await load_seed(engine)
    yield engine
    await engine.dispose()


async def _run(engine: AsyncEngine) -> dict[str, RunSummary]:
    out = {}
    async with sessionmaker_for(engine)() as s:
        for condo in await s.scalars(select(Condominium)):
            out[condo.slug] = await evaluate(s, condo.id, OCT, REF, save=False)
    return out


def _matches(expected: ExpectedFinding, slug: str, rule_code: str, subject_key: str) -> bool:
    return (
        expected.condo_slug == slug
        and expected.rule_code == rule_code
        and expected.subject in subject_key
    )


def _compare(
    runs: dict[str, RunSummary], expected: list[ExpectedFinding]
) -> tuple[list[Any], list[Any]]:
    found = [(slug, d.rule_code, d.subject_key) for slug, r in runs.items() for d in r.drafts]
    missing = [e for e in expected if not any(_matches(e, *f) for f in found)]
    extra = [f for f in found if not any(_matches(e, *f) for e in expected)]
    return missing, extra


async def test_every_planted_case_with_model(
    seed_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R04 with a simulated model answer: painting is out of a cleaning contract's scope."""

    async def fake_scope(*_: Any, charged: str, **__: Any) -> ScopeJudgement:
        out = "pintura" in charged.lower()
        return ScopeJudgement(
            dentro_do_escopo=not out,
            confidence=0.95,
            justificativa="Pintura de fachada não é limpeza." if out else "Dentro do escopo.",
        )

    monkeypatch.setattr(r04_scope, "judge_scope", fake_scope)
    expected = build_seed().expected
    assert {e.rule_code for e in expected} == {f"R{n:02d}" for n in range(1, 13)}
    missing, extra = _compare(await _run(seed_engine), expected)
    assert missing == [], f"positivos não encontrados: {missing}"
    assert extra == [], f"falsos positivos: {extra}"


async def test_without_model_r04_is_reported_not_guessed(seed_engine: AsyncEngine) -> None:
    expected = build_seed().expected
    runs = await _run(seed_engine)
    missing, extra = _compare(runs, expected)
    assert [e.rule_code for e in missing] == ["R04"] and all(e.needs_model for e in missing)
    assert extra == []
    not_evaluated = runs["jardim-das-acacias"].not_evaluated
    assert any(k.startswith("R04:") for k in not_evaluated)


async def test_routing_and_persistence_are_idempotent(seed_engine: AsyncEngine) -> None:
    from app.db.models import Finding

    async with sessionmaker_for(seed_engine)() as s, s.begin():
        condo = await s.scalar(select(Condominium).where(Condominium.slug == "jardim-das-acacias"))
        assert condo is not None
        first = await evaluate(s, condo.id, OCT, REF)
        rows = (await s.scalars(select(Finding).where(Finding.condominium_id == condo.id))).all()
        by_rule = {f.rule_code: f for f in rows}
        assert by_rule["R01"].status == "aguardando_validacao"  # alta → manager validates first
        assert by_rule["R12"].status == "publicado"  # média → published directly
        by_rule["R12"].status = "confirmado"  # a person decided
        second = await evaluate(s, condo.id, OCT, REF)
        again = (await s.scalars(select(Finding).where(Finding.condominium_id == condo.id))).all()
    assert first.created == len(rows) and second.created == 0 and second.updated == len(rows)
    assert len(again) == len(rows)
    assert {f.rule_code: f.status for f in again}["R12"] == "confirmado"  # never reset


async def test_rule_texts_pass_numeric_validation(seed_engine: AsyncEngine) -> None:
    """The deterministic text of every rule only cites numbers from its own inputs."""
    from app.db.models import Finding, Supplier
    from app.findings.explain import allowed_numbers, invalid_numbers

    runs = await _run(seed_engine)
    async with sessionmaker_for(seed_engine)() as s:
        names = {x.id: x.legal_name for x in await s.scalars(select(Supplier))}
    for run in runs.values():
        for d in run.drafts:
            f = Finding(
                rule_inputs=d.rule_inputs,
                evidence=[e.as_dict() for e in d.evidence],
                competence=OCT,
            )
            allowed = allowed_numbers(f, names.get(d.supplier_id) if d.supplier_id else None)
            assert invalid_numbers(f"{d.title} {d.explanation}", allowed) == [], d.rule_code
