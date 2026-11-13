"""Operator commands for CondoOS staff access (D77). Run with the owner database role.

    python -m app.platform add-person  <email> "<nome>"
    python -m app.platform grant-role  <email> <condoos_admin|condoos_reviewer> "<motivo>"
    python -m app.platform revoke-role <email> <condoos_admin|condoos_reviewer>
    python -m app.platform assign      <email> <condoos_admin|condoos_reviewer> <slug> "<motivo>"
    python -m app.platform unassign    <email> <condoos_admin|condoos_reviewer> <slug>
    python -m app.platform reset-data  <domínio do site>   (zera os dados; D131, deploy/reset.sh)

The first CondoOS admin is created here; afterwards an admin assigns reviewers to the
condominiums it is assigned to through the API (``/condominiums/{id}/assignments``).
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.enums import PlatformRole
from app.db.models import CondoAssignment, Condominium
from app.db.session import get_admin_engine, sessionmaker_for
from app.platform import (
    PlatformError,
    add_person,
    assign,
    grant_role,
    revoke_role,
    unassign,
    user_by_email,
)

USAGE = __doc__ or ""


async def _reset(domain: str) -> str:
    from urllib.parse import urlparse

    from app.config import get_settings
    from app.platform.reset import reset_data
    from app.storage.base import get_storage

    expected = urlparse(get_settings().web_base_url).hostname or ""
    if domain != expected:
        raise PlatformError(f"Confirmação não confere: digite {expected}.")
    async with sessionmaker_for(get_admin_engine())() as session, session.begin():
        summary = await reset_data(session, get_storage())
    return (
        f"Dados apagados: {summary['condominios']} condomínio(s), "
        f"{summary['documentos']} documento(s), {summary['arquivos']} arquivo(s). "
        "Contas das pessoas mantidas, sem acesso até novo convite."
    )


async def run(argv: list[str]) -> str:
    if len(argv) == 2 and argv[0] == "reset-data":
        return await _reset(argv[1])
    if len(argv) < 3:
        raise PlatformError(USAGE)
    if argv[0] == "add-person" and len(argv) == 3:
        async with sessionmaker_for(get_admin_engine())() as session, session.begin():
            await add_person(session, email=argv[1], name=argv[2])
        return "Pessoa cadastrada."
    command, email, role_name, *rest = argv
    try:
        role = PlatformRole(role_name)
    except ValueError as exc:
        raise PlatformError(f"Papel desconhecido: {role_name}.") from exc
    async with sessionmaker_for(get_admin_engine())() as session, session.begin():
        user = await user_by_email(session, email)
        if command == "grant-role" and len(rest) == 1:
            await grant_role(session, user=user, role=role, reason=rest[0])
            return f"Papel {role.value} concedido."
        if command == "revoke-role" and not rest:
            await revoke_role(session, user=user, role=role)
            return f"Papel {role.value} revogado."
        if command in ("assign", "unassign") and len(rest) >= 1:
            condo = await session.scalar(select(Condominium).where(Condominium.slug == rest[0]))
            if condo is None:
                raise PlatformError("Condomínio não encontrado.")
            if command == "assign" and len(rest) == 2:
                await assign(session, condominium_id=condo.id, user=user, role=role, reason=rest[1])
                return f"Atribuído a {condo.name}."
            if command == "unassign" and len(rest) == 1:
                row = await session.scalar(
                    select(CondoAssignment).where(
                        CondoAssignment.condominium_id == condo.id,
                        CondoAssignment.user_id == user.id,
                        CondoAssignment.platform_role == role.value,
                    )
                )
                if row is None:
                    raise PlatformError("Atribuição não encontrada.")
                await unassign(session, assignment=row)
                return f"Atribuição removida de {condo.name}."
    raise PlatformError(USAGE)


def main(argv: list[str]) -> int:
    try:
        print(asyncio.run(run(argv)))
    except PlatformError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
