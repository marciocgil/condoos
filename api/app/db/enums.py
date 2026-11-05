"""Domain enumerations. Values are persisted as VARCHAR with CHECK constraints."""

from enum import StrEnum


class Role(StrEnum):
    SINDICO = "sindico"
    SUBSINDICO = "subsindico"
    CONSELHEIRO = "conselheiro"
    GERENTE = "gerente"
    ANALISTA = "analista"


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


class DecisionAction(StrEnum):
    VALIDAR = "validar"
    DESCARTAR = "descartar"
    CONFIRMAR = "confirmar"
    CONTESTAR = "contestar"
    IGNORAR = "ignorar"
    REABRIR = "reabrir"


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
