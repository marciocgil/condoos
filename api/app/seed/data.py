"""Deterministic fictitious seed data.

Every company, CNPJ, person and address here is invented. CNPJs have valid check digits
but are randomly generated; any coincidence with a real registration is accidental.

Planted cases for each audit rule (positive and negative) are added in milestone 3.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.br import generate_cnpj
from app.core.time import add_months
from app.db.base import Base
from app.db.enums import (
    AdjustmentIndex,
    BankTransactionOrigin,
    BoardPosition,
    CompetenceStatus,
    Role,
)
from app.db.models import (
    AppUser,
    BankTransaction,
    BoardMember,
    Competence,
    Condominium,
    Contract,
    Expense,
    ManagementCompany,
    Membership,
    Supplier,
)

SEED_RANDOM = 20261105
# Last month with data. Fixed so tests never depend on today's date.
LAST_MONTH = date(2026, 10, 1)
MONTHS = 12
CENT = Decimal("0.01")

DEFAULT_CATEGORIES = [
    "portaria",
    "limpeza",
    "manutencao",
    "elevadores",
    "jardinagem",
    "energia",
    "agua",
    "gas",
    "seguro",
    "administracao",
    "dedetizacao",
    "obras",
]


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass
class SupplierSpec:
    key: str
    legal_name: str
    trade_name: str
    cnae_code: str
    cnae_description: str
    category: str
    partners: list[str]


SUPPLIERS: list[SupplierSpec] = [
    SupplierSpec(
        "portaria",
        "Vigilare Serviços de Portaria Ltda",
        "Vigilare Portaria",
        "8011-1/01",
        "Atividades de vigilância e segurança privada",
        "portaria",
        ["Rogério Almeida Pinto", "Sueli Martins Costa"],
    ),
    SupplierSpec(
        "limpeza",
        "Brilho Total Conservação e Limpeza Ltda",
        "Brilho Total",
        "8121-4/00",
        "Limpeza em prédios e em domicílios",
        "limpeza",
        ["Marta Cristina Vasconcelos"],
    ),
    SupplierSpec(
        "elevadores",
        "Ascende Elevadores e Manutenção Ltda",
        "Ascende Elevadores",
        "4329-1/03",
        "Instalação, manutenção e reparação de elevadores",
        "elevadores",
        ["Otávio Bernardes Lins", "Helena Siqueira Duarte"],
    ),
    SupplierSpec(
        "jardim",
        "Verde Vivo Paisagismo Ltda",
        "Verde Vivo",
        "8130-3/00",
        "Atividades paisagísticas",
        "jardinagem",
        ["Joaquim Ferraz Neto"],
    ),
    SupplierSpec(
        "dedetizacao",
        "Praga Zero Controle Sanitário Ltda",
        "Praga Zero",
        "8122-2/00",
        "Imunização e controle de pragas urbanas",
        "dedetizacao",
        ["Patrícia Moura Leal"],
    ),
    SupplierSpec(
        "manutencao",
        "Fixa Bem Manutenção Predial Ltda",
        "Fixa Bem",
        "4321-5/00",
        "Instalação e manutenção elétrica",
        "manutencao",
        ["Gilberto Assunção Reis", "Lúcia Fernandes Prates"],
    ),
    SupplierSpec(
        "energia",
        "Companhia Energética Fictícia S.A.",
        "CEF Energia",
        "3514-0/00",
        "Distribuição de energia elétrica",
        "energia",
        ["Conselho de Administração (pessoa jurídica)"],
    ),
    SupplierSpec(
        "agua",
        "Saneamento Exemplar S.A.",
        "Saneamento Exemplar",
        "3600-6/01",
        "Captação, tratamento e distribuição de água",
        "agua",
        ["Conselho de Administração (pessoa jurídica)"],
    ),
    SupplierSpec(
        "gas",
        "Gás Fictício Distribuidora Ltda",
        "Gás Fictício",
        "3520-4/02",
        "Distribuição de combustíveis gasosos por redes urbanas",
        "gas",
        ["Renato Queiroz Batista"],
    ),
    SupplierSpec(
        "seguro",
        "Amparo Seguros Gerais S.A.",
        "Amparo Seguros",
        "6512-0/00",
        "Seguros não-vida",
        "seguro",
        ["Conselho de Administração (pessoa jurídica)"],
    ),
]


@dataclass
class ContractSpec:
    supplier: str
    object: str
    scope_items: list[str]
    monthly_value: Decimal
    index: AdjustmentIndex
    base_month: int | None
    start: date
    end: date | None
    # Fictitious yearly adjustment applied at the base month (not real index data).
    applied_pct: Decimal = Decimal("0")


@dataclass
class CondoSpec:
    name: str
    slug: str
    units: int
    address: str
    approval_limits: dict[str, Any]
    contracts: list[ContractSpec]
    utilities: dict[str, Decimal]  # supplier key -> monthly base amount
    board: list[tuple[str, BoardPosition]]


CONDOS: list[CondoSpec] = [
    CondoSpec(
        name="Condomínio Residencial Jardim das Acácias",
        slug="jardim-das-acacias",
        units=120,
        address="Rua das Acácias Fictícias, 100 — Bairro Exemplo, Cidade Modelo/SP",
        approval_limits={"default": "8000.00", "by_category": {"obras": "5000.00"}},
        contracts=[
            ContractSpec(
                "portaria",
                "Portaria 24 horas",
                ["portaria 24h", "controle de acesso", "ronda noturna"],
                money(18500),
                AdjustmentIndex.INPC,
                3,
                date(2024, 3, 1),
                date(2027, 2, 28),
                Decimal("4.20"),
            ),
            ContractSpec(
                "limpeza",
                "Limpeza e conservação das áreas comuns",
                ["limpeza de áreas comuns", "limpeza de garagem", "recolhimento de lixo"],
                money(9200),
                AdjustmentIndex.IPCA,
                1,
                date(2023, 1, 1),
                date(2026, 12, 31),
                Decimal("4.50"),
            ),
            ContractSpec(
                "elevadores",
                "Manutenção preventiva e corretiva de 4 elevadores",
                [
                    "manutenção preventiva mensal",
                    "atendimento a chamados",
                    "troca de peças de desgaste",
                ],
                money(2400),
                AdjustmentIndex.IGPM,
                7,
                date(2022, 7, 1),
                None,
                Decimal("3.80"),
            ),
            ContractSpec(
                "jardim",
                "Manutenção de jardins",
                ["poda", "corte de grama", "adubação"],
                money(1500),
                AdjustmentIndex.FIXO,
                None,
                date(2025, 2, 1),
                date(2027, 1, 31),
            ),
            ContractSpec(
                "dedetizacao",
                "Controle de pragas trimestral",
                ["dedetização", "desratização"],
                money(650),
                AdjustmentIndex.NENHUM,
                None,
                date(2025, 1, 1),
                date(2026, 12, 31),
            ),
        ],
        utilities={"energia": money(7800), "agua": money(11200), "gas": money(2100)},
        board=[
            ("Ana Ribeiro Sampaio", BoardPosition.SINDICO),
            ("Fábio Lima Cordeiro", BoardPosition.SUBSINDICO),
            ("Bruno Tavares Molina", BoardPosition.CONSELHEIRO),
            ("Inês Carvalho Rocha", BoardPosition.CONSELHEIRO),
            ("Jorge Pacheco Viana", BoardPosition.CONSELHEIRO),
        ],
    ),
    CondoSpec(
        name="Condomínio Edifício Mirante do Vale",
        slug="mirante-do-vale",
        units=64,
        address="Avenida do Vale Imaginário, 2500 — Centro Fictício, Cidade Modelo/SP",
        approval_limits={"default": "5000.00", "by_category": {"obras": "3000.00"}},
        contracts=[
            ContractSpec(
                "portaria",
                "Portaria diurna",
                ["portaria diurna", "controle de acesso"],
                money(9800),
                AdjustmentIndex.INPC,
                5,
                date(2024, 5, 1),
                date(2027, 4, 30),
                Decimal("4.10"),
            ),
            ContractSpec(
                "limpeza",
                "Limpeza das áreas comuns",
                ["limpeza de áreas comuns", "recolhimento de lixo"],
                money(5400),
                AdjustmentIndex.IPCA,
                8,
                date(2023, 8, 1),
                date(2027, 7, 31),
                Decimal("4.40"),
            ),
            ContractSpec(
                "elevadores",
                "Manutenção de 2 elevadores",
                ["manutenção preventiva mensal", "atendimento a chamados"],
                money(1300),
                AdjustmentIndex.IGPM,
                10,
                date(2021, 10, 1),
                None,
                Decimal("3.50"),
            ),
            ContractSpec(
                "manutencao",
                "Manutenção elétrica e hidráulica predial",
                ["manutenção elétrica", "manutenção hidráulica", "bombas de recalque"],
                money(2200),
                AdjustmentIndex.IPCA,
                2,
                date(2024, 2, 1),
                date(2027, 1, 31),
                Decimal("4.60"),
            ),
            ContractSpec(
                "dedetizacao",
                "Controle de pragas trimestral",
                ["dedetização", "desratização"],
                money(420),
                AdjustmentIndex.NENHUM,
                None,
                date(2025, 1, 1),
                date(2026, 12, 31),
            ),
        ],
        utilities={"energia": money(4100), "agua": money(6300)},
        board=[
            ("Carla Menezes Duarte", BoardPosition.SINDICO),
            ("Paulo Henrique Saldanha", BoardPosition.SUBSINDICO),
            ("Renata Oliveira Bastos", BoardPosition.CONSELHEIRO),
            ("Sérgio Antunes Leme", BoardPosition.CONSELHEIRO),
        ],
    ),
]

# (name, email, [(condo slug | None for company, role)])
USERS: list[tuple[str, str, list[tuple[str | None, Role]]]] = [
    (
        "Ana Ribeiro Sampaio",
        "ana.sindica@acacias.example.com",
        [("jardim-das-acacias", Role.SINDICO)],
    ),
    (
        "Bruno Tavares Molina",
        "bruno.conselho@acacias.example.com",
        [("jardim-das-acacias", Role.CONSELHEIRO)],
    ),
    (
        "Carla Menezes Duarte",
        "carla.sindica@mirante.example.com",
        [("mirante-do-vale", Role.SINDICO)],
    ),
    ("Diego Fontes Arruda", "diego.gerente@atlantida.example.com", [(None, Role.GERENTE)]),
    ("Elisa Prado Monteiro", "elisa.analista@atlantida.example.com", [(None, Role.ANALISTA)]),
]


@dataclass
class SeedResult:
    objects: list[list[Base]] = field(default_factory=list)  # insert phases, in FK order
    company_cnpj: str = ""


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _fake_cpf_masked(rng: random.Random) -> str:
    middle = f"{rng.randint(0, 999999):06d}"
    return f"***.{middle[:3]}.{middle[3:]}-**"


def months() -> list[date]:
    return [add_months(LAST_MONTH, -i) for i in range(MONTHS - 1, -1, -1)]


def _contract_value_at(spec: ContractSpec, month: date) -> Decimal:
    """Monthly value at a given month, applying the fictitious yearly adjustment."""
    value = spec.monthly_value
    if spec.base_month is None or spec.applied_pct == 0:
        return value
    # Count base-month anniversaries between contract start (exclusive) and month (inclusive).
    first = date(spec.start.year + 1, spec.base_month, 1)
    if first <= spec.start:
        first = date(first.year + 1, spec.base_month, 1)
    anniversary = first
    while anniversary <= month:
        value = money(value * (1 + spec.applied_pct / 100))
        anniversary = date(anniversary.year + 1, spec.base_month, 1)
    return value


def build_seed() -> SeedResult:
    rng = random.Random(SEED_RANDOM)
    result = SeedResult()

    company = ManagementCompany(
        id=_uuid(rng),
        name="Atlântida Gestão Condominial Ltda (fictícia)",
        cnpj=generate_cnpj(rng),
    )
    result.company_cnpj = company.cnpj

    suppliers: dict[str, Supplier] = {}
    for spec in SUPPLIERS:
        suppliers[spec.key] = Supplier(
            id=_uuid(rng),
            cnpj=generate_cnpj(rng),
            legal_name=spec.legal_name,
            trade_name=spec.trade_name,
            cnae_main={"code": spec.cnae_code, "description": spec.cnae_description},
            cnae_secondary=[],
            registration_status="ATIVA",
            registration_status_date=date(2015, 1, 1) + timedelta(days=rng.randint(0, 2500)),
            partners=[
                {"name": name, "cpf_masked": _fake_cpf_masked(rng), "qualification": "Sócio"}
                for name in spec.partners
            ],
        )

    condos: dict[str, Condominium] = {}
    board_members: list[Base] = []
    contracts: list[Base] = []
    expenses: list[Base] = []
    transactions: list[Base] = []
    competences: list[Base] = []
    invoice_counter: dict[str, int] = {k: rng.randint(1000, 5000) for k in suppliers}

    for cspec in CONDOS:
        condo = Condominium(
            id=_uuid(rng),
            management_company_id=company.id,
            name=cspec.name,
            slug=cspec.slug,
            cnpj=generate_cnpj(rng),
            units=cspec.units,
            address=cspec.address,
            approval_limits=cspec.approval_limits,
            rule_params={},
            expense_categories=DEFAULT_CATEGORIES,
            retention_years=5,
        )
        condos[cspec.slug] = condo
        for name, position in cspec.board:
            board_members.append(
                BoardMember(
                    id=_uuid(rng),
                    condominium_id=condo.id,
                    full_name=name,
                    position=position.value,
                    term_start=date(2025, 4, 1),
                    term_end=date(2027, 3, 31),
                )
            )

        contract_rows: list[tuple[ContractSpec, Contract]] = []
        for kspec in cspec.contracts:
            contract = Contract(
                id=_uuid(rng),
                condominium_id=condo.id,
                supplier_id=suppliers[kspec.supplier].id,
                object=kspec.object,
                scope_items=kspec.scope_items,
                monthly_value=kspec.monthly_value,
                adjustment_index=kspec.index.value,
                adjustment_base_month=kspec.base_month,
                start_date=kspec.start,
                end_date=kspec.end,
            )
            contracts.append(contract)
            contract_rows.append((kspec, contract))

        def add_expense(
            *,
            condo: Condominium,
            supplier_key: str,
            month: date,
            amount: Decimal,
            description: str,
            contract: Contract | None,
        ) -> None:
            supplier = suppliers[supplier_key]
            invoice_counter[supplier_key] += 1
            issue = month + timedelta(days=rng.randint(0, 6))
            due = issue + timedelta(days=10)
            expense = Expense(
                id=_uuid(rng),
                condominium_id=condo.id,
                supplier_id=supplier.id,
                contract_id=contract.id if contract else None,
                competence=month,
                issue_date=issue,
                due_date=due,
                amount=amount,
                category=next(s.category for s in SUPPLIERS if s.key == supplier_key),
                description=description,
                invoice_number=str(invoice_counter[supplier_key]),
            )
            expenses.append(expense)
            transactions.append(
                BankTransaction(
                    id=_uuid(rng),
                    condominium_id=condo.id,
                    posted_at=due + timedelta(days=rng.randint(-1, 2)),
                    amount=-amount,
                    payee_name=supplier.legal_name,
                    payee_document=supplier.cnpj,
                    description=f"PAG BOLETO {supplier.trade_name or supplier.legal_name}"[:300],
                    origin=BankTransactionOrigin.SEED.value,
                    external_id=f"seed-{expense.id}",
                    expense_id=expense.id,
                )
            )

        for month in months():
            for kspec, contract in contract_rows:
                if kspec.end is not None and month > kspec.end:
                    continue
                if kspec.supplier == "dedetizacao" and month.month % 3 != 1:
                    continue  # quarterly service
                add_expense(
                    condo=condo,
                    supplier_key=kspec.supplier,
                    month=month,
                    amount=_contract_value_at(kspec, month),
                    description=f"{kspec.object} — {month:%m/%Y}",
                    contract=contract,
                )
            for key, base in cspec.utilities.items():
                # Mild seasonality and noise; summer months use more energy and water.
                season = 1.12 if month.month in (12, 1, 2, 3) else 1.0
                amount = money(float(base) * season * rng.uniform(0.94, 1.06))
                label = {
                    "energia": "Energia elétrica",
                    "agua": "Água e esgoto",
                    "gas": "Gás canalizado",
                }[key]
                add_expense(
                    condo=condo,
                    supplier_key=key,
                    month=month,
                    amount=amount,
                    description=f"{label} — {month:%m/%Y}",
                    contract=None,
                )
            # Monthly condo-fee income (credit), aggregated.
            transactions.append(
                BankTransaction(
                    id=_uuid(rng),
                    condominium_id=condo.id,
                    posted_at=month + timedelta(days=9),
                    amount=money(cspec.units * rng.uniform(640, 660)),
                    payee_name=None,
                    payee_document=None,
                    description="RECEBIMENTO TAXAS CONDOMINIAIS",
                    origin=BankTransactionOrigin.SEED.value,
                    external_id=f"seed-receita-{condo.slug}-{month:%Y%m}",
                )
            )
            competences.append(
                Competence(
                    id=_uuid(rng),
                    condominium_id=condo.id,
                    month=month,
                    status=(
                        CompetenceStatus.ABERTA.value
                        if month == LAST_MONTH
                        else CompetenceStatus.FECHADA.value
                    ),
                )
            )
        # Annual building insurance, paid in the first seeded month.
        add_expense(
            condo=condo,
            supplier_key="seguro",
            month=months()[0],
            amount=money(cspec.units * 95),
            description="Seguro predial obrigatório — anual",
            contract=None,
        )

    users: list[Base] = []
    memberships: list[Base] = []
    for name, email, grants in USERS:
        user = AppUser(id=_uuid(rng), name=name, email=email, is_active=True)
        users.append(user)
        for slug, role in grants:
            memberships.append(
                Membership(
                    id=_uuid(rng),
                    user_id=user.id,
                    condominium_id=condos[slug].id if slug else None,
                    management_company_id=None if slug else company.id,
                    role=role.value,
                )
            )
    # Link board members that are also users.
    by_name = {u.name: u for u in users if isinstance(u, AppUser)}
    for bm in board_members:
        assert isinstance(bm, BoardMember)
        if bm.full_name in by_name:
            bm.user_id = by_name[bm.full_name].id

    result.objects = [
        [company],
        list(suppliers.values()),
        list(condos.values()),
        users,
        memberships + board_members + contracts + competences,
        expenses,
        transactions,
    ]
    return result
