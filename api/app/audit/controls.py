"""Deterministic evaluation of the controls of cycle 1 (D122): DOC-01, DOC-02, BAN-01..05,
REC-01 and DES-01. Each returns its tests, the evidence it used (or the declared absence),
coverage, differences in cents and a status decided by explicit criteria.

Global rules: no control is "Validado" when a mandatory source was not received; "Não
aplicável" only with an objective reason; nothing is inferred as absent outside what was
received ("não apresentado" ≠ "não existe").
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.audit.catalog import CONTROLS_BY_ID
from app.audit.data import LABELS, NON_REVENUE, ZERO, AccountView, AuditData, Line
from app.core.money import brl
from app.db.enums import ControlStatus, ExtractionStatus

S = ControlStatus
TEXT_ONLY_REVENUE_DOCS = {"balancete", "relatorio_adm"}


@dataclass
class Check:
    name: str
    passed: bool | None  # None: could not run (source missing)
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"teste": self.name, "resultado": _result(self.passed), "detalhe": self.detail}


def _result(passed: bool | None) -> str:
    return "passou" if passed else "não rodou" if passed is None else "falhou"


@dataclass
class Outcome:
    status: ControlStatus
    rationale: str
    checks: list[Check] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    coverage: Decimal | None = None
    differences: Decimal = ZERO
    severity: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)  # what the fingerprint covers


def _pct(n: int, total: int) -> Decimal | None:
    return (Decimal(n) / Decimal(total)).quantize(Decimal("0.0001")) if total else None


def _doc_ref(doc: Any) -> dict[str, Any]:
    return {"tipo": "documento", "id": str(doc.id), "rotulo": doc.original_filename}


def _line_ref(line: Line) -> dict[str, Any]:
    t = line.trn
    return {
        "tipo": "lancamento",
        "id": str(t.id),
        "rotulo": f"{t.posted_at:%d/%m/%Y} · {t.description[:60]} · {brl(t.amount)}",
        "classificacao": LABELS[line.kind],
    }


def _statement_ref(view: AccountView) -> dict[str, Any] | None:
    st = view.statement
    if st is None:
        return None
    return {
        "tipo": "extrato",
        "id": str(st.id),
        "documento_id": str(st.document_id) if st.document_id else None,
        "rotulo": f"Extrato {view.label}"
        + (f" até {st.period_end:%d/%m/%Y}" if st.period_end else ""),
    }


# --------------------------------------------------------------------------- DOC


def doc_01(d: AuditData) -> Outcome:
    docs = d.documents
    unreadable = [
        x
        for x in docs
        if x.extraction_status == ExtractionStatus.FAILED.value
        or any("sem texto legível" in r for r in (x.review_reasons or []))
    ]
    waiting = [
        x
        for x in docs
        if x.extraction_status == ExtractionStatus.NEEDS_REVIEW.value and x not in unreadable
    ]
    reading = [
        x
        for x in docs
        if x.extraction_status
        in (ExtractionStatus.PENDING.value, ExtractionStatus.PROCESSING.value)
    ]
    known = [a for a in d.accounts if a.account is not None]
    without_statement = [a for a in known if a.statement is None]
    checks = [
        Check("Acervo recebido", bool(docs), f"{len(docs)} documentos da competência."),
        Check(
            "Extrato de cada conta conhecida",
            None if not known else not without_statement,
            (
                "Nenhuma conta bancária cadastrada (chega com o primeiro extrato OFX)."
                if not known
                else (
                    "Sem extrato: " + ", ".join(a.label for a in without_statement)
                    if without_statement
                    else f"{len(known)} conta(s) com extrato do mês."
                )
            ),
        ),
        Check(
            "Documentos lidos",
            not (unreadable or waiting or reading),
            f"{len(unreadable)} ilegível(is), {len(waiting)} aguardando correção, "
            f"{len(reading)} em leitura.",
        ),
        Check(
            "Cópias e versões registradas",
            True,
            f"{d.copies} cópia(s) de nota ligadas à nota original; {d.superseded} documento(s) "
            "substituído(s) por versão nova. Nada descartado.",
        ),
    ]
    missing = []
    if not docs:
        missing.append("Envie os documentos da competência (notas, recibos, extratos).")
    if not known:
        missing.append("Envie o extrato do mês em OFX (identifica a conta e o saldo final).")
    missing += [f"Envie o extrato de {a.label} que cubra o mês." for a in without_statement]
    missing += [f"Envie de novo, legível: {x.original_filename}." for x in unreadable]
    evidence = [_doc_ref(x) for x in docs[:200]]
    readable = len(docs) - len(unreadable)
    if not docs or not known or without_statement:
        status, why = S.PENDENTE, "Falta fonte obrigatória do mês: " + "; ".join(missing[:3])
    elif unreadable or waiting or reading:
        status, why = (
            S.COM_RESSALVA,
            "Acervo recebido, mas há documentos ilegíveis, em leitura ou aguardando correção; "
            "o que eles contêm não entra nos demais controles até serem lidos.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Acervo recebido, lido por inteiro e com extrato de todas as contas.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(readable, len(docs)),
        inputs={
            "docs": sorted((str(x.id), x.extraction_status) for x in docs),
            "contas": sorted((a.key, str(a.statement.id) if a.statement else "") for a in known),
        },
    )


def doc_02(d: AuditData) -> Outcome:
    exps = d.expenses
    without = [e for e in exps if not e.has_document]
    debits = [ln for ln in d.lines if ln.amount < 0]
    checks = [
        Check("Despesas do mês", None if not exps else True, f"{len(exps)} despesa(s)."),
        Check(
            "Documento fiscal, recibo ou guia de cada despesa",
            None if not exps else not without,
            f"{len(exps) - len(without)} de {len(exps)} com documento.",
        ),
    ]
    evidence = [
        {
            "tipo": "despesa",
            "id": str(e.expense.id),
            "rotulo": f"{e.expense.description[:60]} · {brl(e.expense.amount)}",
            "documentos": [str(x) for r in ("fiscal", "recibo") for x in e.roles.get(r, [])],
        }
        for e in exps[:200]
    ]
    missing = [
        f"Documento de: {e.expense.description[:60]} ({brl(e.expense.amount)})" for e in without
    ]
    if not exps:
        if d.has_statement and not debits:
            status, why = S.NAO_APLICAVEL, "Nenhuma despesa e nenhum débito no extrato do mês."
        else:
            status, why = (
                S.PENDENTE,
                "Nenhuma despesa registrada no mês, sem extrato que mostre que não houve pagamentos.",
            )
            missing.append("Envie as notas e o extrato do mês.")
    elif without:
        status, why = S.PENDENTE, f"{len(without)} despesa(s) sem documento apresentado."
    else:
        status, why = (
            S.VALIDADO,
            "Toda despesa do mês tem documento. Pagamento é verificado em DES-01.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(exps) - len(without), len(exps)),
        inputs={"despesas": sorted((str(e.expense.id), sorted(e.roles)) for e in exps)},
    )


# --------------------------------------------------------------------------- BAN


def _accounts_or_pending(d: AuditData, control: str) -> Outcome | None:
    if not any(a.account is not None for a in d.accounts):
        return Outcome(
            S.PENDENTE,
            "Nenhum extrato com a conta identificada no mês: sem ele não há saldo para testar "
            "(a falta de extrato nunca vira saldo zero).",
            [Check("Extrato com conta e saldos", None, "Nenhum recebido.")],
            missing=["Envie o extrato do mês em OFX, com o saldo final."],
            inputs={"contas": [], "control": control},
        )
    return None


def ban_01(d: AuditData) -> Outcome:
    if (pending := _accounts_or_pending(d, "BAN-01")) is not None:
        return pending
    checks, evidence, missing = [], [], []
    ok = diverge = pend = 0
    total_diff = ZERO
    known = [a for a in d.accounts if a.account is not None]
    detail: dict[str, Any] = {}
    for a in known:
        c = a.balance_check()
        detail[a.key] = c
        ref = _statement_ref(a)
        if ref:
            evidence.append(ref)
        if c["situacao"] == "confere":
            ok += 1
            checks.append(
                Check(
                    f"{a.label}: saldo inicial + movimentos = saldo final",
                    True,
                    f"{brl(Decimal(c['saldo_inicial']))} ({c['origem_saldo_inicial']}) + "
                    f"{brl(Decimal(c['movimentos']))} = {brl(Decimal(c['saldo_final_declarado']))}.",
                )
            )
        elif c["situacao"] == "diverge":
            diverge += 1
            total_diff += abs(Decimal(c["diferenca"]))
            checks.append(
                Check(
                    f"{a.label}: saldo inicial + movimentos = saldo final",
                    False,
                    f"Calculado {brl(Decimal(c['saldo_final_calculado']))}, declarado "
                    f"{brl(Decimal(c['saldo_final_declarado']))}: diferença "
                    f"{brl(Decimal(c['diferenca']))}.",
                )
            )
        else:
            pend += 1
            reason = {
                "sem_extrato": "sem extrato do mês",
                "sem_saldo_final": "o extrato não traz saldo final",
                "sem_saldo_inicial": "sem saldo inicial (nem no extrato nem no mês anterior)",
            }[c["situacao"]]
            checks.append(Check(f"{a.label}: equação do saldo", None, reason.capitalize() + "."))
            missing.append(f"{a.label}: {reason}.")
    loose = [a for a in d.accounts if a.account is None]
    if loose:
        checks.append(
            Check(
                "Lançamentos sem conta identificada",
                None,
                f"{len(loose[0].lines)} lançamento(s) de arquivo sem identificação da conta: "
                "ficam fora da equação.",
            )
        )
        missing.append("Envie o extrato em OFX para identificar a conta dos lançamentos.")
    checks.append(
        Check(
            "Saldo do extrato × saldo contábil do demonstrativo",
            None,
            "O saldo contábil do demonstrativo ainda não é lido como dado (ciclo 3): conferida "
            "só a aritmética do extrato.",
        )
    )
    if diverge:
        status, why = (
            S.DIVERGENTE,
            f"Saldo do extrato não fecha em {diverge} conta(s): {brl(total_diff)}.",
        )
    elif pend:
        status, why = S.PENDENTE, "Falta saldo para fechar a equação: " + "; ".join(missing[:3])
    else:
        status, why = (
            S.COM_RESSALVA,
            "A aritmética do extrato fecha ao centavo em todas as contas conhecidas, mas o saldo "
            "contábil do demonstrativo não foi confrontado (fonte ainda não lida como dado). "
            "Saldo correto não prova a regularidade das despesas nem o lastro dos fundos.",
        )
        if loose:
            status, why = S.COM_RESSALVA, why + " Há lançamentos sem conta identificada."
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(ok, len(known)),
        total_diff,
        "ALTA" if diverge else None,
        inputs={"contas": detail, "sem_conta": len(loose[0].lines) if loose else 0},
    )


def ban_02(d: AuditData) -> Outcome:
    if (pending := _accounts_or_pending(d, "BAN-02")) is not None:
        return pending
    checks, missing, evidence = [], [], []
    ok = diverge = 0
    total_diff = ZERO
    known = [a for a in d.accounts if a.account is not None]
    detail = {}
    for a in known:
        c = a.continuity()
        detail[a.key] = c
        if (ref := _statement_ref(a)) is not None:
            evidence.append(ref)
        if a.previous is not None:
            evidence.append(
                {
                    "tipo": "extrato",
                    "id": str(a.previous.id),
                    "rotulo": f"Extrato anterior de {a.label}",
                }
            )
        if c["situacao"] == "confere":
            ok += 1
            checks.append(
                Check(
                    f"{a.label}: abertura = fechamento anterior",
                    True,
                    f"{brl(Decimal(c['abertura']))} ({c['metodo']}).",
                )
            )
        elif c["situacao"] == "diverge":
            diverge += 1
            total_diff += abs(Decimal(c["diferenca"]))
            checks.append(
                Check(
                    f"{a.label}: abertura = fechamento anterior",
                    False,
                    f"Fechamento anterior {brl(Decimal(c['fechamento_anterior']))}, abertura "
                    f"{brl(Decimal(c['abertura']))} ({c['metodo']}): diferença {brl(Decimal(c['diferenca']))}.",
                )
            )
        else:
            text = {
                "sem_extrato": "sem extrato do mês",
                "sem_mes_anterior": "sem extrato do mês anterior com saldo final",
                "sem_saldo": "o extrato não traz saldo",
            }[c["situacao"]]
            checks.append(Check(f"{a.label}: continuidade", None, text.capitalize() + "."))
            missing.append(f"{a.label}: {text}.")
    if diverge:
        status, why = (
            S.DIVERGENTE,
            f"Quebra de continuidade em {diverge} conta(s): {brl(total_diff)}.",
        )
    elif missing:
        status, why = S.PENDENTE, "Falta saldo de um dos meses: " + "; ".join(missing[:3])
    else:
        status, why = (
            S.VALIDADO,
            "A abertura do mês é igual ao fechamento anterior em todas as contas conhecidas.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(ok, len(known)),
        total_diff,
        "ALTA" if diverge else None,
        inputs=detail,
    )


def _need_statement(d: AuditData) -> Outcome | None:
    if not d.lines:
        if d.has_statement:
            return None
        return Outcome(
            S.PENDENTE,
            "Nenhum lançamento bancário do mês recebido.",
            [Check("Extrato do mês", None, "Não recebido.")],
            missing=["Envie o extrato do mês."],
        )
    return None


def ban_03(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    debits = [ln for ln in d.lines if ln.amount < 0]
    unknown = [ln for ln in debits if ln.kind == "nao_identificado"]
    indirect = [ln for ln in debits if ln.intermediary]
    by_kind: dict[str, int] = {}
    for ln in debits:
        by_kind[LABELS[ln.kind]] = by_kind.get(LABELS[ln.kind], 0) + 1
    checks = [
        Check(
            "Débitos identificados",
            not unknown,
            f"{len(debits) - len(unknown)} de {len(debits)}: "
            + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())),
        ),
        Check(
            "Pagamentos a intermediário marcados",
            True,
            f"{len(indirect)} pagamento(s) por intermediário: liquidação final é verificada em BAN-07.",
        ),
    ]
    missing = [f"Identifique o débito {_line_ref(ln)['rotulo']}" for ln in unknown]
    evidence = [_line_ref(ln) for ln in debits[:300]]
    if not debits:
        status, why = S.NAO_APLICAVEL, "O extrato do mês não tem débitos."
    elif unknown:
        status, why = S.PENDENTE, f"{len(unknown)} débito(s) sem despesa ligada nem classificação."
    elif indirect:
        status, why = (
            S.COM_RESSALVA,
            f"Todos os débitos identificados; {len(indirect)} pago(s) por intermediário, sem prova de liquidação final.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "100% dos débitos ligados a despesa ou classificados como movimento que não é despesa.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(debits) - len(unknown), len(debits)),
        sum((-ln.amount for ln in unknown), ZERO),
        inputs={
            "debitos": sorted((str(ln.trn.id), ln.kind, str(ln.trn.expense_id)) for ln in debits)
        },
    )


def ban_04(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    credits = [ln for ln in d.lines if ln.amount > 0]
    unknown = [ln for ln in credits if ln.kind == "nao_identificado"]
    suggested = [ln for ln in credits if ln.strength == "sugerido"]
    by_kind: dict[str, Decimal] = {}
    for ln in credits:
        by_kind[LABELS[ln.kind]] = by_kind.get(LABELS[ln.kind], ZERO) + ln.amount
    checks = [
        Check(
            "Créditos classificados",
            not unknown,
            f"{len(credits) - len(unknown)} de {len(credits)}: "
            + ", ".join(f"{k} {brl(v)}" for k, v in sorted(by_kind.items())),
        ),
        Check(
            "Classificação por regra (não por suposição)",
            not suggested,
            f"{len(suggested)} crédito(s) classificados só por indício (ex.: PIX recebido sem identificação).",
        ),
    ]
    missing = [f"Identifique o crédito {_line_ref(ln)['rotulo']}" for ln in unknown + suggested]
    evidence = [_line_ref(ln) for ln in credits[:300]]
    if not credits:
        status, why = S.NAO_APLICAVEL, "O extrato do mês não tem créditos."
    elif unknown:
        status, why = S.PENDENTE, f"{len(unknown)} crédito(s) sem classificação."
    elif suggested:
        status, why = (
            S.COM_RESSALVA,
            f"Todos classificados, mas {len(suggested)} só por indício: origem a confirmar.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "100% dos créditos classificados por regra; transferências e estornos fora da receita.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(credits) - len(unknown) - len(suggested), len(credits)),
        inputs={"creditos": sorted((str(ln.trn.id), ln.kind, ln.strength) for ln in credits)},
    )


def ban_05(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    reversals = [ln for ln in d.lines if ln.amount > 0 and ln.kind == "estorno"]
    unpaired = [ln for ln in reversals if ln.paired_with is None]
    by_id = {ln.trn.id: ln for ln in d.lines}
    counted = [
        by_id[ln.paired_with]
        for ln in reversals
        if ln.paired_with is not None and by_id[ln.paired_with].trn.expense_id is not None
    ]
    checks = [
        Check(
            "Estornos pareados",
            not unpaired,
            f"{len(reversals) - len(unpaired)} de {len(reversals)} com o débito original.",
        ),
        Check(
            "Débito devolvido fora dos pagamentos",
            not counted,
            f"{len(counted)} débito(s) devolvido(s) ainda contado(s) como pagamento de despesa.",
        ),
    ]
    evidence = [_line_ref(ln) for ln in reversals] + [
        _line_ref(by_id[ln.paired_with]) for ln in reversals if ln.paired_with in by_id
    ]
    missing = [f"Débito original do estorno {_line_ref(ln)['rotulo']}" for ln in unpaired]
    diff = sum((-ln.amount for ln in counted), ZERO)
    if not reversals:
        status, why = S.NAO_APLICAVEL, "Nenhum estorno ou devolução no extrato do mês."
    elif counted:
        status, why = (
            S.DIVERGENTE,
            f"Pagamento devolvido contado como liquidação de despesa ({brl(diff)}).",
        )
    elif unpaired:
        status, why = (
            S.PENDENTE,
            f"{len(unpaired)} estorno(s) sem o débito original no período recebido.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Cada estorno tem o débito original e nenhum débito devolvido conta como pagamento.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(reversals) - len(unpaired), len(reversals)),
        diff,
        "ALTA" if counted else None,
        inputs={
            "estornos": sorted((str(ln.trn.id), str(ln.paired_with)) for ln in reversals),
            "contados": [str(x.trn.id) for x in counted],
        },
    )


# --------------------------------------------------------------------------- REC, DES


def rec_01(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    credits = [ln for ln in d.lines if ln.amount > 0]
    revenue = [ln for ln in credits if ln.kind == "arrecadacao"]
    other = [ln for ln in credits if ln.kind in NON_REVENUE]
    unknown = [ln for ln in credits if ln.kind == "nao_identificado" or ln.strength == "sugerido"]
    total = sum((ln.amount for ln in revenue), ZERO)
    statements = [x for x in d.documents if x.doc_type in TEXT_ONLY_REVENUE_DOCS]
    checks = [
        Check(
            "Receita do extrato",
            True,
            f"Arrecadação no extrato: {brl(total)} em {len(revenue)} crédito(s).",
        ),
        Check(
            "Transferências e estornos fora da receita",
            True,
            f"{len(other)} crédito(s) ({brl(sum((ln.amount for ln in other), ZERO))}) separados.",
        ),
        Check(
            "Créditos classificados (BAN-04)",
            not unknown,
            f"{len(unknown)} com origem a confirmar.",
        ),
        Check(
            "Extrato × demonstrativo de receitas",
            None,
            (
                "Demonstrativo recebido como texto: a comparação de valores ainda é feita por uma pessoa."
                if statements
                else "Demonstrativo de receitas não apresentado."
            ),
        ),
    ]
    evidence = [_line_ref(ln) for ln in revenue[:300]] + [_doc_ref(x) for x in statements]
    missing = (
        []
        if statements
        else ["Envie o demonstrativo de receitas (balancete ou relatório da administradora)."]
    )
    if statements:
        status, why = (
            S.COM_RESSALVA,
            f"Arrecadação no extrato de {brl(total)}; o demonstrativo foi recebido mas a comparação "
            "dos valores depende de conferência humana.",
        )
    else:
        status, why = (
            S.PENDENTE,
            f"Arrecadação no extrato de {brl(total)}, sem demonstrativo de receitas para comparar.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        None,
        inputs={
            "receita": str(total),
            "creditos": sorted((str(ln.trn.id), ln.kind) for ln in credits),
            "demonstrativos": sorted(str(x.id) for x in statements),
        },
    )


def des_01(d: AuditData) -> Outcome:
    due = [
        e
        for e in d.expenses
        if (e.expense.due_date or e.expense.issue_date) <= min(d.month_end, d.today)
    ]
    rows, unpaid, no_doc, wrong, indirect, ok = [], [], [], [], [], []
    total_diff = ZERO
    for e in due:
        paid = sum((-t.amount for t in e.payments if t.amount < 0), ZERO)
        via = any(
            (t.payee_document and t.payee_document in d.intermediary_docs) for t in e.payments
        )
        if not e.payments:
            unpaid.append(e)
        elif paid != e.expense.amount:
            wrong.append(e)
            total_diff += abs(paid - e.expense.amount)
        elif via:
            indirect.append(e)
        elif not e.has_document:
            no_doc.append(e)
        else:
            ok.append(e)
        rows.append(
            {
                "tipo": "despesa",
                "id": str(e.expense.id),
                "rotulo": f"{e.expense.description[:60]} · {brl(e.expense.amount)}",
                "pago": str(paid),
                "lancamentos": [str(t.id) for t in e.payments],
            }
        )
    checks = [
        Check("Despesas vencidas no mês", None if not due else True, f"{len(due)} despesa(s)."),
        Check(
            "Débito bancário de cada uma",
            None if not due else not unpaid,
            f"{len(unpaid)} sem débito ligado.",
        ),
        Check(
            "Documento de cada despesa paga",
            None if not due else not no_doc,
            f"{len(no_doc)} paga(s) sem documento apresentado.",
        ),
        Check(
            "Valor pago = valor da despesa (ao centavo)",
            None if not due else not wrong,
            f"{len(wrong)} com diferença: {brl(total_diff)}.",
        ),
        Check(
            "Pago diretamente ao favorecido",
            None if not due else not indirect,
            f"{len(indirect)} pago(s) por intermediário.",
        ),
    ]
    missing = [
        f"Débito bancário de: {e.expense.description[:60]} ({brl(e.expense.amount)})"
        for e in unpaid
    ] + [f"Documento de: {e.expense.description[:60]} ({brl(e.expense.amount)})" for e in no_doc]
    if not d.has_statement and not any(e.payments for e in due):
        status, why = S.PENDENTE, "Sem extrato do mês não há como demonstrar a liquidação."
        missing.append("Envie o extrato do mês.")
    elif not due:
        status, why = S.NAO_APLICAVEL, "Nenhuma despesa vencida no mês."
    elif wrong:
        status, why = (
            S.DIVERGENTE,
            f"{len(wrong)} pagamento(s) com valor diferente da despesa: {brl(total_diff)}.",
        )
    elif unpaid or no_doc:
        status, why = (
            S.PENDENTE,
            f"Liquidação não demonstrada: {len(unpaid)} sem débito ligado e {len(no_doc)} paga(s) "
            "sem documento apresentado.",
        )
    elif indirect:
        status, why = (
            S.COM_RESSALVA,
            f"Liquidação demonstrada; {len(indirect)} paga(s) por intermediário sem prova de recebimento final.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Toda despesa vencida tem documento e débito do mesmo valor. Conciliado financeiramente não é aprovado contratualmente.",
        )
    return Outcome(
        status,
        why,
        checks,
        rows[:300],
        missing,
        _pct(len(ok) + len(indirect), len(due)),
        total_diff,
        "ALTA" if wrong else None,
        inputs={"despesas": rows},
    )


EVALUATORS: dict[str, Callable[[AuditData], Outcome]] = {
    "DOC-01": doc_01,
    "DOC-02": doc_02,
    "BAN-01": ban_01,
    "BAN-02": ban_02,
    "BAN-03": ban_03,
    "BAN-04": ban_04,
    "BAN-05": ban_05,
    "REC-01": rec_01,
    "DES-01": des_01,
}


def not_implemented(control_id: str) -> Outcome:
    c = CONTROLS_BY_ID[control_id]
    return Outcome(
        S.NAO_AVALIADO,
        f"Controle previsto para o ciclo {c.cycle} do CondoOS Audit: o teste ainda não existe, "
        "por isso não é avaliado (e não conta como concluído).",
        [Check("Teste implementado", None, f"Previsto para o ciclo {c.cycle}.")],
        inputs={"ciclo": c.cycle},
    )
