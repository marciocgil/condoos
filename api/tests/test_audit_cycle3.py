"""CondoOS Audit, cycle 3 (D124): contracts (price, extraordinary services, installments),
funds and their backing, investments, budget, insurance and technical obligations, formal
approval of the accounts, historical revalidation and the farol approved by the síndico.
Positive and negative case for every control; synthetic data only."""

import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.audit import governance as gov
from app.audit import publication as pubs
from app.audit.run import run_audit
from app.auth.mailer import MemoryMailer
from app.auth.rbac import REVIEW_PERMISSIONS, ROLE_PERMISSIONS, Permission
from app.db.enums import (
    AccountKind,
    AccountsApprovalBody,
    ControlReviewState,
    PublicationStatus,
    Role,
)
from app.db.models import (
    Approval,
    AppUser,
    AuditControlResult,
    BankAccount,
    BoardMember,
    ComplianceEvidence,
    ComplianceObligation,
    Condominium,
    Contract,
    Expense,
    Fund,
    Supplier,
)
from app.db.session import sessionmaker_for
from tests.helpers import (
    CONSELHEIRO_ACACIAS,
    GERENTE,
    REVISORA,
    SINDICA_MIRANTE,
    condo_id,
    login,
)
from tests.test_audit import _document, _import, _new_condo, ofx
from tests.test_audit_cycle2 import JUNE, TODAY, _csv, _expense, _run, _supplier

R = dict[str, AuditControlResult]


def _contract(condo: Condominium, supplier: Supplier, **kw: object) -> Contract:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "condominium_id": condo.id,
        "supplier_id": supplier.id,
        "nature": "continuo",
        "object": "Limpeza e conservação",
        "scope_items": ["limpeza das áreas comuns"],
        "monthly_value": Decimal("1000.00"),
        "adjustment_index": "FIXO",
        "billing_frequency_months": 1,
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 12, 31),
    }
    values.update(kw)
    return Contract(**values)


def _linked(condo: Condominium, contract: Contract, amount: str, description: str) -> Expense:
    e = _expense(condo, amount, "limpeza", description=description)
    e.supplier_id, e.contract_id = contract.supplier_id, contract.id
    return e


# --------------------------------------------------------------------------- CON-01


async def test_con01_price_matches_contract_and_divergence_above(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["CON-01"].status == "NAO_APLICAVEL"  # no contract in force
        sup = await _supplier(s, "Limpeza Fictícia Ltda")
        c = _contract(condo, sup)
        s.add(c)
        await s.flush()
        e = _linked(condo, c, "1000.00", "Limpeza junho")
        s.add(e)
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-01"].status == "VALIDADO", r["CON-01"].rationale
        e.amount = Decimal("1100.00")
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-01"].status == "DIVERGENTE"
        assert r["CON-01"].differences == Decimal("100.00") and r["CON-01"].review_required
        await s.rollback()


async def test_con01_missing_billing_and_expired_contract_are_reservations(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Portaria Fictícia Ltda")
        s.add(_contract(condo, sup))  # in force, billed monthly, no note in June
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-01"].status == "COM_RESSALVA" and r["CON-01"].missing
        old = _contract(condo, sup, end_date=date(2025, 3, 31), object="Contrato antigo")
        s.add(old)
        await s.flush()
        s.add(_linked(condo, old, "1000.00", "Nota no contrato vencido"))
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-01"].status == "COM_RESSALVA"
        assert any("fora da vigência" in str(x) for x in r["CON-01"].evidence_refs)
        await s.rollback()


# --------------------------------------------------------------------------- CON-02


async def test_con02_extraordinary_service_needs_prior_authorisation_and_acceptance(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)  # default limit R$ 5.000,00
        r = await _run(s, condo)
        assert r["CON-02"].status == "PENDENTE"  # no expense at all
        small = _expense(condo, "800.00", "manutencao", description="Troca de lâmpadas")
        s.add(small)
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-02"].status == "VALIDADO"  # within the síndico's limit
        big = _expense(condo, "8000.00", "obras", description="Reforma do hall")
        s.add(big)
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-02"].status == "PENDENTE"  # authorisation not presented
        ata = await _document(s, condo, "ata-obra.pdf", "ata", {})
        s.add(
            Approval(
                condominium_id=condo.id,
                expense_id=big.id,
                approved_by="Assembleia",
                approved_at=date(2025, 6, 1),
                source_document_id=ata.id,
                kind="autorizacao",
            )
        )
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-02"].status == "PENDENTE"  # acceptance still missing
        s.add(
            Approval(
                condominium_id=condo.id,
                expense_id=big.id,
                approved_by="Síndica",
                approved_at=date(2025, 6, 20),
                kind="aceite",
            )
        )
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-02"].status == "VALIDADO", r["CON-02"].rationale
        await s.rollback()


async def test_con02_late_authorisation_is_a_reservation_and_acceptance_never_answers_r12(
    admin_engine: AsyncEngine,
) -> None:
    from app.rules.engine import build_context
    from app.rules.r12_approval import ApprovalLimit

    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        big = _expense(condo, "8000.00", "obras", description="Reforma do hall")
        s.add(big)
        await s.flush()
        ata = await _document(s, condo, "ata-tardia.pdf", "ata", {})
        for kind, day in (("aceite", 20), ("autorizacao", 25)):
            s.add(
                Approval(
                    condominium_id=condo.id,
                    expense_id=big.id,
                    approved_by="Conselho",
                    approved_at=date(2025, 6, day),
                    source_document_id=ata.id,
                    kind=kind,
                )
            )
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-02"].status == "COM_RESSALVA"  # ratified after the note
        await s.execute(
            delete(Approval).where(Approval.expense_id == big.id, Approval.kind == "autorizacao")
        )
        ctx = await build_context(s, condo.id, JUNE, TODAY)
        drafts = await ApprovalLimit().evaluate(ctx)
        assert [d.subject_key for d in drafts] == [f"R12:{big.id}"]  # an acceptance is not R12
        await s.rollback()


# --------------------------------------------------------------------------- CON-03


async def test_con03_installments_in_sequence_and_repeated_installment(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["CON-03"].status == "NAO_APLICAVEL"
        sup = await _supplier(s, "Pinturas Fictícias Ltda")
        c = _contract(
            condo,
            sup,
            nature="pontual",
            object="Pintura da fachada",
            monthly_value=None,
            total_value=Decimal("3000.00"),
            installments=3,
            billing_frequency_months=0,
        )
        s.add(c)
        await s.flush()
        first = _linked(condo, c, "1000.00", "Pintura parcela 1/3")
        first.competence = date(2025, 5, 1)
        s.add_all([first, _linked(condo, c, "1000.00", "Pintura parcela 2/3")])
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-03"].status == "VALIDADO", r["CON-03"].rationale
        row = r["CON-03"].calculation[-1]["rows"][0]
        assert row["saldo_futuro"] == "1000.00"
        s.add(_linked(condo, c, "1000.00", "Pintura parcela 2/3 de novo"))
        await s.flush()
        r = await _run(s, condo)
        assert r["CON-03"].status == "DIVERGENTE"  # installment 2 billed twice
        await s.rollback()


# --------------------------------------------------------------------------- BAN-08 / BAN-09


async def _accounts(s: AsyncSession, condo: Condominium, *, invest_closing: str) -> BankAccount:
    """Checking account (May and June) and an investment account (May closes 2.000,00)."""
    await _import(
        s,
        condo,
        ofx(
            [("20250510", "-10.00", "TARIFA CESTA DE SERVICOS")],
            start="20250501",
            end="20250531",
            closing="10000.00",
        ),
        "cc-maio.ofx",
    )
    await _import(
        s,
        condo,
        ofx(
            [("20250610", "-1000.00", "APLICACAO AUTOMATICA")],
            start="20250601",
            end="20250630",
            closing="9000.00",
        ),
        "cc-junho.ofx",
    )
    await _import(
        s,
        condo,
        ofx(
            [("20250531", "2.00", "RENDIMENTO")],
            start="20250501",
            end="20250531",
            closing="2000.00",
            account="77777-0",
        ),
        "aplic-maio.ofx",
    )
    await _import(
        s,
        condo,
        ofx(
            [
                ("20250610", "1000.00", "APLICACAO"),
                ("20250630", "5.00", "RENDIMENTO"),
                ("20250630", "-1.00", "IRRF"),
            ],
            start="20250601",
            end="20250630",
            closing=invest_closing,
            account="77777-0",
        ),
        "aplic-junho.ofx",
    )
    account = await s.scalar(
        select(BankAccount).where(
            BankAccount.condominium_id == condo.id, BankAccount.number == "77777-0"
        )
    )
    assert account is not None
    await gov.set_account_kind(
        s, condo, account.id, AccountKind.APLICACAO, "Aplicação reserva", (await _user(s)).id
    )
    return account


async def test_ban09_investment_reconciled_and_missing_counterpart(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["BAN-09"].status == "NAO_APLICAVEL"
        await _accounts(s, condo, invest_closing="3004.00")
        r = await _run(s, condo)
        assert r["BAN-09"].status == "VALIDADO", r["BAN-09"].rationale
        assert r["BAN-04"].status != "PENDENTE" or "aplica" not in r["BAN-04"].rationale
        await s.rollback()
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _import(
            s,
            condo,
            ofx(
                [("20250610", "-1000.00", "APLICACAO AUTOMATICA")],
                start="20250601",
                end="20250630",
                closing="9000.00",
            ),
            "cc.ofx",
        )
        r = await _run(s, condo)
        assert r["BAN-09"].status == "PENDENTE"  # investment statement not presented
        await s.rollback()


async def test_ban09_money_that_never_reached_the_investment_is_divergent(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _accounts(s, condo, invest_closing="3004.00")
        await _import(
            s,
            condo,
            ofx(
                [("20250620", "-500.00", "APLICACAO AUTOMATICA")],
                start="20250620",
                end="20250630",
                closing="8500.00",
            ),
            "cc-extra.ofx",
        )
        r = await _run(s, condo)
        assert r["BAN-09"].status == "DIVERGENTE"
        assert r["BAN-09"].differences == Decimal("500.00")
        await s.rollback()


async def test_ban08_fund_backing(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["BAN-08"].status == "PENDENTE"  # no fund
        account = await _accounts(s, condo, invest_closing="3004.00")
        result = await gov.import_fund_balances(
            s,
            condo,
            _csv(
                [
                    "Fundo;Competência;Saldo inicial;Entradas;Saídas;Rendimentos;Saldo final",
                    "Fundo de reserva;05/2025;;;;;2000,00",
                    "Fundo de reserva;06/2025;2000,00;1000,00;0,00;4,00;3004,00",
                ]
            ),
            None,
        )
        assert result.created == 2 and result.extra["fundos_criados"] == 1
        r = await _run(s, condo)
        assert r["BAN-08"].status == "COM_RESSALVA"  # no backing account named
        fund = (await s.scalars(select(Fund).where(Fund.condominium_id == condo.id))).one()
        await gov.update_fund(
            s,
            condo,
            fund.id,
            kind=None,
            purpose=None,
            account_ids=[account.id],
            user_id=(await _user(s)).id,
        )
        r = await _run(s, condo)
        assert r["BAN-08"].status == "VALIDADO", r["BAN-08"].rationale
        await gov.import_fund_balances(
            s,
            condo,
            _csv(
                [
                    "Fundo;Competência;Saldo inicial;Entradas;Saídas;Rendimentos;Saldo final",
                    "Fundo de reserva;06/2025;2000,00;2000,00;0,00;4,00;4004,00",
                ]
            ),
            None,
        )
        r = await _run(s, condo)
        assert r["BAN-08"].status == "DIVERGENTE"  # 4.004,00 declared, 3.004,00 of backing
        assert r["BAN-08"].differences == Decimal("1000.00")
        await s.rollback()


# --------------------------------------------------------------------------- GOV-01


async def test_gov01_budget_variance_needs_explanation(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        s.add(_expense(condo, "1500.00", "manutencao", description="Manutenção predial"))
        await s.flush()
        r = await _run(s, condo)
        assert r["GOV-01"].status == "PENDENTE"
        ata = await _document(s, condo, "ata-orcamento.pdf", "ata", {})
        result = await gov.import_budget(
            s,
            condo,
            _csv(["Categoria;Mês;Valor", "Manutenção;;12000,00", "limpeza;06/2025;500,00"]),
            year=2025,
            approved_on=date(2024, 12, 10),
            source_document_id=ata.id,
            user_id=None,
        )
        assert result.extra["versao"] == 1 and not result.errors
        r = await _run(s, condo)
        assert r["GOV-01"].status == "COM_RESSALVA"  # 50% above, no explanation
        calc = {c["label"]: c["value"] for c in r["GOV-01"].calculation}
        assert calc["Orçado no mês"] == "1500.00" and calc["Realizado no mês"] == "1500.00"
        user = await _user(s)
        await gov.add_budget_note(
            s, condo, JUNE, "manutencao", "Troca emergencial da bomba d'água.", user.id
        )
        r = await _run(s, condo)
        # Limpeza had 500 budgeted and nothing realized: -100%, also explained or not.
        assert r["GOV-01"].status == "COM_RESSALVA"
        await gov.add_budget_note(
            s, condo, JUNE, "limpeza", "Nota de junho chega em julho.", user.id
        )
        r = await _run(s, condo)
        assert r["GOV-01"].status == "VALIDADO", r["GOV-01"].rationale
        await s.rollback()


# --------------------------------------------------------------------------- GOV-02


async def test_gov02_insurance_in_force_and_expired(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["GOV-02"].status == "PENDENTE"
        ob = ComplianceObligation(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            name="Seguro obrigatório da edificação",
            category="seguro",
            periodicity_months=12,
            lead_days=60,
            applicability="aplicavel",
            responsible="Corretora Fictícia",
        )
        s.add(ob)
        await s.flush()
        apolice = await _document(s, condo, "apolice.pdf", "apolice", {})
        ev = ComplianceEvidence(
            condominium_id=condo.id,
            obligation_id=ob.id,
            document_id=apolice.id,
            issued_on=date(2025, 3, 1),
            valid_until=date(2026, 3, 1),
            source="pessoa",
            confirmed=True,
        )
        s.add(ev)
        await s.flush()
        r = await _run(s, condo)
        assert r["GOV-02"].status == "VALIDADO", r["GOV-02"].rationale
        ev.valid_until = date(2025, 6, 15)  # the same policy, read again with its real end
        await s.flush()
        r = await _run(s, condo)
        assert r["GOV-02"].status == "PENDENTE"  # expired before the end of June
        await s.rollback()


# --------------------------------------------------------------------------- DOC-03


async def _user(s: AsyncSession, tag: str = "") -> AppUser:
    user = AppUser(
        id=uuid.uuid4(),
        name=f"Pessoa Fictícia {tag}",
        email=f"p-{uuid.uuid4().hex[:8]}@teste.example.com",
    )
    s.add(user)
    await s.flush()
    return user


async def test_doc03_formal_approval_signatories_and_powers(admin_engine: AsyncEngine) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        r = await _run(s, condo)
        assert r["DOC-03"].status == "PENDENTE"
        conselheiro = BoardMember(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            full_name="Conselheira Fictícia",
            position="conselheiro",
            term_start=date(2024, 1, 1),
        )
        sindico = BoardMember(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            full_name="Síndico Fictício",
            position="sindico",
            term_start=date(2024, 1, 1),
        )
        s.add_all([conselheiro, sindico])
        await s.flush()
        ata = await _document(s, condo, "parecer.pdf", "ata", {})
        user = await _user(s)
        with pytest.raises(gov.GovernanceError):
            await gov.record_accounts_approval(
                s,
                condo,
                body=AccountsApprovalBody.CONSELHO_FISCAL,
                period_start=date(2025, 4, 1),
                period_end=date(2025, 6, 1),
                approved_on=date(2025, 8, 1),  # after TODAY
                document_id=ata.id,
                signatories=[{"board_member_id": str(conselheiro.id)}],
                with_reservations=False,
                notes=None,
                user_id=user.id,
                today=TODAY,
            )
        await gov.record_accounts_approval(
            s,
            condo,
            body=AccountsApprovalBody.CONSELHO_FISCAL,
            period_start=date(2025, 4, 1),
            period_end=date(2025, 6, 1),
            approved_on=date(2025, 7, 15),
            document_id=ata.id,
            signatories=[{"board_member_id": str(conselheiro.id)}],
            with_reservations=False,
            notes=None,
            user_id=user.id,
            today=TODAY,
        )
        r = await _run(s, condo)
        assert r["DOC-03"].status == "VALIDADO", r["DOC-03"].rationale
        await gov.record_accounts_approval(
            s,
            condo,
            body=AccountsApprovalBody.CONSELHO_FISCAL,
            period_start=date(2025, 6, 1),
            period_end=date(2025, 6, 1),
            approved_on=date(2025, 7, 16),
            document_id=ata.id,
            signatories=[
                {"board_member_id": str(conselheiro.id)},
                {"board_member_id": str(sindico.id)},
            ],
            with_reservations=False,
            notes=None,
            user_id=user.id,
            today=TODAY,
        )
        r = await _run(s, condo)
        assert r["DOC-03"].status == "COM_RESSALVA"  # the síndico approved own accounts
        await s.rollback()


# --------------------------------------------------------------------------- publication


async def test_publication_waits_for_review_and_the_sindico_approves_the_version_seen(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        sup = await _supplier(s, "Limpeza Fictícia Ltda")
        c = _contract(condo, sup)
        s.add(c)
        await s.flush()
        e = _linked(condo, c, "1100.00", "Limpeza junho")
        s.add(e)
        await s.flush()
        await _run(s, condo)
        reviewer, sindico = await _user(s, "revisora"), await _user(s, "síndica")
        with pytest.raises(pubs.PublicationError, match="CON-01"):
            await pubs.submit(s, condo.id, JUNE, reviewer.id)  # divergence not reviewed
        e.amount = Decimal("1000.00")
        await s.flush()
        await _run(s, condo)
        pending = (
            await s.scalars(
                select(AuditControlResult).where(
                    AuditControlResult.condominium_id == condo.id,
                    AuditControlResult.superseded_by_id.is_(None),
                    AuditControlResult.review_state == ControlReviewState.NEEDS_HUMAN_REVIEW.value,
                )
            )
        ).all()
        for row in pending:
            row.review_state = ControlReviewState.REVIEWED.value
        await s.flush()
        pub = await pubs.submit(s, condo.id, JUNE, reviewer.id)
        assert pub.status == PublicationStatus.AGUARDANDO.value
        assert len(pub.snapshot["controles"]) == 25
        assert all(
            not c["pendencias"]
            for c in pub.snapshot["controles"]
            if c["id"].startswith("REC-0") and c["id"] != "REC-01"
        )
        with pytest.raises(pubs.PublicationError, match="enviou"):
            await pubs.decide(
                s,
                condo.id,
                pub.id,
                approve=True,
                seen_sha256=pub.snapshot_sha256,
                reason=None,
                user_id=reviewer.id,
            )
        with pytest.raises(pubs.PublicationError, match="versão"):
            await pubs.decide(
                s,
                condo.id,
                pub.id,
                approve=True,
                seen_sha256="0" * 64,
                reason=None,
                user_id=sindico.id,
            )
        done = await pubs.decide(
            s,
            condo.id,
            pub.id,
            approve=True,
            seen_sha256=pub.snapshot_sha256,
            reason=None,
            user_id=sindico.id,
        )
        assert done.status == PublicationStatus.APROVADA.value
        states = {
            r.review_state
            for r in await s.scalars(
                select(AuditControlResult).where(
                    AuditControlResult.condominium_id == condo.id,
                    AuditControlResult.superseded_by_id.is_(None),
                )
            )
        }
        assert states == {ControlReviewState.APPROVED_FOR_PUBLICATION.value}
        assert not await pubs.changed_since(s, done)
        # A later revalidation that changes a result marks the approved farol as changed.
        e.amount = Decimal("1200.00")
        await s.flush()
        await _run(s, condo)
        assert await pubs.changed_since(s, done)
        await s.rollback()


async def test_sending_superseded_by_a_new_run_cannot_be_approved(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await _run(s, condo)
        await s.execute(
            update(AuditControlResult)
            .where(AuditControlResult.condominium_id == condo.id)
            .values(review_state=ControlReviewState.REVIEWED.value)
        )
        reviewer, sindico = await _user(s, "r"), await _user(s, "s")
        pub = await pubs.submit(s, condo.id, JUNE, reviewer.id)
        s.add(_expense(condo, "300.00", "manutencao", description="Reparo"))
        await s.flush()
        await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        await s.refresh(pub)
        assert pub.status == PublicationStatus.SUPERADA.value
        with pytest.raises(pubs.PublicationError):
            await pubs.decide(
                s,
                condo.id,
                pub.id,
                approve=True,
                seen_sha256=pub.snapshot_sha256,
                reason=None,
                user_id=sindico.id,
            )
        await s.rollback()


async def test_revalidation_reruns_past_months_and_reuses_what_did_not_change(
    admin_engine: AsyncEngine,
) -> None:
    async with sessionmaker_for(admin_engine)() as s, s.begin():
        condo = await _new_condo(s)
        await run_audit(s, condo, JUNE, today=TODAY, user_id=None)
        again = await run_audit(s, condo, JUNE, today=TODAY, user_id=None, trigger="revalidacao")
        assert again.summary["novos_resultados"] == 0 and again.summary["reutilizados"] == 25
        await s.rollback()


# --------------------------------------------------------------------------- access


def test_only_the_sindico_approves_the_farol_and_never_reviews_it() -> None:
    holders = {
        r for r, perms in ROLE_PERMISSIONS.items() if Permission.APPROVE_AUDIT_PUBLICATION in perms
    }
    assert holders == {Role.SINDICO}
    for role, perms in ROLE_PERMISSIONS.items():
        assert not (
            perms & REVIEW_PERMISSIONS and Permission.APPROVE_AUDIT_PUBLICATION in perms
        ), role
    assert Permission.VIEW_AUDIT not in ROLE_PERMISSIONS[Role.SINDICO]  # no unit data


async def test_api_publication_flow_and_access(
    client: httpx.AsyncClient, mailer: MemoryMailer, admin_engine: AsyncEngine
) -> None:
    mirante = await condo_id(admin_engine, "mirante-do-vale")
    acacias = await condo_id(admin_engine, "jardim-das-acacias")
    await login(client, mailer, REVISORA)
    assert (
        await client.post(f"/condominiums/{mirante}/audit/runs", json={"competencia": "2024-03"})
    ).status_code == 200
    farol = (await client.get(f"/condominiums/{mirante}/audit/farol?competencia=2024-03")).json()
    for c in farol["controls"]:
        if c.get("review_state") == "NEEDS_HUMAN_REVIEW":
            ok = await client.post(
                f"/condominiums/{mirante}/audit/results/{c['result_id']}/review",
                json={"decision": "confirmar", "reason": "Conferido na revisão interna."},
            )
            assert ok.status_code == 200
    sent = await client.post(
        f"/condominiums/{mirante}/audit/publications", json={"competencia": "2024-03"}
    )
    assert sent.status_code == 201, sent.text
    pub = sent.json()
    gov_view = await client.get(f"/condominiums/{mirante}/audit/governance?competencia=2024-03")
    assert gov_view.status_code == 200 and "funds" in gov_view.json()
    client.cookies.clear()
    await login(client, mailer, GERENTE)
    decision = f"/condominiums/{mirante}/audit/publications/{pub['id']}/decision"
    assert (
        await client.post(decision, json={"approve": True, "sha256": pub["sha256"]})
    ).status_code == 403
    client.cookies.clear()
    await login(client, mailer, SINDICA_MIRANTE)
    listing = (await client.get(f"/condominiums/{mirante}/audit/publications")).json()
    assert listing["can_approve"] and listing["publications"][0]["status"] == "aguardando_sindico"
    assert (
        await client.post(
            f"/condominiums/{mirante}/audit/publications", json={"competencia": "2024-03"}
        )
    ).status_code == 403
    returned = await client.post(
        decision, json={"approve": False, "sha256": pub["sha256"], "reason": "curto"}
    )
    assert returned.status_code == 409  # a return needs a reason
    approved = await client.post(decision, json={"approve": True, "sha256": pub["sha256"]})
    assert approved.status_code == 200 and approved.json()["status"] == "aprovada"
    client.cookies.clear()
    await login(client, mailer, CONSELHEIRO_ACACIAS)
    other = await client.get(f"/condominiums/{acacias}/audit/publications")
    assert other.status_code == 200 and not other.json()["can_approve"]
    assert all(p["status"] == "aprovada" for p in other.json()["publications"])
    assert (await client.get(f"/condominiums/{mirante}/audit/publications")).status_code == 404
