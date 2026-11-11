"""The monthly farol sent to the síndico (D124).

The CondoOS team (review_audit) sends the month once every result that needed a person was
reviewed; the content is frozen with its SHA-256. The síndico approves (or returns, with a
reason) the version seen: if any result changed after sending, the sending is superseded and
the team sends again. Approving marks the results APPROVED_FOR_PUBLICATION; the conselho
and the subsíndico see only what was approved. The síndico's approval says the farol may be
shown, never that the accounts are approved (that is DOC-03, by the conselho or assembly).

What is published carries no unit data (D123): for the unit-based controls only the status
and the rationale (which states counts, never unit codes) go out.
"""

import hashlib
import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.catalog import CONTROLS, PILLARS
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import ControlReviewState, PublicationStatus
from app.db.models import AuditControlResult, AuditPeriod, AuditPublication

UNIT_CONTROLS = {"REC-02", "REC-03", "REC-04"}
P = PublicationStatus


class PublicationError(ValueError):
    pass


async def current_results(
    session: AsyncSession, period_id: uuid.UUID
) -> dict[str, AuditControlResult]:
    rows = await session.scalars(
        select(AuditControlResult).where(
            AuditControlResult.period_id == period_id,
            AuditControlResult.superseded_by_id.is_(None),
        )
    )
    return {r.control_id: r for r in rows}


def snapshot_of(period: AuditPeriod, results: dict[str, AuditControlResult]) -> dict[str, Any]:
    controls = []
    counts: dict[str, int] = {}
    for c in CONTROLS:
        r = results.get(c.id)
        if r is None:
            continue
        counts[r.status] = counts.get(r.status, 0) + 1
        controls.append(
            {
                "id": c.id,
                "nome": c.name,
                "pilar": PILLARS[c.pillar],
                "status": r.status,
                "motivo": r.rationale,
                "cobertura": str(r.coverage) if r.coverage is not None else None,
                "diferencas": str(r.differences) if r.differences is not None else None,
                "pendencias": [] if c.id in UNIT_CONTROLS else list(r.missing or [])[:5],
                "resultado_id": str(r.id),
            }
        )
    return {
        "competencia": period.competence.strftime("%Y-%m"),
        "controles": controls,
        "contagem": counts,
    }


def digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


async def _period(session: AsyncSession, condo_id: uuid.UUID, competence: date) -> AuditPeriod:
    period = await session.scalar(
        select(AuditPeriod).where(
            AuditPeriod.condominium_id == condo_id, AuditPeriod.competence == competence
        )
    )
    if period is None:
        raise PublicationError("Nenhuma execução da auditoria nesta competência.")
    return period


async def waiting(session: AsyncSession, period_id: uuid.UUID) -> AuditPublication | None:
    return await session.scalar(
        select(AuditPublication).where(
            AuditPublication.period_id == period_id,
            AuditPublication.status == P.AGUARDANDO.value,
        )
    )


async def supersede_if_changed(session: AsyncSession, period: AuditPeriod) -> bool:
    """A sending whose content no longer matches the current results is superseded."""
    pub = await waiting(session, period.id)
    if pub is None:
        return False
    current = snapshot_of(period, await current_results(session, period.id))
    if digest(current) == pub.snapshot_sha256:
        return False
    pub.status = P.SUPERADA.value
    pub.reason = "Resultado mudou depois do envio ao síndico."
    await session.flush()
    await record_audit(
        session,
        action="audit.publication.superseded",
        object_type="audit_publication",
        object_id=pub.id,
        actor_user_id=None,
        condominium_id=pub.condominium_id,
        details={"competencia": period.competence.isoformat()},
    )
    return True


async def submit(
    session: AsyncSession, condo_id: uuid.UUID, competence: date, user_id: uuid.UUID
) -> AuditPublication:
    period = await _period(session, condo_id, competence)
    results = await current_results(session, period.id)
    if len(results) < len(CONTROLS):
        raise PublicationError("Rode a auditoria do mês antes de enviar ao síndico.")
    open_review = sorted(
        cid
        for cid, r in results.items()
        if r.review_state == ControlReviewState.NEEDS_HUMAN_REVIEW.value
    )
    if open_review:
        raise PublicationError(
            "Revise antes de enviar: " + ", ".join(open_review) + " aguardam revisão humana."
        )
    previous = await waiting(session, period.id)
    if previous is not None:
        previous.status = P.SUPERADA.value
        previous.reason = "Substituído por um envio novo."
        await session.flush()
    snap = snapshot_of(period, results)
    pub = AuditPublication(
        id=uuid.uuid4(),
        condominium_id=condo_id,
        period_id=period.id,
        status=P.AGUARDANDO.value,
        snapshot=snap,
        snapshot_sha256=digest(snap),
        submitted_by=user_id,
        submitted_at=utcnow(),
    )
    session.add(pub)
    await session.flush()
    await record_audit(
        session,
        action="audit.publication.submitted",
        object_type="audit_publication",
        object_id=pub.id,
        actor_user_id=user_id,
        condominium_id=condo_id,
        details={"competencia": competence.isoformat(), "sha256": pub.snapshot_sha256},
    )
    return pub


async def decide(
    session: AsyncSession,
    condo_id: uuid.UUID,
    publication_id: uuid.UUID,
    *,
    approve: bool,
    seen_sha256: str,
    reason: str | None,
    user_id: uuid.UUID,
) -> AuditPublication:
    pub = await session.get(AuditPublication, publication_id)
    if pub is None or pub.condominium_id != condo_id:
        raise LookupError("envio não encontrado")
    if pub.status != P.AGUARDANDO.value:
        raise PublicationError("Este envio não está mais aguardando o síndico.")
    if pub.submitted_by is not None and pub.submitted_by == user_id:
        raise PublicationError("Quem enviou o farol não pode aprová-lo.")
    if seen_sha256 != pub.snapshot_sha256:
        raise PublicationError("A versão aprovada não é a que está aguardando: recarregue.")
    period = await session.get(AuditPeriod, pub.period_id)
    assert period is not None
    if await supersede_if_changed(session, period):
        raise PublicationError(
            "O farol mudou depois do envio (nova execução). A equipe CondoOS precisa reenviar."
        )
    clean = (reason or "").strip()
    if not approve and len(clean) < 10:
        raise PublicationError("Diga o motivo da devolução (pelo menos 10 caracteres).")
    pub.status = (P.APROVADA if approve else P.DEVOLVIDA).value
    pub.decided_by = user_id
    pub.decided_at = utcnow()
    pub.reason = clean[:2000] or None
    if approve:
        ids = [uuid.UUID(c["resultado_id"]) for c in pub.snapshot.get("controles", [])]
        for r in await session.scalars(
            select(AuditControlResult).where(AuditControlResult.id.in_(ids or [uuid.uuid4()]))
        ):
            r.review_state = ControlReviewState.APPROVED_FOR_PUBLICATION.value
    await session.flush()
    await record_audit(
        session,
        action="audit.publication.approved" if approve else "audit.publication.returned",
        object_type="audit_publication",
        object_id=pub.id,
        actor_user_id=user_id,
        condominium_id=condo_id,
        details={"competencia": period.competence.isoformat(), "sha256": pub.snapshot_sha256},
    )
    return pub


async def latest(
    session: AsyncSession, condo_id: uuid.UUID, *, statuses: tuple[str, ...]
) -> list[AuditPublication]:
    return list(
        await session.scalars(
            select(AuditPublication)
            .where(
                AuditPublication.condominium_id == condo_id,
                AuditPublication.status.in_(statuses),
            )
            .order_by(AuditPublication.submitted_at.desc())
        )
    )


async def changed_since(session: AsyncSession, pub: AuditPublication) -> bool:
    """An approved farol whose month was revalidated with a different result."""
    period = await session.get(AuditPeriod, pub.period_id)
    if period is None:
        return False
    return digest(snapshot_of(period, await current_results(session, period.id))) != (
        pub.snapshot_sha256
    )
