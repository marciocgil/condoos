from fastapi import APIRouter
from sqlalchemy import select

from app.auth.deps import CurrentPrincipal, roles_on_condominium
from app.auth.rbac import CondoAccess
from app.db.models import Condominium, ManagementCompany, Membership
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
        roles = await roles_on_condominium(session, user.id, condo)
        access = CondoAccess(user_id=user.id, condominium_id=condo.id, roles=roles)
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
            .where(Membership.user_id == user.id)
            .order_by(ManagementCompany.name)
        )
    ).all()
    companies: dict[str, CompanyMembershipOut] = {}
    for company, role in company_rows:
        key = str(company.id)
        if key not in companies:
            companies[key] = CompanyMembershipOut(id=company.id, name=company.name, roles=[])
        companies[key].roles.append(role)

    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        condominiums=condo_out,
        management_companies=list(companies.values()),
    )
