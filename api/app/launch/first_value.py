"""The first-value card (LB-006, F01): what the CondoOS read in a document, built by code.

Every value comes from ``document.extracted``; nothing is computed or guessed here. Each field
says where it came from (``field_provenance``, D85):

- ``lido``: read with confidence >= 0.9, or confirmed by a person;
- ``a_confirmar``: read with lower confidence — shown as such, never as a fact;
- ``nao_encontrado``: the document does not show it;
- ``inferido``: filled by a rule (no end date = indeterminate term, start = signature date,
  adjustment month = start month), shown with the rule (LB-036, D94).

The card always states the limits of the reading: one document is not an audit.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.br import format_cnpj
from app.core.money import brl
from app.data_issues import documents_of, open_issues
from app.db.enums import DocumentType, ExtractionStatus
from app.db.models import Contract, ContractAmendment, Document, ExpenseDocument
from app.extraction.fields import REVIEW_THRESHOLD, SPECS, TEXT_ONLY_TYPES

TYPE_LABEL = {
    "nfse": "uma nota fiscal de serviço",
    "nfe": "uma nota fiscal de produto",
    "boleto": "um boleto ou conta",
    "recibo": "um recibo",
    "extrato": "um extrato bancário",
    "cnab_retorno": "um arquivo de retorno do banco",
    "contrato": "um contrato",
    "convencao": "a convenção do condomínio",
    "ata": "uma ata",
    "regimento": "o regimento interno",
    "apolice": "uma apólice de seguro",
    "balancete": "um balancete",
    "laudo": "um laudo técnico",
    "plano_manutencao": "um plano de manutenção",
    "comprovante": "um comprovante de pagamento",
    "guia_tributo": "uma guia de tributo",
    "relatorio_adm": "um relatório da administradora",
    "extrato_rendimento": "um extrato de rendimento",
    "titulos": "uma planilha de unidades e títulos (sem nomes)",
    "outro": "um documento que não reconheci",
}
INDEX_LABEL = {"IPCA": "IPCA", "IGPM": "IGP-M", "INPC": "INPC", "FIXO": "Valor fixo"}
CONTRACT_FIELDS = (
    "razao_social_contratada",
    "cnpj_contratada",
    "objeto",
    "valor_mensal",
    "indice_reajuste",
    "data_inicio",
    "data_fim",
)
# Card labels where the correction screen's label carries instructions for the analyst.
CARD_LABEL = {"data_fim": "Fim da vigência"}
CONTRACT_LIMITS = [
    "Esta é a leitura de um documento, não uma auditoria.",
    "Ainda não comparei este contrato com o que foi cobrado.",
    "Aditivos que eu não recebi podem mudar valores e prazos.",
]


def _display(kind: str, value: Any, extracted: dict[str, Any]) -> str:
    try:
        if kind == "money":
            return brl(Decimal(str(value)))
        if kind == "date":
            return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
        if kind == "cnpj":
            return format_cnpj(str(value))
        if kind == "index":
            if value == "OUTRO":
                return str(extracted.get("indice_reajuste_outro") or "Outro índice")
            if value == "NENHUM":
                return "Sem reajuste"
            return INDEX_LABEL.get(str(value), str(value))
    except (ValueError, InvalidOperation):
        pass
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def _fields(doc: Document) -> list[dict[str, Any]]:
    specs = {s.name: s for s in SPECS[DocumentType.CONTRATO]}
    out: list[dict[str, Any]] = []
    for name in CONTRACT_FIELDS:
        spec = specs[name]
        value = doc.extracted.get(name)
        prov = (doc.field_provenance or {}).get(name) or {}
        item: dict[str, Any] = {"name": name, "label": CARD_LABEL.get(name, spec.label)}
        if value in (None, "", []):
            if name == "data_fim" and doc.extracted.get("data_inicio"):
                item.update(
                    status="inferido",
                    value="Prazo indeterminado",
                    rule="O documento não traz data de fim: tratado como prazo indeterminado.",
                )
            else:
                item.update(status="nao_encontrado", value=None)
            out.append(item)
            continue
        by_person = prov.get("source") == "pessoa" or doc.reviewed_at is not None
        confident = (doc.field_confidence or {}).get(name, 0.0) >= REVIEW_THRESHOLD
        item["status"] = "lido" if by_person or confident else "a_confirmar"
        if prov.get("source") == "inferido" and not by_person:
            # Filled by a rule, not read (LB-036): said as such, with the rule.
            item["status"], item["rule"] = "inferido", prov.get("rule")
        item["value"] = _display(spec.kind, value, doc.extracted)
        item["source"] = "pessoa" if by_person else prov.get("source")
        if prov.get("excerpt"):
            item["evidence"] = {"page": prov.get("page"), "excerpt": prov["excerpt"]}
        out.append(item)
    return out


async def _clauses(session: AsyncSession, doc: Document) -> list[dict[str, Any]]:
    contract = await session.scalar(
        select(Contract).where(
            Contract.condominium_id == doc.condominium_id, Contract.source_document_id == doc.id
        )
    )
    if contract is None:
        return []
    out: list[dict[str, Any]] = []
    ev = contract.clause_evidence or {}
    if contract.notice_days is not None:
        out.append(
            {
                "label": "Aviso prévio para rescisão",
                "value": f"{contract.notice_days} dias",
                "evidence": ev.get("notice_days"),
            }
        )
    if contract.auto_renewal is not None:
        out.append(
            {
                "label": "Renovação automática",
                "value": "Sim" if contract.auto_renewal else "Não",
                "evidence": ev.get("auto_renewal"),
            }
        )
    if contract.termination_penalty:
        out.append(
            {
                "label": "Multa por rescisão",
                "value": contract.termination_penalty,
                "evidence": ev.get("termination_penalty"),
            }
        )
    return out


async def _has_amendment(session: AsyncSession, doc: Document) -> bool:
    found = await session.scalar(
        select(ContractAmendment.id)
        .join(Contract, Contract.id == ContractAmendment.contract_id)
        .where(Contract.condominium_id == doc.condominium_id, Contract.source_document_id == doc.id)
        .limit(1)
    )
    return found is not None


async def first_value(session: AsyncSession, doc: Document) -> dict[str, Any]:
    base: dict[str, Any] = {
        "document_id": str(doc.id),
        "filename": doc.original_filename,
        "doc_type": doc.doc_type,
    }
    status = doc.extraction_status
    if status in (ExtractionStatus.PENDING.value, ExtractionStatus.PROCESSING.value):
        return {**base, "state": "lendo", "message": "Lendo o documento…"}
    if status == ExtractionStatus.FAILED.value:
        return {
            **base,
            "state": "falhou",
            "message": "Não consegui ler este arquivo. Tente o PDF original ou uma foto mais "
            "nítida.",
        }
    if (doc.extracted or {}).get("recusado"):
        return {**base, "state": "recusado", "message": str(doc.extracted.get("motivo") or "")}
    copy_of = await session.scalar(
        select(ExpenseDocument.expense_id).where(
            ExpenseDocument.document_id == doc.id, ExpenseDocument.role == "copia"
        )
    )
    original = (
        await session.scalar(
            select(Document.original_filename)
            .join(ExpenseDocument, ExpenseDocument.document_id == Document.id)
            .where(ExpenseDocument.expense_id == copy_of, ExpenseDocument.role == "fiscal")
            .limit(1)
        )
        if copy_of is not None
        else None
    )
    if original is not None:
        return {
            **base,
            "state": "outro_tipo",
            "message": f"Esta é uma cópia da nota já recebida ({original}). Guardei junto da "
            "mesma despesa, sem criar despesa nova.",
        }
    if doc.doc_type in {t.value for t in TEXT_ONLY_TYPES}:
        pages = doc.page_count or 0
        return {
            **base,
            "state": "memoria",
            "message": f"Guardei {TYPE_LABEL[doc.doc_type]}"
            + (f" ({pages} página{'s' if pages != 1 else ''})" if pages else "")
            + ". Já posso localizar trechos deste documento quando você precisar.",
            "limits": [
                "Guardar o texto não é interpretar o documento: questões jurídicas ou técnicas "
                "seguem com um profissional."
            ],
        }
    if doc.doc_type != DocumentType.CONTRATO.value:
        return {
            **base,
            "state": "outro_tipo",
            "message": f"Isto parece {TYPE_LABEL.get(doc.doc_type, TYPE_LABEL['outro'])}. "
            "Guardei. Para a leitura de contrato, envie o contrato.",
        }

    fields = _fields(doc)
    conflicts = [
        c for c in await open_issues(session, doc.condominium_id) if str(doc.id) in documents_of(c)
    ]
    for f in fields:  # a field in dispute is never shown as read (D93)
        if any(c.field == f["name"] for c in conflicts):
            f["status"] = "conflitante"
    to_confirm = [f["label"] for f in fields if f["status"] in ("a_confirmar", "conflitante")]
    limits = list(CONTRACT_LIMITS)
    if await _has_amendment(session, doc):
        limits[2] = (
            "Este contrato tem aditivo registrado: valores e prazos em vigor podem ser outros."
        )
    not_found = [f["label"] for f in fields if f["status"] == "nao_encontrado"]
    parts: list[str] = []
    if to_confirm:
        parts.append("Um revisor vai confirmar: " + ", ".join(to_confirm).lower() + ".")
    if not_found:
        parts.append("Não encontrei no documento: " + ", ".join(not_found).lower() + ".")
    if conflicts:
        parts.append("Há divergência com outro documento em validação.")
    if parts:
        message = "Li parte do contrato. " + " ".join(parts)
    else:
        message = "Memória ativada: já posso responder sobre este contrato."
    presumed = [f["label"] for f in fields if f["status"] == "inferido"]
    if presumed:
        message += " Presumi, por regra e não pelo texto: " + ", ".join(presumed).lower() + "."
    # Facts worth a note that do not block (D120): e.g. signed after the term started.
    for item in (doc.field_provenance or {}).values():
        if isinstance(item, dict) and item.get("note"):
            message += f" Observação: {item['note']}"
    return {
        **base,
        "state": "parcial" if parts else "lido",
        "message": message,
        "fields": fields,
        "clauses": await _clauses(session, doc),
        "conflicts": [{"id": str(c.id), "title": c.title, "detail": c.detail} for c in conflicts],
        "limits": limits,
        "next_step": {
            "key": "enviar_faturas",
            "label": "Envie as últimas faturas deste fornecedor",
            "why": "Com as faturas eu comparo o que foi cobrado com o que o contrato diz.",
        },
    }
