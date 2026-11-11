"""CondoOS Audit, cycle 2 (D123): units and titles without resident names, consumption
rateio, delinquency, transfers, intermediaries, withheld taxes, periodic taxes, tax
installments, N:N payment allocation and persistent issues. Positive and negative case for
every control; synthetic data only (fictitious condominium, bank 999 and suppliers)."""

import random
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.audit.imports import import_readings, import_titles, import_units, set_profile
from app.audit.run import run_audit
from app.core.br import generate_cnpj
from app.db.models import (
    AuditControlResult,
    AuditIssue,
    BankTransaction,
    Condominium,
    Document,
    Expense,
    ExpenseDocument,
    PaymentAllocation,
    Supplier,
)
from app.db.session import sessionmaker_for
from app.ingestion.bank.cnab.common import parse_cnab
from app.storage.base import get_storage
from tests.bankfiles import Liquidation, cnab400
from tests.test_audit import _document, _import, _new_condo, ofx

TODAY = date(2025, 7, 20)
JUNE, MAY = date(2025, 6, 1), date(2025, 5, 1)


async def _run(
    s: AsyncSession, condo: Condominium, month: date = JUNE
) -> dict[str, AuditControlResult]:
    """Current results of that month only (other audited months have their own)."""
    run = await run_audit(s, condo, month, today=TODAY, user_id=None)
    rows = await s.scalars(
        select(AuditControlResult).where(
            AuditControlResult.period_id == run.period_id,
            AuditControlResult.superseded_by_id.is_(None),
        )
    )
    return {r.control_id: r for r in rows}


def _csv(rows: list[str]) -> bytes:
    return ("\n".join(rows) + "\n").encode()


async def _supplier(s: AsyncSession, name: str) -> Supplier:
    sup = Supplier(
        cnpj=generate_cnpj(random.Random(uuid.uuid4().hex)),
        legal_name=name,
        cnae_secondary=[],
        partners=[],
        enrichment_source="seed",
    )
    s.add(sup)
    await s.flush()
    return sup


def _expense(
    condo: Condominium,
    amount: str,
    category: str,
    *,
    competence: date = JUNE,
    supplier: Supplier | None = None,
    description: str = "Despesa",
    due: date | None = None,
) -> Expense:
    return Expense(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        supplier_id=supplier.id if supplier else None,
        competence=competence,
        issue_date=competence.replace(day=2),
        due_date=due or competence.replace(day=10),
        amount=Decimal(amount),
        category=category,
        description=description,
        origin="documento",
    )


# --------------------------------------------------------------------------- imports and privacy


async def test_titles_import_drops_names_and_keeps_only_a_clean_copy(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        data = _csv(
            [
                "Unidade;Nome do condômino;CPF;Competência;Tipo;Valor;Vencimento;Situação;Data pagamento",
                "101;Fulano Fictício;52998224725;06/2025;Ordinária;500,00;10/06/2025;Pago;10/06/2025",
                "102;Beltrana Fictícia;11144477735;06/2025;Ordinária;600,00;10/06/2025;Aberto;",
            ]
        )
        result = await import_titles(s, condo, data, None)
        assert result.created == 2 and result.units_created == 2
        assert {"Nome do condômino", "CPF"} <= set(result.dropped_columns)
        doc = await s.get(Document, result.document_id)
        assert doc is not None and doc.doc_type == "titulos"
        stored = get_storage().get(doc.storage_key).decode()
        assert "Fulano" not in stored and "52998224725" not in stored and "101" in stored
        again = await import_titles(s, condo, data.replace(b";Aberto;", b";Pago;10/06/2025"), None)
        assert again.updated == 2 and again.created == 0  # same list: updated, never duplicated
        await s.rollback()


def test_collection_return_never_keeps_the_payer() -> None:
    st = parse_cnab(
        cnab400(
            "341",
            generate_cnpj(random.Random("c2")),
            [Liquidation("777", "UNID201", Decimal("712.40"), date(2026, 10, 11))],
        )
    )
    assert st.transactions[0].payee_name is None and st.transactions[0].payee_document is None


# --------------------------------------------------------------------------- REC


async def _titles_scenario(
    s: AsyncSession, *, duplicate: bool = False, credit: str = "1100.00"
) -> Condominium:
    condo = await _new_condo(s)
    await import_units(s, condo, _csv(["unidade;fracao", "101;0,33", "102;0,33", "103;0,34"]), None)
    rows = [
        "unidade;competencia;tipo;valor;vencimento;situacao;data pagamento",
        "101;06/2025;ordinaria;500,00;10/06/2025;pago;10/06/2025",
        "102;06/2025;ordinaria;600,00;10/06/2025;pago;10/06/2025",
        "103;06/2025;ordinaria;650,00;10/06/2025;aberto;",
    ]
    if duplicate:
        rows.append("101;06/2025;ordinaria;500,00;15/06/2025;aberto;")
    await import_titles(s, condo, _csv(rows), None)
    await _import(
        s,
        condo,
        ofx(
            [("20250611", credit, "LIQUIDACAO COBRANCA")],
            start="20250601",
            end="20250630",
            closing=credit,
        ),
        "junho.ofx",
    )
    return condo


async def test_rec02_titles_confirmed_by_the_day_credit(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        r = await _run(s, await _titles_scenario(s))
        assert r["REC-02"].status == "VALIDADO"  # 500 + 600 paid on 10/06 = credit of 11/06
        assert any("Confirmados" in c["label"] for c in r["REC-02"].calculation)
        await s.rollback()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        r = await _run(s, await _titles_scenario(s, credit="1099.99"))
        assert r["REC-02"].status == "PENDENTE"  # the day does not close: no confirmation
        await s.rollback()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        r = await _run(s, await _titles_scenario(s, duplicate=True))
        assert r["REC-02"].status == "DIVERGENTE" and r["REC-02"].differences == Decimal("500.00")
        await s.rollback()


async def test_rec02_and_rec04_pending_without_titles(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        r = await _run(s, await _new_condo(s))
        assert r["REC-02"].status == "PENDENTE" and r["REC-04"].status == "PENDENTE"
        await s.rollback()


async def test_rec04_reconstructs_by_unit_and_checks_the_previous_month(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _titles_scenario(s)
        await import_titles(
            s,
            condo,
            _csv(
                [
                    "unidade;competencia;tipo;valor;vencimento;situacao;data pagamento",
                    "103;05/2025;ordinaria;650,00;10/05/2025;aberto;",
                ]
            ),
            None,
        )
        may = await _run(s, condo, MAY)
        assert may["REC-04"].status == "COM_RESSALVA"  # first month: nothing to compare with
        june = await _run(s, condo)
        assert june["REC-04"].status == "VALIDADO"
        rows = next(c["rows"] for c in june["REC-04"].calculation if c.get("rows"))
        unit = next(x for x in rows if x["unidade"] == "103")
        assert unit["saldo_inicial"] == "650.00" and unit["saldo_final"] == "1300.00"
        assert all(set(x) >= {"unidade", "saldo_final"} and "nome" not in x for x in rows)
        # The May title is changed after May was audited: the opening no longer matches.
        await import_titles(
            s,
            condo,
            _csv(
                [
                    "unidade;competencia;tipo;valor;vencimento;situacao;data pagamento",
                    "103;05/2025;ordinaria;650,00;10/05/2025;pago;20/05/2025",
                ]
            ),
            None,
        )
        june = await _run(s, condo)
        assert june["REC-04"].status == "DIVERGENTE"
        await s.rollback()


async def test_rec03_rateio_with_and_without_readings(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        s.add(_expense(condo, "300.00", "agua", competence=MAY, description="Conta de água"))
        await import_titles(
            s,
            condo,
            _csv(
                [
                    "unidade;competencia;tipo;valor;vencimento;competencia consumo",
                    "101;06/2025;agua;100,00;10/06/2025;05/2025",
                    "102;06/2025;agua;120,00;10/06/2025;05/2025",
                    "103;06/2025;agua;80,00;10/06/2025;05/2025",
                ]
            ),
            None,
        )
        r = await _run(s, condo)
        assert r["REC-03"].status == "COM_RESSALVA"  # the sum matches; readings missing
        await import_readings(
            s,
            condo,
            _csv(
                [
                    "unidade;competencia;servico;consumo",
                    "101;05/2025;agua;10",
                    "102;05/2025;agua;12",
                    "103;05/2025;agua;8",
                ]
            ),
            None,
        )
        r = await _run(s, condo)
        assert r["REC-03"].status == "VALIDADO"
        await import_readings(
            s,
            condo,
            _csv(
                [
                    "unidade;competencia;servico;consumo",
                    "101;05/2025;agua;12",
                    "102;05/2025;agua;10",
                    "103;05/2025;agua;8",
                ]
            ),
            None,
        )
        r = await _run(s, condo)
        assert r["REC-03"].status == "DIVERGENTE" and r["REC-03"].differences > 0
        await s.rollback()


async def test_rec03_not_applicable_only_by_declared_profile(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        assert (await _run(s, condo))["REC-03"].status == "PENDENTE"
        await set_profile(s, condo, {"rateio_agua": False, "rateio_gas": False, "rateio_energia": False}, None, "Teste sem rateio")  # type: ignore[arg-type]
        assert (await _run(s, condo))["REC-03"].status == "NAO_APLICAVEL"
        await s.rollback()


# --------------------------------------------------------------------------- BAN


async def test_ban06_transfer_between_two_accounts(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _import(
            s,
            condo,
            ofx(
                [("20250605", "-1000.00", "TRANSF ENTRE CONTAS")],
                start="20250601",
                end="20250630",
                closing="-1000.00",
                account="111-1",
            ),
            "a.ofx",
        )
        r = await _run(s, condo)
        assert r["BAN-06"].status == "COM_RESSALVA"  # destination account not presented
        await _import(
            s,
            condo,
            ofx(
                [("20250605", "1000.00", "TRANSF ENTRE CONTAS")],
                start="20250601",
                end="20250630",
                closing="1000.00",
                account="222-2",
            ),
            "b.ofx",
        )
        r = await _run(s, condo)
        assert r["BAN-06"].status == "VALIDADO"
        await s.rollback()


async def test_ban07_intermediary_needs_final_receipt(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Elevadores Fictícios Ltda")
        exp = _expense(condo, "800.00", "elevadores", supplier=sup)
        s.add(exp)
        note = await _document(s, condo, "nf.pdf", "nfse", {"numero": "9"})
        s.add(
            ExpenseDocument(
                condominium_id=condo.id, expense_id=exp.id, document_id=note.id, role="fiscal"
            )
        )
        await _import(
            s,
            condo,
            ofx(
                [("20250610", "-800.00", "PIX REPASSE ADMINISTRADORA")],
                start="20250601",
                end="20250630",
                closing="-800.00",
            ),
            "j.ofx",
        )
        trn = await s.scalar(
            select(BankTransaction).where(
                BankTransaction.condominium_id == condo.id, BankTransaction.amount < 0
            )
        )
        assert trn is not None
        trn.expense_id = exp.id
        await s.flush()
        r = await _run(s, condo)
        assert r["BAN-07"].status == "PENDENTE" and r["DES-01"].status == "COM_RESSALVA"
        receipt = await _document(
            s,
            condo,
            "comprovante.pdf",
            "comprovante",
            {"documento_beneficiario": sup.cnpj, "valor": "800.00"},
        )
        s.add(
            ExpenseDocument(
                condominium_id=condo.id, expense_id=exp.id, document_id=receipt.id, role="pagamento"
            )
        )
        await s.flush()
        assert (await _run(s, condo))["BAN-07"].status == "VALIDADO"
        await s.rollback()


# --------------------------------------------------------------------------- DES and N:N


async def _taxes(s: AsyncSession, slip: str | None, *, paid: bool = True) -> Condominium:
    condo = await _new_condo(s)
    sup = await _supplier(s, "Vigilância Fictícia Ltda")
    exp = _expense(condo, "1000.00", "seguranca", supplier=sup)
    s.add(exp)
    note = await _document(
        s,
        condo,
        "nf-1.pdf",
        "nfse",
        {
            "numero": "1",
            "retencao_ir": "15.00",
            "retencao_pis": "6.50",
            "retencao_cofins": "30.00",
            "retencao_csll": "10.00",
        },
    )
    s.add(
        ExpenseDocument(
            condominium_id=condo.id, expense_id=exp.id, document_id=note.id, role="fiscal"
        )
    )
    lines = []
    if slip is not None:
        tax = _expense(
            condo,
            slip,
            "tributos",
            description="Guia de tributo: DARF IRRF PIS COFINS CSLL (06/2025)",
            due=date(2025, 7, 20),
        )
        s.add(tax)
        guide = await _document(s, condo, "darf.pdf", "guia_tributo", {"tributo": "DARF retenções"})
        s.add(
            ExpenseDocument(
                condominium_id=condo.id, expense_id=tax.id, document_id=guide.id, role="fiscal"
            )
        )
        if paid:
            lines.append(("20250618", f"-{slip}", "PAGAMENTO DARF RECEITA FEDERAL"))
    await _import(
        s,
        condo,
        ofx(
            lines or [("20250601", "0.01", "RENDIMENTO")],
            start="20250601",
            end="20250630",
            closing="0.00",
        ),
        "t.ofx",
    )
    await s.flush()
    return condo


async def test_des02_federal_slip_equals_withholdings(admin_engine: AsyncEngine) -> None:
    for slip, expected in (("61.50", "VALIDADO"), ("61.51", "DIVERGENTE"), (None, "PENDENTE")):
        async with sessionmaker_for(admin_engine)() as s, s.begin():
            r = await _run(s, await _taxes(s, slip))
            assert r["DES-02"].status == expected, slip
            await s.rollback()


async def test_des02_not_applicable_without_withholdings(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        assert (await _run(s, await _new_condo(s)))["DES-02"].status == "NAO_APLICAVEL"
        await s.rollback()


async def test_des03_follows_the_profile(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        assert (await _run(s, condo))["DES-03"].status == "PENDENTE"  # profile unknown
        await set_profile(s, condo, {"funcionarios_proprios": False}, None, "Sem funcionários")  # type: ignore[arg-type]
        assert (await _run(s, condo))["DES-03"].status == "NAO_APLICAVEL"
        await set_profile(s, condo, {"funcionarios_proprios": True}, None, "Com funcionários")  # type: ignore[arg-type]
        assert (await _run(s, condo))["DES-03"].status == "PENDENTE"  # FGTS and INSS slips missing
        await s.rollback()


async def test_des04_installment_numbering_needs_the_agreement(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await set_profile(s, condo, {"parcelamento_fiscal": False}, None, "Sem parcelamento")  # type: ignore[arg-type]
        assert (await _run(s, condo))["DES-04"].status == "NAO_APLICAVEL"
        s.add(
            _expense(
                condo,
                "200.00",
                "tributos",
                competence=MAY,
                description="Parcelamento INSS parcela 02/02",
                due=date(2025, 5, 20),
            )
        )
        s.add(
            _expense(
                condo,
                "200.00",
                "tributos",
                description="Parcelamento INSS parcela 03/04",
                due=date(2025, 7, 30),
            )
        )
        await s.flush()
        assert (await _run(s, condo))["DES-04"].status == "COM_RESSALVA"
        await s.rollback()


async def test_grouped_payment_is_allocated_only_when_unique(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Manutenção Fictícia Ltda")
        a, b = _expense(condo, "300.00", "manutencao", supplier=sup), _expense(
            condo, "200.00", "manutencao", supplier=sup
        )
        s.add_all([a, b])
        for e in (a, b):
            note = await _document(s, condo, f"nf-{e.id}.pdf", "nfse", {"numero": str(e.amount)})
            s.add(
                ExpenseDocument(
                    condominium_id=condo.id, expense_id=e.id, document_id=note.id, role="fiscal"
                )
            )
        await _import(
            s,
            condo,
            ofx(
                [("20250612", "-500.00", "TED MANUTENCAO")],
                start="20250601",
                end="20250630",
                closing="-500.00",
            ),
            "g.ofx",
        )
        trn = await s.scalar(
            select(BankTransaction).where(BankTransaction.condominium_id == condo.id)
        )
        assert trn is not None
        trn.payee_document = sup.cnpj
        await s.flush()
        r = await _run(s, condo)
        allocs = list(
            await s.scalars(
                select(PaymentAllocation).where(PaymentAllocation.bank_transaction_id == trn.id)
            )
        )
        assert sorted(x.amount for x in allocs) == [Decimal("200.00"), Decimal("300.00")]
        assert {x.kind for x in allocs} == {"verificado"}
        assert r["DES-01"].status == "VALIDADO" and r["BAN-03"].status == "VALIDADO"
        await s.rollback()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Manutenção Ambígua Ltda")
        s.add_all(
            [_expense(condo, v, "manutencao", supplier=sup) for v in ("300.00", "200.00", "200.00")]
        )
        await _import(
            s,
            condo,
            ofx(
                [("20250612", "-500.00", "TED MANUTENCAO")],
                start="20250601",
                end="20250630",
                closing="-500.00",
            ),
            "g.ofx",
        )
        trn = await s.scalar(
            select(BankTransaction).where(BankTransaction.condominium_id == condo.id)
        )
        assert trn is not None
        trn.payee_document = sup.cnpj
        await s.flush()
        r = await _run(s, condo)
        allocs = list(
            await s.scalars(
                select(PaymentAllocation).where(PaymentAllocation.bank_transaction_id == trn.id)
            )
        )
        assert allocs and {x.kind for x in allocs} == {
            "sugerido"
        }  # two combinations: nobody chooses
        assert r["BAN-03"].status == "PENDENTE"
        await s.rollback()


# --------------------------------------------------------------------------- issues


async def test_issues_persist_resolve_and_reopen_with_the_same_id(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _run(s, condo)
        issue = await s.scalar(
            select(AuditIssue).where(
                AuditIssue.condominium_id == condo.id, AuditIssue.control_id == "DES-03"
            )
        )
        assert issue is not None and issue.status == "aberta"
        await set_profile(s, condo, {"funcionarios_proprios": False}, None, "Sem funcionários")  # type: ignore[arg-type]
        await _run(s, condo)
        await s.refresh(issue)
        assert issue.status == "resolvida"
        await set_profile(s, condo, {"funcionarios_proprios": None}, None, "Sem informação")  # type: ignore[arg-type]
        await _run(s, condo)
        again = await s.scalar(
            select(AuditIssue).where(
                AuditIssue.condominium_id == condo.id,
                AuditIssue.control_id == "DES-03",
                AuditIssue.subject_key == issue.subject_key,
            )
        )
        assert again is not None and again.id == issue.id and again.status == "aberta"
        await s.rollback()


def _unused(*_: Any) -> None:  # keeps imports used by type checkers in every branch
    return None


async def test_unit_data_is_internal_and_imports_drop_names(
    client: Any, mailer: Any, admin_engine: AsyncEngine
) -> None:
    from tests.helpers import GERENTE, SINDICA_MIRANTE, condo_id, login

    mirante = await condo_id(admin_engine, "mirante-do-vale")
    await login(client, mailer, SINDICA_MIRANTE)
    assert (await client.get(f"/condominiums/{mirante}/audit/units")).status_code == 403
    client.cookies.clear()
    await login(client, mailer, GERENTE)
    csv_data = "unidade;nome;competencia;valor;vencimento\nC2-901;Fulano Fictício;06/2025;300,00;10/06/2025\n"
    r = await client.post(
        f"/condominiums/{mirante}/audit/imports/titulos",
        files={"file": ("t.csv", csv_data.encode(), "text/csv")},
    )
    assert r.status_code == 200 and "nome" in r.json()["colunas_descartadas"]
    units = (await client.get(f"/condominiums/{mirante}/audit/units?competencia=2025-06")).json()
    unit = next(u for u in units["units"] if u["code"] == "C2-901")
    assert unit["titles"][0]["amount"] == "300.00" and "Fulano" not in str(units)
    bad = await client.put(
        f"/condominiums/{mirante}/audit/profile",
        json={"values": {"funcionarios_proprios": True}, "reason": "curto"},
    )
    assert bad.status_code == 422
    ok = await client.put(
        f"/condominiums/{mirante}/audit/profile",
        json={
            "values": {"funcionarios_proprios": True},
            "reason": "Condomínio tem porteiros próprios.",
        },
    )
    assert ok.status_code == 200 and ok.json()["profile"]["funcionarios_proprios"] is True
    assert (
        await client.post(f"/condominiums/{mirante}/audit/runs", json={"competencia": "2025-06"})
    ).status_code == 200
    issues = (await client.get(f"/condominiums/{mirante}/audit/issues?status=aberta")).json()
    assert any(i["control_id"] == "DES-03" for i in issues)
