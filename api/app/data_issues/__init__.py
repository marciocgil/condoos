"""Data issues (D93, ADR-L05): conflicts between documents, detected by code.

Detectors (deterministic, versioned in ``detector``):

- ``aditivo_fora_da_vigencia_v1``: an amendment takes effect after the end its contract
  document states (or before the contract starts).
- ``contratos_sobrepostos_v1``: two contracts of the same supplier for the same service
  (object words overlap) with periods that cross, neither being a version of the other.
- ``aditivos_mesmo_dia_v1``: two amendments of one contract, same effective date, different
  monthly values.

Lifecycle: detected → ``aberto``; a person resolves (prevailing version and reason) or
discards (reason). An open issue that is no longer detected, with no person's action, is
discarded as "superado por novos dados" (like D61) and comes back if detected again. What a
person decided stays. Every step is a ``data_issue_event`` (append only).

While open, readiness C2/C3 is partial, the first-value card marks the field as conflicting,
findings on the contract say so in their evidence, and the policy refuses actions with the
supplier (D93). Resolving records the decision; it does not edit the contract — a correction
of the data goes through the existing screens.
"""

import uuid
from dataclasses import dataclass, field
from dataclasses import field as dc_field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.money import brl
from app.core.time import utcnow
from app.db.enums import DataIssueAudience, DataIssueEventKind, DataIssueKind, DataIssueStatus
from app.db.models import Contract, ContractAmendment, DataIssue, DataIssueEvent, Document
from app.matching.text import overlap
from app.rules.contracts import value_label

CAPABILITIES = ["C2", "C3"]
SAME_SERVICE = 0.6  # share of the shorter object's words found in the other
SUPERSEDED = "Superado por novos dados: o conflito não aparece mais nos documentos."
ALERT_SUPERSEDED = "Superado: a condição do alerta não aparece mais nos dados."
MIN_REASON = 10

ZERO = Decimal("0")


class DataIssueError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Found:
    dedupe_key: str
    detector: str
    subject_id: uuid.UUID
    supplier_id: uuid.UUID | None
    title: str
    detail: str
    field: str | None
    evidence: list[dict[str, Any]]
    amount_at_stake: Decimal | None = None
    # Conflicts (D93) by default; the health monitors (D110) set their own.
    kind: str = DataIssueKind.CONFLITO_DOCUMENTOS.value
    subject_type: str = "contract"
    capabilities: list[str] = dc_field(default_factory=lambda: list(CAPABILITIES))
    audience: str = DataIssueAudience.CONDOMINIO.value


@dataclass
class DetectionResult:
    opened: list[uuid.UUID] = field(default_factory=list)
    superseded: list[uuid.UUID] = field(default_factory=list)


def _br(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "sem data"


def _side(
    doc: Document | None, label: str, value: str, contract_id: uuid.UUID, prov_field: str
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": label,
        "value": value,
        "contract_id": str(contract_id),
        "document_id": str(doc.id) if doc else None,
        "filename": doc.original_filename if doc else None,
    }
    prov = ((doc.field_provenance or {}).get(prov_field) or {}) if doc else {}
    if prov.get("excerpt"):
        item["excerpt"], item["page"] = prov["excerpt"], prov.get("page")
    return item


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


async def _find(session: AsyncSession, condo_id: uuid.UUID) -> list[Found]:
    contracts = list(
        await session.scalars(select(Contract).where(Contract.condominium_id == condo_id))
    )
    amendments = list(
        await session.scalars(
            select(ContractAmendment).where(ContractAmendment.condominium_id == condo_id)
        )
    )
    doc_ids = {c.source_document_id for c in contracts} | {a.document_id for a in amendments}
    docs = {
        d.id: d
        for d in await session.scalars(
            select(Document).where(Document.id.in_([i for i in doc_ids if i is not None]))
        )
    }
    by_id = {c.id: c for c in contracts}
    found: list[Found] = []

    # 1. Amendment outside the term its contract document states.
    for a in amendments:
        c = by_id.get(a.contract_id)
        if c is None:
            continue
        source = docs.get(c.source_document_id) if c.source_document_id else None
        stated_end = _date((source.extracted or {}).get("data_fim")) if source else None
        before = a.effective_date < c.start_date
        after = stated_end is not None and a.effective_date > stated_end
        if not (before or after):
            continue
        adoc = docs.get(a.document_id) if a.document_id else None
        limit = f"começo em {_br(c.start_date)}" if before else f"fim em {_br(stated_end)}"
        found.append(
            Found(
                dedupe_key=f"aditivo_fora_da_vigencia:{c.id}:{a.document_id or a.id}",
                detector="aditivo_fora_da_vigencia_v1",
                subject_id=c.id,
                supplier_id=c.supplier_id,
                title="Aditivo com data de efeito fora da vigência do contrato",
                detail=(
                    f"O aditivo vale a partir de {_br(a.effective_date)}, mas o contrato diz "
                    f"{limit}. Confira se o aditivo é deste contrato ou se houve renovação não "
                    "enviada."
                ),
                field="data_fim" if after else "data_inicio",
                evidence=[
                    _side(
                        source,
                        "Contrato",
                        limit,
                        c.id,
                        "data_fim" if after else "data_inicio",
                    ),
                    _side(
                        adoc, "Aditivo", f"efeito em {_br(a.effective_date)}", c.id, "data_inicio"
                    ),
                ],
            )
        )

    # 2. Two contracts of the same supplier for the same service, periods crossing.
    for i, ca in enumerate(contracts):
        for cb in contracts[i + 1 :]:
            if (
                ca.supplier_id is None
                or ca.supplier_id != cb.supplier_id
                or ca.monthly_value is None
                or cb.monthly_value is None
                or overlap(ca.object, cb.object) < SAME_SERVICE
            ):
                continue
            a_end, b_end = ca.end_date or date.max, cb.end_date or date.max
            if ca.start_date > b_end or cb.start_date > a_end:
                continue
            da = docs.get(ca.source_document_id) if ca.source_document_id else None
            db = docs.get(cb.source_document_id) if cb.source_document_id else None
            if da and db and (da.supersedes_id == db.id or db.supersedes_id == da.id):
                continue  # a new version of the same document (D85), not a conflict
            first, second = sorted((ca, cb), key=lambda k: (k.start_date, str(k.id)))
            diff = abs((first.monthly_value or ZERO) - (second.monthly_value or ZERO))
            found.append(
                Found(
                    dedupe_key=f"contratos_sobrepostos:{first.id}:{second.id}",
                    detector="contratos_sobrepostos_v1",
                    subject_id=second.id,
                    supplier_id=first.supplier_id,
                    title="Dois contratos vigentes do mesmo fornecedor para o mesmo serviço",
                    detail=(
                        "Os períodos se cruzam e nenhum é versão do outro. Pode ser uma versão "
                        "antiga não marcada ou um segundo serviço: confirme qual vale."
                    ),
                    field=None,
                    evidence=[
                        _side(
                            docs.get(k.source_document_id) if k.source_document_id else None,
                            f"Contrato de {_br(k.start_date)}",
                            f"{value_label(k)}, de {_br(k.start_date)} a "
                            f"{_br(k.end_date) if k.end_date else 'prazo indeterminado'}",
                            k.id,
                            "valor_mensal",
                        )
                        for k in (first, second)
                    ],
                    amount_at_stake=diff or None,
                )
            )

    # 3. Two amendments of one contract on the same day with different values.
    by_day: dict[tuple[uuid.UUID, date], list[ContractAmendment]] = {}
    for a in amendments:
        if a.monthly_value is not None:
            by_day.setdefault((a.contract_id, a.effective_date), []).append(a)
    for (contract_id, day), group in by_day.items():
        values = {a.monthly_value for a in group}
        c = by_id.get(contract_id)
        if len(values) < 2 or c is None:
            continue
        group.sort(key=lambda a: str(a.id))
        found.append(
            Found(
                dedupe_key=f"aditivos_mesmo_dia:{contract_id}:{day.isoformat()}",
                detector="aditivos_mesmo_dia_v1",
                subject_id=contract_id,
                supplier_id=c.supplier_id,
                title="Aditivos do mesmo dia com valores mensais diferentes",
                detail=f"Há {len(group)} aditivos com efeito em {_br(day)} e valores diferentes.",
                field="valor_mensal",
                evidence=[
                    _side(
                        docs.get(a.document_id) if a.document_id else None,
                        "Aditivo",
                        (
                            f"{brl(a.monthly_value)} por mês"
                            if a.monthly_value is not None
                            else "sem valor"
                        ),
                        contract_id,
                        "valor_mensal",
                    )
                    for a in group
                ],
                amount_at_stake=max(values) - min(values),  # type: ignore[type-var,operator]
            )
        )
    return found


async def _event(
    session: AsyncSession,
    issue: DataIssue,
    kind: DataIssueEventKind,
    user_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
) -> None:
    session.add(
        DataIssueEvent(
            id=uuid.uuid4(),
            condominium_id=issue.condominium_id,
            issue_id=issue.id,
            kind=kind.value,
            user_id=user_id,
            payload=payload or {},
        )
    )


async def reconcile(
    session: AsyncSession, condo_id: uuid.UUID, found_list: list[Found], kinds: set[str]
) -> DetectionResult:
    """Open what was found, open again what came back after "superado", and close as
    "superado" what is no longer found and nobody acted on. Only issues of ``kinds`` are
    touched: conflicts and health alerts are reconciled separately. Idempotent."""
    result = DetectionResult()
    found = {f.dedupe_key: f for f in found_list}
    existing = {
        i.dedupe_key: i
        for i in await session.scalars(
            select(DataIssue).where(
                DataIssue.condominium_id == condo_id, DataIssue.kind.in_(sorted(kinds))
            )
        )
    }
    for key, f in found.items():
        issue = existing.get(key)
        if issue is None:
            issue = DataIssue(
                id=uuid.uuid4(),
                condominium_id=condo_id,
                kind=f.kind,
                status=DataIssueStatus.ABERTO.value,
                subject_type=f.subject_type,
                subject_id=f.subject_id,
                supplier_id=f.supplier_id,
                field=f.field,
                title=f.title,
                detail=f.detail,
                evidence=f.evidence,
                capabilities=list(f.capabilities),
                amount_at_stake=f.amount_at_stake,
                detector=f.detector,
                dedupe_key=key,
                audiencia=f.audience,
            )
            session.add(issue)
            await session.flush()
            await _event(session, issue, DataIssueEventKind.DETECTADO, None)
            result.opened.append(issue.id)
            continue
        superseded = (issue.resolution or {}).get("superado") is True
        if issue.status == DataIssueStatus.ABERTO.value or superseded:
            issue.evidence, issue.detail = f.evidence, f.detail
            issue.amount_at_stake = f.amount_at_stake
        if superseded:  # back after "superado": open again
            issue.status = DataIssueStatus.ABERTO.value
            issue.resolution = None
            await _event(session, issue, DataIssueEventKind.REDETECTADO, None)
            result.opened.append(issue.id)
    for key, issue in existing.items():
        if key in found or issue.status != DataIssueStatus.ABERTO.value:
            continue
        human = await session.scalar(
            select(DataIssueEvent.id)
            .where(DataIssueEvent.issue_id == issue.id, DataIssueEvent.user_id.is_not(None))
            .limit(1)
        )
        if human is not None:
            continue  # a person acted on it: never closed by itself
        reason = (
            SUPERSEDED
            if issue.kind == DataIssueKind.CONFLITO_DOCUMENTOS.value
            else (ALERT_SUPERSEDED)
        )
        issue.status = DataIssueStatus.DESCARTADO.value
        issue.resolution = {"superado": True, "reason": reason}
        await _event(session, issue, DataIssueEventKind.SUPERADO, None)
        result.superseded.append(issue.id)
    await session.flush()
    return result


async def detect(session: AsyncSession, condo_id: uuid.UUID) -> DetectionResult:
    """Run every conflict detector for one condominium. Idempotent."""
    return await reconcile(
        session, condo_id, await _find(session, condo_id), {DataIssueKind.CONFLITO_DOCUMENTOS}
    )


def _reason(reason: str) -> str:
    text = (reason or "").strip()
    if len(text) < MIN_REASON:
        raise DataIssueError("Explique o motivo em pelo menos 10 caracteres.")
    return text[:1000]


async def resolve(
    session: AsyncSession,
    issue: DataIssue,
    *,
    user_id: uuid.UUID,
    prevailing_index: int | None,
    reason: str,
) -> DataIssue:
    """Record which side prevails, why and who decided. The contract is not edited here."""
    if issue.status != DataIssueStatus.ABERTO.value:
        raise DataIssueError("Só uma divergência aberta pode ser resolvida.", 409)
    text = _reason(reason)
    if issue.kind != DataIssueKind.CONFLITO_DOCUMENTOS.value:
        # A health alert (D110) has no sides: resolving records what was done and why.
        prevailing_index = None
        issue.status = DataIssueStatus.RESOLVIDO.value
        issue.resolution = {"reason": text}
    else:
        if prevailing_index is None or not 0 <= prevailing_index < len(issue.evidence):
            raise DataIssueError("Escolha uma das versões mostradas.")
        side = issue.evidence[prevailing_index]
        issue.status = DataIssueStatus.RESOLVIDO.value
        issue.resolution = {"prevailing": side, "reason": text}
    issue.resolved_by_user_id, issue.resolved_at = user_id, utcnow()
    await _event(
        session, issue, DataIssueEventKind.RESOLVIDO, user_id, {"prevailing": prevailing_index}
    )
    await record_audit(
        session,
        action="data_issue.resolved",
        object_type="data_issue",
        object_id=issue.id,
        actor_user_id=user_id,
        condominium_id=issue.condominium_id,
    )
    return issue


async def discard(
    session: AsyncSession, issue: DataIssue, *, user_id: uuid.UUID, reason: str
) -> DataIssue:
    if issue.status != DataIssueStatus.ABERTO.value:
        raise DataIssueError("Só uma divergência aberta pode ser descartada.", 409)
    text = _reason(reason)
    issue.status = DataIssueStatus.DESCARTADO.value
    issue.resolution = {"reason": text}
    issue.resolved_by_user_id, issue.resolved_at = user_id, utcnow()
    await _event(session, issue, DataIssueEventKind.DESCARTADO, user_id)
    await record_audit(
        session,
        action="data_issue.discarded",
        object_type="data_issue",
        object_id=issue.id,
        actor_user_id=user_id,
        condominium_id=issue.condominium_id,
    )
    return issue


async def reopen(
    session: AsyncSession, issue: DataIssue, *, user_id: uuid.UUID, reason: str
) -> DataIssue:
    if issue.status == DataIssueStatus.ABERTO.value:
        raise DataIssueError("A divergência já está aberta.", 409)
    text = _reason(reason)
    issue.status = DataIssueStatus.ABERTO.value
    issue.resolution = None
    issue.resolved_by_user_id = issue.resolved_at = None
    await _event(session, issue, DataIssueEventKind.REABERTO, user_id, {"reason": text})
    await record_audit(
        session,
        action="data_issue.reopened",
        object_type="data_issue",
        object_id=issue.id,
        actor_user_id=user_id,
        condominium_id=issue.condominium_id,
    )
    return issue


async def open_issues(
    session: AsyncSession, condo_id: uuid.UUID, *, supplier_id: uuid.UUID | None = None
) -> list[DataIssue]:
    # Conflicts between documents only: health alerts (D110) never make a capability partial,
    # mark a field as conflicting or refuse an action.
    stmt = select(DataIssue).where(
        DataIssue.condominium_id == condo_id,
        DataIssue.status == DataIssueStatus.ABERTO.value,
        DataIssue.kind == DataIssueKind.CONFLITO_DOCUMENTOS.value,
    )
    if supplier_id is not None:
        stmt = stmt.where(DataIssue.supplier_id == supplier_id)
    return list(await session.scalars(stmt.order_by(DataIssue.created_at)))


def contracts_of(issue: DataIssue) -> set[str]:
    """Every contract the issue touches (subject and each side)."""
    out = {str(issue.subject_id)}
    out |= {str(e["contract_id"]) for e in issue.evidence if e.get("contract_id")}
    return out


def documents_of(issue: DataIssue) -> set[str]:
    return {str(e["document_id"]) for e in issue.evidence if e.get("document_id")}


def as_dict(issue: DataIssue) -> dict[str, Any]:
    return {
        "id": str(issue.id),
        "condominium_id": str(issue.condominium_id),
        "kind": issue.kind,
        "audiencia": issue.audiencia,
        "status": issue.status,
        "subject_type": issue.subject_type,
        "subject_id": str(issue.subject_id),
        "supplier_id": str(issue.supplier_id) if issue.supplier_id else None,
        "field": issue.field,
        "title": issue.title,
        "detail": issue.detail,
        "evidence": issue.evidence,
        "capabilities": issue.capabilities,
        "amount_at_stake": f"{issue.amount_at_stake:.2f}" if issue.amount_at_stake else None,
        "detector": issue.detector,
        "resolution": issue.resolution,
        "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
    }
