"""Finding explanations: numeric validation and the model path (API replaced by a fake)."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import get_settings
from app.db.models import Finding
from app.findings.explain import (
    Explanation,
    allowed_numbers,
    check,
    explain_finding,
    invalid_numbers,
)
from app.llm import client as llm


def _finding(**kw: Any) -> Finding:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": uuid.uuid4(),
        "rule_code": "R03",
        "severity": "media",
        "title": "Reajuste acima do IPCA",
        "explanation": "texto da regra",
        "amount_at_risk": Decimal("80.38"),
        "status": "publicado",
        "competence": date(2026, 10, 1),
        "rule_inputs": {
            "indice_acumulado_12m_pct": "4.5612",
            "valor_anterior": "1300.00",
            "valor_atual": "1417.00",
            "diferenca": "80.38",
            "data": "2026-10-05",
        },
        "evidence": [
            {
                "kind": "expense",
                "id": "x",
                "label": "NF 4471 · 03/10/2026 · R$ 6200.00",
                "excerpt": "",
            }
        ],
    }
    base.update(kw)
    return Finding(**base)


def test_numbers_must_come_from_inputs() -> None:
    allowed = allowed_numbers(_finding(), "Ascende Elevadores Ltda")
    assert (
        invalid_numbers("Reajuste de 4,56% sobre R$ 1.300,00, diferença de R$ 80,38.", allowed)
        == []
    )
    assert invalid_numbers("Em 05/10/2026 e na NF 4471 de 03/10/2026, R$ 6.200,00.", allowed) == []
    assert invalid_numbers("Competência 10/2026.", allowed) == []
    assert invalid_numbers("Reajuste de 18% e diferença de R$ 4.880,00.", allowed) == [
        "18",
        "4.880,00",
    ]


def test_check_rejects_forbidden_words() -> None:
    allowed = allowed_numbers(_finding(), None)
    assert check(Explanation(titulo="Indício de fraude", explicacao="Texto."), allowed)
    assert not check(
        Explanation(titulo="Reajuste acima do IPCA", explicacao="O reajuste foi maior que 4,56%."),
        allowed,
    )


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setattr(get_settings(), "llm_mode", "live")
    texts: list[str] = []

    async def fake(req: llm.LLMRequest[Any], model: str) -> tuple[dict[str, Any], Any, str]:
        text = texts.pop(0)
        return (
            {"titulo": "Reajuste acima do IPCA", "explicacao": text},
            SimpleNamespace(input_tokens=10, output_tokens=10),
            model,
        )

    monkeypatch.setattr(llm, "_call_api", fake)
    return texts


async def test_model_retries_once_after_invented_number(
    live: list[str], worker_engine: Any
) -> None:
    from app.db.session import sessionmaker_for

    live.extend(
        [
            "O contrato subiu 18% em outubro.",  # invented number: rejected
            "O valor passou de R$ 1.300,00 para R$ 1.417,00, acima do IPCA de 4,56%.",
        ]
    )
    async with sessionmaker_for(worker_engine)() as s:
        out = await explain_finding(s, _finding(condominium_id=None), "Ascende")
    assert out is not None and "R$ 1.417,00" in out.explicacao and live == []


async def test_model_fails_twice_keeps_rule_text(live: list[str], worker_engine: Any) -> None:
    from app.db.session import sessionmaker_for

    live.extend(["Subiu 18%.", "Subiu 19%."])
    async with sessionmaker_for(worker_engine)() as s:
        assert await explain_finding(s, _finding(condominium_id=None), None) is None


async def test_without_model_keeps_rule_text() -> None:
    assert await explain_finding(None, _finding(), None) is None  # type: ignore[arg-type]
