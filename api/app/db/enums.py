"""Domain enumerations. Values are persisted as VARCHAR with CHECK constraints."""

from enum import StrEnum


class Role(StrEnum):
    SINDICO = "sindico"
    SUBSINDICO = "subsindico"
    CONSELHEIRO = "conselheiro"
    GERENTE = "gerente"
    ANALISTA = "analista"
    # Reserved for later pilots (D77): accepted in memberships, no permission yet.
    ZELADOR = "zelador"
    FORNECEDOR = "fornecedor"
    MORADOR = "morador"
    # CondoOS staff (D77). Never stored in ``membership``: they come from ``platform_role``
    # plus a ``condo_assignment`` on each condominium.
    CONDOOS_ADMIN = "condoos_admin"
    CONDOOS_REVIEWER = "condoos_reviewer"


class PlatformRole(StrEnum):
    CONDOOS_ADMIN = "condoos_admin"
    CONDOOS_REVIEWER = "condoos_reviewer"


# Roles a ``membership`` row may hold (the CHECK constraint of migration 0011).
MEMBERSHIP_ROLES: tuple[Role, ...] = (
    Role.SINDICO,
    Role.SUBSINDICO,
    Role.CONSELHEIRO,
    Role.GERENTE,
    Role.ANALISTA,
    Role.ZELADOR,
    Role.FORNECEDOR,
    Role.MORADOR,
)


class BoardPosition(StrEnum):
    SINDICO = "sindico"
    SUBSINDICO = "subsindico"
    CONSELHEIRO = "conselheiro"


class AdjustmentIndex(StrEnum):
    IPCA = "IPCA"
    IGPM = "IGPM"
    INPC = "INPC"
    FIXO = "FIXO"
    NENHUM = "NENHUM"
    OUTRO = "OUTRO"  # another index or criterion, described in text (D68)


class DocumentType(StrEnum):
    NFSE = "nfse"
    NFE = "nfe"
    BOLETO = "boleto"
    RECIBO = "recibo"
    EXTRATO = "extrato"
    CNAB_RETORNO = "cnab_retorno"
    CONTRATO = "contrato"
    CONVENCAO = "convencao"
    ATA = "ata"
    OUTRO = "outro"


class DocumentOrigin(StrEnum):
    UPLOAD = "upload"
    EMAIL = "email"
    SEED = "seed"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class BankTransactionOrigin(StrEnum):
    CNAB = "cnab"
    OFX = "ofx"
    CSV = "csv"
    OPEN_FINANCE = "open_finance"
    SEED = "seed"


class Severity(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class FindingStatus(StrEnum):
    AGUARDANDO_VALIDACAO = "aguardando_validacao"
    PUBLICADO = "publicado"
    CONFIRMADO = "confirmado"
    CONTESTADO = "contestado"
    IGNORADO = "ignorado"
    DESCARTADO = "descartado"
    # The rule stopped detecting it after new data (e.g. the missing note arrived) before any
    # person acted on it (D61). Kept for the record; not shown to the board, not at risk.
    SUPERADO = "superado"
    # Inconclusive: a reviewer asked for more evidence (D74). Not shown to the board and not
    # counted at risk until reviewed again.
    PENDENTE_EVIDENCIA = "pendente_evidencia"


class DecisionAction(StrEnum):
    VALIDAR = "validar"
    DESCARTAR = "descartar"
    CONFIRMAR = "confirmar"
    CONTESTAR = "contestar"
    IGNORAR = "ignorar"
    REABRIR = "reabrir"
    SOLICITAR_EVIDENCIA = "solicitar_evidencia"


class ReviewRequirement(StrEnum):
    """What a finding (or, later, an opportunity) needs before the board sees it (D74)."""

    NONE = "none"  # published directly
    QUALIFIED_REVIEW = (
        "qualified_review"  # a qualified person reviews (reviewer; manager if allowed)
    )
    INTERNAL_REVIEW = "internal_review"  # only a CondoOS reviewer (economy recommendations)
    PENDING_EVIDENCE = "pending_evidence"  # inconclusive: waits for evidence


class CompetenceStatus(StrEnum):
    ABERTA = "aberta"
    FECHADA = "fechada"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


# Statuses a síndico / conselheiro / subsíndico may see.
VISIBLE_TO_BOARD: frozenset[FindingStatus] = frozenset(
    {
        FindingStatus.PUBLICADO,
        FindingStatus.CONFIRMADO,
        FindingStatus.CONTESTADO,
        FindingStatus.IGNORADO,
    }
)

# Statuses that are no longer (or not yet) risk: out of "valor em risco".
NOT_AT_RISK: frozenset[FindingStatus] = frozenset(
    {
        FindingStatus.IGNORADO,
        FindingStatus.DESCARTADO,
        FindingStatus.SUPERADO,
        FindingStatus.PENDENTE_EVIDENCIA,
    }
)

# Statuses waiting for a reviewer (queue, closing check, portfolio counters).
UNDER_REVIEW: frozenset[FindingStatus] = frozenset(
    {FindingStatus.AGUARDANDO_VALIDACAO, FindingStatus.PENDENTE_EVIDENCIA}
)


# --------------------------------------------------------------------------- cases (D75, D80)


class CaseStatus(StrEnum):
    """Spec §8.2. ``suspenso_justificadamente`` is the only open state without a due date."""

    NOVO = "novo"
    EM_TRIAGEM = "em_triagem"
    EM_PLANEJAMENTO = "em_planejamento"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao"
    EM_EXECUCAO = "em_execucao"
    AGUARDANDO_TERCEIRO = "aguardando_terceiro"
    AGUARDANDO_VALIDACAO = "aguardando_validacao"
    RESOLVIDO = "resolvido"
    CANCELADO = "cancelado"
    REABERTO = "reaberto"
    SUSPENSO = "suspenso_justificadamente"


CLOSED_CASE: frozenset[CaseStatus] = frozenset({CaseStatus.RESOLVIDO, CaseStatus.CANCELADO})


class CaseOrigin(StrEnum):
    FINDING = "finding"
    OPPORTUNITY = "opportunity"
    HUMAN_REQUEST = "human_request"
    MAINTENANCE = "maintenance"
    OBLIGATION = "obligation"
    EXTERNAL_EVENT = "external_event"


class CaseSeverity(StrEnum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


class CaseCategory(StrEnum):
    FINANCEIRO = "financeiro"
    CONTRATO = "contrato"
    MANUTENCAO = "manutencao"
    CONFORMIDADE = "conformidade"
    ADMINISTRATIVO = "administrativo"
    ATENDIMENTO = "atendimento"
    SEGURANCA = "seguranca"
    OBRA = "obra"
    OUTRO = "outro"


class CaseLinkTarget(StrEnum):
    FINDING = "finding"
    OPPORTUNITY = "opportunity"  # accepted by the schema; the Optimize slice enables it
    DOCUMENT = "document"
    CONTRACT = "contract"
    SUPPLIER = "supplier"
    EXPENSE = "expense"
    CASE = "case"


class TaskStatus(StrEnum):
    ABERTA = "aberta"
    EM_ANDAMENTO = "em_andamento"
    BLOQUEADA = "bloqueada"
    CONCLUIDA = "concluida"
    CANCELADA = "cancelada"


CLOSED_TASK: frozenset[TaskStatus] = frozenset({TaskStatus.CONCLUIDA, TaskStatus.CANCELADA})


# --------------------------------------------------------------------------- opportunities (D76, D81)


class OpportunityStatus(StrEnum):
    IDENTIFICADA = "identificada"
    EM_REVISAO_INTERNA = "em_revisao_interna"
    DEVOLVIDA = "devolvida"
    REJEITADA = "rejeitada"
    APROVADA_PARA_CLIENTE = "aprovada_para_cliente"
    APROVADA_PELO_CONDOMINIO = "aprovada_pelo_condominio"
    RECUSADA_PELO_CONDOMINIO = "recusada_pelo_condominio"
    EM_EXECUCAO = "em_execucao"
    IMPLEMENTADA = "implementada"
    RESULTADO_MEDIDO = "resultado_medido"
    ENCERRADA = "encerrada"


class OpportunityType(StrEnum):
    REAJUSTE = "reajuste"
    COBRANCA_INCONSISTENTE = "cobranca_inconsistente"
    RENEGOCIACAO = "renegociacao"
    RACIONALIZACAO_ESCOPO = "racionalizacao_escopo"
    RECUPERACAO = "recuperacao"
    COMPRA_ALTERNATIVA = "compra_alternativa"
    EFICIENCIA_OPERACIONAL = "eficiencia_operacional"


class SavingsStage(StrEnum):
    """Never summed with each other (D76): each is a separate, dated photograph."""

    POTENCIAL = "potencial"
    ESTIMADA_VALIDADA = "estimada_validada"
    APROVADA = "aprovada"
    CONTRATADA = "contratada"
    REALIZADA = "realizada"


class OpportunityReviewAction(StrEnum):
    APROVAR = "aprovar"
    AJUSTAR = "ajustar"
    DEVOLVER = "devolver"
    REJEITAR = "rejeitar"
    REABRIR_REVISAO = "reabrir_revisao"
    # The condominium's own decision (approve_in_condo), recorded in the same trail.
    CONDOMINIO_APROVAR = "condominio_aprovar"
    CONDOMINIO_RECUSAR = "condominio_recusar"
