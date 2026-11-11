"""CondoOS Audit API (D122): the monthly farol, runs, controls with their evidence and how they
were produced, human review, bank reconciliation, inventory and "Agentes & Prompts"."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.audit import agents as ag
from app.audit.catalog import CONTROLS, CONTROLS_BY_ID, PILLARS
from app.audit.controls2 import remaining_balance
from app.audit.data import CLASSIFICATION_VERSION, CREDIT_RULES, DEBIT_RULES, LABELS, load
from app.audit.imports import (
    PROFILE_FIELDS,
    ImportFileError,
    import_readings,
    import_titles,
    import_units,
    profile_of,
    set_profile,
)
from app.audit.run import RunError, month_start, run_audit
from app.auth.deps import CurrentPrincipal, access_for, require
from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import add_months, local_today, utcnow
from app.db.enums import ControlReviewState, ControlStatus
from app.db.models import (
    AgentPromptEvent,
    AgentPromptVersion,
    AppUser,
    AuditAgentRun,
    AuditControlResult,
    AuditControlReview,
    AuditIssue,
    AuditIssueEvent,
    AuditPeriod,
    AuditRun,
    AuditStageRun,
    Condominium,
    Expense,
    ExpenseDocument,
    PaymentAllocation,
    PlatformRoleGrant,
    PromptTestRun,
    ReceivableTitle,
    Unit,
    UtilityReading,
)
from app.db.session import DbSession

router = APIRouter(tags=["audit"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW_AUDIT))]
CanRun = Annotated[CondoAccess, Depends(require(Permission.RUN_AUDIT))]
CanReview = Annotated[CondoAccess, Depends(require(Permission.REVIEW_AUDIT))]
MIN_REASON = 10
STATUS_LABEL = {
    "VALIDADO": "Validado",
    "COM_RESSALVA": "Com ressalva",
    "PENDENTE": "Pendente",
    "DIVERGENTE": "Divergente",
    "NAO_AVALIADO": "Não avaliado",
    "NAO_APLICAVEL": "Não aplicável",
}


def _month(value: str | None, condo: Condominium) -> date:
    if value:
        try:
            return date(int(value[:4]), int(value[5:7]), 1)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Competência inválida (AAAA-MM)."
            ) from exc
    return add_months(month_start(local_today(condo.timezone)), -1)


async def _condo(db: DbSession, access: CondoAccess) -> Condominium:
    condo = await db.get(Condominium, access.condominium_id)
    if condo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Condomínio não encontrado.")
    return condo


async def _period(db: DbSession, condo_id: uuid.UUID, competence: date) -> AuditPeriod | None:
    return await db.scalar(
        select(AuditPeriod).where(
            AuditPeriod.condominium_id == condo_id, AuditPeriod.competence == competence
        )
    )


async def _current(db: DbSession, period_id: uuid.UUID) -> dict[str, AuditControlResult]:
    rows = await db.scalars(
        select(AuditControlResult).where(
            AuditControlResult.period_id == period_id, AuditControlResult.superseded_by_id.is_(None)
        )
    )
    return {r.control_id: r for r in rows}


def _num(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _result_out(r: AuditControlResult) -> dict[str, Any]:
    return {
        "result_id": str(r.id),
        "status": r.status,
        "status_label": STATUS_LABEL[r.status],
        "review_state": r.review_state,
        "review_required": r.review_required,
        "coverage": _num(r.coverage),
        "differences": str(r.differences),
        "rationale": r.rationale,
        "missing": r.missing,
        "severity": r.severity,
        "rule_version": r.rule_version,
        "source": r.source,
        "run_id": str(r.run_id),
        "created_at": r.created_at,
    }


# --------------------------------------------------------------------------- farol


@router.get("/condominiums/{condominium_id}/audit/farol")
async def farol(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    period = await _period(db, condo.id, month)
    current = await _current(db, period.id) if period else {}
    runs = (
        list(
            await db.scalars(
                select(AuditRun)
                .where(AuditRun.period_id == period.id)
                .order_by(AuditRun.number.desc())
            )
        )
        if period
        else []
    )
    prev_period = await _period(db, condo.id, add_months(month, -1))
    prev = await _current(db, prev_period.id) if prev_period else {}
    controls = []
    counts = {s.value: 0 for s in ControlStatus}
    for c in CONTROLS:
        r = current.get(c.id)
        if r is not None:
            counts[r.status] += 1
        controls.append(
            {
                "id": c.id,
                "pillar": c.pillar,
                "pillar_label": PILLARS[c.pillar],
                "name": c.name,
                "cycle": c.cycle,
                "agents": list(c.agents),
                "previous_status": prev[c.id].status if c.id in prev else None,
                **(_result_out(r) if r else {"status": None, "status_label": "Sem execução"}),
            }
        )
    a4 = None
    if runs:
        a4 = await db.scalar(
            select(AuditAgentRun).where(
                AuditAgentRun.run_id == runs[0].id, AuditAgentRun.agent_id == "A4"
            )
        )
    doc01, des01 = current.get("DOC-01"), current.get("DES-01")
    return {
        "competencia": month.strftime("%Y-%m"),
        "condominium": {"id": str(condo.id), "name": condo.name},
        "period_id": str(period.id) if period else None,
        "runs": [
            {
                "id": str(r.id),
                "number": r.number,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "trigger": r.trigger,
                "summary": r.summary,
            }
            for r in runs[:12]
        ],
        "counts": counts,
        "indicators": {
            "cobertura_documental": _num(doc01.coverage) if doc01 else None,
            "liquidacao_demonstrada": _num(des01.coverage) if des01 else None,
            "contas": (a4.output.get("contas") if a4 else []) or [],
            "aguardando_revisao": sum(
                1
                for r in current.values()
                if r.review_state == ControlReviewState.NEEDS_HUMAN_REVIEW.value
            ),
            "diferenca_total": str(sum((r.differences for r in current.values()), Decimal("0"))),
        },
        "controls": controls,
        "can_run": access.can(Permission.RUN_AUDIT),
        "can_review": access.can(Permission.REVIEW_AUDIT),
    }


class RunIn(BaseModel):
    competencia: str = Field(pattern=r"^\d{4}-\d{2}$")


@router.post("/condominiums/{condominium_id}/audit/runs")
async def start_run(
    condominium_id: uuid.UUID, body: RunIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    condo = await _condo(db, access)
    try:
        run = await run_audit(
            db,
            condo,
            _month(body.competencia, condo),
            today=local_today(condo.timezone),
            user_id=access.user_id,
        )
    except RunError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return {"id": str(run.id), "number": run.number, "status": run.status, "summary": run.summary}


@router.get("/condominiums/{condominium_id}/audit/runs/{run_id}")
async def get_run(
    condominium_id: uuid.UUID, run_id: uuid.UUID, access: CanView, db: DbSession
) -> dict[str, Any]:
    run = await db.scalar(
        select(AuditRun).where(
            AuditRun.id == run_id, AuditRun.condominium_id == access.condominium_id
        )
    )
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada.")
    period = await db.get(AuditPeriod, run.period_id)
    assert period is not None
    stages = list(
        await db.scalars(
            select(AuditStageRun)
            .where(AuditStageRun.run_id == run.id)
            .order_by(AuditStageRun.stage)
        )
    )
    agent_runs = list(
        await db.scalars(
            select(AuditAgentRun)
            .where(AuditAgentRun.run_id == run.id)
            .order_by(AuditAgentRun.stage, AuditAgentRun.agent_id)
        )
    )
    versions = {
        v.id: v.version
        for v in await db.scalars(
            select(AgentPromptVersion).where(
                AgentPromptVersion.id.in_(
                    [a.prompt_version_id for a in agent_runs if a.prompt_version_id]
                )
            )
        )
    }
    return {
        "id": str(run.id),
        "number": run.number,
        "competencia": period.competence.strftime("%Y-%m"),
        "status": run.status,
        "trigger": run.trigger,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary": run.summary,
        "stages": [
            {"stage": s.stage, "name": s.name, "status": s.status, "detail": s.detail}
            for s in stages
        ],
        "agents": [
            {
                "agent_id": a.agent_id,
                "name": ag.AGENTS[a.agent_id].name,
                "stage": a.stage,
                "prompt_version": (
                    versions.get(a.prompt_version_id) if a.prompt_version_id else None
                ),
                "prompt_version_id": str(a.prompt_version_id) if a.prompt_version_id else None,
                "runtime_prompt_sha256": a.runtime_prompt_sha256,
                "llm_invoked": a.llm_invoked,
                "model": a.model,
                "status": a.status,
                "duration_ms": a.duration_ms,
                "output": a.output,
                "unresolved": a.unresolved,
                "warnings": a.warnings,
            }
            for a in agent_runs
        ],
    }


@router.get("/condominiums/{condominium_id}/audit/controls/{control_id}")
async def get_control(
    condominium_id: uuid.UUID,
    control_id: str,
    access: CanView,
    db: DbSession,
    competencia: str | None = None,
) -> dict[str, Any]:
    c = CONTROLS_BY_ID.get(control_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Controle não encontrado.")
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    period = await _period(db, condo.id, month)
    history = (
        list(
            await db.scalars(
                select(AuditControlResult)
                .where(
                    AuditControlResult.period_id == period.id,
                    AuditControlResult.control_id == control_id,
                )
                .order_by(AuditControlResult.created_at.desc())
            )
        )
        if period
        else []
    )
    current = next((r for r in history if r.superseded_by_id is None), None)
    reviews = (
        list(
            await db.scalars(
                select(AuditControlReview)
                .where(AuditControlReview.result_id.in_([r.id for r in history]))
                .order_by(AuditControlReview.created_at)
            )
        )
        if history
        else []
    )
    names = {
        u.id: u.name
        for u in await db.scalars(
            select(AppUser).where(AppUser.id.in_([r.user_id for r in reviews if r.user_id]))
        )
    }
    run_numbers = (
        {
            r.id: r.number
            for r in await db.scalars(
                select(AuditRun).where(AuditRun.id.in_([h.run_id for h in history]))
            )
        }
        if history
        else {}
    )
    return {
        "competencia": month.strftime("%Y-%m"),
        "definition": {
            "id": c.id,
            "name": c.name,
            "pillar": PILLARS[c.pillar],
            "agents": list(c.agents),
            "sources": list(c.sources),
            "criteria": list(c.criteria),
            "cycle": c.cycle,
            "rule_version": c.rule_version,
            "parameters": c.parameters or {},
        },
        "current": (
            {
                **_result_out(current),
                "tests": current.tests,
                "evidence_refs": current.evidence_refs,
                "calculation": current.calculation,
                # "Como este resultado foi produzido?": agents, prompt versions and hashes, rule.
                "produced_by": {
                    "run_id": str(current.run_id),
                    "run_number": run_numbers.get(current.run_id),
                    "rule_version": current.rule_version,
                    "agents": current.agents,
                    "input_fingerprint": current.input_fingerprint,
                    "deterministic": "O status vem da regra versionada; a IA só sugere ou questiona.",
                },
            }
            if current
            else None
        ),
        "history": [
            {
                **_result_out(h),
                "run_number": run_numbers.get(h.run_id),
                "current": h.superseded_by_id is None,
            }
            for h in history
        ],
        "reviews": [
            {
                "decision": r.decision,
                "reason": r.reason,
                "from": r.from_status,
                "to": r.to_status,
                "user": names.get(r.user_id) if r.user_id else None,
                "at": r.created_at,
            }
            for r in reviews
        ],
        "can_review": access.can(Permission.REVIEW_AUDIT),
    }


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(confirmar|reclassificar)$")
    status: ControlStatus | None = None
    reason: str = Field(max_length=2000)


@router.post("/condominiums/{condominium_id}/audit/results/{result_id}/review")
async def review_result(
    condominium_id: uuid.UUID,
    result_id: uuid.UUID,
    body: ReviewIn,
    access: CanReview,
    db: DbSession,
) -> dict[str, Any]:
    """Internal human review. "confirmar" keeps the status; "reclassificar" creates a new
    result (source "revisao") that supersedes this one. The original is never edited."""
    r = await db.scalar(
        select(AuditControlResult)
        .where(
            AuditControlResult.id == result_id,
            AuditControlResult.condominium_id == access.condominium_id,
        )
        .with_for_update()
    )
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resultado não encontrado.")
    if r.superseded_by_id is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Este resultado já foi substituído: revise o atual."
        )
    reason = body.reason.strip()
    if len(reason) < MIN_REASON:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Escreva o motivo (mínimo de 10 caracteres)."
        )
    target = r
    if body.decision == "reclassificar":
        if body.status is None or body.status.value == r.status:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Escolha um status diferente do atual."
            )
        if body.status == ControlStatus.VALIDADO and r.status in (
            ControlStatus.PENDENTE.value,
            ControlStatus.NAO_AVALIADO.value,
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Sem a fonte que falta, o controle não pode ficar Validado: envie a evidência e rode de novo.",
            )
        target = AuditControlResult(
            id=uuid.uuid4(),
            condominium_id=r.condominium_id,
            period_id=r.period_id,
            run_id=r.run_id,
            control_id=r.control_id,
            rule_version=r.rule_version,
            status=body.status.value,
            review_state=ControlReviewState.REVIEWED.value,
            severity=r.severity,
            tests=r.tests,
            evidence_refs=r.evidence_refs,
            coverage=r.coverage,
            differences=r.differences,
            rationale=f"Reclassificado por revisão humana: {reason} (antes: {STATUS_LABEL[r.status]}. {r.rationale})",
            missing=r.missing,
            review_required=False,
            input_fingerprint=r.input_fingerprint,
            agents=r.agents,
            source="revisao",
        )
        db.add(target)
        await db.flush()
        r.superseded_by_id = target.id
    else:
        r.review_state = ControlReviewState.REVIEWED.value
    db.add(
        AuditControlReview(
            condominium_id=r.condominium_id,
            result_id=r.id,
            user_id=access.user_id,
            decision=body.decision,
            reason=reason,
            from_status=r.status,
            to_status=target.status,
        )
    )
    await record_audit(
        db,
        action="audit.control.reviewed",
        object_type="audit_control_result",
        object_id=r.id,
        actor_user_id=access.user_id,
        condominium_id=r.condominium_id,
        details={
            "control": r.control_id,
            "decision": body.decision,
            "from": r.status,
            "to": target.status,
        },
    )
    await db.flush()
    return _result_out(target)


# --------------------------------------------------------------------------- views


@router.get("/condominiums/{condominium_id}/audit/reconciliation")
async def reconciliation(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    """Per account: balances, continuity and every line with its classification and the
    levels (a) balance reconciled, (b) classified, (c) payment proof checked, (d) final
    payee confirmed, (e) obligation documented — shown apart, never as one checkbox."""
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    data = await load(db, condo, month, local_today(condo.timezone))
    expenses = {e.expense.id: e for e in data.expenses}
    proof = set(
        await db.scalars(
            select(ExpenseDocument.expense_id).where(
                ExpenseDocument.condominium_id == condo.id, ExpenseDocument.role == "pagamento"
            )
        )
    )
    alloc: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for pa, desc in (
        await db.execute(
            select(PaymentAllocation, Expense.description)
            .join(Expense, Expense.id == PaymentAllocation.expense_id)
            .where(
                PaymentAllocation.condominium_id == condo.id,
                PaymentAllocation.bank_transaction_id.in_(
                    [ln.trn.id for ln in data.lines] or [uuid.uuid4()]
                ),
            )
        )
    ).all():
        alloc.setdefault(pa.bank_transaction_id, []).append(
            {"expense": desc, "amount": str(pa.amount), "kind": pa.kind, "method": pa.method}
        )
    accounts = []
    for a in data.accounts:
        balance = a.balance_check()
        lines = []
        for ln in a.lines:
            allocated = alloc.get(ln.trn.id, [])
            e = expenses.get(ln.trn.expense_id) if ln.trn.expense_id else None
            lines.append(
                {
                    "id": str(ln.trn.id),
                    "date": ln.trn.posted_at,
                    "description": ln.trn.description,
                    "amount": str(ln.amount),
                    "classification": LABELS[ln.kind],
                    "kind": ln.kind,
                    "strength": ln.strength,
                    "intermediary": ln.intermediary,
                    "paired_with": str(ln.paired_with) if ln.paired_with else None,
                    "allocations": allocated,
                    "expense": (
                        {
                            "id": str(e.expense.id),
                            "description": e.expense.description,
                            "amount": str(e.expense.amount),
                        }
                        if e
                        else None
                    ),
                    "levels": {
                        "a_saldo": balance["situacao"] == "confere",
                        "b_classificado": ln.kind != "nao_identificado" and ln.strength == "regra",
                        "c_comprovante": bool(e and e.expense.id in proof),
                        "d_favorecido": bool(
                            e and e.supplier and ln.trn.payee_document == e.supplier.cnpj
                        ),
                        "e_obrigacao": bool(e and e.has_document),
                    },
                }
            )
        st = a.statement
        accounts.append(
            {
                "key": a.key,
                "label": a.label,
                "statement": (
                    {
                        "id": str(st.id),
                        "document_id": str(st.document_id) if st.document_id else None,
                        "period_start": st.period_start,
                        "period_end": st.period_end,
                        "opening_balance": _num(st.opening_balance),
                        "closing_balance": _num(st.closing_balance),
                        "balance_source": st.balance_source,
                    }
                    if st
                    else None
                ),
                "balance": balance,
                "continuity": a.continuity(),
                "lines": lines,
                "classified": sum(
                    1 for ln in a.lines if ln.kind != "nao_identificado" and ln.strength == "regra"
                ),
            }
        )
    return {
        "competencia": month.strftime("%Y-%m"),
        "classification_version": CLASSIFICATION_VERSION,
        "accounts": accounts,
    }


@router.get("/condominiums/{condominium_id}/audit/inventory")
async def inventory(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    data = await load(db, condo, month, local_today(condo.timezone))
    return {
        "competencia": month.strftime("%Y-%m"),
        "documents": [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "doc_type": d.doc_type,
                "status": d.extraction_status,
                "needs_review": d.needs_review,
                "pages": d.page_count,
                "version": d.version,
                "supersedes_id": str(d.supersedes_id) if d.supersedes_id else None,
                "created_at": d.created_at,
                "agents": (d.field_provenance or {}).get("_agentes") or {},
            }
            for d in data.documents
        ],
        "accounts": [
            {"label": a.label, "has_statement": a.statement is not None} for a in data.accounts
        ],
        "copies": data.copies,
    }


@router.get("/audit/review-queue")
async def review_queue(db: DbSession, principal: CurrentPrincipal) -> list[dict[str, Any]]:
    out = []
    for condo in await db.scalars(
        select(Condominium).where(Condominium.id.in_(principal.condominium_ids))
    ):
        access = await access_for(db, principal.user.id, condo)
        if not access.can(Permission.REVIEW_AUDIT):
            continue
        rows = await db.execute(
            select(AuditControlResult, AuditPeriod.competence)
            .join(AuditPeriod, AuditPeriod.id == AuditControlResult.period_id)
            .where(
                AuditControlResult.condominium_id == condo.id,
                AuditControlResult.superseded_by_id.is_(None),
                AuditControlResult.review_state == ControlReviewState.NEEDS_HUMAN_REVIEW.value,
            )
        )
        for r, competence in rows.all():
            out.append(
                {
                    "condominium_id": str(condo.id),
                    "condominium": condo.name,
                    "competencia": competence.strftime("%Y-%m"),
                    "control_id": r.control_id,
                    "name": CONTROLS_BY_ID[r.control_id].name,
                    **_result_out(r),
                }
            )
    return sorted(out, key=lambda x: (Decimal(x["differences"]), x["competencia"]), reverse=True)


@router.get("/audit/controls-catalog")
async def controls_catalog(principal: CurrentPrincipal) -> dict[str, Any]:
    """ "Regras, não prompts": deterministic rules behind the 25 controls."""
    return {
        "controls": [
            {
                "id": c.id,
                "pillar": PILLARS[c.pillar],
                "name": c.name,
                "agents": list(c.agents),
                "sources": list(c.sources),
                "criteria": list(c.criteria),
                "inputs": list(c.inputs),
                "cycle": c.cycle,
                "rule_version": c.rule_version,
                "parameters": c.parameters or {},
            }
            for c in CONTROLS
        ],
        "classification": {
            "version": CLASSIFICATION_VERSION,
            "debits": [{"kind": LABELS[k], "pattern": p} for k, p in DEBIT_RULES],
            "credits": [{"kind": LABELS[k], "pattern": p} for k, p in CREDIT_RULES],
        },
        "statuses": STATUS_LABEL,
    }


# --------------------------------------------------------------------------- agents & prompts


async def _platform_roles(db: DbSession, user_id: uuid.UUID) -> set[str]:
    now = utcnow()
    return set(
        await db.scalars(
            select(PlatformRoleGrant.role).where(
                PlatformRoleGrant.user_id == user_id,
                PlatformRoleGrant.revoked_at.is_(None),
                or_(PlatformRoleGrant.expires_at.is_(None), PlatformRoleGrant.expires_at > now),
            )
        )
    )


async def _staff(db: DbSession, principal: CurrentPrincipal) -> set[str]:
    roles = await _platform_roles(db, principal.user.id)
    if not roles:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só a equipe CondoOS vê os prompts dos agentes."
        )
    return roles


def _can_manage(roles: set[str]) -> bool:
    return "condoos_admin" in roles


def _version_out(v: AgentPromptVersion, names: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "id": str(v.id),
        "agent_id": v.agent_id,
        "version": v.version,
        "status": v.status,
        "text": v.text,
        "sha256": v.sha256,
        "model_role": v.model_role,
        "config": v.config,
        "source": v.source,
        "change_note": v.change_note,
        "based_on_id": str(v.based_on_id) if v.based_on_id else None,
        "author": names.get(v.author_user_id) if v.author_user_id else "Prompt Mestre v1.0",
        "approved_by": names.get(v.approved_by) if v.approved_by else None,
        "created_at": v.created_at,
        "approved_at": v.approved_at,
        "activated_at": v.activated_at,
        "archived_at": v.archived_at,
    }


def _agent_out(a: ag.AgentDef) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "purpose": a.purpose,
        "stage": a.stage,
        "depends_on": list(a.depends_on),
        "tools": list(a.tools),
        "inputs": a.inputs,
        "outputs": a.outputs,
        "limits": a.limits,
        "owner": a.owner,
        "active": a.active,
        "mode": a.mode,
        "cycle": a.cycle,
    }


@router.get("/audit/agents")
async def list_agents(db: DbSession, principal: CurrentPrincipal) -> dict[str, Any]:
    roles = await _staff(db, principal)
    await ag.ensure_initial_versions(db)
    active = {
        v.agent_id: v
        for v in await db.scalars(
            select(AgentPromptVersion).where(AgentPromptVersion.status == "ACTIVE")
        )
    }
    drafts: dict[str, int] = {}
    for v in await db.scalars(
        select(AgentPromptVersion).where(AgentPromptVersion.status.in_(["DRAFT", "IN_REVIEW"]))
    ):
        drafts[v.agent_id] = drafts.get(v.agent_id, 0) + 1
    return {
        "agents": [
            {
                **_agent_out(a),
                "active_version": active[a.id].version if a.id in active else None,
                "active_sha256": active[a.id].sha256 if a.id in active else None,
                "open_drafts": drafts.get(a.id, 0),
            }
            for a in ag.AGENTS.values()
        ],
        "can_manage": _can_manage(roles),
        "safety_rule": ag.SAFETY_RULE,
    }


@router.get("/audit/agents/{agent_id}")
async def get_agent(agent_id: str, db: DbSession, principal: CurrentPrincipal) -> dict[str, Any]:
    roles = await _staff(db, principal)
    a = ag.AGENTS.get(agent_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agente não encontrado.")
    await ag.ensure_initial_versions(db)
    versions = list(
        await db.scalars(
            select(AgentPromptVersion)
            .where(AgentPromptVersion.agent_id == agent_id)
            .order_by(AgentPromptVersion.version.desc())
        )
    )
    ids = [v.id for v in versions]
    events = list(
        await db.scalars(
            select(AgentPromptEvent)
            .where(AgentPromptEvent.version_id.in_(ids))
            .order_by(AgentPromptEvent.created_at.desc())
            .limit(100)
        )
    )
    tests = list(
        await db.scalars(
            select(PromptTestRun)
            .where(PromptTestRun.version_id.in_(ids))
            .order_by(PromptTestRun.created_at.desc())
            .limit(50)
        )
    )
    user_ids = {u for v in versions for u in (v.author_user_id, v.approved_by) if u} | {
        e.user_id for e in events if e.user_id
    }
    names = {
        u.id: u.name for u in await db.scalars(select(AppUser).where(AppUser.id.in_(user_ids)))
    }
    version_no = {v.id: v.version for v in versions}
    runs = (
        await db.execute(
            select(AuditAgentRun, AuditRun.number, AuditPeriod.competence, Condominium.name)
            .join(AuditRun, AuditRun.id == AuditAgentRun.run_id)
            .join(AuditPeriod, AuditPeriod.id == AuditRun.period_id)
            .join(Condominium, Condominium.id == AuditAgentRun.condominium_id)
            .where(AuditAgentRun.agent_id == agent_id)
            .order_by(AuditAgentRun.created_at.desc())
            .limit(50)
        )
    ).all()
    active = next((v for v in versions if v.status == "ACTIVE"), None)
    return {
        **_agent_out(a),
        "can_manage": _can_manage(roles),
        "can_approve": bool(roles),
        "runtime_example": (
            ag.compose(active.text, "(tarefa gerada pela aplicação em cada chamada)")
            if active
            else None
        ),
        "boundaries": {
            "agent": ag.SECTION_AGENT,
            "safety": ag.SECTION_SAFETY,
            "task": ag.SECTION_TASK,
            "safety_rule": ag.SAFETY_RULE,
        },
        "versions": [_version_out(v, names) for v in versions],
        "events": [
            {
                "version": version_no.get(e.version_id),
                "kind": e.kind,
                "user": names.get(e.user_id) if e.user_id else None,
                "detail": e.detail,
                "at": e.created_at,
            }
            for e in events
        ],
        "tests": [
            {
                "version": version_no.get(t.version_id),
                "passed": t.passed,
                "results": t.results,
                "at": t.created_at,
                "user": names.get(t.user_id) if t.user_id else None,
            }
            for t in tests
        ],
        "runs": [
            {
                "run_id": str(r.run_id),
                "run_number": number,
                "condominium": condo_name,
                "competencia": competence.strftime("%Y-%m"),
                "prompt_version": (
                    version_no.get(r.prompt_version_id) if r.prompt_version_id else None
                ),
                "runtime_prompt_sha256": r.runtime_prompt_sha256,
                "llm_invoked": r.llm_invoked,
                "model": r.model,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "unresolved": len(r.unresolved or []),
                "warnings": r.warnings,
                "at": r.created_at,
            }
            for r, number, competence, condo_name in runs
        ],
    }


@router.get("/audit/agents/{agent_id}/diff")
async def diff_versions(
    agent_id: str,
    db: DbSession,
    principal: CurrentPrincipal,
    a: Annotated[int, Query(ge=1)],
    b: Annotated[int, Query(ge=1)],
) -> dict[str, Any]:
    await _staff(db, principal)
    rows = {
        v.version: v
        for v in await db.scalars(
            select(AgentPromptVersion).where(
                AgentPromptVersion.agent_id == agent_id, AgentPromptVersion.version.in_([a, b])
            )
        )
    }
    if a not in rows or b not in rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versão não encontrada.")
    return {"a": a, "b": b, "lines": ag.diff(rows[a].text, rows[b].text)}


class DraftIn(BaseModel):
    text: str = Field(min_length=1, max_length=ag.MAX_CHARS + 2000)
    note: str = Field(max_length=500)


class ReasonIn(BaseModel):
    reason: str = Field(max_length=500)


async def _version(db: DbSession, version_id: uuid.UUID) -> AgentPromptVersion:
    v = await db.scalar(
        select(AgentPromptVersion).where(AgentPromptVersion.id == version_id).with_for_update()
    )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versão não encontrada.")
    return v


def _raise(exc: ag.PromptError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


@router.post("/audit/agents/{agent_id}/prompt-drafts")
async def new_draft(
    agent_id: str, body: DraftIn, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    roles = await _staff(db, principal)
    if not _can_manage(roles):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só o Admin CondoOS escreve rascunhos de prompt."
        )
    try:
        v = await ag.create_draft(db, agent_id, body.text, body.note, principal.user.id)
    except ag.PromptError as exc:
        raise _raise(exc) from exc
    return _version_out(v, {})


@router.post("/audit/prompt-versions/{version_id}/test")
async def test_version(
    version_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    roles = await _staff(db, principal)
    if not _can_manage(roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o Admin CondoOS testa prompts.")
    run = await ag.run_tests(db, await _version(db, version_id), principal.user.id)
    return {"passed": run.passed, "results": run.results}


@router.post("/audit/prompt-versions/{version_id}/submit")
async def submit_version(
    version_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    roles = await _staff(db, principal)
    if not _can_manage(roles):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Só o Admin CondoOS envia prompts para revisão."
        )
    v = await _version(db, version_id)
    try:
        await ag.submit(db, v, principal.user.id)
    except ag.PromptError as exc:
        raise _raise(exc) from exc
    return {"status": v.status}


@router.post("/audit/prompt-versions/{version_id}/approve")
async def approve_version(
    version_id: uuid.UUID, body: ReasonIn, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    await _staff(db, principal)
    v = await _version(db, version_id)
    try:
        await ag.approve(db, v, principal.user.id, body.reason)
    except ag.PromptError as exc:
        raise _raise(exc) from exc
    return {"status": v.status}


@router.post("/audit/prompt-versions/{version_id}/rollback")
async def rollback_version(
    version_id: uuid.UUID, body: ReasonIn, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    roles = await _staff(db, principal)
    if not _can_manage(roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o Admin CondoOS volta versões.")
    v = await _version(db, version_id)
    try:
        await ag.rollback(db, v, principal.user.id, body.reason)
    except ag.PromptError as exc:
        raise _raise(exc) from exc
    return {"status": v.status}


@router.post("/audit/prompt-versions/{version_id}/discard")
async def discard_version(
    version_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal
) -> dict[str, Any]:
    roles = await _staff(db, principal)
    if not _can_manage(roles):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o Admin CondoOS descarta rascunhos.")
    v = await _version(db, version_id)
    try:
        await ag.archive_draft(db, v, principal.user.id)
    except ag.PromptError as exc:
        raise _raise(exc) from exc
    return {"status": v.status}


# --------------------------------------------------------------------------- cycle 2 (D123)


@router.post("/condominiums/{condominium_id}/audit/imports/{kind}")
async def import_file(
    condominium_id: uuid.UUID,
    kind: str,
    access: CanRun,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Units, titles or readings (CSV). Name, document, e-mail and phone columns are dropped
    before anything is stored; the stored source is a copy with only the allowed columns."""
    importers = {"unidades": import_units, "titulos": import_titles, "leituras": import_readings}
    if kind not in importers:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Importação desconhecida.")
    condo = await _condo(db, access)
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Planilha maior que 5 MB.")
    try:
        result = await importers[kind](db, condo, data, access.user_id)
    except ImportFileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return result.as_dict()


@router.get("/condominiums/{condominium_id}/audit/profile")
async def get_profile(condominium_id: uuid.UUID, access: CanView, db: DbSession) -> dict[str, Any]:
    condo = await _condo(db, access)
    return {
        "profile": profile_of(condo.rule_params or {}),
        "questions": PROFILE_FIELDS,
        "can_edit": access.can(Permission.RUN_AUDIT),
    }


class ProfileIn(BaseModel):
    values: dict[str, bool | None]
    reason: str = Field(max_length=300)


@router.put("/condominiums/{condominium_id}/audit/profile")
async def put_profile(
    condominium_id: uuid.UUID, body: ProfileIn, access: CanRun, db: DbSession
) -> dict[str, Any]:
    if len(body.reason.strip()) < MIN_REASON:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Escreva o motivo (mínimo de 10 caracteres)."
        )
    condo = await _condo(db, access)
    return {
        "profile": await set_profile(db, condo, body.values, access.user_id, body.reason.strip())
    }


@router.get("/condominiums/{condominium_id}/audit/units")
async def units(
    condominium_id: uuid.UUID, access: CanView, db: DbSession, competencia: str | None = None
) -> dict[str, Any]:
    """Internal unit view (D123): unit code, titles of the month and open balance. No names."""
    condo = await _condo(db, access)
    month = _month(competencia, condo)
    last = add_months(month, 1) - timedelta(days=1)
    rows = list(
        await db.scalars(select(Unit).where(Unit.condominium_id == condo.id).order_by(Unit.code))
    )
    titles = list(
        await db.scalars(
            select(ReceivableTitle).where(
                ReceivableTitle.condominium_id == condo.id, ReceivableTitle.due_date <= last
            )
        )
    )
    readings = list(
        await db.scalars(
            select(UtilityReading).where(
                UtilityReading.condominium_id == condo.id,
                UtilityReading.competence == add_months(month, -1),
            )
        )
    )
    out = []
    for u in rows:
        mine = [t for t in titles if t.unit_id == u.id]
        open_ = sum((remaining_balance(t, last) for t in mine), Decimal("0"))
        out.append(
            {
                "id": str(u.id),
                "code": u.code,
                "block": u.block,
                "fraction": str(u.fraction) if u.fraction is not None else None,
                "titles": [
                    {
                        "kind": t.kind,
                        "amount": str(t.amount),
                        "due_date": t.due_date,
                        "status": t.status,
                        "paid_at": t.paid_at,
                        "paid_amount": str(t.paid_amount) if t.paid_amount is not None else None,
                    }
                    for t in mine
                    if t.competence == month
                ],
                "open_balance": str(open_),
                "readings": [
                    {"utility": r.utility, "consumption": str(r.consumption)}
                    for r in readings
                    if r.unit_id == u.id
                ],
            }
        )
    return {
        "competencia": month.strftime("%Y-%m"),
        "units": out,
        "can_import": access.can(Permission.RUN_AUDIT),
    }


@router.get("/condominiums/{condominium_id}/audit/issues")
async def issues(
    condominium_id: uuid.UUID,
    access: CanView,
    db: DbSession,
    status_: Annotated[str | None, Query(alias="status")] = None,
) -> list[dict[str, Any]]:
    stmt = select(AuditIssue).where(AuditIssue.condominium_id == access.condominium_id)
    if status_ in ("aberta", "resolvida"):
        stmt = stmt.where(AuditIssue.status == status_)
    rows = list(await db.scalars(stmt.order_by(AuditIssue.first_competence, AuditIssue.control_id)))
    events: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for e in await db.scalars(
        select(AuditIssueEvent)
        .where(AuditIssueEvent.issue_id.in_([i.id for i in rows] or [uuid.uuid4()]))
        .order_by(AuditIssueEvent.created_at)
    ):
        events.setdefault(e.issue_id, []).append(
            {"kind": e.kind, "competencia": e.competence.strftime("%Y-%m"), "at": e.created_at}
        )
    return [
        {
            "id": str(i.id),
            "control_id": i.control_id,
            "control": (
                CONTROLS_BY_ID[i.control_id].name
                if i.control_id in CONTROLS_BY_ID
                else i.control_id
            ),
            "title": i.title,
            "status": i.status,
            "first_competence": i.first_competence.strftime("%Y-%m"),
            "last_competence": i.last_competence.strftime("%Y-%m"),
            "months_open": (i.last_competence.year - i.first_competence.year) * 12
            + i.last_competence.month
            - i.first_competence.month
            + 1,
            "events": events.get(i.id, []),
        }
        for i in rows
    ]
