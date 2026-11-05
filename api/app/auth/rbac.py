"""Role-based access control, scoped per condominium.

A user's roles on a condominium are its direct memberships plus any company-level role
(gerente/analista) on the condominium's management company.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.db.enums import Role


class Permission(StrEnum):
    VIEW = "view"  # summary, published findings, contracts, history, chat
    VIEW_PENDING_FINDINGS = "view_pending_findings"  # findings awaiting validation
    DECIDE_FINDING = "decide_finding"  # confirm / contest / ignore
    COMMENT_FINDING = "comment_finding"
    VALIDATE_FINDING = "validate_finding"  # validate or discard serious findings
    UPLOAD_DOCUMENT = "upload_document"
    CORRECT_EXTRACTION = "correct_extraction"
    CONFIGURE = "configure"  # approval limits, rule params, categories, members
    CLOSE_COMPETENCE = "close_competence"
    EXPORT = "export"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SINDICO: frozenset(
        {
            Permission.VIEW,
            Permission.DECIDE_FINDING,
            Permission.COMMENT_FINDING,
            Permission.UPLOAD_DOCUMENT,
            Permission.EXPORT,
        }
    ),
    Role.SUBSINDICO: frozenset({Permission.VIEW, Permission.COMMENT_FINDING, Permission.EXPORT}),
    Role.CONSELHEIRO: frozenset({Permission.VIEW, Permission.COMMENT_FINDING, Permission.EXPORT}),
    Role.ANALISTA: frozenset(
        {
            Permission.VIEW,
            Permission.VIEW_PENDING_FINDINGS,
            Permission.UPLOAD_DOCUMENT,
            Permission.CORRECT_EXTRACTION,
            Permission.EXPORT,
        }
    ),
    Role.GERENTE: frozenset(Permission),
}


@dataclass(frozen=True)
class CondoAccess:
    user_id: uuid.UUID
    condominium_id: uuid.UUID
    roles: frozenset[Role]

    @property
    def permissions(self) -> frozenset[Permission]:
        perms: set[Permission] = set()
        for role in self.roles:
            perms |= ROLE_PERMISSIONS[role]
        return frozenset(perms)

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions
