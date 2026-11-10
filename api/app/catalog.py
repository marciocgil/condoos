"""Catalogue of what runs in the CondoOS, for the CondoOS team (D121): audit rules, model
prompts per purpose, reading and confidence rules, automatic checks and the action policy.

Read only. Everything comes from the code itself (rule classes, prompt files, field specs,
policy catalogue) or from records (findings, ``llm_calls``); nothing is edited here. A prompt
changes only through the code, with tests and review.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.condo_settings import settings_at
from app.config import get_settings
from app.db.enums import DocumentType
from app.db.models import Condominium, DataIssue, Finding, LlmCall
from app.extraction import evidence
from app.extraction.fields import REVIEW_THRESHOLD, SPECS, TEXT_ONLY_TYPES
from app.extraction.llm_extract import PROMPT_FILES
from app.llm.prompts import PROMPTS_DIR, load_prompt, prompt_fingerprint
from app.policy import CATALOGUE, POLICY_VERSION
from app.rules.engine import ALL_RULES


@dataclass(frozen=True)
class Purpose:
    """One use of the model: which prompt files make its system prompt, in order."""

    code: str
    label: str
    prompts: tuple[str, ...]
    model_role: str  # extraction | reasoning | fast
    where: str


def _extraction_purposes() -> list[Purpose]:
    out = []
    for doc_type, prompt in PROMPT_FILES.items():
        out.append(
            Purpose(
                f"document.extract.{doc_type.value}",
                f"Ler os campos: {DOC_LABEL.get(doc_type.value, doc_type.value)}",
                ("extract_common", prompt),
                "extraction",
                "Leitura de documentos (fila document.process)",
            )
        )
    return out


DOC_LABEL = {
    "nfse": "nota fiscal de serviço",
    "nfe": "nota fiscal de produto",
    "boleto": "boleto ou conta",
    "recibo": "recibo",
    "contrato": "contrato",
    "comprovante": "comprovante de pagamento",
    "guia_tributo": "guia de tributo",
}

PURPOSES: list[Purpose] = [
    Purpose(
        "document.classify",
        "Identificar o tipo do documento",
        ("classify_document",),
        "fast",
        "Leitura de documentos, quando o título não basta",
    ),
    *_extraction_purposes(),
    Purpose(
        "rule.R04.scope",
        "R04: o serviço está no escopo do contrato?",
        ("rule_scope",),
        "reasoning",
        "Regras de auditoria, quando a conferência por palavras não decide",
    ),
    Purpose(
        "rule.R07.cnae",
        "R07: a atividade do fornecedor combina com o serviço?",
        ("rule_cnae",),
        "reasoning",
        "Regras de auditoria, para categorias sem mapa de CNAE",
    ),
    Purpose(
        "finding.explain",
        "Reescrever a explicação de um achado",
        ("explain_finding",),
        "fast",
        "Achados (números conferidos por código)",
    ),
    Purpose(
        "compliance.validity",
        "Ler emissão e validade de um documento",
        ("compliance_validity",),
        "fast",
        "Conformidade (sempre 'a confirmar')",
    ),
    Purpose(
        "chat", "Pergunte à IA", ("chat_system",), "reasoning", "Chat com ferramentas de leitura"
    ),
]

# Automatic checks that open conflicts or alerts (D93, D110, D120), by detector.
DETECTORS: list[dict[str, str]] = [
    {
        "code": "aditivo_fora_da_vigencia_v1",
        "group": "Conflito entre documentos",
        "what": "Aditivo com data de efeito fora da vigência do contrato.",
    },
    {
        "code": "contratos_sobrepostos_v1",
        "group": "Conflito entre documentos",
        "what": "Dois contratos vigentes do mesmo fornecedor para o mesmo serviço.",
    },
    {
        "code": "aditivos_mesmo_dia_v1",
        "group": "Conflito entre documentos",
        "what": "Dois aditivos do mesmo contrato com efeito no mesmo dia e valores diferentes.",
    },
    {
        "code": "canal_parado_v1",
        "group": "Alerta de saúde (diário)",
        "what": "Nenhum documento recebido há mais tempo que o esperado.",
    },
    {
        "code": "contrato_aditado_v1",
        "group": "Alerta de saúde (diário)",
        "what": "Contrato com aditivo recente: valores e prazos mudaram.",
    },
    {
        "code": "revisor_ausente_v1",
        "group": "Alerta de saúde (diário)",
        "what": "Condomínio sem revisora CondoOS ativa.",
    },
    {
        "code": "sindico_sem_acesso_v1",
        "group": "Alerta de saúde (diário)",
        "what": "Nenhum síndico com acesso ativo, ou acesso perto de vencer.",
    },
    {
        "code": "acao_parada_v1",
        "group": "Alerta de saúde (diário)",
        "what": "Ação aprovada que ninguém executou.",
    },
    {
        "code": "contrato_leitura_v1",
        "group": "Alerta de contrato (leitura)",
        "what": "Assinatura depois do início, contratante que não é o condomínio, CNPJ do "
        "condomínio errado ou contrato sem o CNPJ da contratada.",
    },
]


def _since(today: date) -> datetime:
    return datetime(today.year, today.month, 1)


async def rules(
    session: AsyncSession, condos: list[Condominium], today: date
) -> list[dict[str, Any]]:
    month = today.replace(day=1)
    counts = dict(
        (
            await session.execute(
                select(Finding.rule_code, func.count())
                .where(
                    Finding.condominium_id.in_([c.id for c in condos] or [uuid.uuid4()]),
                    Finding.competence == month,
                )
                .group_by(Finding.rule_code)
            )
        ).all()
    )
    params_by_condo = {}
    for c in condos:
        _, params, _ = await settings_at(session, c, today)
        params_by_condo[c.name] = params
    out = []
    for r in ALL_RULES:
        overrides = {
            name: params.get(r.code)
            for name, params in params_by_condo.items()
            if params.get(r.code)
        }
        out.append(
            {
                "code": r.code,
                "name": r.name,
                "description": r.description,
                "severity": str(r.default_severity.value),
                "ai_assisted": r.ai_assisted,
                "default_params": r.default_params,
                "condo_params": overrides,
                "findings_this_month": int(counts.get(r.code, 0)),
            }
        )
    return out


def _versions_row(sha: str | None, first: datetime, last: datetime, n: int) -> dict[str, Any]:
    return {"sha256": sha, "first_at": first, "last_at": last, "calls": n}


async def prompts(session: AsyncSession, today: date) -> list[dict[str, Any]]:
    since = _since(today)
    stats = {
        purpose: (n, cost, failures)
        for purpose, n, cost, failures in (
            await session.execute(
                select(
                    LlmCall.purpose,
                    func.count(),
                    func.coalesce(func.sum(LlmCall.cost_usd), 0),
                    func.count().filter(LlmCall.success.is_(False)),
                )
                .where(LlmCall.created_at >= since)
                .group_by(LlmCall.purpose)
            )
        ).all()
    }
    history: dict[str, list[dict[str, Any]]] = {}
    for purpose, sha, first, last, n in (
        await session.execute(
            select(
                LlmCall.purpose,
                LlmCall.prompt_sha256,
                func.min(LlmCall.created_at),
                func.max(LlmCall.created_at),
                func.count(),
            )
            .where(LlmCall.prompt_sha256.is_not(None))
            .group_by(LlmCall.purpose, LlmCall.prompt_sha256)
            .order_by(func.max(LlmCall.created_at).desc())
        )
    ).all():
        history.setdefault(purpose, []).append(_versions_row(sha, first, last, n))
    s = get_settings()
    models = {
        "extraction": s.claude_model_extraction,
        "reasoning": s.claude_model_reasoning,
        "fast": s.claude_model_fast,
    }
    out = []
    for p in PURPOSES:
        system = "\n\n".join(load_prompt(name) for name in p.prompts)
        n, cost, failures = stats.get(p.code, (0, Decimal("0"), 0))
        current = prompt_fingerprint(system)
        out.append(
            {
                "code": p.code,
                "label": p.label,
                "where": p.where,
                "model": models[p.model_role],
                "files": [f"{name}.md" for name in p.prompts],
                "text": system,
                "sha256": current,
                "calls_this_month": int(n),
                "cost_usd_this_month": str(Decimal(cost).quantize(Decimal("0.0001"))),
                "failures_this_month": int(failures),
                "versions": [
                    {**v, "current": v["sha256"] == current} for v in history.get(p.code, [])
                ],
            }
        )
    return out


def unused_prompt_files() -> list[str]:
    """Prompt files no purpose uses (should be none; checked by a test)."""
    used = {f"{name}.md" for p in PURPOSES for name in p.prompts}
    return sorted(f.name for f in PROMPTS_DIR.glob("*.md") if f.name not in used)


def reading() -> dict[str, Any]:
    labels = {
        "nfse": "Nota fiscal de serviço",
        "nfe": "Nota fiscal de produto",
        "boleto": "Boleto ou conta",
        "recibo": "Recibo",
        "contrato": "Contrato",
        "comprovante": "Comprovante de pagamento",
        "guia_tributo": "Guia de tributo",
    }
    return {
        "threshold": REVIEW_THRESHOLD,
        "confirmed": evidence.CONFIRMED,
        "written_floor": evidence.WRITTEN_FLOOR,
        "rules": [
            f"Campo obrigatório abaixo de {REVIEW_THRESHOLD:.0%} vai para a fila de exceções.",
            f"Um campo sobe para {evidence.CONFIRMED:.0%} só com prova conferida por código: o "
            f"valor está escrito no documento (e a IA deu pelo menos "
            f"{evidence.WRITTEN_FLOOR:.0%}), a razão social é a mesma da Receita para o CNPJ "
            "lido, ou o CNPJ do condomínio é o do cadastro.",
            "Campo com problema de validação (dígito verificador, CNPJ do condomínio no lugar "
            "do fornecedor, data implausível, totais que não fecham) nunca sobe.",
            "XML fiscal e códigos com dígito verificador valem 100%; padrões do texto são só "
            "sugestão para a pessoa.",
            "Contrato pontual pede o valor total no lugar do valor mensal e do índice; contrato "
            "sem CNPJ da contratada só não trava quando o texto não mostra nenhum outro CNPJ.",
            "Documento corrigido por uma pessoa nunca é lido de novo.",
        ],
        "types": [
            {
                "code": t.value,
                "label": labels.get(t.value, t.value),
                "required": [s.label for s in specs if s.required],
                "optional": [s.label for s in specs if not s.required],
            }
            for t, specs in SPECS.items()
        ],
        "text_only": sorted(t.value for t in TEXT_ONLY_TYPES),
        "refused": ["Relação de devedores (dados de moradores): recusada e apagada."],
    }


async def detectors(session: AsyncSession) -> list[dict[str, Any]]:
    open_by = dict(
        (
            await session.execute(
                select(DataIssue.detector, func.count())
                .where(DataIssue.status == "aberto")
                .group_by(DataIssue.detector)
            )
        ).all()
    )
    return [{**d, "open": int(open_by.get(d["code"], 0))} for d in DETECTORS]


def policy() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "actions": [
            {
                "code": t.code,
                "label": t.label,
                "level": t.level,
                "always_denied": t.always_denied,
                "zero_cost_only": t.zero_cost_only,
                "sends_email": t.sends_email,
            }
            for t in CATALOGUE.values()
        ],
        "rules": [
            "Nega por padrão: ação fora do catálogo é recusada.",
            "Pagamento, contratação, multa e dados bancários: negados sempre.",
            "Toda ação precisa da aprovação do síndico na versão exata; vale 7 dias.",
            "Nada é enviado para fora, exceto o e-mail do pedido de documentos aprovado e o "
            "resumo semanal de vencimentos que o síndico ligou.",
        ],
    }


async def build(session: AsyncSession, condos: list[Condominium], today: date) -> dict[str, Any]:
    return {
        "rules": await rules(session, condos, today),
        "prompts": await prompts(session, today),
        "reading": reading(),
        "detectors": await detectors(session),
        "policy": policy(),
        "document_types": [t.value for t in DocumentType],
    }
