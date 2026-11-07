from fastapi import APIRouter
from sqlalchemy import or_, select

from app.auth.deps import CurrentPrincipal, access_for, active_membership
from app.core.time import utcnow
from app.db.models import Condominium, ManagementCompany, Membership, PlatformRoleGrant
from app.db.session import DbSession
from app.routers.schemas import CompanyMembershipOut, CondoMembershipOut, MeOut

router = APIRouter(tags=["me"])


@router.get("/me")
async def me(principal: CurrentPrincipal, session: DbSession) -> MeOut:
    user = principal.user
    condos = (
        await session.scalars(
            select(Condominium)
            .where(Condominium.id.in_(principal.condominium_ids))
            .order_by(Condominium.name)
        )
    ).all()
    condo_out = []
    for condo in condos:
        access = await access_for(session, user.id, condo)
        roles = access.roles
        condo_out.append(
            CondoMembershipOut(
                id=condo.id,
                name=condo.name,
                slug=condo.slug,
                management_company_id=condo.management_company_id,
                roles=sorted(roles),
                permissions=sorted(access.permissions),
            )
        )

    company_rows = (
        await session.execute(
            select(ManagementCompany, Membership.role)
            .join(Membership, Membership.management_company_id == ManagementCompany.id)
            .where(Membership.user_id == user.id, *active_membership())
            .order_by(ManagementCompany.name)
        )
    ).all()
    companies: dict[str, CompanyMembershipOut] = {}
    for company, role in company_rows:
        key = str(company.id)
        if key not in companies:
            companies[key] = CompanyMembershipOut(id=company.id, name=company.name, roles=[])
        companies[key].roles.append(role)

    now = utcnow()
    platform_roles = sorted(
        await session.scalars(
            select(PlatformRoleGrant.role).where(
                PlatformRoleGrant.user_id == user.id,
                PlatformRoleGrant.revoked_at.is_(None),
                or_(PlatformRoleGrant.expires_at.is_(None), PlatformRoleGrant.expires_at > now),
            )
        )
    )
    return MeOut(
        id=user.id,
        platform_roles=platform_roles,
        name=user.name,
        email=user.email,
        condominiums=condo_out,
        management_companies=list(companies.values()),
    )
