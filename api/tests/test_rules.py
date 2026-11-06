"""Unit tests of the 12 audit rules: one positive and at least one negative case each.

Contexts are built in memory (no database). The model is replaced by a fake in R04/R07.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.db.enums import Severity
from app.db.models import (
    Approval,
    BankTransaction,
    BoardMember,
    Condominium,
    Contract,
    ContractAmendment,
    Document,
    Expense,
    Supplier,
)
from app.enrichment.indices import accumulated_12m, fixture_values
from app.rules import r04_scope, r07_cnae
from app.rules.base import RuleContext
from app.rules.contracts import anniversaries, value_at
from app.rules.engine import RULES_BY_CODE, run_rules
from app.rules.judge import CnaeJudgement, ScopeJudgement

OCT = date(2026, 10, 1)
SEP = date(2026, 9, 1)
REF = date(2026, 11, 5)
INDEX = {k.value: v for k, v in fixture_values().items()}


def dec(v: str) -> Decimal:
    return Decimal(v)


def condo(**kw: Any) -> Condominium:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "Condomínio Teste",
        "slug": "teste",
        "cnpj": "11222333000181",
        "units": 10,
        "address": "Rua Teste",
        "approval_limits": {"default": "5000.00"},
        "rule_params": {},
        "expense_categories": [],
        "retention_years": 5,
    }
    base.update(kw)
    return Condominium(**base)


def supplier(**kw: Any) -> Supplier:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "cnpj": "45723174000110",
        "legal_name": "Fornecedor Teste Ltda",
        "cnae_main": {"code": "8121-4/00", "description": "Limpeza em prédios"},
        "cnae_secondary": [],
        "registration_status": "ATIVA",
        "partners": [],
    }
    base.update(kw)
    return Supplier(**base)


def expense(s: Supplier | None, amount: str, competence: date = OCT, **kw: Any) -> Expense:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "condominium_id": uuid.uuid4(),
        "supplier_id": s.id if s else None,
        "contract_id": None,
        "competence": competence,
        "issue_date": competence.replace(day=5),
        "due_date": competence.replace(day=15),
        "amount": dec(amount),
        "category": "limpeza",
        "description": "Limpeza das áreas comuns",
        "invoice_number": None,
    }
    base.update(kw)
    return Expense(**base)


def debit(e: Expense | None, amount: str, when: date, **kw: Any) -> BankTransaction:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "posted_at": when,
        "amount": -dec(amount),
        "payee_name": None,
        "payee_document": None,
        "description": "PAGAMENTO",
        "origin": "seed",
        "external_id": str(uuid.uuid4()),
        "expense_id": e.id if e else None,
    }
    base.update(kw)
    return BankTransaction(**base)


def ctx(
    expenses: list[Expense],
    *,
    suppliers: list[Supplier] = (),  # type: ignore[assignment]
    contracts: list[Contract] = (),  # type: ignore[assignment]
    transactions: list[BankTransaction] | None = None,
    board: list[BoardMember] = (),  # type: ignore[assignment]
    approvals: dict[uuid.UUID, list[Approval]] | None = None,
    documents: dict[uuid.UUID, list[tuple[str, Document]]] | None = None,
    c: Condominium | None = None,
    amendments: dict[uuid.UUID, list[ContractAmendment]] | None = None,
) -> RuleContext:
    if transactions is None:  # every expense paid on its due date unless told otherwise
        transactions = [debit(e, str(e.amount), e.due_date or e.issue_date) for e in expenses]
    return RuleContext(
        session=None,
        condominium=c or condo(),
        competence=OCT,
        reference_date=REF,
        expenses=expenses,
        suppliers={s.id: s for s in suppliers},
        contracts={k.id: k for k in contracts},
        transactions=transactions,
        documents=documents or {},
        board=list(board),
        approvals=approvals or {},
        index_table=INDEX,
        amendments=amendments or {},
    )


async def run(code: str, context: RuleContext) -> list[Any]:
    return await run_rules(context, [RULES_BY_CODE[code]])


def contract(s: Supplier, **kw: Any) -> Contract:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "supplier_id": s.id,
        "object": "Limpeza e conservação das áreas comuns",
        "scope_items": ["limpeza de áreas comuns", "recolhimento de lixo"],
        "monthly_value": dec("9200.00"),
        "adjustment_index": "IPCA",
        "adjustment_base_month": 1,
        "start_date": date(2023, 1, 1),
        "end_date": date(2026, 12, 31),
    }
    base.update(kw)
    return Contract(**base)


# --------------------------------------------------------------------------- helpers


def test_index_accumulation_uses_real_series() -> None:
    # IPCA accumulated feb/2025..jan/2026 must exist and be a plausible annual rate.
    acc = accumulated_12m(INDEX, "IPCA", date(2026, 2, 1))
    assert acc is not None and Decimal("2") < acc < Decimal("8")
    assert accumulated_12m(INDEX, "IPCA", date(2019, 5, 1)) is None  # before the fixture
    assert accumulated_12m(INDEX, "FIXO", OCT) == 0


def test_anniversaries() -> None:
    assert anniversaries(date(2024, 3, 1), 3, OCT) == [date(2025, 3, 1), date(2026, 3, 1)]
    assert anniversaries(date(2023, 8, 15), 8, date(2024, 7, 1)) == []
    assert anniversaries(date(2025, 2, 1), None, OCT) == []


# --------------------------------------------------------------------------- R01


async def test_r01_same_competence_similar_value() -> None:
    s = supplier()
    a = expense(s, "6200.00", issue_date=date(2026, 10, 3), invoice_number="4471")
    b = expense(s, "6200.00", issue_date=date(2026, 10, 17), invoice_number="4502")
    found = await run("R01", ctx([a, b], suppliers=[s]))
    assert len(found) == 1 and found[0].subject_key == f"R01:{b.id}"
    assert found[0].amount_at_risk == dec("6200.00") and found[0].severity == Severity.ALTA


async def test_r01_same_invoice_number_across_months() -> None:
    s = supplier()
    a = expense(s, "500.00", competence=SEP, invoice_number="77")
    b = expense(s, "510.00", invoice_number="77")
    assert len(await run("R01", ctx([a, b], suppliers=[s]))) == 1


async def test_r01_negatives() -> None:
    s, other = supplier(), supplier(cnpj="11444777000161")
    monthly = [expense(s, "9200.00", competence=SEP), expense(s, "9200.00")]  # recurring
    different_value = [expense(s, "100.00"), expense(s, "300.00")]
    other_supplier = [expense(s, "800.00"), expense(other, "800.00")]
    for case in (monthly, different_value, other_supplier):
        assert await run("R01", ctx(case, suppliers=[s, other])) == []


# --------------------------------------------------------------------------- R02 / R03


async def test_r02_value_above_adjusted_contract() -> None:
    s = supplier()
    k = contract(s)
    expected = value_at(k.monthly_value, "IPCA", 1, k.start_date, OCT, INDEX)
    assert expected is not None
    ok = expense(s, str(expected), contract_id=k.id)
    assert await run("R02", ctx([ok], suppliers=[s], contracts=[k])) == []
    within_tolerance = expense(
        s, str((expected * Decimal("1.015")).quantize(dec("0.01"))), contract_id=k.id
    )
    assert await run("R02", ctx([within_tolerance], suppliers=[s], contracts=[k])) == []
    high = expense(s, str(expected + dec("1000.00")), contract_id=k.id)
    [f] = await run("R02", ctx([high], suppliers=[s], contracts=[k]))
    assert f.amount_at_risk == dec("1000.00")


async def test_r02_uses_the_amendment_in_force() -> None:
    """D66: a termo aditivo sets a new value from its date; later adjustments apply on it."""
    s = supplier()
    k = contract(s)
    amended = ContractAmendment(
        id=uuid.uuid4(),
        contract_id=k.id,
        effective_date=date(2026, 6, 1),
        monthly_value=dec("12000.00"),  # scope increase: more cleaning staff
        scope_items=[],
        description="1º Termo aditivo",
    )
    paid_new_value = expense(s, "12000.00", contract_id=k.id)
    # Positive without the amendment: 12.000 is far above the adjusted 9.200.
    [f] = await run("R02", ctx([paid_new_value], suppliers=[s], contracts=[k]))
    assert f.rule_code == "R02"
    # Negative with it: the value in force in October is the amended one.
    found = await run(
        "R02",
        ctx([paid_new_value], suppliers=[s], contracts=[k], amendments={k.id: [amended]}),
    )
    assert found == []
    # Positive above the amended value; the inputs cite the value in force.
    high = expense(s, "13500.00", contract_id=k.id)
    [f] = await run("R02", ctx([high], suppliers=[s], contracts=[k], amendments={k.id: [amended]}))
    assert f.amount_at_risk == dec("1500.00")
    assert f.rule_inputs["valor_mensal_original"] == "12000.00"


def test_value_at_skips_adjustments_before_the_amendment() -> None:
    k = contract(supplier())
    base = value_at(dec("12000.00"), "IPCA", 1, k.start_date, OCT, INDEX, since=date(2026, 6, 1))
    assert base == dec("12000.00")  # next anniversary is jan/2027
    later = value_at(
        dec("12000.00"), "IPCA", 1, k.start_date, date(2027, 2, 1), INDEX, since=date(2026, 6, 1)
    )
    assert later is None or later > dec("12000.00")


async def test_r03_adjustment_above_index() -> None:
    s = supplier(cnae_main={"code": "4329-1/03", "description": "Elevadores"})
    k = contract(
        s,
        object="Manutenção de elevadores",
        adjustment_index="IGPM",
        adjustment_base_month=10,
        start_date=date(2021, 10, 1),
        end_date=None,
        monthly_value=dec("1000.00"),
    )
    allowed = accumulated_12m(INDEX, "IGPM", OCT)
    assert allowed is not None
    prev = expense(s, "1300.00", competence=SEP, contract_id=k.id, category="elevadores")
    fair = (dec("1300.00") * (1 + allowed / 100)).quantize(dec("0.01"))
    ok = expense(s, str(fair), contract_id=k.id, category="elevadores")
    assert await run("R03", ctx([prev, ok], suppliers=[s], contracts=[k])) == []
    bad = expense(s, "1417.00", contract_id=k.id, category="elevadores")  # +9%
    found = await run("R03", ctx([prev, bad], suppliers=[s], contracts=[k]))
    assert len(found) == 1 and found[0].amount_at_risk == dec("1417.00") - fair
    # R02 does not judge the adjustment month (no double counting).
    assert await run("R02", ctx([prev, bad], suppliers=[s], contracts=[k])) == []


# --------------------------------------------------------------------------- R04 (AI)


async def test_r04_in_scope_by_words_does_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("model should not be called")

    monkeypatch.setattr(r04_scope, "judge_scope", boom)
    s = supplier()
    k = contract(s)
    e = expense(s, "9200.00", contract_id=k.id, description="Limpeza de áreas comuns - outubro")
    assert await run("R04", ctx([e], suppliers=[s], contracts=[k])) == []


async def test_r04_model_says_out_of_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(*a: Any, **k: Any) -> ScopeJudgement:
        return ScopeJudgement(
            dentro_do_escopo=False,
            confidence=0.93,
            justificativa="Pintura não está entre os itens de limpeza.",
        )

    monkeypatch.setattr(r04_scope, "judge_scope", fake)
    s = supplier()
    k = contract(s)
    e = expense(s, "4500.00", contract_id=k.id, description="Pintura da fachada do bloco A")
    [f] = await run("R04", ctx([e], suppliers=[s], contracts=[k]))
    assert f.ai_assisted and "assistida por IA" in f.explanation


async def test_r04_low_confidence_and_no_model() -> None:
    s = supplier()
    k = contract(s)
    e = expense(s, "4500.00", contract_id=k.id, description="Pintura da fachada do bloco A")
    c = ctx([e], suppliers=[s], contracts=[k])
    assert await run("R04", c) == []  # replay mode, no recorded answer: not evaluated
    assert any(key.startswith("R04:") for key in c.not_evaluated)


# --------------------------------------------------------------------------- R05 / R06


async def test_r05_payment_after_end() -> None:
    s = supplier()
    k = contract(s, end_date=date(2026, 8, 31))
    e = expense(s, "9200.00", contract_id=k.id)
    [f] = await run("R05", ctx([e], suppliers=[s], contracts=[k]))
    assert f.rule_inputs["fim_vigencia"] == "2026-08-31"
    k2 = contract(s, end_date=date(2026, 12, 31))
    e2 = expense(s, "9200.00", contract_id=k2.id)
    assert await run("R05", ctx([e2], suppliers=[s], contracts=[k2])) == []


async def test_r06_irregular_supplier_on_expense_date() -> None:
    closed = supplier(registration_status="BAIXADA", registration_status_date=date(2026, 5, 10))
    [f] = await run("R06", ctx([expense(closed, "3000.00")], suppliers=[closed]))
    assert f.severity == Severity.ALTA and "baixada" in f.title
    later = supplier(registration_status="INAPTA", registration_status_date=date(2026, 12, 1))
    active = supplier()
    assert (
        await run(
            "R06", ctx([expense(later, "1.00"), expense(active, "1.00")], suppliers=[later, active])
        )
        == []
    )


# --------------------------------------------------------------------------- R07


async def test_r07_cnae_table() -> None:
    shop = supplier(
        cnae_main={"code": "4781-4/00", "description": "Comércio varejista de vestuário"}
    )
    [f] = await run("R07", ctx([expense(shop, "2400.00", category="manutencao")], suppliers=[shop]))
    assert not f.ai_assisted and f.rule_inputs["avaliacao"] == "tabela_cnae"
    electrician = supplier(cnae_main={"code": "4321-5/00", "description": "Instalação elétrica"})
    assert (
        await run(
            "R07",
            ctx([expense(electrician, "2400.00", category="manutencao")], suppliers=[electrician]),
        )
        == []
    )


async def test_r07_unmapped_category_asks_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(*a: Any, **k: Any) -> CnaeJudgement:
        return CnaeJudgement(compativel=False, confidence=0.9, justificativa="Sem relação.")

    monkeypatch.setattr(r07_cnae, "judge_cnae", fake)
    s = supplier()
    [f] = await run("R07", ctx([expense(s, "700.00", category="outros")], suppliers=[s]))
    assert f.ai_assisted


# --------------------------------------------------------------------------- R08


async def test_r08_full_name_match_only() -> None:
    member = BoardMember(
        id=uuid.uuid4(),
        full_name="Inês Carvalho Rocha",
        position="conselheiro",
        term_start=date(2025, 4, 1),
        term_end=date(2027, 3, 31),
    )
    linked = supplier(partners=[{"name": "INES CARVALHO ROCHA", "qualification": "Sócia"}])
    old = expense(linked, "1500.00", competence=SEP)
    [f] = await run(
        "R08", ctx([old, expense(linked, "1500.00")], suppliers=[linked], board=[member])
    )
    assert f.amount_at_risk == dec("3000.00") and f.severity == Severity.ALTA
    partial = supplier(partners=[{"name": "Ines Carvalho", "qualification": "Sócia"}])
    assert (
        await run("R08", ctx([expense(partial, "10.00")], suppliers=[partial], board=[member]))
        == []
    )
    ended = BoardMember(
        id=uuid.uuid4(),
        full_name="Inês Carvalho Rocha",
        position="conselheiro",
        term_start=date(2023, 4, 1),
        term_end=date(2025, 3, 31),
    )
    assert (
        await run("R08", ctx([expense(linked, "10.00")], suppliers=[linked], board=[ended])) == []
    )


# --------------------------------------------------------------------------- R09 / R10


async def test_r09_debit_without_document() -> None:
    orphan = debit(None, "2300.00", date(2026, 10, 14), description="PIX ENVIADO JOAO")
    fee = debit(None, "45.90", date(2026, 10, 14), description="TARIFA CESTA DE SERVICOS")
    recent = debit(None, "800.00", date(2026, 10, 30))  # grace period not over on 05/11
    s = supplier()
    documented = expense(s, "900.00", invoice_number="12")
    found = await run(
        "R09",
        ctx(
            [documented],
            suppliers=[s],
            transactions=[orphan, fee, recent, debit(documented, "900.00", date(2026, 10, 15))],
        ),
    )
    assert [f.subject_key for f in found] == [f"R09:{orphan.id}"]


async def test_r09_utility_bill_is_the_fiscal_document() -> None:
    s = supplier()
    billed = expense(s, "8143.27", category="energia")
    unbilled = expense(s, "7000.00", category="energia")  # utility debit with no bill at all
    service = expense(s, "650.00", category="dedetizacao")  # a boleto alone is not a note
    bill = Document(id=uuid.uuid4(), doc_type="boleto")
    charge = Document(id=uuid.uuid4(), doc_type="boleto")
    found = await run(
        "R09",
        ctx(
            [billed, unbilled, service],
            suppliers=[s],
            transactions=[
                debit(billed, "8143.27", date(2026, 10, 15)),
                t_unbilled := debit(unbilled, "7000.00", date(2026, 10, 15)),
                t_service := debit(service, "650.00", date(2026, 10, 15)),
            ],
            documents={billed.id: [("cobranca", bill)], service.id: [("cobranca", charge)]},
        ),
    )
    assert sorted(f.subject_key for f in found) == sorted(
        [f"R09:{t_unbilled.id}", f"R09:{t_service.id}"]
    )


async def test_r10_unpaid_after_grace() -> None:
    s = supplier()
    unpaid = expense(s, "1200.00", due_date=date(2026, 10, 20))
    recent = expense(s, "300.00", due_date=date(2026, 10, 30))
    found = await run("R10", ctx([unpaid, recent], suppliers=[s], transactions=[]))
    assert [f.subject_key for f in found] == [f"R10:{unpaid.id}"]


# --------------------------------------------------------------------------- R11 / R12


def _history(s: Supplier, values: list[str], category: str = "agua") -> list[Expense]:
    months = [date(2025, m, 1) for m in range(11, 13)] + [date(2026, m, 1) for m in range(1, 10)]
    return [
        expense(s, v, competence=m, category=category) for v, m in zip(values, months, strict=False)
    ]


async def test_r11_anomaly() -> None:
    s = supplier()
    hist = _history(
        s, ["11000", "11500", "12000", "11200", "10900", "11800", "11300", "11100", "11600"]
    )
    [f] = await run("R11", ctx([*hist, expense(s, "33000.00", category="agua")], suppliers=[s]))
    assert f.amount_at_risk > 0 and f.rule_inputs["meses_historico"] == 9
    assert (
        await run("R11", ctx([*hist, expense(s, "11700.00", category="agua")], suppliers=[s])) == []
    )
    short = _history(s, ["11000", "11500", "12000"])
    assert (
        await run("R11", ctx([*short, expense(s, "33000.00", category="agua")], suppliers=[s]))
        == []
    )


async def test_r12_approval_limit() -> None:
    s = supplier()
    c = condo(approval_limits={"default": "8000.00", "by_category": {"obras": "5000.00"}})
    big = expense(s, "6000.00", category="obras")
    approved = expense(s, "7000.00", category="obras")
    utility = expense(s, "12000.00", category="agua")
    k = contract(s)
    contracted = expense(s, "9200.00", contract_id=k.id)
    approvals = {
        approved.id: [
            Approval(
                id=uuid.uuid4(), expense_id=approved.id, approved_by="Assembleia", approved_at=OCT
            )
        ]
    }
    found = await run(
        "R12",
        ctx(
            [big, approved, utility, contracted],
            suppliers=[s],
            contracts=[k],
            approvals=approvals,
            c=c,
        ),
    )
    assert [f.subject_key for f in found] == [f"R12:{big.id}"]


# --------------------------------------------------------------------------- language


async def test_findings_never_use_forbidden_words() -> None:
    s = supplier(registration_status="BAIXADA", registration_status_date=date(2026, 1, 1))
    found = await run_rules(ctx([expense(s, "9000.00", category="obras")], suppliers=[s]))
    assert found
    for f in found:
        text = (f.title + f.explanation).lower()
        assert "fraude" not in text and "desvio" not in text
