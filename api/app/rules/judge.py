"""LLM judgements for the two AI-assisted rules (R04 scope, R07 CNAE), always structured."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMRequest, call_structured
from app.llm.prompts import load_prompt


class ScopeJudgement(BaseModel):
    dentro_do_escopo: bool
    confidence: float = Field(ge=0, le=1)
    justificativa: str


class CnaeJudgement(BaseModel):
    compativel: bool
    confidence: float = Field(ge=0, le=1)
    justificativa: str


async def judge_scope(
    session: AsyncSession | None,
    *,
    condominium_id: uuid.UUID,
    contract_object: str,
    scope_items: list[str],
    charged: str,
) -> ScopeJudgement:
    items = "\n".join(f"- {i}" for i in scope_items) or "- (sem itens listados)"
    result = await call_structured(
        session,
        LLMRequest(
            purpose="rule.R04.scope",
            role="extraction",
            system=load_prompt("rule_scope"),
            user_text=(
                f"Objeto do contrato: {contract_object}\nItens do escopo:\n{items}\n\n"
                f"Serviço cobrado: {charged}"
            ),
            output_model=ScopeJudgement,
            condominium_id=condominium_id,
            max_tokens=2000,
            effort="low",
        ),
    )
    return result.output


async def judge_cnae(
    session: AsyncSession | None,
    *,
    condominium_id: uuid.UUID,
    cnaes: list[dict[str, str]],
    charged: str,
) -> CnaeJudgement:
    lines = "\n".join(f"- {c['code']} {c.get('description', '')}" for c in cnaes)
    result = await call_structured(
        session,
        LLMRequest(
            purpose="rule.R07.cnae",
            role="extraction",
            system=load_prompt("rule_cnae"),
            user_text=f"CNAEs da empresa:\n{lines}\n\nServiço cobrado: {charged}",
            output_model=CnaeJudgement,
            condominium_id=condominium_id,
            max_tokens=2000,
            effort="low",
        ),
    )
    return result.output
