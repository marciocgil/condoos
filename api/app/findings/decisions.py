"""Finding lifecycle: who may do what, and the resulting status (spec §7).

- Síndico (DECIDE_FINDING): confirmar, contestar (comment required), ignorar — only on
  findings the board can see.
- Reviewers (VALIDATE_FINDING): validar (→ publicado) and descartar (comment required) findings
  under review; reabrir a decided or discarded finding. Since D74 the reviewer is the CondoOS
  reviewer, or the management company's manager when the condominium allows it (the
  permission itself is then removed in ``CondoAccess``). A finding whose requirement is
  ``internal_review`` is reviewed by a CondoOS reviewer only.
- solicitar_evidencia (REVIEW_FINDING, comment required): an inconclusive finding waits for
  evidence (pendente_evidencia) instead of being validated or discarded.
Every action becomes one row in ``decision`` (append-only) and one in ``audit_log``.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rbac import CondoAccess, Permission
from app.core.audit import record_audit
from app.db.enums import DecisionAction, FindingStatus, ReviewRequirement, Role
from app.db.models import Decision, Finding

A, S = DecisionAction, FindingStatus


@dataclass(frozen=True)
class Transition:
    permission: Permission
    from_status: frozenset[FindingStatus]
    comment_required: bool


TRANSITIONS: dict[DecisionAction, Transition] = {
    A.CONFIRMAR: Transition(
        Permission.DECIDE_FINDING, frozenset({S.PUBLICADO, S.CONTESTADO, S.IGNORADO}), False
    ),
    A.CONTESTAR: Transition(
        Permission.DECIDE_FINDING, frozenset({S.PUBLICADO, S.CONFIRMADO, S.IGNORADO}), True
    ),
    A.IGNORAR: Transition(
        Permission.DECIDE_FINDING, frozenset({S.PUBLICADO, S.CONFIRMADO, S.CONTESTADO}), False
    ),
    A.VALIDAR: Transition(
        Permission.VALIDATE_FINDING,
        frozenset({S.AGUARDANDO_VALIDACAO, S.PENDENTE_EVIDENCIA}),
        False,
    ),
    A.DESCARTAR: Transition(
        Permission.VALIDATE_FINDING, frozenset({S.AGUARDANDO_VALIDACAO, S.PENDENTE_EVIDENCIA}), True
    ),
    A.SOLICITAR_EVIDENCIA: Transition(
        Permission.REVIEW_FINDING, frozenset({S.AGUARDANDO_VALIDACAO}), True
    ),
    A.REABRIR: Transition(
        Permission.VALIDATE_FINDING,
        frozenset({S.CONFIRMADO, S.CONTESTADO, S.IGNORADO, S.DESCARTADO}),
        False,
    ),
}

RESULT: dict[DecisionAction, FindingStatus] = {
    A.CONFIRMAR: S.CONFIRMADO,
    A.CONTESTAR: S.CONTESTADO,
    A.IGNORAR: S.IGNORADO,
    A.VALIDAR: S.PUBLICADO,
    A.DESCARTAR: S.DESCARTADO,
    A.SOLICITAR_EVIDENCIA: S.PENDENTE_EVIDENCIA,
}

REVIEW_ACTIONS = frozenset({A.VALIDAR, A.DESCARTAR, A.SOLICITAR_EVIDENCIA, A.REABRIR})


def _reviewer_allowed(access: CondoAccess, finding: Finding, action: DecisionAction) -> bool:
    """``internal_review`` (economy recommendations) is CondoOS-only (D74)."""
    if action not in REVIEW_ACTIONS:
        return True
    if finding.review_requirement == ReviewRequirement.INTERNAL_REVIEW.value:
        return Role.CONDOOS_REVIEWER in access.roles
    return True


class DecisionError(ValueError):
    """Message shown to the user (pt-BR); ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def allowed_actions(access: CondoAccess, finding: Finding) -> list[DecisionAction]:
    current = FindingStatus(finding.status)
    return [
        action
        for action, t in TRANSITIONS.items()
        if access.can(t.permission)
        and current in t.from_status
        and _reviewer_allowed(access, finding, action)
    ]


def _reopen_target(finding: Finding) -> FindingStatus:
    # A discarded serious finding goes back to the manager; anything else is published again.
    return S.AGUARDANDO_VALIDACAO if finding.status == S.DESCARTADO.value else S.PUBLICADO


async def decide(
    session: AsyncSession,
    access: CondoAccess,
    finding: Finding,
    action: DecisionAction,
    comment: str | None,
) -> Decision:
    t = TRANSITIONS[action]
    if not access.can(t.permission) or not _reviewer_allowed(access, finding, action):
        raise DecisionError("Seu papel não permite esta ação.", 403)
    if FindingStatus(finding.status) not in t.from_status:
        raise DecisionError("Esta ação não está disponível para o achado neste momento.", 409)
    text = (comment or "").strip() or None
    if t.comment_required and (text is None or len(text) < 5):
        raise DecisionError(
            "Escreva um comentário explicando o motivo (mínimo de 5 caracteres).", 422
        )
    previous = finding.status
    finding.status = (RESULT.get(action) or _reopen_target(finding)).value
    decision = Decision(
        id=uuid.uuid4(),
        condominium_id=finding.condominium_id,
        finding_id=finding.id,
        user_id=access.user_id,
        action=action.value,
        comment=text,
    )
    session.add(decision)
    await record_audit(
        session,
        action="finding.decision",
        object_type="finding",
        object_id=finding.id,
        actor_user_id=access.user_id,
        condominium_id=finding.condominium_id,
        details={"action": action.value, "from": previous, "to": finding.status},
    )
    await session.flush()
    return decision
