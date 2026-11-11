"""Imports of units, receivable titles and utility readings (D123), and the audit profile.

Unit data is internal and never carries a resident's name: any column that looks like a
name, document, e-mail or phone is dropped before anything is stored, and the file kept as
the source is a sanitised copy with only the allowed columns (the original is never
stored). Titles are keyed by unit, competence, kind and our number (or due date and amount),
so importing the same list again updates the payment status instead of duplicating.
"""

import csv
import hashlib
import io
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.condo_settings import record_version
from app.core.audit import record_audit
from app.core.money import parse_brl, parse_ddmmyyyy
from app.db.enums import DocumentOrigin, DocumentType, TitleKind, TitleStatus, Utility
from app.db.models import Condominium, Document, ReceivableTitle, Unit, UtilityReading
from app.ingestion.documents import ingest_file

# Columns that may hold personal data: never read, never stored.
PERSONAL = re.compile(
    r"nome|propriet|morador|sacado|pagador|cond[oô]mino|inquilino|locat|cpf|cnpj|"
    r"documento|e-?mail|telefone|celular|contato|endereco"
)
UNIT_COLUMNS = {
    "unidade": "unidade",
    "bloco": "bloco",
    "fracao": "fracao",
    "fracao ideal": "fracao",
}
TITLE_COLUMNS = {
    "unidade": "unidade",
    "competencia": "competencia",
    "tipo": "tipo",
    "valor": "valor",
    "vencimento": "vencimento",
    "nosso numero": "nosso_numero",
    "situacao": "situacao",
    "data pagamento": "data_pagamento",
    "data de pagamento": "data_pagamento",
    "valor pago": "valor_pago",
    "competencia consumo": "competencia_consumo",
    "data cancelamento": "data_cancelamento",
}
READING_COLUMNS = {
    "unidade": "unidade",
    "competencia": "competencia",
    "servico": "servico",
    "leitura anterior": "leitura_anterior",
    "leitura atual": "leitura_atual",
    "consumo": "consumo",
}
KIND_ALIASES = {
    "ordinaria": TitleKind.ORDINARIA,
    "taxa ordinaria": TitleKind.ORDINARIA,
    "condominio": TitleKind.ORDINARIA,
    "reserva": TitleKind.RESERVA,
    "fundo de reserva": TitleKind.RESERVA,
    "obras": TitleKind.OBRAS,
    "fundo de obras": TitleKind.OBRAS,
    "agua": TitleKind.AGUA,
    "gas": TitleKind.GAS,
    "energia": TitleKind.ENERGIA,
    "luz": TitleKind.ENERGIA,
    "multa": TitleKind.MULTA,
    "acordo": TitleKind.ACORDO,
}
STATUS_ALIASES = {
    "aberto": TitleStatus.ABERTO,
    "em aberto": TitleStatus.ABERTO,
    "pago": TitleStatus.PAGO,
    "liquidado": TitleStatus.PAGO,
    "baixado": TitleStatus.PAGO,
    "cancelado": TitleStatus.CANCELADO,
    "acordo": TitleStatus.ACORDO,
}


class ImportFileError(ValueError):
    pass


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    units_created: int = 0
    dropped_columns: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    document_id: uuid.UUID | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "criados": self.created,
            "atualizados": self.updated,
            "unidades_criadas": self.units_created,
            "colunas_descartadas": self.dropped_columns,
            "erros": self.errors[:50],
            "documento_id": str(self.document_id) if self.document_id else None,
        }


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[_\-./]", " ", text).split())


def _rows(data: bytes, allowed: dict[str, str]) -> tuple[list[dict[str, str]], list[str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    sample = text[:2000]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    lines = [r for r in reader if any(c.strip() for c in r)]
    if not lines:
        raise ImportFileError("Arquivo vazio.")
    header = [_fold(h) for h in lines[0]]
    keep: dict[int, str] = {}
    dropped: list[str] = []
    for i, h in enumerate(header):
        if PERSONAL.search(h):
            dropped.append(lines[0][i].strip())
        elif h in allowed:
            keep[i] = allowed[h]
        else:
            dropped.append(lines[0][i].strip())
    if "unidade" not in keep.values():
        raise ImportFileError("A planilha precisa da coluna “unidade”.")
    rows = [
        {name: (r[i].strip() if i < len(r) else "") for i, name in keep.items()} for r in lines[1:]
    ]
    return rows, dropped


def _sanitised_csv(rows: list[dict[str, str]], columns: list[str]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(columns)
    for r in rows:
        writer.writerow([r.get(c, "") for c in columns])
    return out.getvalue().encode("utf-8")


def _month(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    m = re.match(r"^(\d{1,2})/(\d{4})$", raw) or re.match(r"^(\d{4})-(\d{1,2})", raw)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        year, month = (b, a) if a <= 12 and b > 12 else (a, b)
        if 1 <= month <= 12:
            return date(year, month, 1)
    raise ValueError("competência inválida (use MM/AAAA)")


def _date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return date.fromisoformat(raw)
    parsed = parse_ddmmyyyy(raw)
    if parsed is None:
        raise ValueError("data inválida (use DD/MM/AAAA)")
    return parsed


def _money(raw: str) -> Decimal | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return (
            parse_brl(raw)
            if ("," in raw or "R$" in raw)
            else Decimal(raw).quantize(Decimal("0.01"))
        )
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("valor inválido") from exc


def _number(raw: str) -> Decimal | None:
    raw = raw.strip().replace(".", "").replace(",", ".") if "," in raw else raw.strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("número inválido") from exc


async def _store(
    session: AsyncSession,
    condo: Condominium,
    name: str,
    rows: list[dict[str, str]],
    columns: list[str],
    user_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Keep the sanitised copy (allowed columns only) as the source document."""
    outcome = await ingest_file(
        session,
        condominium_id=condo.id,
        filename=f"{name}-sem-nomes.csv",
        data=_sanitised_csv(rows, columns),
        origin=DocumentOrigin.UPLOAD,
        actor_user_id=user_id,
        process=False,
    )
    if outcome.document_id is not None:
        doc = await session.get(Document, outcome.document_id)
        if doc is not None:
            doc.doc_type = DocumentType.TITULOS.value
    return outcome.document_id


async def _unit(
    session: AsyncSession,
    condo: Condominium,
    code: str,
    result: ImportResult,
    cache: dict[str, Unit],
) -> Unit:
    key = " ".join(code.split())[:40]
    if key in cache:
        return cache[key]
    unit = await session.scalar(
        select(Unit).where(Unit.condominium_id == condo.id, Unit.code == key)
    )
    if unit is None:
        unit = Unit(id=uuid.uuid4(), condominium_id=condo.id, code=key)
        session.add(unit)
        await session.flush()
        result.units_created += 1
    cache[key] = unit
    return unit


async def import_units(
    session: AsyncSession, condo: Condominium, data: bytes, user_id: uuid.UUID | None
) -> ImportResult:
    rows, dropped = _rows(data, UNIT_COLUMNS)
    result = ImportResult(dropped_columns=dropped)
    result.document_id = await _store(
        session, condo, "unidades", rows, ["unidade", "bloco", "fracao"], user_id
    )
    cache: dict[str, Unit] = {}
    for n, r in enumerate(rows, start=2):
        if not r.get("unidade"):
            result.errors.append(f"Linha {n}: sem unidade.")
            continue
        existed = await session.scalar(
            select(Unit.id).where(
                Unit.condominium_id == condo.id, Unit.code == " ".join(r["unidade"].split())[:40]
            )
        )
        unit = await _unit(session, condo, r["unidade"], result, cache)
        try:
            fraction = _number(r.get("fracao", ""))
        except ValueError as exc:
            result.errors.append(f"Linha {n}: {exc}.")
            continue
        unit.block = (r.get("bloco") or None) and r["bloco"][:20]
        unit.fraction = fraction
        unit.source_document_id = result.document_id
        if existed:
            result.updated += 1
        else:
            result.created += 1
    result.units_created = 0
    await _audit(session, condo, user_id, "units", result)
    return result


def _title_key(
    unit: str, competence: date, kind: str, our_number: str, due: date, amount: Decimal
) -> str:
    raw = f"{unit}|{competence}|{kind}|{our_number or ''}|{'' if our_number else f'{due}|{amount}'}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def import_titles(
    session: AsyncSession, condo: Condominium, data: bytes, user_id: uuid.UUID | None
) -> ImportResult:
    rows, dropped = _rows(data, TITLE_COLUMNS)
    result = ImportResult(dropped_columns=dropped)
    columns = [
        "unidade",
        "competencia",
        "tipo",
        "valor",
        "vencimento",
        "nosso_numero",
        "situacao",
        "data_pagamento",
        "valor_pago",
        "competencia_consumo",
        "data_cancelamento",
    ]
    result.document_id = await _store(session, condo, "titulos", rows, columns, user_id)
    cache: dict[str, Unit] = {}
    for n, r in enumerate(rows, start=2):
        try:
            if not r.get("unidade"):
                raise ValueError("sem unidade")
            competence = _month(r.get("competencia", ""))
            amount = _money(r.get("valor", ""))
            due = _date(r.get("vencimento", ""))
            if competence is None or amount is None or due is None:
                raise ValueError("competência, valor e vencimento são obrigatórios")
            if amount <= 0:
                raise ValueError("valor precisa ser positivo")
            kind = KIND_ALIASES.get(_fold(r.get("tipo", "")) or "ordinaria", TitleKind.OUTRO)
            paid_at = _date(r.get("data_pagamento", ""))
            paid_amount = _money(r.get("valor_pago", ""))
            cancelled = _date(r.get("data_cancelamento", ""))
            status = STATUS_ALIASES.get(_fold(r.get("situacao", "")))
            if status is None:
                status = (
                    TitleStatus.CANCELADO
                    if cancelled
                    else TitleStatus.PAGO if paid_at else TitleStatus.ABERTO
                )
            reference = _month(r.get("competencia_consumo", ""))
        except ValueError as exc:
            result.errors.append(f"Linha {n}: {exc}.")
            continue
        unit = await _unit(session, condo, r["unidade"], result, cache)
        our = (r.get("nosso_numero") or "").strip()[:40]
        key = _title_key(unit.code, competence, kind.value, our, due, amount)
        title = await session.scalar(
            select(ReceivableTitle).where(
                ReceivableTitle.condominium_id == condo.id, ReceivableTitle.import_key == key
            )
        )
        values = {
            "unit_id": unit.id,
            "competence": competence,
            "reference_competence": reference,
            "kind": kind.value,
            "amount": amount,
            "due_date": due,
            "our_number": our or None,
            "status": status.value,
            "paid_at": paid_at,
            "paid_amount": (
                paid_amount
                if paid_amount is not None
                else (amount if status == TitleStatus.PAGO and paid_at else None)
            ),
            "cancelled_at": cancelled,
            "source_document_id": result.document_id,
        }
        if title is None:
            session.add(
                ReceivableTitle(id=uuid.uuid4(), condominium_id=condo.id, import_key=key, **values)
            )
            result.created += 1
        else:
            for k, v in values.items():
                setattr(title, k, v)
            result.updated += 1
    await session.flush()
    await _audit(session, condo, user_id, "titles", result)
    return result


async def import_readings(
    session: AsyncSession, condo: Condominium, data: bytes, user_id: uuid.UUID | None
) -> ImportResult:
    rows, dropped = _rows(data, READING_COLUMNS)
    result = ImportResult(dropped_columns=dropped)
    result.document_id = await _store(
        session,
        condo,
        "leituras",
        rows,
        ["unidade", "competencia", "servico", "leitura_anterior", "leitura_atual", "consumo"],
        user_id,
    )
    cache: dict[str, Unit] = {}
    for n, r in enumerate(rows, start=2):
        try:
            competence = _month(r.get("competencia", ""))
            utility = Utility(_fold(r.get("servico", "")).replace("luz", "energia"))
            previous, current = _number(r.get("leitura_anterior", "")), _number(
                r.get("leitura_atual", "")
            )
            consumption = _number(r.get("consumo", ""))
            if consumption is None and previous is not None and current is not None:
                consumption = current - previous
            if competence is None or consumption is None or consumption < 0:
                raise ValueError("competência e consumo (ou as duas leituras) são obrigatórios")
        except ValueError as exc:
            result.errors.append(f"Linha {n}: {exc}.")
            continue
        unit = await _unit(session, condo, r["unidade"], result, cache)
        row = await session.scalar(
            select(UtilityReading).where(
                UtilityReading.unit_id == unit.id,
                UtilityReading.competence == competence,
                UtilityReading.utility == utility.value,
            )
        )
        if row is None:
            session.add(
                UtilityReading(
                    condominium_id=condo.id,
                    unit_id=unit.id,
                    competence=competence,
                    utility=utility.value,
                    previous_reading=previous,
                    current_reading=current,
                    consumption=consumption,
                    source_document_id=result.document_id,
                )
            )
            result.created += 1
        else:
            row.previous_reading, row.current_reading, row.consumption = (
                previous,
                current,
                consumption,
            )
            row.source_document_id = result.document_id
            result.updated += 1
    await session.flush()
    await _audit(session, condo, user_id, "readings", result)
    return result


async def _audit(
    session: AsyncSession,
    condo: Condominium,
    user_id: uuid.UUID | None,
    kind: str,
    result: ImportResult,
) -> None:
    await record_audit(
        session,
        action=f"audit.import.{kind}",
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=user_id,
        condominium_id=condo.id,
        details={
            "created": result.created,
            "updated": result.updated,
            "dropped_columns": len(result.dropped_columns),
            "errors": len(result.errors),
        },
    )


# --------------------------------------------------------------------------- profile

PROFILE_FIELDS = {
    "funcionarios_proprios": "O condomínio tem funcionários próprios (FGTS e INSS)?",
    "parcelamento_fiscal": "Há parcelamento de tributos em andamento?",
    "iss_retido": "O condomínio retém ISS das notas de serviço?",
    "rateio_agua": "A água é rateada por unidade?",
    "rateio_gas": "O gás é rateado por unidade?",
    "rateio_energia": "A energia é rateada por unidade?",
}


def profile_of(rule_params: dict[str, Any]) -> dict[str, bool | None]:
    raw = (rule_params or {}).get("AUDIT", {}) or {}
    return {k: raw.get(k) if isinstance(raw.get(k), bool) else None for k in PROFILE_FIELDS}


async def set_profile(
    session: AsyncSession,
    condo: Condominium,
    values: dict[str, bool | None],
    user_id: uuid.UUID,
    reason: str,
) -> dict[str, bool | None]:
    """The audit profile (what applies to this condominium) is a versioned setting, with
    author and reason, like the approval limits (D85)."""
    clean = {
        k: v
        for k, v in values.items()
        if k in PROFILE_FIELDS and (v is None or isinstance(v, bool))
    }
    params = dict(condo.rule_params or {})
    params["AUDIT"] = {**(params.get("AUDIT") or {}), **clean}
    condo.rule_params = params
    await record_version(
        session, condo, actor_user_id=user_id, reason=f"Perfil de auditoria: {reason}"
    )
    return profile_of(params)
