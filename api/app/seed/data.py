"""Deterministic fictitious seed data.

Every company, CNPJ, person and address here is invented. CNPJs have valid check digits
but are randomly generated; any coincidence with a real registration is accidental.

Planted cases for each audit rule (positive and negative) are added in milestone 3.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
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
    Approval,
    AppUser,
    BankTransaction,
    BoardMember,
    Competence,
    Condominium,
    Contract,
    Expense,
    IndexValue,
    ManagementCompany,
    Membership,
    Supplier,
)
from app.enrichment.indices import fixture_values
from app.rules.contracts import value_at

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


@dataclass(frozen=True)
class ExpectedFinding:
    """A planted case that the rules engine must find (milestone 3 acceptance)."""

    condo_slug: str
    rule_code: str
    subject: str  # an id (or category) that appears in the finding's subject_key
    needs_model: bool = False  # R04/R07 cases judged by the model
    note: str = ""


@dataclass
class SeedResult:
    objects: list[list[Base]] = field(default_factory=list)  # insert phases, in FK order
    company_cnpj: str = ""
    expected: list[ExpectedFinding] = field(default_factory=list)


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


def _fake_cpf_masked(rng: random.Random) -> str:
    middle = f"{rng.randint(0, 999999):06d}"
    return f"***.{middle[:3]}.{middle[3:]}-**"


def months() -> list[date]:
    return [add_months(LAST_MONTH, -i) for i in range(MONTHS - 1, -1, -1)]


def index_table() -> dict[str, dict[date, Decimal]]:
    """Real BCB series (IPCA, IGP-M, INPC) from the versioned fixture."""
    return {k.value: v for k, v in fixture_values().items()}


def _contract_value_at(spec: ContractSpec, month: date) -> Decimal:
    """Monthly value after every adjustment, with the real index (same function as R02/R03)."""
    value = value_at(
        spec.monthly_value, spec.index.value, spec.base_month, spec.start, month, index_table()
    )
    assert value is not None, f"índice ausente para {spec.object} em {month}"
    return value


ENRICHED_AT = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


class Builder:
    """Collects seed rows; every expense gets a matching bank debit unless told otherwise."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.expenses: list[Base] = []
        self.transactions: list[Base] = []
        self.approvals: list[Base] = []
        self.extra_suppliers: list[Base] = []
        self.extra_contracts: list[Base] = []
        self.invoice_counter: dict[str, int] = {}

    def supplier(
        self,
        legal_name: str,
        cnae: tuple[str, str],
        *,
        status: str = "ATIVA",
        status_date: date | None = None,
        partners: list[str] = (),  # type: ignore[assignment]
    ) -> Supplier:
        s = Supplier(
            id=_uuid(self.rng),
            cnpj=generate_cnpj(self.rng),
            legal_name=legal_name,
            trade_name=None,
            cnae_main={"code": cnae[0], "description": cnae[1]},
            cnae_secondary=[],
            registration_status=status,
            registration_status_date=status_date or date(2018, 3, 1),
            partners=[
                {"name": n, "cpf_masked": _fake_cpf_masked(self.rng), "qualification": "Sócio"}
                for n in partners
            ],
            enriched_at=ENRICHED_AT,
            enrichment_source="seed",
        )
        self.extra_suppliers.append(s)
        return s

    def expense(
        self,
        condo: Condominium,
        supplier: Supplier,
        *,
        amount: Decimal,
        month: date,
        category: str,
        description: str,
        contract: Contract | None = None,
        issue: date | None = None,
        due: date | None = None,
        invoice: str | None = None,
        paid: bool = True,
    ) -> Expense:
        if invoice is None:
            self.invoice_counter[supplier.cnpj] = (
                self.invoice_counter.get(supplier.cnpj, self.rng.randint(1000, 5000)) + 1
            )
            invoice = str(self.invoice_counter[supplier.cnpj])
        issue = issue or month + timedelta(days=self.rng.randint(0, 6))
        due = due or issue + timedelta(days=10)
        e = Expense(
            id=_uuid(self.rng),
            condominium_id=condo.id,
            supplier_id=supplier.id,
            contract_id=contract.id if contract else None,
            competence=month,
            issue_date=issue,
            due_date=due,
            amount=amount,
            category=category,
            description=description,
            invoice_number=invoice,
            origin="seed",
        )
        self.expenses.append(e)
        if paid:
            self.debit(
                condo,
                amount,
                due + timedelta(days=self.rng.randint(-1, 2)),
                f"PAG BOLETO {supplier.trade_name or supplier.legal_name}",
                supplier,
                e,
            )
        return e

    def debit(
        self,
        condo: Condominium,
        amount: Decimal,
        when: date,
        description: str,
        supplier: Supplier | None = None,
        expense: Expense | None = None,
    ) -> BankTransaction:
        t = BankTransaction(
            id=_uuid(self.rng),
            condominium_id=condo.id,
            posted_at=when,
            amount=-amount,
            payee_name=supplier.legal_name if supplier else None,
            payee_document=supplier.cnpj if supplier else None,
            description=description[:300],
            origin=BankTransactionOrigin.SEED.value,
            external_id=f"seed-{expense.id if expense else uuid.UUID(int=self.rng.getrandbits(128))}",
            expense_id=expense.id if expense else None,
        )
        self.transactions.append(t)
        return t

    def find(self, condo: Condominium, supplier: Supplier, month: date) -> Expense:
        return next(
            e
            for e in self.expenses
            if isinstance(e, Expense)
            and e.condominium_id == condo.id
            and e.supplier_id == supplier.id
            and e.competence == month
        )

    def set_amount(self, e: Expense, amount: Decimal) -> None:
        e.amount = amount
        for t in self.transactions:
            if isinstance(t, BankTransaction) and t.expense_id == e.id:
                t.amount = -amount


def build_seed() -> SeedResult:
    rng = random.Random(SEED_RANDOM)
    result = SeedResult()
    b = Builder(rng)

    company = ManagementCompany(
        id=_uuid(rng),
        name="Atlântida Gestão Condominial Ltda (fictícia)",
        cnpj=generate_cnpj(rng),
    )
    result.company_cnpj = company.cnpj

    suppliers: dict[str, Supplier] = {}
    categories: dict[str, str] = {}
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
            enriched_at=ENRICHED_AT,
            enrichment_source="seed",
        )
        categories[spec.key] = spec.category

    condos: dict[str, Condominium] = {}
    board_members: list[Base] = []
    contracts: list[Base] = []
    competences: list[Base] = []
    contract_by: dict[tuple[str, str], Contract] = {}

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
                billing_frequency_months=3 if kspec.supplier == "dedetizacao" else 1,
            )
            contracts.append(contract)
            contract_rows.append((kspec, contract))
            contract_by[(cspec.slug, kspec.supplier)] = contract

        for month in months():
            for kspec, contract in contract_rows:
                if kspec.end is not None and month > kspec.end:
                    continue
                if kspec.supplier == "dedetizacao" and month.month % 3 != 1:
                    continue  # quarterly service
                b.expense(
                    condo,
                    suppliers[kspec.supplier],
                    amount=_contract_value_at(kspec, month),
                    month=month,
                    category=categories[kspec.supplier],
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
                b.expense(
                    condo,
                    suppliers[key],
                    amount=amount,
                    month=month,
                    category=categories[key],
                    description=f"{label} — {month:%m/%Y}",
                )
            # Monthly condo-fee income (credit), aggregated.
            b.transactions.append(
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
        # Annual building insurance, paid in the first seeded month, approved in assembly.
        insurance = b.expense(
            condo,
            suppliers["seguro"],
            amount=money(cspec.units * 95),
            month=months()[0],
            category="seguro",
            description="Seguro predial obrigatório — anual",
        )
        b.approvals.append(
            Approval(
                id=_uuid(rng),
                condominium_id=condo.id,
                expense_id=insurance.id,
                approved_by="Assembleia geral ordinária",
                approved_at=date(2025, 10, 20),
                notes="Renovação do seguro aprovada em assembleia.",
            )
        )

    planted_contracts = plant_cases(b, condos, suppliers, contract_by, result.expected)

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
    by_name = {u.name: u for u in users if isinstance(u, AppUser)}
    for bm in board_members:
        assert isinstance(bm, BoardMember)
        if bm.full_name in by_name:
            bm.user_id = by_name[bm.full_name].id

    index_rows: list[Base] = [
        IndexValue(
            id=_uuid(rng), index_name=name, month=month, pct_change=pct, source="bcb_sgs_fixture"
        )
        for name, series in index_table().items()
        for month, pct in sorted(series.items())
    ]

    result.objects = [
        [company, *index_rows],
        list(suppliers.values()) + b.extra_suppliers,
        list(condos.values()),
        users,
        memberships + board_members + contracts + planted_contracts + competences,
        b.expenses,
        b.transactions + b.approvals,
    ]
    return result


def plant_cases(
    b: Builder,
    condos: dict[str, Condominium],
    suppliers: dict[str, Supplier],
    contract_by: dict[tuple[str, str], Contract],
    expected: list[ExpectedFinding],
) -> list[Base]:
    """One positive and at least one negative case per rule, all in October 2026.

    The engine, run for October with reference date 05/11/2026, must find exactly the
    positives recorded in ``expected`` and nothing else.
    """
    oct_ = LAST_MONTH
    sep = add_months(oct_, -1)
    ac, mi = condos["jardim-das-acacias"], condos["mirante-do-vale"]
    new_contracts: list[Base] = []

    # R01 + : same supplier, same value, same month, two invoices.
    hidraulica = b.supplier(
        "Hidráulica Fictícia Serviços Ltda",
        ("4322-3/01", "Instalações hidráulicas, sanitárias e de gás"),
    )
    b.expense(
        ac,
        hidraulica,
        amount=money(3400),
        month=oct_,
        category="manutencao",
        description="Reparo na prumada de água do bloco B",
        issue=date(2026, 10, 3),
        invoice="501",
    )
    dup = b.expense(
        ac,
        hidraulica,
        amount=money(3400),
        month=oct_,
        category="manutencao",
        description="Reparo na prumada de água do bloco B",
        issue=date(2026, 10, 17),
        invoice="502",
    )
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias", "R01", str(dup.id), note="duas notas de R$ 3.400,00 no mesmo mês"
        )
    )
    # R01 − : recurring monthly contract payments of the same value (every month in the seed).

    # R02 + : portaria charged 10% above the adjusted contract value.

    over = b.find(ac, suppliers["portaria"], oct_)
    b.set_amount(over, over.amount + money(1850))
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias", "R02", str(over.id), note="portaria R$ 1.850,00 acima do contrato"
        )
    )
    # R02 − : limpeza at exactly the contract value (seed).

    # R03 + : elevators (IGP-M, base month October) adjusted by 9%.
    elev = b.find(mi, suppliers["elevadores"], oct_)
    prev = b.find(mi, suppliers["elevadores"], sep)
    b.set_amount(elev, money(prev.amount * Decimal("1.09")))
    expected.append(
        ExpectedFinding(
            "mirante-do-vale", "R03", str(elev.id), note="reajuste de 9% contra o IGP-M acumulado"
        )
    )
    # R03 − : no other October anniversary; covered by unit tests.

    # R04 + (model): cleaning company bills a façade painting under the cleaning contract.
    limpeza = contract_by[("jardim-das-acacias", "limpeza")]
    paint = b.expense(
        ac,
        suppliers["limpeza"],
        amount=money(4500),
        month=oct_,
        category="limpeza",
        description="Pintura da fachada do bloco A",
        contract=limpeza,
    )
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias",
            "R04",
            str(paint.id),
            needs_model=True,
            note="pintura cobrada no contrato de limpeza",
        )
    )
    # R04 − : elevator call-out within "atendimento a chamados" (in scope by words).
    b.expense(
        ac,
        suppliers["elevadores"],
        amount=money(780),
        month=oct_,
        category="elevadores",
        description="Atendimento a chamados: troca de botoeira do elevador 2",
        contract=contract_by[("jardim-das-acacias", "elevadores")],
    )

    # R05 + : pump maintenance contract ended 31/08/2026, still paid in October.
    bombas = b.supplier(
        "Bombas Fictícias Manutenção Ltda",
        ("3314-7/02", "Manutenção e reparação de equipamentos hidráulicos e pneumáticos"),
    )
    pump_contract = Contract(
        id=_uuid(b.rng),
        condominium_id=ac.id,
        supplier_id=bombas.id,
        object="Manutenção das bombas de recalque",
        scope_items=["manutenção preventiva das bombas", "troca de selos e rolamentos"],
        monthly_value=money(850),
        adjustment_index=AdjustmentIndex.FIXO.value,
        adjustment_base_month=None,
        start_date=date(2025, 9, 1),
        end_date=date(2026, 8, 31),
    )
    new_contracts.append(pump_contract)
    for m in months():
        if m <= date(2026, 8, 1) or m == oct_:
            e = b.expense(
                ac,
                bombas,
                amount=money(850),
                month=m,
                category="manutencao",
                description=f"Manutenção das bombas de recalque — {m:%m/%Y}",
                contract=pump_contract,
            )
            if m == oct_:
                expected.append(
                    ExpectedFinding(
                        "jardim-das-acacias",
                        "R05",
                        str(e.id),
                        note="contrato terminou em 31/08/2026",
                    )
                )
    # R05 − : limpeza contract valid until 31/12/2026 (seed).

    # R06 + : supplier closed (BAIXADA) since May 2026.
    closed = b.supplier(
        "Reforma Rápida Construções Ltda",
        ("4120-4/00", "Construção de edifícios"),
        status="BAIXADA",
        status_date=date(2026, 5, 10),
    )
    e = b.expense(
        ac,
        closed,
        amount=money(4200),
        month=oct_,
        category="obras",
        description="Recuperação do piso da garagem",
    )
    expected.append(ExpectedFinding("jardim-das-acacias", "R06", str(e.id), note="CNPJ baixado"))
    # R06 − : status INAPTA only from December 2026 (after the expense); partners near-miss for R08.
    glass = b.supplier(
        "Vidraçaria Fictícia Ltda",
        ("4330-4/02", "Instalação de portas, janelas, tetos, divisórias e armários"),
        status="INAPTA",
        status_date=date(2026, 12, 1),
        partners=["Ana Ribeiro Sampaio", "Ines Carvalho"],
    )
    b.expense(
        mi,
        glass,
        amount=money(1900),
        month=oct_,
        category="obras",
        description="Troca de vidros do hall",
    )

    # R07 + : clothing retailer billing electrical maintenance.
    shop = b.supplier(
        "Moda Bela Confecções Ltda",
        ("4781-4/00", "Comércio varejista de artigos do vestuário e acessórios"),
    )
    b.expense(
        ac,
        shop,
        amount=money(2400),
        month=oct_,
        category="manutencao",
        description="Manutenção elétrica do salão de festas",
    )
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias", "R07", str(shop.id), note="CNAE de comércio de roupas"
        )
    )
    # R07 − : electrical/hydraulic firms in maintenance (Fixa Bem, Hidráulica).

    # R08 + : a conselheira of Jardim das Acácias is a partner of a supplier.
    garden = b.supplier(
        "Jardins & Cia Paisagismo Ltda",
        ("8130-3/00", "Atividades paisagísticas"),
        partners=["INES CARVALHO ROCHA", "Otávio Brandão Lima"],
    )
    b.expense(
        ac,
        garden,
        amount=money(1300),
        month=oct_,
        category="jardinagem",
        description="Plantio de mudas no jardim interno",
    )
    expected.append(
        ExpectedFinding("jardim-das-acacias", "R08", str(garden.id), note="sócia é conselheira")
    )
    # R08 − : Vidraçaria partners "Ana Ribeiro Sampaio" (board of the *other* condominium)
    #         and "Ines Carvalho" (partial name).

    # R09 + : PIX with no document. − : bank fee; PIX inside the grace period.
    pix = b.debit(ac, money(2300), date(2026, 10, 14), "PIX ENVIADO JOAO S")
    expected.append(
        ExpectedFinding("jardim-das-acacias", "R09", str(pix.id), note="PIX sem nota após 10 dias")
    )
    b.debit(ac, Decimal("89.90"), date(2026, 10, 5), "TARIFA CESTA DE SERVICOS")
    b.debit(ac, money(650), date(2026, 10, 30), "PIX ENVIADO MARIA L")

    # R10 + : invoice due 20/10 never paid. − : invoice due 02/11 (grace period).
    fix = suppliers["manutencao"]
    unpaid = b.expense(
        mi,
        fix,
        amount=money(640),
        month=oct_,
        category="manutencao",
        description="Conserto do interfone",
        issue=date(2026, 10, 10),
        due=date(2026, 10, 20),
        paid=False,
    )
    expected.append(
        ExpectedFinding(
            "mirante-do-vale", "R10", str(unpaid.id), note="vencida em 20/10 sem débito"
        )
    )
    b.expense(
        mi,
        fix,
        amount=money(210),
        month=oct_,
        category="manutencao",
        description="Troca de lâmpadas do corredor",
        issue=date(2026, 10, 31),
        due=date(2026, 11, 2),
        paid=False,
    )

    # R11 + : water bill three times the usual (leak). − : energy and gas as usual.
    water = b.find(ac, suppliers["agua"], oct_)
    b.set_amount(water, money(water.amount * 3))
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias", "R11", "agua", note="conta de água três vezes a média"
        )
    )

    # R12 + : works above the R$ 5.000 limit without approval. − : same, with approval.
    smith = b.supplier(
        "Serralheria Fictícia Ltda",
        ("4330-4/02", "Instalação de portas, janelas, tetos, divisórias e armários"),
    )
    big = b.expense(
        ac,
        smith,
        amount=money(6000),
        month=oct_,
        category="obras",
        description="Novo portão da garagem",
    )
    expected.append(
        ExpectedFinding(
            "jardim-das-acacias", "R12", str(big.id), note="obra acima da alçada sem aprovação"
        )
    )
    approved = b.expense(
        ac,
        smith,
        amount=money(7000),
        month=oct_,
        category="obras",
        description="Grades das janelas do térreo",
    )
    b.approvals.append(
        Approval(
            id=_uuid(b.rng),
            condominium_id=ac.id,
            expense_id=approved.id,
            approved_by="Assembleia geral extraordinária",
            approved_at=date(2026, 9, 20),
            notes="Grades aprovadas em assembleia.",
        )
    )
    return new_contracts
