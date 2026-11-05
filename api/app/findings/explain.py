"""Plain-language explanation of a finding, written by the model and checked by code.

The model may only use numbers present in the rule's inputs or in the evidence. Every number
in its text is extracted and checked (a value shown with k decimals must equal an allowed value
rounded to k decimals). If the check fails, the model gets one more try; if it fails again,
the deterministic text of the rule stays. Serious findings use the reasoning model.
"""

import json
import logging
import re
import uuid
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Finding, Supplier
from app.llm.client import LLMRequest, LLMUnavailable, call_structured
from app.llm.prompts import load_prompt
from app.rules.engine import FORBIDDEN_WORDS, RULES_BY_CODE

logger = logging.getLogger(__name__)

EXPLAIN_JOB = "finding.explain"
MAX_ATTEMPTS = 2

# Numbers as a person writes them in pt-BR (1.234,56 / 4,56 / 1234), used on the text.
_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")
# Numbers as the code stores them (1234.56 / 2026-10-05 / 03/10/2026), used on the inputs.
_MACHINE = re.compile(r"\d+(?:\.\d+)?")
# A formatted CNPJ is one identifier, not five numbers: compared by its 14 digits.
_CNPJ = re.compile(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}")


def _cnpj_as_digits(text: str) -> str:
    return _CNPJ.sub(lambda m: re.sub(r"\D", "", m.group(0)), text)


class Explanation(BaseModel):
    titulo: str = Field(max_length=80)
    explicacao: str = Field(max_length=900)


def _to_decimal(raw: str) -> tuple[Decimal, int] | None:
    """Parse a number as written and return (value, decimals shown)."""
    text = raw
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")  # thousands separators only
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    decimals = len(text.split(".")[1]) if "." in text else 0
    return value, decimals


def numbers_in(text: str) -> list[tuple[Decimal, int]]:
    out = []
    for match in _NUMBER.finditer(text):
        parsed = _to_decimal(match.group(0))
        if parsed is not None:
            out.append(parsed)
    return out


def _collect(value: Any, sink: list[str]) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _collect(v, sink)
    elif isinstance(value, list):
        for v in value:
            _collect(v, sink)
    elif value is not None and not isinstance(value, bool):
        sink.append(str(value))


def allowed_numbers(finding: Finding, supplier_name: str | None) -> set[Decimal]:
    """Every number the explanation may cite: rule inputs (incl. dates, codes), evidence
    labels and excerpts, the supplier name and the competence."""
    texts: list[str] = []
    _collect(finding.rule_inputs, texts)
    for e in finding.evidence:
        texts += [e.get("label", ""), e.get("excerpt", "")]
    texts.append(supplier_name or "")
    texts.append(f"{finding.competence:%m/%Y}")
    allowed: set[Decimal] = set()
    for t in texts:
        for match in _MACHINE.finditer(_cnpj_as_digits(t)):
            allowed.add(Decimal(match.group(0)))
    return allowed


def invalid_numbers(text: str, allowed: set[Decimal]) -> list[str]:
    """Numbers in ``text`` that do not come from ``allowed`` (respecting shown precision)."""
    bad = []
    for match in _NUMBER.finditer(_cnpj_as_digits(text).replace("/", " ")):
        parsed = _to_decimal(match.group(0))
        if parsed is None:
            continue
        value, decimals = parsed
        quantum = Decimal(1).scaleb(-decimals)
        if not any(
            a.quantize(quantum, rounding=ROUND_HALF_UP) == value
            for a in allowed
            if abs(a) < Decimal("1e15")
        ):
            bad.append(match.group(0))
    return bad


def check(explanation: Explanation, allowed: set[Decimal]) -> list[str]:
    problems = []
    text = f"{explanation.titulo} {explanation.explicacao}"
    if bad := invalid_numbers(text, allowed):
        problems.append(f"números que não estão nos dados: {', '.join(bad)}")
    if any(w in text.lower() for w in (*FORBIDDEN_WORDS, "irregularidade")):
        problems.append("linguagem proibida")
    return problems


async def explain_finding(
    session: AsyncSession, finding: Finding, supplier_name: str | None
) -> Explanation | None:
    """Model-written explanation that passed the checks, or None (keep the rule's text)."""
    rule = RULES_BY_CODE.get(finding.rule_code)
    allowed = allowed_numbers(finding, supplier_name)
    payload = {
        "regra": f"{finding.rule_code} — {rule.name if rule else finding.rule_code}",
        "fornecedor": supplier_name,
        "competencia": f"{finding.competence:%m/%Y}",
        "valor_em_risco": str(finding.amount_at_risk),
        "dados": finding.rule_inputs,
        "evidencias": [
            {"tipo": e.get("kind"), "descricao": e.get("label")} for e in finding.evidence
        ],
        "texto_de_referencia": finding.explanation,
    }
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await call_structured(
                session,
                LLMRequest(
                    purpose="finding.explain",
                    role="reasoning" if finding.severity == "alta" else "extraction",
                    system=load_prompt("explain_finding"),
                    user_text=json.dumps(payload, ensure_ascii=False, default=str) + feedback,
                    output_model=Explanation,
                    condominium_id=finding.condominium_id,
                    max_tokens=2000,
                    effort="low",
                ),
            )
        except LLMUnavailable as exc:
            logger.info(
                "explanation kept from rule finding=%s reason=%s", finding.id, type(exc).__name__
            )
            return None
        problems = check(result.output, allowed)
        if not problems:
            return result.output
        logger.info("explanation rejected finding=%s attempt=%s", finding.id, attempt)
        feedback = (
            "\n\nA versão anterior foi recusada: "
            + "; ".join(problems)
            + ". Reescreva usando só os números fornecidos."
        )
    return None


async def explain_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    finding = await session.get(Finding, uuid.UUID(payload["finding_id"]), with_for_update=True)
    if finding is None or finding.explanation_source == "ia":
        return
    supplier = await session.get(Supplier, finding.supplier_id) if finding.supplier_id else None
    explanation = await explain_finding(session, finding, supplier.legal_name if supplier else None)
    if explanation is not None:
        finding.title = explanation.titulo.strip().rstrip(".")
        finding.explanation = explanation.explicacao.strip()
        finding.explanation_source = "ia"
