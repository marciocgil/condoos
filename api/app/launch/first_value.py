"""The first-value card (LB-006, F01): what the CondoOS read in a contract, built by code.

Every value comes from ``document.extracted`` (or, for the notice period, from the clause
rule over the document's own text, D85). Nothing is computed or guessed here. Each field says
where it came from (``field_provenance``) and its state:

- ``lido``: read with confidence >= 0.9, or confirmed by a person;
- ``a_confirmar``: a value was read below 0.9 — never shown as a fact;
- ``nao_encontrado``: the document does not show it.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

from app.db.enums import DocumentType, ExtractionStatus
from app.db.models import Document
from app.extraction.clauses import read_clauses
from app.extraction.fields import REVIEW_THRESHOLD, specs_for

DOC_TYPE_LABEL = {
    "nfse": "uma nota fiscal de serviço",
    "nfe": "uma nota fiscal",
    "boleto": "um boleto ou conta",
    "recibo": "um recibo",
    "extrato": "um extrato bancário",
    "cnab_retorno": "um arquivo de retorno do banco",
    "convencao": "a convenção do condomínio",
    "ata": "uma ata",
    "apolice": "uma apólice de seguro",
    "balancete": "um balancete",
    "regimento": "o regimento interno",
    "laudo": "um laudo técnico",
    "plano_manutencao": "um plano de manutenção",
    "outro": "um documento de outro tipo",
}

# The fields of the card, in reading order (a subset of the contract's extraction schema).
CARD_FIELDS = (
    "razao_social_contratada",
    "cnpj_contratada",
    "objeto",
    "valor_mensal",
    "indice_reajuste",
    "mes_base_reajuste",
    "data_inicio",
    "data_fim",
)

LIMITS = (
    "Isto é a leitura de um contrato, não uma auditoria: ainda não comparei com as cobranças.",
    "Termos aditivos que eu não recebi podem mudar valores e prazos.",
    "Campo marcado “a confirmar” não entra em nenhuma conferência até uma pessoa confirmar.",
)

LIDO, A_CONFIRMAR, NAO_ENCONTRADO = "lido", "a_confirmar", "nao_encontrado"
# FR-016 classes (LB-036, D95): read with confidence but the text does not show the value
# (no excerpt to point to), and in conflict with the registered contract (open data issue).
INFERIDO, CONFLITANTE = "inferido", "conflitante"
# Document field -> contract attribute compared by app.data_issues.
CONFLICT_FIELDS = {
    "valor_mensal": "monthly_value",
    "data_inicio": "start_date",
    "data_fim": "end_date",
}


@dataclass(frozen=True)
class CardField:
    name: str
    label: str
    kind: str
    state: str
    value: Any = None
    source: str | None = None  # xml | texto | ia | pessoa | regra
    page: int | None = None
    excerpt: str | None = None


@dataclass
class FirstValue:
    document_id: str
    filename: str
    status: str  # lendo | lido | lido_parcial | nao_contrato | nao_identificado | falhou
    message: str
    doc_type: str
    fields: list[CardField] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    next_step: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _field(
    doc: Document, name: str, label: str, kind: str, conflict: str | None = None
) -> CardField:
    value = (doc.extracted or {}).get(name)
    prov = (doc.field_provenance or {}).get(name) or {}
    if _empty(value):
        return CardField(name, label, kind, NAO_ENCONTRADO)
    confirmed = doc.reviewed_at is not None or prov.get("source") == "pessoa"
    conf = float((doc.field_confidence or {}).get(name, 0.0))
    if conflict is not None:
        state = CONFLITANTE
    elif confirmed:
        state = LIDO
    elif conf < REVIEW_THRESHOLD:
        state = A_CONFIRMAR
    elif not prov.get("excerpt") and prov.get("source") != "xml":
        state = INFERIDO  # confident, but there is no excerpt showing the value
    else:
        state = LIDO
    page = prov.get("page")
    return CardField(
        name,
        label,
        kind,
        state,
        value,
        prov.get("source"),
        int(page) if isinstance(page, int) else None,
        prov.get("excerpt"),
    )


def _notice(doc: Document) -> CardField:
    clauses = read_clauses(doc.text_content)
    excerpt = (clauses.evidence.get("notice_days") or {}).get("excerpt")
    if clauses.notice_days is None:
        return CardField("aviso_previo_dias", "Aviso prévio (dias)", "int", NAO_ENCONTRADO)
    return CardField(
        "aviso_previo_dias",
        "Aviso prévio (dias)",
        "int",
        LIDO,
        clauses.notice_days,
        "regra",
        None,
        excerpt,
    )


def build(doc: Document, conflicts: dict[str, str] | None = None) -> FirstValue:
    """The card for one document, from what is stored. Pure: no query, no write.
    ``conflicts``: document field -> title of the open data issue about it (D95)."""
    conflicts = conflicts or {}

    def card(status: str, message: str, **more: Any) -> FirstValue:
        return FirstValue(
            document_id=str(doc.id),
            filename=doc.original_filename,
            doc_type=doc.doc_type,
            status=status,
            message=message,
            **more,
        )

    status = doc.extraction_status
    if status in (ExtractionStatus.PENDING.value, ExtractionStatus.PROCESSING.value):
        return card("lendo", "Lendo o documento…")
    if status == ExtractionStatus.FAILED.value:
        return card(
            "falhou",
            "Não consegui ler este arquivo. Tente o PDF original ou uma foto mais nítida.",
        )
    if doc.doc_type == DocumentType.OUTRO.value and not (doc.text_content or "").strip():
        # Nothing readable: "outro" here means "not identified", not another kind of document.
        return card(
            "nao_identificado",
            "Não consegui identificar este arquivo. Ele ficou guardado e uma pessoa vai olhar. "
            "Se for um contrato, tente o PDF original ou uma foto mais nítida.",
        )
    if doc.doc_type != DocumentType.CONTRATO.value:
        what = DOC_TYPE_LABEL.get(doc.doc_type, "um documento de outro tipo")
        return card(
            "nao_contrato",
            f"Isto parece {what}. Guardei. Para a leitura de contrato, envie o contrato.",
        )

    specs = {s.name: s for s in specs_for(DocumentType.CONTRATO)}
    fields = [_field(doc, n, specs[n].label, specs[n].kind, conflicts.get(n)) for n in CARD_FIELDS]
    fields.append(_notice(doc))
    to_confirm = [f.label for f in fields if f.state == A_CONFIRMAR]
    missing_required = [
        specs[f.name].label
        for f in fields
        if f.state == NAO_ENCONTRADO and f.name in specs and specs[f.name].required
    ]
    pending = to_confirm + missing_required
    in_conflict = [f.label for f in fields if f.state == CONFLITANTE]
    if in_conflict:
        status_out = "lido_parcial"
        message = (
            "O documento e o contrato cadastrado não batem em: "
            + ", ".join(in_conflict).lower()
            + ". Até alguém escolher a versão certa, nada é conferido com esses campos."
        )
        next_step = {
            "key": "resolver_conflito",
            "title": "Escolha a versão certa em Conflitos de dados",
        }
    elif pending:
        status_out = "lido_parcial"
        message = (
            "Li parte do contrato. Um revisor vai confirmar: " + ", ".join(pending).lower() + "."
        )
        next_step = {
            "key": "confirmar_contrato",
            "title": "Um revisor vai confirmar os campos em dúvida; você não precisa fazer nada agora",
        }
    else:
        status_out = "lido"
        message = "Memória ativada: já posso responder sobre este contrato."
        next_step = {
            "key": "enviar_faturas",
            "title": "Envie as notas fiscais recentes deste fornecedor",
        }
    return card(
        status_out,
        message,
        fields=fields,
        limits=list(LIMITS),
        next_step=next_step,
    )
