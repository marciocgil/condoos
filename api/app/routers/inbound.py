"""Inbound e-mail channel of a condominium (D101, LB-050/051): the address, its health and
changing the address. Computed from ``inbound_message`` and the documents at each read."""

import uuid
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import local_date, local_today, utcnow
from app.db.enums import DocumentOrigin, InboundMessageStatus
from app.db.models import Condominium, Document, InboundMessage, new_inbound_token
from app.db.session import DbSession
from app.ingestion.email import PAUSE_TYPE, inbound_address
from app.policy import active_pause

router = APIRouter(tags=["inbound"])
CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]
CanChange = Annotated[CondoAccess, Depends(require(Permission.MANAGE_DELEGATION))]
RECENT = 10


async def _health(db: DbSession, access: CondoAccess) -> dict[str, Any]:
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    since = utcnow() - timedelta(days=30)
    cid = condo.id
    last_message = await db.scalar(
        select(func.max(InboundMessage.created_at)).where(InboundMessage.condominium_id == cid)
    )
    last_document = await db.scalar(
        select(func.max(Document.created_at)).where(
            Document.condominium_id == cid, Document.origin == DocumentOrigin.EMAIL.value
        )
    )
    counts = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(InboundMessage.documents), 0),
                func.count().filter(InboundMessage.status != InboundMessageStatus.PROCESSADA.value),
            ).where(InboundMessage.condominium_id == cid, InboundMessage.created_at >= since)
        )
    ).one()
    recent = await db.scalars(
        select(InboundMessage)
        .where(InboundMessage.condominium_id == cid)
        .order_by(InboundMessage.created_at.desc())
        .limit(RECENT)
    )
    today = local_today(condo.timezone)
    return {
        "address": inbound_address(condo),
        "can_change": access.can(Permission.MANAGE_DELEGATION),
        "paused": await active_pause(db, cid, PAUSE_TYPE) is not None,
        "last_message_at": last_message.isoformat() if last_message else None,
        "last_document_at": last_document.isoformat() if last_document else None,
        "days_since_last_message": (
            (today - local_date(last_message, condo.timezone)).days if last_message else None
        ),
        "last_30_days": {
            "messages": int(counts[0]),
            "documents": int(counts[1]),
            "not_processed": int(counts[2]),
        },
        "recent": [
            {
                "received_at": m.created_at.isoformat(),
                "sender_domain": m.sender_domain,
                "status": m.status,
                "attachments": m.attachments,
                "documents": m.documents,
                "duplicates": m.duplicates,
                "refused": m.refused,
                "reasons": m.reasons,
            }
            for m in recent
        ],
    }


@router.get("/condominiums/{condominium_id}/inbound")
async def channel(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    return await _health(db, access)


@router.post("/condominiums/{condominium_id}/inbound/change-address")
async def change_address(
    condominium_id: uuid.UUID, access: CanChange, db: DbSession
) -> dict[str, Any]:
    """A new random part: the old address stops working at once. Documents that already
    arrived stay. Only ids go to the audit log."""
    condo = await db.get(Condominium, access.condominium_id)
    assert condo is not None
    condo.inbound_token = new_inbound_token()
    await record_audit(
        db,
        action="inbound.address_changed",
        object_type="condominium",
        object_id=condo.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
    )
    await db.flush()
    return await _health(db, access)
