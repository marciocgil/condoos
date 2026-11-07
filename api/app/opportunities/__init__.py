"""Opportunities (Optimize, D76, D81): a possible benefit drawn from findings, with savings
in separate, dated stages, an internal CondoOS review before the board sees anything, and
the condominium's own decision afterwards.

- Money is computed by code (``estimate_from_finding``), never by the model; the method is
  versioned (``method_code``) and each value is a new ``savings_record`` row.
- The review requirement comes from the review policy (D74); in the pilot an opportunity
  always waits for a CondoOS reviewer (``internal_review``).
- The board sees an opportunity only after ``presented_at`` (FR-046, OPT-01), and sees the
  validated estimate, never the raw potential.
- Stages are never added up: the interface shows each one with its own label.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.core.time import utcnow
from app.db.enums import (
    OpportunityReviewAction,
    OpportunityStatus,
    OpportunityType,
    ReviewRequirement,
    Role,
    SavingsStage,
)
from app.db.models import (
    Condominium,
    Contract,
    Document,
    Expense,
    Finding,
    Opportunity,
    OpportunityFinding,
    OpportunityReview,
    SavingsRecord,
    Supplier,
)
from app.review import current_policy
from app.review import evaluate as evaluate_policy

S = OpportunityStatus
A = OpportunityReviewAction
CENT = Decimal("0.01")
METHOD = "excesso_mensal_v1"
SOURCE_RULES = ("R02", "R03")
CLOSED = frozenset({S.REJEITADA, S.RECUSADA_PELO_CONDOMINIO, S.ENCERRADA})
EDITABLE = frozenset({S.EM_REVISAO_INTERNA, S.DEVOLVIDA, S.IDENTIFICADA})


class OpportunityError(ValueError):
    def __init__(self, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class Estimate:
    amount: Decimal
    periodicity: str
    one_time_cost: Decimal
    baseline_start: date
    baseline_end: date
    baseline_amount: Decimal
    assumptions: list[str]
    evidence: list[dict[str, Any]]
    confidence: str
    quality_risks: str
    method_code: str = METHOD
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def annualized(self) -> Decimal:
        factor = {"mensal": 12, "anual": 1, "unica": 1}[self.periodicity]
        return (self.amount * factor).quantize(CENT)

    @property
    def net(self) -> Decimal:
        return (self.annualized - self.one_time_cost).quantize(CENT)

    def version_hash(self) -> str:
        """What a reviewer approves: any material change gives another hash."""
        payload = {
            "amount": str(self.amount.quantize(CENT)),
            "periodicity": self.periodicity,
            "one_time_cost": str(self.one_time_cost.quantize(CENT)),
            "baseline": [
                self.baseline_start.isoformat(),
                self.baseline_end.isoformat(),
                str(self.baseline_amount),
            ],
            "assumptions": self.assumptions,
            "confidence": self.confidence,
            "method": self.method_code,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENT)
    except Exception as exc:
        raise OpportunityError(f"O achado não tem {label} para calcular a economia.") from exc


def estimate_from_finding(finding: Finding, supplier_name: str) -> tuple[Estimate, str, str, str]:
    """Potential savings from an R02/R03 finding (method ``excesso_mensal_v1``).

    The monthly difference between what was charged and what the contract allows is the
    potential saving per month if the charge is corrected; annualised ×12 assuming it would
    repeat. One-time cost is zero: correcting a charge does not change the service.
    Returns the estimate, the opportunity type, the title and the recommendation.
    """
    inputs = finding.rule_inputs or {}
    diff = _decimal(inputs.get("diferenca"), "a diferença cobrada")
    if diff <= 0:
        raise OpportunityError("A diferença do achado não é positiva: não há economia a estimar.")
    month = finding.competence
    if finding.rule_code == "R02":
        baseline = _decimal(inputs.get("valor_contratual_reajustado"), "o valor contratual")
        kind = OpportunityType.COBRANCA_INCONSISTENTE
        title = f"Cobrança acima do contrato — {supplier_name}"
        recommendation = (
            f"Contestar a diferença cobrada por {supplier_name} e pedir o faturamento pelo valor "
            "contratual reajustado; avaliar o ressarcimento do valor já pago a maior."
        )
        basis = "valor contratual reajustado do mês"
    elif finding.rule_code == "R03":
        baseline = _decimal(inputs.get("valor_com_indice"), "o valor com o índice")
        kind = OpportunityType.REAJUSTE
        title = f"Reajuste acima do índice — {supplier_name}"
        recommendation = (
            f"Pedir a {supplier_name} a revisão do reajuste para o índice previsto no contrato "
            f"({inputs.get('indice', 'índice contratual')}); avaliar o ressarcimento do mês."
        )
        basis = "valor anterior corrigido pelo índice do contrato"
    else:
        raise OpportunityError("Só achados R02 e R03 geram oportunidade nesta versão.")
    estimate = Estimate(
        amount=diff,
        periodicity="mensal",
        one_time_cost=Decimal("0.00"),
        baseline_start=month,
        baseline_end=month,
        baseline_amount=baseline,
        assumptions=[
            f"Baseline: {basis} na competência {month:%m/%Y}.",
            "A diferença se repete nos próximos 12 meses se nada for feito.",
            "A correção da cobrança não altera o escopo nem a qualidade do serviço.",
            "Não inclui o ressarcimento do valor já pago a maior (tratado à parte).",
        ],
        evidence=[
            {"type": "finding", "id": str(finding.id), "rule": finding.rule_code},
            *[e for e in (finding.evidence or []) if isinstance(e, dict)][:5],
        ],
        confidence="alta" if finding.status == "confirmado" else "media",
        quality_risks=(
            "Não avalia se houve serviço extra autorizado; conferir aditivos e aprovações "
            "antes de contestar."
        ),
    )
    return estimate, kind.value, title[:200], recommendation


async def latest(
    session: AsyncSession, opp: Opportunity, stage: SavingsStage
) -> SavingsRecord | None:
    return await session.scalar(
        select(SavingsRecord)
        .where(SavingsRecord.opportunity_id == opp.id, SavingsRecord.stage == stage.value)
        .order_by(SavingsRecord.created_at.desc(), SavingsRecord.id.desc())
        .limit(1)
    )


def _record(
    opp: Opportunity,
    stage: SavingsStage,
    e: Estimate,
    actor: uuid.UUID | None,
    supersedes: uuid.UUID | None = None,
) -> SavingsRecord:
    return SavingsRecord(
        id=uuid.uuid4(),
        condominium_id=opp.condominium_id,
        opportunity_id=opp.id,
        stage=stage.value,
        amount=e.amount,
        periodicity=e.periodicity,
        annualized_amount=e.annualized,
        one_time_cost=e.one_time_cost,
        net_amount=e.net,
        baseline_period_start=e.baseline_start,
        baseline_period_end=e.baseline_end,
        baseline_amount=e.baseline_amount,
        method_code=e.method_code,
        assumptions=e.assumptions,
        evidence=e.evidence,
        confidence=e.confidence,
        quality_risks=e.quality_risks,
        version_hash=e.version_hash(),
        recorded_by_user_id=actor,
        supersedes_id=supersedes,
    )


def estimate_of(r: SavingsRecord) -> Estimate:
    return Estimate(
        amount=r.amount,
        periodicity=r.periodicity,
        one_time_cost=r.one_time_cost,
        baseline_start=r.baseline_period_start,
        baseline_end=r.baseline_period_end,
        baseline_amount=r.baseline_amount,
        assumptions=list(r.assumptions),
        evidence=list(r.evidence),
        confidence=r.confidence,
        quality_risks=r.quality_risks,
        method_code=r.method_code,
    )


def visible(access: CondoAccess, opp: Opportunity) -> bool:
    return access.can(Permission.VIEW_OPPORTUNITY_DRAFT) or opp.presented_at is not None


async def _number(session: AsyncSession, condo: Condominium, today: date) -> str:
    prefix = f"O-{today.year}-"
    last = await session.scalar(
        select(func.max(Opportunity.number)).where(
            Opportunity.condominium_id == condo.id, Opportunity.number.like(f"{prefix}%")
        )
    )
    return f"{prefix}{(int(last.rsplit('-', 1)[1]) + 1) if last else 1:04d}"


async def create_from_finding(
    session: AsyncSession, access: CondoAccess, finding_id: uuid.UUID, today: date
) -> Opportunity:
    if not access.can(Permission.VIEW_OPPORTUNITY_DRAFT):
        raise OpportunityError("Só a equipe CondoOS gera oportunidades.", 403)
    condo = await session.scalar(
        select(Condominium).where(Condominium.id == access.condominium_id).with_for_update()
    )
    assert condo is not None
    finding = await session.scalar(
        select(Finding).where(Finding.id == finding_id, Finding.condominium_id == condo.id)
    )
    if finding is None:
        raise OpportunityError("Achado não encontrado.", 404)
    if finding.status in ("descartado", "superado", "ignorado"):
        raise OpportunityError("Este achado foi descartado, superado ou ignorado.", 409)
    existing = await session.scalar(
        select(Opportunity.number)
        .join(OpportunityFinding, OpportunityFinding.opportunity_id == Opportunity.id)
        .where(
            OpportunityFinding.finding_id == finding.id,
            Opportunity.status.not_in([s.value for s in CLOSED]),
        )
    )
    if existing:
        raise OpportunityError(f"Este achado já está na oportunidade {existing}.", 409)
    supplier = await session.get(Supplier, finding.supplier_id) if finding.supplier_id else None
    estimate, kind, title, recommendation = estimate_from_finding(
        finding, supplier.legal_name if supplier else "o fornecedor"
    )
    contract_id = None
    for ev in finding.evidence or []:
        if isinstance(ev, dict) and ev.get("kind") == "contract" and ev.get("id"):
            contract_id = uuid.UUID(str(ev["id"]))
    if contract_id and await session.get(Contract, contract_id) is None:
        contract_id = None
    outcome = evaluate_policy(await current_policy(session, condo.id), "opportunity")
    status = (
        S.APROVADA_PARA_CLIENTE
        if outcome.requirement == ReviewRequirement.NONE
        else S.EM_REVISAO_INTERNA
    )
    opp = Opportunity(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        number=await _number(session, condo, today),
        title=title,
        opportunity_type=kind,
        status=status.value,
        contract_id=contract_id,
        supplier_id=finding.supplier_id,
        recommendation=recommendation,
        operational_impact="Nenhum: corrige a cobrança sem mudar o serviço.",
        legal_contractual_risk="baixo",
        implementation_readiness="precisa_aprovacao",
        review_requirement=outcome.requirement.value,
        review_policy_version=outcome.version,
        presented_at=utcnow() if status == S.APROVADA_PARA_CLIENTE else None,
        created_by_user_id=access.user_id,
    )
    session.add(opp)
    await session.flush()
    session.add(
        OpportunityFinding(
            id=uuid.uuid4(), condominium_id=condo.id, opportunity_id=opp.id, finding_id=finding.id
        )
    )
    session.add(_record(opp, SavingsStage.POTENCIAL, estimate, access.user_id))
    await record_audit(
        session,
        action="opportunity.created",
        object_type="opportunity",
        object_id=opp.id,
        actor_user_id=access.user_id,
        condominium_id=condo.id,
        details={"finding_id": str(finding.id), "method": METHOD, "status": status.value},
    )
    await session.flush()
    return opp


def _need_comment(comment: str | None) -> str:
    text = (comment or "").strip()
    if len(text) < 5:
        raise OpportunityError("Escreva o motivo (mínimo de 5 caracteres).")
    return text


def is_reviewer(access: CondoAccess, opp: Opportunity) -> bool:
    if not access.can(Permission.REVIEW_OPPORTUNITY):
        return False
    if opp.review_requirement == ReviewRequirement.INTERNAL_REVIEW.value:
        return Role.CONDOOS_REVIEWER in access.roles
    return True


REVIEW_MOVES: dict[
    OpportunityReviewAction, tuple[frozenset[OpportunityStatus], OpportunityStatus]
] = {
    A.APROVAR: (frozenset({S.EM_REVISAO_INTERNA}), S.APROVADA_PARA_CLIENTE),
    A.DEVOLVER: (frozenset({S.EM_REVISAO_INTERNA}), S.DEVOLVIDA),
    A.REJEITAR: (frozenset({S.EM_REVISAO_INTERNA, S.DEVOLVIDA}), S.REJEITADA),
    A.REABRIR_REVISAO: (frozenset({S.APROVADA_PARA_CLIENTE}), S.EM_REVISAO_INTERNA),
}
CONDO_MOVES: dict[
    OpportunityReviewAction, tuple[frozenset[OpportunityStatus], OpportunityStatus]
] = {
    A.CONDOMINIO_APROVAR: (frozenset({S.APROVADA_PARA_CLIENTE}), S.APROVADA_PELO_CONDOMINIO),
    A.CONDOMINIO_RECUSAR: (frozenset({S.APROVADA_PARA_CLIENTE}), S.RECUSADA_PELO_CONDOMINIO),
}


def allowed_actions(access: CondoAccess, opp: Opportunity) -> list[str]:
    status = OpportunityStatus(opp.status)
    out: list[str] = []
    if is_reviewer(access, opp):
        out += [a.value for a, (src, _) in REVIEW_MOVES.items() if status in src]
        if status in EDITABLE:
            out.append(A.AJUSTAR.value)
    if access.can(Permission.APPROVE_IN_CONDO):
        out += [a.value for a, (src, _) in CONDO_MOVES.items() if status in src]
    return out


async def _review_row(
    session: AsyncSession,
    access: CondoAccess,
    opp: Opportunity,
    action: OpportunityReviewAction,
    comment: str | None,
    from_status: str,
    version_hash: str | None,
) -> None:
    session.add(
        OpportunityReview(
            id=uuid.uuid4(),
            condominium_id=opp.condominium_id,
            opportunity_id=opp.id,
            user_id=access.user_id,
            action=action.value,
            comment=comment,
            from_status=from_status,
            to_status=opp.status,
            reviewed_version_hash=version_hash,
        )
    )
    await record_audit(
        session,
        action=f"opportunity.{action.value}",
        object_type="opportunity",
        object_id=opp.id,
        actor_user_id=access.user_id,
        condominium_id=opp.condominium_id,
        details={"from": from_status, "to": opp.status},
    )


async def decide(
    session: AsyncSession,
    access: CondoAccess,
    opp: Opportunity,
    action: OpportunityReviewAction,
    comment: str | None,
) -> None:
    status = OpportunityStatus(opp.status)
    if action in REVIEW_MOVES:
        if not is_reviewer(access, opp):
            raise OpportunityError("Só a revisão CondoOS decide esta etapa.", 403)
        sources, target = REVIEW_MOVES[action]
    elif action in CONDO_MOVES:
        if not access.can(Permission.APPROVE_IN_CONDO):
            raise OpportunityError("Só quem decide pelo condomínio aprova ou recusa.", 403)
        sources, target = CONDO_MOVES[action]
    else:
        raise OpportunityError("Ação não reconhecida.")
    if status not in sources:
        raise OpportunityError("Esta ação não está disponível agora.", 409)
    text = (comment or "").strip() or None
    if action in (A.DEVOLVER, A.REJEITAR, A.REABRIR_REVISAO, A.CONDOMINIO_RECUSAR):
        text = _need_comment(comment)
    potential = await latest(session, opp, SavingsStage.POTENCIAL)
    assert potential is not None
    version = potential.version_hash
    if action == A.APROVAR:
        session.add(
            _record(
                opp,
                SavingsStage.ESTIMADA_VALIDADA,
                estimate_of(potential),
                access.user_id,
                supersedes=potential.id,
            )
        )
        opp.presented_at = utcnow()
    elif action == A.REABRIR_REVISAO:
        opp.presented_at = None  # back out of the board's view until approved again
    elif action == A.CONDOMINIO_APROVAR:
        validated = await latest(session, opp, SavingsStage.ESTIMADA_VALIDADA)
        if validated is None or validated.version_hash != version:
            # A material change after the review: it must be reviewed again (US-011).
            raise OpportunityError(
                "A estimativa mudou depois da revisão: aguarde nova revisão.", 409
            )
        session.add(
            _record(
                opp,
                SavingsStage.APROVADA,
                estimate_of(validated),
                access.user_id,
                supersedes=validated.id,
            )
        )
    previous = opp.status
    opp.status = target.value
    await _review_row(session, access, opp, action, text, previous, version)
    await session.flush()


async def adjust(
    session: AsyncSession,
    access: CondoAccess,
    opp: Opportunity,
    changes: dict[str, Any],
    reason: str | None,
) -> None:
    """The reviewer corrects the estimate: a new potential row, never an edit."""
    if not is_reviewer(access, opp):
        raise OpportunityError("Só a revisão CondoOS ajusta a estimativa.", 403)
    if OpportunityStatus(opp.status) not in EDITABLE:
        raise OpportunityError("Reabra a revisão para ajustar a estimativa.", 409)
    text = _need_comment(reason)
    current = await latest(session, opp, SavingsStage.POTENCIAL)
    assert current is not None
    e = estimate_of(current)
    for key in ("amount", "one_time_cost"):
        if changes.get(key) is not None:
            value = Decimal(str(changes[key])).quantize(CENT)
            if value < 0:
                raise OpportunityError("Valores não podem ser negativos.")
            setattr(e, key, value)
    for key in ("periodicity", "confidence", "quality_risks"):
        if changes.get(key) is not None:
            setattr(e, key, changes[key])
    if changes.get("assumptions") is not None:
        e.assumptions = [a.strip() for a in changes["assumptions"] if a and a.strip()]
    e.method_code = f"{current.method_code}+ajuste"
    if e.version_hash() == current.version_hash:
        raise OpportunityError("Nada mudou na estimativa.", 409)
    session.add(_record(opp, SavingsStage.POTENCIAL, e, access.user_id, supersedes=current.id))
    previous = opp.status
    if opp.status == S.DEVOLVIDA.value:
        opp.status = S.EM_REVISAO_INTERNA.value
    await _review_row(session, access, opp, A.AJUSTAR, text, previous, e.version_hash())
    await session.flush()


# --------------------------------------------------------------------------- after approval (CB-063)

CONTRACT_METHOD = "acordo_v1"
MEASURE_METHOD = "medicao_faturas_v1"


def follow_up_actions(access: CondoAccess, opp: Opportunity) -> list[str]:
    """Recording the agreement and measuring the result. Neither moves money nor sends
    anything: they record what people did outside the system, with evidence."""
    status = OpportunityStatus(opp.status)
    out: list[str] = []
    if status == S.APROVADA_PELO_CONDOMINIO and (
        access.can(Permission.APPROVE_IN_CONDO) or is_reviewer(access, opp)
    ):
        out.append("registrar_contratacao")
    if status in (S.EM_EXECUCAO, S.IMPLEMENTADA, S.RESULTADO_MEDIDO) and is_reviewer(access, opp):
        out.append("medir_resultado")
    return out


async def record_contracted(
    session: AsyncSession,
    access: CondoAccess,
    opp: Opportunity,
    *,
    document_id: uuid.UUID,
    agreed_amount: Decimal,
    one_time_cost: Decimal,
    comment: str | None,
) -> SavingsRecord:
    """ "Contratada" (D76): the new agreed monthly value, proven by the agreement document.
    Saving per month = baseline − agreed value (method ``acordo_v1``)."""
    if "registrar_contratacao" not in follow_up_actions(access, opp):
        if OpportunityStatus(opp.status) != S.APROVADA_PELO_CONDOMINIO:
            raise OpportunityError("Registre a contratação depois da aprovação do condomínio.", 409)
        raise OpportunityError("Seu papel não registra a contratação.", 403)
    doc = await session.scalar(
        select(Document).where(
            Document.id == document_id, Document.condominium_id == opp.condominium_id
        )
    )
    if doc is None:
        raise OpportunityError("Documento do acordo não encontrado.", 404)
    approved = await latest(session, opp, SavingsStage.APROVADA)
    if approved is None:
        raise OpportunityError("A oportunidade não tem economia aprovada.", 409)
    agreed = Decimal(agreed_amount).quantize(CENT)
    cost = Decimal(one_time_cost).quantize(CENT)
    if agreed < 0 or cost < 0:
        raise OpportunityError("Valores não podem ser negativos.")
    base = estimate_of(approved)
    saving = (base.baseline_amount - agreed).quantize(CENT)
    if saving <= 0:
        raise OpportunityError(
            "O valor acordado não é menor que o baseline: não há economia contratada a registrar."
        )
    e = Estimate(
        amount=saving,
        periodicity="mensal",
        one_time_cost=cost,
        baseline_start=base.baseline_start,
        baseline_end=base.baseline_end,
        baseline_amount=base.baseline_amount,
        assumptions=[
            f"Valor mensal acordado: R$ {agreed:.2f} (documento {doc.original_filename}).",
            f"Baseline: R$ {base.baseline_amount:.2f} por mês, o mesmo da estimativa aprovada.",
            "A economia contratada ainda não foi observada nas faturas.",
            *([f"Observação: {comment.strip()}"] if comment and comment.strip() else []),
        ],
        evidence=[
            {"type": "document", "id": str(doc.id), "role": "acordo"},
            {"type": "savings_record", "id": str(approved.id), "stage": "aprovada"},
        ],
        confidence="alta",
        quality_risks="Depende de o fornecedor faturar pelo valor acordado.",
        method_code=CONTRACT_METHOD,
    )
    row = _record(opp, SavingsStage.CONTRATADA, e, access.user_id, supersedes=approved.id)
    session.add(row)
    previous = opp.status
    opp.status = S.EM_EXECUCAO.value
    await record_audit(
        session,
        action="opportunity.contratada",
        object_type="opportunity",
        object_id=opp.id,
        actor_user_id=access.user_id,
        condominium_id=opp.condominium_id,
        details={"from": previous, "to": opp.status, "document_id": str(doc.id)},
    )
    await session.flush()
    return row


async def measure_realized(
    session: AsyncSession, access: CondoAccess, opp: Opportunity
) -> SavingsRecord:
    """ "Realizada e comprovada" (D76): only from invoices issued after the agreement, each with
    its fiscal document, compared with the baseline by code (``medicao_faturas_v1``). The
    change cost is discounted in the net value. A new measurement is a new row."""
    if "medir_resultado" not in follow_up_actions(access, opp):
        raise OpportunityError("Só a revisão CondoOS mede o resultado, depois da contratação.", 403)
    contracted = await latest(session, opp, SavingsStage.CONTRATADA)
    if contracted is None:
        raise OpportunityError("Registre a contratação antes de medir o resultado.", 409)
    since = contracted.created_at.date()
    stmt = select(Expense).where(
        Expense.condominium_id == opp.condominium_id,
        Expense.issue_date >= since,
        Expense.document_id.is_not(None),
    )
    if opp.contract_id is not None:
        stmt = stmt.where(Expense.contract_id == opp.contract_id)
    elif opp.supplier_id is not None:
        stmt = stmt.where(Expense.supplier_id == opp.supplier_id)
    else:
        raise OpportunityError("A oportunidade não tem contrato nem fornecedor para medir.")
    invoices = list(await session.scalars(stmt.order_by(Expense.competence).limit(12)))
    if not invoices:
        raise OpportunityError(
            "Ainda não há faturas com nota emitidas depois do acordo: nada a medir.", 409
        )
    base = estimate_of(contracted)
    reductions = [(base.baseline_amount - x.amount).quantize(CENT) for x in invoices]
    monthly = (sum(reductions, Decimal("0")) / len(reductions)).quantize(CENT)
    months = ", ".join(f"{x.competence:%m/%Y}" for x in invoices)
    e = Estimate(
        amount=monthly,
        periodicity="mensal",
        one_time_cost=base.one_time_cost,
        baseline_start=base.baseline_start,
        baseline_end=base.baseline_end,
        baseline_amount=base.baseline_amount,
        assumptions=[
            f"Média de {len(invoices)} fatura(s) com nota emitidas depois do acordo ({months}).",
            f"Redução por fatura = baseline de R$ {base.baseline_amount:.2f} menos o valor faturado.",
            "Anualizado ×12 a partir da média observada; o custo da mudança é descontado.",
        ],
        evidence=[
            {"type": "savings_record", "id": str(contracted.id), "stage": "contratada"},
            *[{"type": "expense", "id": str(x.id)} for x in invoices],
        ],
        confidence="alta" if len(invoices) >= 3 else "media",
        quality_risks=(
            ""
            if monthly > 0
            else "As faturas posteriores não mostram redução em relação ao baseline."
        ),
        method_code=MEASURE_METHOD,
    )
    row = _record(opp, SavingsStage.REALIZADA, e, access.user_id, supersedes=contracted.id)
    session.add(row)
    previous = opp.status
    opp.status = S.RESULTADO_MEDIDO.value
    await record_audit(
        session,
        action="opportunity.realizada",
        object_type="opportunity",
        object_id=opp.id,
        actor_user_id=access.user_id,
        condominium_id=opp.condominium_id,
        details={"from": previous, "to": opp.status, "invoices": len(invoices)},
    )
    await session.flush()
    return row
