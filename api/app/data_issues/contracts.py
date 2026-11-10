"""Contract alerts from the reading (D120, B1) and the case to adjust a contract without the
contracted party's CNPJ (B2).

The alerts keep what the document says, even after a person corrected the registry to let
the contract in: (a) signed after the term started; (b) the contracting party is not the
condominium (e.g. the management company); (c) wrong condominium CNPJ in the contract;
(d) no CNPJ of the contracted party. They never block anything (capabilities empty, like the
health alerts of D110): they record the gap and offer "Pedir correção do contrato" or
"Criar assunto". Deterministic, versioned, idempotent by ``dedupe_key``.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cases import add_event, next_number
from app.condo_settings import settings_at
from app.core.br import format_cnpj
from app.core.money import brl
from app.core.time import utcnow
from app.data_issues import DetectionResult, Found, reconcile
from app.db.enums import (
    CONTRACT_ALERT_KINDS,
    CaseCategory,
    CaseLinkTarget,
    CaseOrigin,
    CaseSeverity,
    CaseStatus,
    DataIssueKind,
    Role,
)
from app.db.models import (
    CaseLink,
    CaseRecord,
    Condominium,
    Contract,
    Document,
    ExtractionCorrection,
    ManagementCompany,
    Membership,
    Supplier,
)
from app.matching.categories import category_for
from app.matching.text import normalize_name

DETECTOR = "contrato_leitura_v1"
ADJUST_TITLE = "Ajustar contrato: incluir o CNPJ da contratada"
ADJUST_DAYS = 30
# Services the condominium cannot be without (approved by Marcio, D120): a contract for them
# without the contracted party's CNPJ always opens the case to adjust it.
ESSENTIAL_WORDS = {
    "portaria": ("portaria", "porteiro", "controlador de acesso", "recepcao"),
    "limpeza": ("limpeza", "zeladoria", "asseio", "conservacao"),
    "elevadores": ("elevador",),
    "seguranca": ("seguranca", "vigilancia", "monitoramento", "ronda"),
    "manutencao predial": ("manutencao predial", "manutencao preventiva", "manutencao corretiva"),
    "seguro": ("seguro", "apolice"),
}


def essential_service(contract: Contract) -> str | None:
    """The essential service a contract is for, or None."""
    text = normalize_name(" ".join([contract.object, *(contract.scope_items or [])]))
    for service, words in ESSENTIAL_WORDS.items():
        if any(normalize_name(w) in text for w in words):
            return service
    return None


def contract_value(contract: Contract) -> Decimal | None:
    return contract.monthly_value if contract.monthly_value is not None else contract.total_value


async def within_alcada(session: AsyncSession, condo: Condominium, contract: Contract) -> bool:
    """The contract's value (monthly, or total for a one-off contract) is within the síndico's
    approval limit in force for its category (the same limit rule R12 uses)."""
    limits, _, _ = await settings_at(session, condo, contract.start_date)
    category = category_for(contract, None, contract.object)
    raw = (limits.get("by_category") or {}).get(category, limits.get("default"))
    value = contract_value(contract)
    if raw is None or value is None:
        return False
    return value <= Decimal(str(raw))


async def _active_sindico(session: AsyncSession, condo_id: uuid.UUID) -> uuid.UUID | None:
    now = utcnow()
    return await session.scalar(
        select(Membership.user_id)
        .where(
            Membership.condominium_id == condo_id,
            Membership.role == Role.SINDICO.value,
            Membership.revoked_at.is_(None),
            or_(Membership.expires_at.is_(None), Membership.expires_at > now),
        )
        .order_by(Membership.created_at)
        .limit(1)
    )


async def needs_adjust_case(session: AsyncSession, condo: Condominium, contract: Contract) -> bool:
    return essential_service(contract) is not None or not await within_alcada(
        session, condo, contract
    )


async def open_adjust_case(
    session: AsyncSession, condo: Condominium, contract: Contract
) -> CaseRecord | None:
    """B2: a contract without the contracted party's CNPJ, essential or above the síndico's
    approval limit, opens the case "Ajustar contrato" for the síndico, due in 30 days.
    Within the limit and not essential, it enters by legal name with an observation only.
    One case per contract (never duplicated)."""
    if contract.supplier_id is not None or not await needs_adjust_case(session, condo, contract):
        return None
    linked = await session.scalar(
        select(CaseLink.case_id).where(
            CaseLink.condominium_id == condo.id,
            CaseLink.target_type == CaseLinkTarget.CONTRACT.value,
            CaseLink.target_id == contract.id,
        )
    )
    if linked is not None:
        return None
    locked = await session.scalar(
        select(Condominium).where(Condominium.id == condo.id).with_for_update()
    )
    assert locked is not None
    today = date.today()
    service = essential_service(contract)
    why = (
        f"serviço essencial ({service})"
        if service
        else f"valor acima da alçada do síndico ({brl(contract_value(contract) or Decimal(0))})"
    )
    owner = await _active_sindico(session, condo.id)
    due = datetime.combine(today + timedelta(days=ADJUST_DAYS), time(23, 59), tzinfo=UTC)
    case = CaseRecord(
        id=uuid.uuid4(),
        condominium_id=condo.id,
        number=await next_number(session, locked, today),
        title=ADJUST_TITLE,
        description=(
            f"O contrato com {contract.supplier_name} ({contract.object}) não traz o CNPJ da "
            f"contratada. Ele foi cadastrado pela razão social; por ser {why}, o contrato "
            "precisa ser ajustado."
        ),
        category=CaseCategory.CONTRATO.value,
        origin=CaseOrigin.HUMAN_REQUEST.value,
        severity=CaseSeverity.MEDIA.value,
        status=CaseStatus.NOVO.value,
        owner_user_id=owner,
        next_action="Pedir à contratada o contrato (ou aditivo) com o CNPJ",
        next_action_due_at=due,
        resolution_criterion="Contrato com o CNPJ da contratada registrado no CondoOS",
        requires_evidence=True,
        created_by_user_id=None,
    )
    session.add(case)
    await session.flush()
    await add_event(
        session,
        case,
        kind="created",
        actor_user_id=None,
        to_value=CaseStatus.NOVO.value,
        details={"origin": "contrato_sem_cnpj", "contract_id": str(contract.id)},
    )
    session.add(
        CaseLink(
            id=uuid.uuid4(),
            condominium_id=condo.id,
            case_id=case.id,
            target_type=CaseLinkTarget.CONTRACT.value,
            target_id=contract.id,
            as_evidence=False,
            reason="Contrato sem o CNPJ da contratada",
        )
    )
    await session.flush()
    return case


def _br(iso: Any) -> str:
    try:
        return date.fromisoformat(str(iso)).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _evidence(doc: Document, field: str, label: str, value: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": label,
        "value": value,
        "document_id": str(doc.id),
        "filename": doc.original_filename,
    }
    prov = (doc.field_provenance or {}).get(field) or {}
    if prov.get("excerpt"):
        item["excerpt"], item["page"] = prov["excerpt"], prov.get("page")
    return item


def _alert(
    kind: DataIssueKind,
    contract: Contract,
    title: str,
    detail: str,
    evidence: list[dict[str, Any]],
) -> Found:
    return Found(
        dedupe_key=f"{DETECTOR}:{kind.value}:{contract.id}",
        detector=DETECTOR,
        subject_id=contract.id,
        supplier_id=contract.supplier_id,
        title=title,
        detail=detail,
        field=None,
        evidence=evidence,
        kind=kind.value,
        subject_type="contract",
        capabilities=[],
    )


def _looks_like_condominium(name: str | None) -> bool:
    return "condominio" in normalize_name(name or "") or "edificio" in normalize_name(name or "")


async def contract_alerts(session: AsyncSession, condo: Condominium) -> list[Found]:
    contracts = list(
        await session.scalars(select(Contract).where(Contract.condominium_id == condo.id))
    )
    docs = {
        d.id: d
        for d in await session.scalars(
            select(Document).where(
                Document.condominium_id == condo.id,
                Document.id.in_([c.source_document_id for c in contracts if c.source_document_id]),
            )
        )
    }
    manager_cnpj = None
    if condo.management_company_id is not None:
        company = await session.get(ManagementCompany, condo.management_company_id)
        manager_cnpj = company.cnpj if company else None
    out: list[Found] = []
    for c in contracts:
        doc = docs.get(c.source_document_id) if c.source_document_id else None
        v = doc.extracted if doc is not None else {}
        start_inferred = (
            ((doc.field_provenance or {}).get("data_inicio") or {}).get("source") == "inferido"
            if doc is not None
            else True
        )
        signed = v.get("data_assinatura")
        if doc is not None and signed and not start_inferred and signed > c.start_date.isoformat():
            out.append(
                _alert(
                    DataIssueKind.CONTRATO_ASSINADO_DEPOIS,
                    c,
                    "Contrato assinado depois do início da vigência",
                    f"Assinado em {_br(signed)}, depois do início da vigência em "
                    f"{c.start_date:%d/%m/%Y}. Os serviços anteriores à assinatura ficaram sem "
                    "contrato assinado: confirme com a contratada.",
                    [
                        _evidence(doc, "data_assinatura", "Assinatura", _br(signed)),
                        _evidence(doc, "data_inicio", "Início da vigência", _br(c.start_date)),
                    ],
                )
            )
        if doc is not None:
            out.extend(await _party_alerts(session, condo, c, doc, manager_cnpj))
        if c.supplier_id is None:
            adjust = await needs_adjust_case(session, condo, c)
            detail = (
                "O contrato não traz o CNPJ da contratada e foi cadastrado pela razão social. "
                + (
                    f"Aberto o assunto “{ADJUST_TITLE}”."
                    if adjust
                    else "Valor dentro da alçada do síndico e serviço não essencial: fica a "
                    "observação. A primeira nota desse fornecedor preenche o CNPJ."
                )
            )
            out.append(
                _alert(
                    DataIssueKind.CONTRATO_SEM_CNPJ,
                    c,
                    "Contrato sem o CNPJ da contratada",
                    detail,
                    [
                        (
                            _evidence(
                                doc, "razao_social_contratada", "Contratada", c.supplier_name or ""
                            )
                            if doc is not None
                            else {"label": "Contratada", "value": c.supplier_name or ""}
                        )
                    ],
                )
            )
    return out


async def _party_alerts(
    session: AsyncSession,
    condo: Condominium,
    contract: Contract,
    doc: Document,
    manager_cnpj: str | None,
) -> list[Found]:
    """(b) and (c): what the document said about the contracting party before a person
    corrected it (kept in ``extraction_correction``)."""
    written = await session.scalar(
        select(ExtractionCorrection.extracted_value)
        .where(
            ExtractionCorrection.document_id == doc.id,
            ExtractionCorrection.field_name == "cnpj_contratante",
        )
        .order_by(ExtractionCorrection.created_at)
        .limit(1)
    )
    if not written or written == condo.cnpj:
        return []
    written = str(written)
    registry = await session.scalar(select(Supplier.legal_name).where(Supplier.cnpj == written))
    evidence = [
        {
            "label": "No contrato",
            "value": format_cnpj(written) + (f" — {registry}" if registry else ""),
            "document_id": str(doc.id),
            "filename": doc.original_filename,
        },
        {"label": "Cadastro do condomínio", "value": f"{format_cnpj(condo.cnpj)} — {condo.name}"},
    ]
    if written == manager_cnpj or (registry and not _looks_like_condominium(registry)):
        who = "a administradora" if written == manager_cnpj else (registry or "outra empresa")
        if written == manager_cnpj and registry:
            who = f"a administradora {registry}"
        return [
            _alert(
                DataIssueKind.CONTRATO_CONTRATANTE,
                contract,
                "O contratante no contrato não é o condomínio",
                f"O contrato está em nome de {who} (CNPJ {format_cnpj(written)}), não do "
                "condomínio. O cadastro foi corrigido para o condomínio; peça a correção do "
                "contrato.",
                evidence,
            )
        ]
    return [
        _alert(
            DataIssueKind.CONTRATO_CNPJ_CONDOMINIO,
            contract,
            "CNPJ do condomínio errado no contrato",
            f"O contrato traz o CNPJ {format_cnpj(written)}; o do condomínio é "
            f"{format_cnpj(condo.cnpj)}. O cadastro usa o CNPJ certo; peça a correção do "
            "contrato.",
            evidence,
        )
    ]


async def detect_contracts(session: AsyncSession, condo_id: uuid.UUID) -> DetectionResult:
    """Every contract alert for one condominium, reconciled with the open ones. Idempotent."""
    condo = await session.get(Condominium, condo_id)
    if condo is None:
        return DetectionResult()
    return await reconcile(
        session,
        condo_id,
        await contract_alerts(session, condo),
        {k.value for k in CONTRACT_ALERT_KINDS},
    )
