"""Role-based access control, scoped per condominium.

A user's roles on a condominium are its active direct memberships, any active company-level
role (gerente/analista) on the condominium's management company, and CondoOS staff roles
with an active assignment to the condominium (D77). See ``app.auth.deps.roles_on_condominium``.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.db.enums import Role


class Permission(StrEnum):
    VIEW = "view"  # summary, published findings, contracts, history, chat
    VIEW_PENDING_FINDINGS = "view_pending_findings"  # findings awaiting review or evidence
    DECIDE_FINDING = "decide_finding"  # confirm / contest / ignore
    COMMENT_FINDING = "comment_finding"
    VALIDATE_FINDING = "validate_finding"  # validate, discard or reopen findings under review
    REVIEW_FINDING = "review_finding"  # ask for evidence on a finding under review (D74)
    UPLOAD_DOCUMENT = "upload_document"
    CORRECT_EXTRACTION = "correct_extraction"
    CONFIGURE = "configure"  # approval limits, rule params, categories, members
    CONFIGURE_POLICY = "configure_policy"  # who reviews findings in this condominium (D74)
    CLOSE_COMPETENCE = "close_competence"
    RECORD_APPROVAL = "record_approval"  # register a board/assembly approval of an expense
    EXPORT = "export"
    # Declared for the Optimize slice (D76, D77); no endpoint uses them yet.
    VIEW_OPPORTUNITY_DRAFT = "view_opportunity_draft"
    REVIEW_OPPORTUNITY = "review_opportunity"  # internal CondoOS review of a recommendation
    APPROVE_IN_CONDO = "approve_in_condo"  # the condominium's own decision, within its limits
    MANAGE_PLATFORM = "manage_platform"  # assign CondoOS staff to this condominium
    # Cases (D75, D80). MANAGE_CASES: create, edit, link, assign and move any case.
    # UPDATE_TASK: work on what is one's own (tasks assigned to them, cases they own).
    MANAGE_CASES = "manage_cases"
    UPDATE_TASK = "update_task"
    # Launch (D89): choose the journey's goal, put steps off, hide the card. Order only.
    MANAGE_LAUNCH = "manage_launch"
    # Delegated document requests (D95): revoke a link, close a request.
    MANAGE_DELEGATION = "manage_delegation"
    # Compliance (D108). MANAGE: turn the catalogue on, create obligations, link documents
    # and dates. VALIDATE: decide whether an obligation applies and how often (a person).
    MANAGE_COMPLIANCE = "manage_compliance"
    VALIDATE_COMPLIANCE = "validate_compliance"


P = Permission

# Validating and approving are kept apart (D77): no role holds both a review permission and
# APPROVE_IN_CONDO. ``tests/test_access_model.py`` checks it for every role.
REVIEW_PERMISSIONS: frozenset[Permission] = frozenset(
    {P.VALIDATE_FINDING, P.REVIEW_FINDING, P.REVIEW_OPPORTUNITY}
)

_MANAGEMENT_COMPANY = frozenset(
    {
        P.VIEW,
        P.VIEW_PENDING_FINDINGS,
        P.UPLOAD_DOCUMENT,
        P.CORRECT_EXTRACTION,
        P.RECORD_APPROVAL,
        P.EXPORT,
        P.UPDATE_TASK,
        P.MANAGE_COMPLIANCE,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SINDICO: frozenset(
        {
            P.VIEW,
            P.DECIDE_FINDING,
            P.COMMENT_FINDING,
            P.UPLOAD_DOCUMENT,
            P.EXPORT,
            P.CONFIGURE_POLICY,
            P.APPROVE_IN_CONDO,
            P.MANAGE_CASES,
            P.UPDATE_TASK,
            P.MANAGE_LAUNCH,
            P.MANAGE_DELEGATION,
            P.MANAGE_COMPLIANCE,
            P.VALIDATE_COMPLIANCE,
        }
    ),
    Role.SUBSINDICO: frozenset({P.VIEW, P.COMMENT_FINDING, P.EXPORT}),
    Role.CONSELHEIRO: frozenset({P.VIEW, P.COMMENT_FINDING, P.EXPORT}),
    Role.ANALISTA: _MANAGEMENT_COMPANY,
    # The manager keeps everything it had before D77; validating findings now also depends on
    # the condominium allowing the management company to review (see ``CondoAccess``).
    Role.GERENTE: _MANAGEMENT_COMPANY
    | {
        P.COMMENT_FINDING,
        P.VALIDATE_FINDING,
        P.REVIEW_FINDING,
        P.CONFIGURE,
        P.CLOSE_COMPETENCE,
        P.DECIDE_FINDING,
        P.VALIDATE_COMPLIANCE,
    },
    # Reserved roles (D77): accepted in memberships, no permission until activated.
    Role.ZELADOR: frozenset(),
    Role.FORNECEDOR: frozenset(),
    Role.MORADOR: frozenset(),
    Role.CONDOOS_ADMIN: frozenset(
        {
            P.VIEW,
            P.VIEW_PENDING_FINDINGS,
            P.UPLOAD_DOCUMENT,
            P.CORRECT_EXTRACTION,
            P.CONFIGURE,
            P.CONFIGURE_POLICY,
            P.EXPORT,
            P.VIEW_OPPORTUNITY_DRAFT,
            P.MANAGE_PLATFORM,
            P.MANAGE_CASES,
            P.UPDATE_TASK,
            P.MANAGE_LAUNCH,
            P.MANAGE_DELEGATION,
            P.MANAGE_COMPLIANCE,
        }
    ),
    Role.CONDOOS_REVIEWER: frozenset(
        {
            P.VIEW,
            P.VIEW_PENDING_FINDINGS,
            P.COMMENT_FINDING,
            P.VALIDATE_FINDING,
            P.REVIEW_FINDING,
            P.UPLOAD_DOCUMENT,
            P.CORRECT_EXTRACTION,
            P.RECORD_APPROVAL,
            P.CLOSE_COMPETENCE,
            P.EXPORT,
            P.VIEW_OPPORTUNITY_DRAFT,
            P.REVIEW_OPPORTUNITY,
            P.MANAGE_CASES,
            P.UPDATE_TASK,
        }
    ),
}

MANAGEMENT_COMPANY_ROLES: frozenset[Role] = frozenset({Role.GERENTE, Role.ANALISTA})


@dataclass(frozen=True)
class CondoAccess:
    user_id: uuid.UUID
    condominium_id: uuid.UUID
    roles: frozenset[Role]
    # ``condominium.management_company_reviews`` (D74): without it, the management company's
    # roles do not review findings in this condominium.
    company_reviews: bool = False

    @property
    def permissions(self) -> frozenset[Permission]:
        perms: set[Permission] = set()
        for role in self.roles:
            granted = ROLE_PERMISSIONS[role]
            if role in MANAGEMENT_COMPANY_ROLES and not self.company_reviews:
                granted = granted - REVIEW_PERMISSIONS
            perms |= granted
        return frozenset(perms)

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions
