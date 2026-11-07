"""Review proportional to risk (D74; docs/data-model.md §3).

Every finding is identified and recorded automatically. A versioned policy decides, from the
finding's own data, whether a person must review it before the board sees it. Rules are
typed data evaluated by code: no expression strings, no ``eval`` (spec §9.2).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.db.enums import FindingStatus, ReviewRequirement, Role
from app.db.models import ReviewPolicy


class RuleMatch(BaseModel):
    """All given conditions must hold. Omitted = any value."""

    model_config = ConfigDict(extra="forbid")

    rule_code: list[str] | None = None
    category: list[str] | None = None
    severity: list[Literal["alta", "media", "baixa"]] | None = None
    min_amount: Decimal | None = Field(default=None, ge=0)
    confidence: list[Literal["alta", "media", "baixa"]] | None = None
    ai_assisted: bool | None = None


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: Literal["finding", "opportunity"]
    match: RuleMatch = RuleMatch()
    requirement: ReviewRequirement
    reviewers: list[Literal["condoos_reviewer", "gerente"]] = []


# Platform default, version 1. It reproduces the behaviour before D74 for findings (serious
# ones wait for review, the others are published) and makes the internal CondoOS review
# mandatory for economy recommendations (the Optimize slice will use it).
PLATFORM_DEFAULT_V1: list[dict[str, Any]] = [
    {
        "object": "opportunity",
        "requirement": "internal_review",
        "reviewers": ["condoos_reviewer"],
    },
    {
        "object": "finding",
        "match": {"severity": ["alta"]},
        "requirement": "qualified_review",
        "reviewers": ["condoos_reviewer", "gerente"],
    },
    {"object": "finding", "requirement": "none"},
]

# Reviewer roles a policy may name, and the system role each corresponds to.
REVIEWER_ROLES: dict[str, Role] = {
    "condoos_reviewer": Role.CONDOOS_REVIEWER,
    "gerente": Role.GERENTE,
}


@dataclass(frozen=True)
class Policy:
    version: int
    rules: list[PolicyRule]
    condominium_specific: bool


@dataclass(frozen=True)
class Outcome:
    requirement: ReviewRequirement
    reviewers: frozenset[Role]
    version: int


def parse_rules(raw: list[dict[str, Any]]) -> list[PolicyRule]:
    rules = [PolicyRule.model_validate(r) for r in raw]
    for obj in ("finding", "opportunity"):
        mine = [r for r in rules if r.object == obj]
        if mine and mine[-1].match != RuleMatch():
            raise ValueError(f"a última regra de {obj} precisa valer para todos os casos")
    return rules


async def current_policy(session: AsyncSession, condominium_id: uuid.UUID) -> Policy:
    """The condominium's latest version in force, or the platform default."""
    row = await session.scalar(
        select(ReviewPolicy)
        .where(
            or_(
                ReviewPolicy.condominium_id == condominium_id, ReviewPolicy.condominium_id.is_(None)
            ),
            ReviewPolicy.valid_from <= utcnow(),
        )
        # A condominium's own policy wins over the platform default; then the latest version.
        .order_by(ReviewPolicy.condominium_id.is_(None), ReviewPolicy.version.desc())
        .limit(1)
    )
    if row is None:  # migration 0012 always inserts the default; this is only a safety net
        return Policy(version=1, rules=parse_rules(PLATFORM_DEFAULT_V1), condominium_specific=False)
    return Policy(
        version=row.version,
        rules=parse_rules(row.rules),
        condominium_specific=row.condominium_id is not None,
    )


def _matches(m: RuleMatch, facts: dict[str, Any]) -> bool:
    for key in ("rule_code", "category", "severity", "confidence"):
        allowed = getattr(m, key)
        if allowed is not None and facts.get(key) not in allowed:
            return False
    if m.min_amount is not None and Decimal(str(facts.get("amount") or 0)) < m.min_amount:
        return False
    return m.ai_assisted is None or bool(facts.get("ai_assisted")) == m.ai_assisted


def evaluate(policy: Policy, obj: Literal["finding", "opportunity"], **facts: Any) -> Outcome:
    for rule in policy.rules:
        if rule.object == obj and _matches(rule.match, facts):
            return Outcome(
                requirement=rule.requirement,
                reviewers=frozenset(REVIEWER_ROLES[r] for r in rule.reviewers),
                version=policy.version,
            )
    # No rule: the conservative answer is a review by CondoOS.
    return Outcome(
        ReviewRequirement.QUALIFIED_REVIEW, frozenset({Role.CONDOOS_REVIEWER}), policy.version
    )


def initial_status(requirement: ReviewRequirement | str) -> FindingStatus:
    req = ReviewRequirement(requirement)
    if req == ReviewRequirement.NONE:
        return FindingStatus.PUBLICADO
    if req == ReviewRequirement.PENDING_EVIDENCE:
        return FindingStatus.PENDENTE_EVIDENCIA
    return FindingStatus.AGUARDANDO_VALIDACAO
