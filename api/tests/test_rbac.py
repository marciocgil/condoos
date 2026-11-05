"""Role rules: board members never see findings awaiting validation."""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.auth.rbac import ROLE_PERMISSIONS, CondoAccess, Permission
from app.db.enums import FindingStatus, Role
from app.db.models import Finding
from app.db.session import sessionmaker_for
from tests.helpers import ANALISTA, CONSELHEIRO_ACACIAS, GERENTE, SINDICA_ACACIAS, condo_id, login


@pytest.fixture
async def findings(admin_engine: AsyncEngine) -> dict[str, uuid.UUID]:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    created: dict[str, uuid.UUID] = {}
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        for status in (FindingStatus.AGUARDANDO_VALIDACAO, FindingStatus.PUBLICADO):
            f = Finding(
                id=uuid.uuid4(),
                condominium_id=acacias,
                rule_code="R01",
                severity="alta" if status == FindingStatus.AGUARDANDO_VALIDACAO else "media",
                title=f"Achado de teste {status.value}",
                explanation="Indício para verificação.",
                amount_at_risk=Decimal("100.00"),
                status=status.value,
                evidence=[],
                rule_inputs={},
                competence=date(2026, 10, 1),
                dedupe_key=f"test-{uuid.uuid4()}",
            )
            s.add(f)
            created[status.value] = f.id
    return created


@pytest.mark.parametrize(
    ("email", "sees_pending"),
    [(SINDICA_ACACIAS, False), (CONSELHEIRO_ACACIAS, False), (GERENTE, True), (ANALISTA, True)],
)
async def test_pending_findings_visibility(
    client: httpx.AsyncClient,
    mailer: MemoryMailer,
    admin_engine: AsyncEngine,
    findings: dict[str, uuid.UUID],
    email: str,
    sees_pending: bool,
) -> None:
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, email)
    ids = {f["id"] for f in (await client.get(f"/condominiums/{acacias}/findings")).json()}
    assert str(findings["publicado"]) in ids
    assert (str(findings["aguardando_validacao"]) in ids) is sees_pending


def test_only_gerente_validates_and_configures() -> None:
    for role, perms in ROLE_PERMISSIONS.items():
        allowed = role == Role.GERENTE
        assert (Permission.VALIDATE_FINDING in perms) is allowed
        assert (Permission.CONFIGURE in perms) is allowed


def test_permissions_union_of_roles() -> None:
    access = CondoAccess(uuid.uuid4(), uuid.uuid4(), frozenset({Role.CONSELHEIRO, Role.ANALISTA}))
    assert access.can(Permission.CORRECT_EXTRACTION)
    assert not access.can(Permission.DECIDE_FINDING)
