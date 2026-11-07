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
