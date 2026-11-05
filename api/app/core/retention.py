"""Retention of fiscal documents (spec §12): files older than the condominium's
``retention_years`` (default 5) are deleted from storage and from ``document``.

Only fiscal and bank files are purged. Kept: convention and minutes (governing documents),
any contract file while the contract is in force or ended less than the retention period
ago, and every accounting record (expenses, bank transactions, findings, decisions and the
audit log, which only receive a reference to the purge). The age of a file is its issue
date when extracted, else the day it was received.
"""

import asyncio
import logging
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.time import add_months
from app.db.enums import DocumentType
from app.db.models import Condominium, Contract, Document
from app.reports.data import month_of
from app.storage.base import get_storage

logger = logging.getLogger(__name__)

RETENTION_JOB = "retention.purge"
PURGED_TYPES = {
    DocumentType.NFSE.value,
    DocumentType.NFE.value,
    DocumentType.BOLETO.value,
    DocumentType.RECIBO.value,
    DocumentType.EXTRATO.value,
    DocumentType.CNAB_RETORNO.value,
    DocumentType.OUTRO.value,
    DocumentType.CONTRATO.value,  # only once the contract itself is past retention
}


def _document_date(doc: Document) -> date:
    v = doc.extracted or {}
    for key in ("data_emissao", "data", "vencimento"):
        when = month_of(v.get(key))
        if when is not None:
            return when
    return doc.created_at.date()


async def purge_condominium(session: AsyncSession, condo: Condominium, today: date) -> int:
    cutoff = add_months(today.replace(day=1), -12 * condo.retention_years)
    candidates = list(
        await session.scalars(
            select(Document).where(
                Document.condominium_id == condo.id, Document.doc_type.in_(PURGED_TYPES)
            )
        )
    )
    in_force: set[uuid.UUID] = set()
    for c in await session.scalars(
        select(Contract).where(
            Contract.condominium_id == condo.id, Contract.source_document_id.is_not(None)
        )
    ):
        if c.end_date is None or c.end_date >= cutoff:
            assert c.source_document_id is not None
            in_force.add(c.source_document_id)
    purged = 0
    storage = get_storage()
    for doc in candidates:
        if doc.id in in_force or _document_date(doc) >= cutoff:
            continue
        try:
            await asyncio.to_thread(storage.delete, doc.storage_key)
        except Exception:  # storage errors must not keep the row forever; retried next day
            logger.warning("retention: file not deleted id=%s", doc.id)
            continue
        await session.delete(doc)
        purged += 1
    if purged:
        await record_audit(
            session,
            action="retention.purged",
            object_type="condominium",
            object_id=condo.id,
            condominium_id=condo.id,
            details={"documents": purged, "cutoff": cutoff.isoformat()},
        )
    await session.flush()
    return purged


async def purge_job(session: AsyncSession, payload: dict[str, Any]) -> None:
    today = date.fromisoformat(payload["today"]) if payload.get("today") else date.today()
    for condo in list(await session.scalars(select(Condominium))):
        n = await purge_condominium(session, condo, today)
        if n:
            logger.info("retention purged condominium=%s documents=%s", condo.id, n)
