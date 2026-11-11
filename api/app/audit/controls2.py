"""Controls of cycle 2 (D123): BAN-06, BAN-07, REC-02, REC-03, REC-04, DES-02, DES-03 and
DES-04. Deterministic, with the calculation memory of each result.

Unit data is internal: rows carry the unit code, never a resident's name. Tax rules are not
invented: the controls check arithmetic between notes, slips and payments, never rates.
"""

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.audit.controls import EVALUATORS, Check, Outcome, _line_ref, _need_statement, _pct
from app.audit.data import ZERO, AuditData, ExpenseView, _fold
from app.core.money import brl
from app.core.time import add_months
from app.db.enums import ControlStatus
from app.db.models import Document, Expense, ReceivableTitle

S = ControlStatus
CENT = Decimal("0.01")
FEDERAL = re.compile(r"irrf|\bir\b|\bpis\b|cofins|csll|darf|csrf|retenc")
INSS = re.compile(r"inss|\bgps\b|dctf|previd")
FGTS = re.compile(r"fgts")
ISS = re.compile(r"\biss\b|issqn")
PARCEL = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value)) if value not in (None, "") else ZERO
    except ArithmeticError:
        return ZERO


def _calc(label: str, value: Any, formula: str = "") -> dict[str, Any]:
    return {"label": label, "value": str(value), "formula": formula}


def _expense_view(d: AuditData, expense: Expense) -> ExpenseView | None:
    return next((e for e in d.expenses if e.expense.id == expense.id), None)


def _slip_text(expense: Expense, doc: Document | None) -> str:
    tributo = str((doc.extracted or {}).get("tributo", "")) if doc is not None else ""
    return _fold(f"{expense.description} {tributo}")


def _is_paid(d: AuditData, expense: Expense) -> bool:
    view = _expense_view(d, expense)
    return bool(view and view.paid >= expense.amount)


# --------------------------------------------------------------------------- BAN


def ban_06(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    transfers = [ln for ln in d.lines if ln.kind == "transferencia"]
    accounts = [a for a in d.accounts if a.account is not None and a.statement is not None]
    matched, external, missing_pair = [], [], []
    for ln in transfers:
        others = [
            o
            for a in accounts
            if a.account is not None and a.account.id != ln.trn.bank_account_id
            for o in a.lines
            if o.amount == -ln.amount and abs((o.trn.posted_at - ln.trn.posted_at).days) <= 3
        ]
        if others:
            matched.append(ln)
        elif len(accounts) <= 1:
            external.append(ln)
        else:
            missing_pair.append(ln)
    checks = [
        Check(
            "Transferências com contrapartida",
            not missing_pair,
            f"{len(matched)} de {len(transfers)} conferidas nas duas contas.",
        ),
        Check(
            "Origem ou destino em conta apresentada",
            not external,
            f"{len(external)} de/para conta não apresentada.",
        ),
    ]
    missing = [f"Contrapartida da transferência {_line_ref(x)['rotulo']}" for x in missing_pair]
    missing += [
        f"Extrato da outra conta da transferência {_line_ref(x)['rotulo']}" for x in external
    ]
    if not transfers:
        status, why = S.NAO_APLICAVEL, "Nenhuma transferência entre contas no extrato do mês."
    elif missing_pair:
        status, why = (
            S.PENDENTE,
            f"{len(missing_pair)} transferência(s) sem a contrapartida na outra conta apresentada.",
        )
    elif external:
        status, why = (
            S.COM_RESSALVA,
            f"{len(external)} transferência(s) de ou para conta não apresentada: crédito recebido não é origem comprovada.",
        )
    else:
        status, why = S.VALIDADO, "Toda transferência tem contrapartida conferida nas duas contas."
    return Outcome(
        status,
        why,
        checks,
        [_line_ref(x) for x in transfers],
        missing,
        _pct(len(matched), len(transfers)),
        inputs={
            "transferencias": sorted(
                (str(x.trn.id), str(x.trn.bank_account_id)) for x in transfers
            ),
            "contas": len(accounts),
        },
        calculation=[
            _calc("Transferências", len(transfers)),
            _calc("Com contrapartida", len(matched)),
            _calc("Conta não apresentada", len(external)),
        ],
    )


def ban_07(d: AuditData) -> Outcome:
    if (pending := _need_statement(d)) is not None:
        return pending
    indirect = [
        e
        for e in d.expenses
        if any(t.payee_document and t.payee_document in d.intermediary_docs for t in e.payments)
        or any(ln.intermediary and ln.trn in e.payments for ln in d.lines)
    ]
    confirmed: list[ExpenseView] = []
    open_: list[ExpenseView] = []
    for e in indirect:
        receipts = [d.receipts[r] for r in e.roles.get("pagamento", []) if r in d.receipts]
        cnpj = e.supplier.cnpj if e.supplier else None
        final = [
            r
            for r in receipts
            if cnpj and str((r.extracted or {}).get("documento_beneficiario") or "") == cnpj
        ]
        (confirmed if final else open_).append(e)
    checks = [
        Check(
            "Liquidação final comprovada",
            not open_,
            f"{len(confirmed)} de {len(indirect)} com comprovante do beneficiário final.",
        )
    ]
    missing = [
        f"Comprovante do pagamento final de: {e.expense.description[:60]} ({brl(e.expense.amount)})"
        for e in open_
    ]
    evidence = [
        {
            "tipo": "despesa",
            "id": str(e.expense.id),
            "rotulo": f"{e.expense.description[:60]} · {brl(e.expense.amount)}",
        }
        for e in indirect
    ]
    if not indirect:
        status, why = S.NAO_APLICAVEL, "Nenhum pagamento por intermediário no mês."
    elif open_:
        status, why = (
            S.PENDENTE,
            f"{len(open_)} pagamento(s) ao intermediário sem prova de liquidação ao favorecido final.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Todo pagamento por intermediário tem comprovante do beneficiário final.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(confirmed), len(indirect)),
        inputs={
            "indiretos": sorted(
                (str(e.expense.id), sorted(e.roles.get("pagamento", []), key=str).__repr__())
                for e in indirect
            )
        },
        calculation=[
            _calc("Pagos por intermediário", len(indirect)),
            _calc("Com liquidação final", len(confirmed)),
        ],
    )


# --------------------------------------------------------------------------- REC


def _our_numbers(d: AuditData) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for t in d.collection_lines:
        parts = t.external_id.split(":")
        number = (
            parts[3]
            if t.external_id.startswith("cnab240") and len(parts) > 3
            else parts[2] if len(parts) > 2 else ""
        )
        if number:
            out[number.lstrip("0")] = t.amount
    return out


def rec_02(d: AuditData) -> Outcome:
    month = d.competence
    titles = [t for t in d.titles if t.competence == month and t.status != "cancelado"]
    if not titles:
        return Outcome(
            S.PENDENTE,
            "Nenhum título da competência importado: sem a lista de boletos não há como conferir a cobrança por unidade.",
            [Check("Títulos da competência", None, "Não importados.")],
            missing=[
                "Importe a lista de títulos do mês (unidade, tipo, valor, vencimento, situação; sem nomes)."
            ],
            inputs={"titulos": []},
        )
    units = {u.id: u.code for u in d.units}
    with_title = {t.unit_id for t in titles}
    without = [code for uid, code in units.items() if uid not in with_title]
    groups: dict[tuple[Any, str], list[ReceivableTitle]] = defaultdict(list)
    for t in titles:
        groups[(t.unit_id, t.kind)].append(t)
    duplicates = [g for g in groups.values() if len(g) > 1]
    dup_amount = sum((sum((x.amount for x in g[1:]), ZERO) for g in duplicates), ZERO)
    paid = [t for t in titles if t.status == "pago"]
    numbers = _our_numbers(d)
    confirmed: set[Any] = set()
    for t in paid:
        if t.our_number and numbers.get(t.our_number.lstrip("0")) == (t.paid_amount or t.amount):
            confirmed.add(t.id)
    credits = [ln for ln in d.lines if ln.amount > 0 and ln.kind == "arrecadacao"]
    used: set[Any] = set()
    by_day: dict[date, list[ReceivableTitle]] = defaultdict(list)
    for t in paid:
        if t.id not in confirmed and t.paid_at is not None:
            by_day[t.paid_at].append(t)
    for day, group in sorted(by_day.items()):
        total = sum(((x.paid_amount or x.amount) for x in group), ZERO)
        match = next(
            (
                c
                for c in credits
                if c.trn.id not in used
                and c.amount == total
                and day <= c.trn.posted_at <= day + timedelta(days=3)
            ),
            None,
        )
        if match is not None:
            used.add(match.trn.id)
            confirmed |= {x.id for x in group}
    unconfirmed = [t for t in paid if t.id not in confirmed]
    code = {t.id: units.get(t.unit_id, "?") for t in titles}
    checks = [
        Check(
            "Toda unidade com título",
            not without,
            f"{len(units) - len(without)} de {len(units)} unidades com título na competência.",
        ),
        Check(
            "Sem título repetido",
            not duplicates,
            f"{len(duplicates)} repetição(ões) (mesma unidade, tipo e competência).",
        ),
        Check(
            "Pagamentos confirmados",
            not unconfirmed,
            f"{len(paid) - len(unconfirmed)} de {len(paid)} pagos com confirmação no retorno ou no extrato.",
        ),
    ]
    missing = [f"Título da unidade {c} na competência" for c in without]
    missing += [
        f"Confirmação do pagamento do título da unidade {code[t.id]} ({brl(t.paid_amount or t.amount)} em {t.paid_at:%d/%m/%Y})"
        for t in unconfirmed
        if t.paid_at
    ]
    if duplicates:
        status, why = (
            S.DIVERGENTE,
            f"{len(duplicates)} unidade(s) com título repetido: {brl(dup_amount)} cobrados a mais.",
        )
    elif without or unconfirmed:
        status, why = (
            S.PENDENTE,
            f"{len(without)} unidade(s) sem título e {len(unconfirmed)} pagamento(s) sem confirmação.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Toda unidade tem título, nenhum repetido e todo pagamento está confirmado no retorno ou no extrato.",
        )
    emitted = sum((t.amount for t in titles), ZERO)
    paid_total = sum(((t.paid_amount or t.amount) for t in paid), ZERO)
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "titulo",
                "id": str(t.id),
                "rotulo": f"Unidade {code[t.id]} · {t.kind} · {brl(t.amount)} · {t.status}",
            }
            for t in titles[:300]
        ],
        missing,
        _pct(len(paid) - len(unconfirmed), len(paid)),
        dup_amount,
        "ALTA" if duplicates else None,
        inputs={
            "titulos": sorted(
                (str(t.id), t.status, str(t.paid_amount), str(t.paid_at)) for t in titles
            ),
            "creditos": sorted(str(c.trn.id) for c in credits),
            "retornos": sorted(numbers),
        },
        calculation=[
            _calc("Títulos emitidos", f"{len(titles)} · {brl(emitted)}"),
            _calc("Pagos", f"{len(paid)} · {brl(paid_total)}"),
            _calc(
                "Confirmados",
                len(paid) - len(unconfirmed),
                "retorno (nosso número) ou crédito do dia = soma dos pagos",
            ),
            _calc("Em aberto", f"{len([t for t in titles if t.status == 'aberto'])}"),
        ],
    )


def rec_03(d: AuditData) -> Outcome:
    month = d.competence
    rows: list[dict[str, Any]] = []
    calc: list[dict[str, Any]] = []
    checks: list[Check] = []
    missing: list[str] = []
    diverge = pending = ressalva = 0
    total_diff = ZERO
    units = {u.id: u.code for u in d.units}
    applies = 0
    for utility in ("agua", "gas", "energia"):
        charged = [
            t
            for t in d.titles
            if t.kind == utility and t.competence == month and t.status != "cancelado"
        ]
        declared = d.profile.get(f"rateio_{utility}")
        if not charged and declared is not True:
            checks.append(
                Check(f"Rateio de {utility}", True, "Sem cobrança por unidade na competência.")
            )
            continue
        applies += 1
        reference = (
            charged[0].reference_competence
            if charged and charged[0].reference_competence
            else add_months(month, -1)
        )
        bills = [
            e for e in d.utility_expenses if e.category == utility and e.competence == reference
        ]
        bill = sum((e.amount for e in bills), ZERO)
        total = sum((t.amount for t in charged), ZERO)
        if not charged:
            pending += 1
            missing.append(f"Títulos do rateio de {utility} da competência.")
            checks.append(
                Check(f"Rateio de {utility}", None, "Perfil diz que há rateio, mas não há títulos.")
            )
            continue
        if not bills:
            pending += 1
            missing.append(f"Fatura de {utility} de {reference:%m/%Y}.")
            checks.append(
                Check(
                    f"{utility}: soma do rateio = fatura",
                    None,
                    f"Rateio de {brl(total)} sem a fatura de {reference:%m/%Y}.",
                )
            )
            continue
        diff = total - bill
        calc.append(_calc(f"{utility}: fatura de {reference:%m/%Y}", brl(bill)))
        calc.append(
            _calc(f"{utility}: soma do rateio", brl(total), "soma dos títulos da competência")
        )
        if diff != ZERO:
            diverge += 1
            total_diff += abs(diff)
            checks.append(
                Check(
                    f"{utility}: soma do rateio = fatura",
                    False,
                    f"Rateio {brl(total)}, fatura {brl(bill)}: diferença {brl(diff)}.",
                )
            )
            continue
        checks.append(
            Check(f"{utility}: soma do rateio = fatura", True, f"{brl(total)} = {brl(bill)}.")
        )
        readings = {
            r.unit_id: r.consumption
            for r in d.readings
            if r.utility == utility and r.competence == reference
        }
        if not readings or any(t.unit_id not in readings for t in charged):
            ressalva += 1
            missing.append(f"Leituras de {utility} de {reference:%m/%Y} por unidade.")
            checks.append(
                Check(
                    f"{utility}: rateio pela leitura",
                    None,
                    "Sem leitura de todas as unidades: só a aritmética foi validada.",
                )
            )
            continue
        consumption = sum(readings.values(), Decimal("0"))
        bad = 0
        for t in charged:
            expected = (
                (bill * readings[t.unit_id] / consumption).quantize(CENT, rounding=ROUND_HALF_UP)
                if consumption
                else ZERO
            )
            delta = t.amount - expected
            ok = abs(delta) <= CENT
            bad += 0 if ok else 1
            rows.append(
                {
                    "servico": utility,
                    "unidade": units.get(t.unit_id, "?"),
                    "consumo": str(readings[t.unit_id]),
                    "cobrado": str(t.amount),
                    "calculado": str(expected),
                    "diferenca": str(delta),
                }
            )
        calc.append(_calc(f"{utility}: consumo total", consumption, "soma das leituras"))
        if bad:
            diverge += 1
            total_diff += sum(
                (
                    abs(Decimal(r["diferenca"]))
                    for r in rows
                    if r["servico"] == utility and abs(Decimal(r["diferenca"])) > CENT
                ),
                ZERO,
            )
            checks.append(
                Check(
                    f"{utility}: rateio pela leitura",
                    False,
                    f"{bad} unidade(s) cobradas fora do cálculo (fatura × consumo ÷ total).",
                )
            )
        else:
            checks.append(
                Check(
                    f"{utility}: rateio pela leitura",
                    True,
                    "Cada unidade paga fatura × consumo da unidade ÷ consumo total (até R$ 0,01).",
                )
            )
    if rows:
        calc.append(
            {
                "label": "Rateio por unidade",
                "value": "",
                "formula": "fatura × consumo da unidade ÷ consumo total",
                "rows": rows,
            }
        )
    if applies == 0:
        if all(d.profile.get(f"rateio_{u}") is False for u in ("agua", "gas", "energia")):
            status, why = (
                S.NAO_APLICAVEL,
                "O perfil de auditoria declara que não há rateio de consumo.",
            )
        else:
            status, why = (
                S.PENDENTE,
                "Sem cobrança de consumo por unidade e sem declaração no perfil de auditoria.",
            )
            missing.append("Informe no perfil de auditoria se água, gás ou energia são rateados.")
    elif diverge:
        status, why = S.DIVERGENTE, f"Rateio diferente da fatura ou da leitura: {brl(total_diff)}."
    elif pending:
        status, why = S.PENDENTE, "Falta fatura ou cobrança do rateio: " + "; ".join(missing[:3])
    elif ressalva:
        status, why = (
            S.COM_RESSALVA,
            "A soma do rateio confere com a fatura, mas sem leituras a divisão por unidade não foi validada.",
        )
    else:
        status, why = S.VALIDADO, "Rateio igual à fatura e à leitura de cada unidade."
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "despesa",
                "id": str(e.id),
                "rotulo": f"Fatura {e.category} {e.competence:%m/%Y} · {brl(e.amount)}",
            }
            for e in d.utility_expenses
        ],
        missing,
        differences=total_diff,
        severity="MEDIA" if diverge else None,
        inputs={
            "titulos": sorted(
                (str(t.id), str(t.amount))
                for t in d.titles
                if t.competence == month and t.kind in ("agua", "gas", "energia")
            ),
            "faturas": sorted((str(e.id), str(e.amount)) for e in d.utility_expenses),
            "leituras": sorted((str(r.id), str(r.consumption)) for r in d.readings),
            "perfil": {k: v for k, v in d.profile.items() if k.startswith("rateio")},
        },
        calculation=calc,
    )


def remaining_balance(t: ReceivableTitle, until: date) -> Decimal:
    if t.cancelled_at is not None and t.cancelled_at <= until:
        return ZERO
    if t.status == "cancelado" and t.cancelled_at is None:
        return ZERO
    paid = (t.paid_amount or t.amount) if t.paid_at is not None and t.paid_at <= until else ZERO
    return max(t.amount - paid, ZERO)


def rec_04(d: AuditData) -> Outcome:
    first, last = d.competence, d.month_end
    titles = [t for t in d.titles if t.due_date <= last]
    if not titles:
        return Outcome(
            S.PENDENTE,
            "Nenhum título importado: sem a situação dos títulos não se afirma nada sobre inadimplência.",
            [Check("Títulos com situação", None, "Não importados.")],
            missing=["Importe a lista de títulos com a situação de pagamento (sem nomes)."],
            inputs={"titulos": []},
        )
    units = {u.id: u.code for u in d.units}
    inconsistent = [
        t
        for t in titles
        if (t.status == "pago" and t.paid_at is None)
        or (t.status == "aberto" and t.paid_at is not None)
    ]
    rows = []
    mismatch = []
    total_open = ZERO
    for uid in sorted({t.unit_id for t in titles}, key=lambda u: units.get(u, "")):
        mine = [t for t in titles if t.unit_id == uid]
        start = sum(
            (remaining_balance(t, first - timedelta(days=1)) for t in mine if t.due_date < first),
            ZERO,
        )
        emitted = sum((t.amount for t in mine if first <= t.due_date <= last), ZERO)
        paid = sum(
            ((t.paid_amount or t.amount) for t in mine if t.paid_at and first <= t.paid_at <= last),
            ZERO,
        )
        cancelled = sum(
            (t.amount for t in mine if t.cancelled_at and first <= t.cancelled_at <= last), ZERO
        )
        closing = sum((remaining_balance(t, last) for t in mine), ZERO)
        total_open += closing
        code = units.get(uid, "?")
        previous = d.previous_rec04.get(code)
        rows.append(
            {
                "unidade": code,
                "saldo_inicial": str(start),
                "emitidos": str(emitted),
                "pagos": str(paid),
                "cancelados": str(cancelled),
                "saldo_final": str(closing),
                "fechamento_anterior": previous,
            }
        )
        if previous is not None and Decimal(previous) != start:
            mismatch.append((code, Decimal(previous) - start))
    diff = sum((abs(x) for _, x in mismatch), ZERO)
    checks = [
        Check(
            "Situação dos títulos coerente",
            not inconsistent,
            f"{len(inconsistent)} título(s) pago sem data ou em aberto com data de pagamento.",
        ),
        Check(
            "Saldo inicial = fechamento do mês anterior",
            None if not d.previous_rec04 else not mismatch,
            (
                "Sem fechamento anterior auditado."
                if not d.previous_rec04
                else f"{len(mismatch)} unidade(s) com diferença."
            ),
        ),
    ]
    missing = [
        f"Corrija a situação do título da unidade {units.get(t.unit_id, '?')} de {t.competence:%m/%Y}"
        for t in inconsistent
    ]
    debtors = sum(1 for r in rows if Decimal(str(r["saldo_final"])) > 0)
    if mismatch:
        status, why = (
            S.DIVERGENTE,
            f"O saldo em aberto no início difere do fechamento do mês anterior em {len(mismatch)} unidade(s): títulos mudaram depois do fechamento.",
        )
    elif inconsistent:
        status, why = (
            S.PENDENTE,
            f"{len(inconsistent)} título(s) com situação incoerente: corrija antes de afirmar a inadimplência.",
        )
    elif not d.previous_rec04:
        status, why = (
            S.COM_RESSALVA,
            f"Inadimplência reconstruída por título: {debtors} unidade(s) com {brl(total_open)} em aberto. Primeiro mês auditado: sem fechamento anterior para conferir.",
        )
    else:
        status, why = (
            S.VALIDADO,
            f"Inadimplência reconstruída por título: {debtors} unidade(s) com {brl(total_open)} em aberto, contínua com o mês anterior.",
        )
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "titulo",
                "id": str(t.id),
                "rotulo": f"Unidade {units.get(t.unit_id, '?')} · {t.competence:%m/%Y} · {brl(t.amount)} · {t.status}",
            }
            for t in titles
            if remaining_balance(t, last) > 0
        ][:300],
        missing,
        None,
        diff,
        "ALTA" if mismatch else None,
        inputs={
            "titulos": sorted(
                (str(t.id), t.status, str(t.paid_at), str(t.paid_amount), str(t.cancelled_at))
                for t in titles
            ),
            "anterior": d.previous_rec04,
        },
        calculation=[
            _calc("Unidades com saldo em aberto", debtors),
            _calc(
                "Total em aberto no fim do mês",
                brl(total_open),
                "Σ por unidade: inicial + emitidos − pagos − cancelados",
            ),
            {
                "label": "Por unidade (dado interno, sem nomes)",
                "value": "",
                "formula": "saldo inicial + emitidos − pagos − cancelados = saldo final",
                "rows": rows,
            },
        ],
    )


# --------------------------------------------------------------------------- DES


def _retentions(d: AuditData, kinds: tuple[str, ...]) -> tuple[Decimal, list[dict[str, Any]]]:
    total, rows = ZERO, []
    for n in d.notes:
        v = n.extracted or {}
        amount = sum((_money(v.get(f"retencao_{k}")) for k in kinds), ZERO)
        if amount > 0:
            total += amount
            rows.append(
                {"nota": str(v.get("numero") or n.original_filename), "retencoes": str(amount)}
            )
    return total, rows


def des_02(d: AuditData) -> Outcome:
    retained, rows = _retentions(d, ("ir", "pis", "cofins", "csll"))
    slips = [(e, doc) for e, doc in d.tax_slips if FEDERAL.search(_slip_text(e, doc))]
    total = sum((e.amount for e, _ in slips), ZERO)
    unpaid = [
        e
        for e, _ in slips
        if (e.due_date or e.issue_date) <= min(d.today, d.month_end + timedelta(days=40))
        and not _is_paid(d, e)
    ]
    diff = total - retained
    checks = [
        Check("Retenções federais das notas", True, f"{brl(retained)} em {len(rows)} nota(s)."),
        Check(
            "Guias federais da competência",
            None if not slips and retained else True,
            f"{len(slips)} guia(s): {brl(total)}.",
        ),
        Check(
            "Guia = retenções (ao centavo)",
            None if not slips else diff == ZERO,
            f"Diferença {brl(diff)}.",
        ),
        Check(
            "Guias vencidas pagas",
            None if not slips else not unpaid,
            f"{len(unpaid)} sem débito bancário.",
        ),
    ]
    missing = []
    if retained and not slips:
        missing.append(f"Guia federal (DARF) da competência com {brl(retained)} de retenções.")
    missing += [f"Pagamento da guia {e.description[:60]} ({brl(e.amount)})" for e in unpaid]
    if not retained and not slips:
        status, why = (
            S.NAO_APLICAVEL,
            "Nenhuma nota da competência com retenção federal e nenhuma guia federal.",
        )
    elif retained and not slips:
        status, why = S.PENDENTE, f"{brl(retained)} retidos nas notas sem guia federal apresentada."
    elif diff != ZERO and retained:
        status, why = (
            S.DIVERGENTE,
            f"Guia de {brl(total)} para {brl(retained)} retidos: diferença {brl(diff)}.",
        )
    elif not retained:
        status, why = (
            S.COM_RESSALVA,
            f"Guia federal de {brl(total)} sem nota com retenção na competência: confira a origem.",
        )
    elif unpaid:
        status, why = (
            S.PENDENTE,
            f"Guia confere com as retenções, mas {len(unpaid)} sem pagamento demonstrado.",
        )
    else:
        status, why = S.VALIDADO, "Guia federal igual à soma das retenções das notas, e paga."
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "despesa",
                "id": str(e.id),
                "rotulo": f"{e.description[:60]} · {brl(e.amount)}",
            }
            for e, _ in slips
        ]
        + [
            {"tipo": "documento", "id": str(n.id), "rotulo": n.original_filename}
            for n in d.notes
            if any(
                _money((n.extracted or {}).get(f"retencao_{k}"))
                for k in ("ir", "pis", "cofins", "csll")
            )
        ],
        missing,
        None,
        abs(diff) if retained and slips else ZERO,
        "ALTA" if retained and slips and diff else None,
        inputs={
            "retencoes": rows,
            "guias": sorted((str(e.id), str(e.amount), _is_paid(d, e)) for e, _ in slips),
        },
        calculation=[
            _calc(
                "Retenções federais (IR, PIS, COFINS, CSLL)",
                brl(retained),
                "soma das notas da competência",
            ),
            _calc("Guias federais", brl(total)),
            _calc("Diferença", brl(diff), "guias − retenções"),
            {"label": "Notas com retenção", "value": "", "formula": "", "rows": rows},
        ],
    )


def des_03(d: AuditData) -> Outcome:
    staff = d.profile.get("funcionarios_proprios")
    iss_retained, iss_rows = _retentions(d, ("iss",))
    iss_expected = iss_retained > 0 or d.profile.get("iss_retido") is True
    checks, missing, calc = [], [], []
    divergent = ZERO
    pending = 0
    expected: list[tuple[str, re.Pattern[str]]] = []
    if staff is None:
        pending += 1
        missing.append("Informe no perfil de auditoria se o condomínio tem funcionários próprios.")
        checks.append(Check("Funcionários próprios", None, "Não informado no perfil."))
    elif staff:
        expected += [("FGTS", FGTS), ("INSS/DCTFWeb", INSS)]
    for label, pattern in expected:
        found = [(e, doc) for e, doc in d.tax_slips if pattern.search(_slip_text(e, doc))]
        if not found:
            pending += 1
            missing.append(f"Guia de {label} da competência.")
            checks.append(Check(f"Guia de {label}", None, "Não apresentada."))
            continue
        unpaid = [
            e for e, _ in found if (e.due_date or e.issue_date) <= d.today and not _is_paid(d, e)
        ]
        checks.append(
            Check(
                f"Guia de {label} paga",
                not unpaid,
                f"{len(found)} guia(s), {brl(sum((e.amount for e, _ in found), ZERO))}; {len(unpaid)} vencida(s) sem débito.",
            )
        )
        pending += len(unpaid)
        missing += [f"Pagamento da guia {e.description[:60]}" for e in unpaid]
    if iss_expected:
        found = [(e, doc) for e, doc in d.tax_slips if ISS.search(_slip_text(e, doc))]
        total = sum((e.amount for e, _ in found), ZERO)
        calc.append(_calc("ISS retido nas notas", brl(iss_retained)))
        calc.append(_calc("Guias de ISS", brl(total)))
        if not found:
            pending += 1
            missing.append(f"Guia de ISS da competência ({brl(iss_retained)} retidos).")
            checks.append(Check("Guia de ISS = ISS retido", None, "Guia não apresentada."))
        elif iss_retained and total != iss_retained:
            divergent += abs(total - iss_retained)
            checks.append(
                Check(
                    "Guia de ISS = ISS retido",
                    False,
                    f"Guia {brl(total)}, retido {brl(iss_retained)}.",
                )
            )
        else:
            checks.append(Check("Guia de ISS = ISS retido", True, f"{brl(total)}."))
    late = [e for e, _ in d.previous_tax_slips]
    checks.append(
        Check(
            "Guias de meses anteriores pagas no mês",
            True,
            f"{len(late)} guia(s) de competência anterior com vencimento no mês.",
        )
    )
    if staff is False and not iss_expected:
        status, why = (
            S.NAO_APLICAVEL,
            "Perfil sem funcionários próprios e nenhuma nota com ISS retido.",
        )
    elif divergent:
        status, why = (
            S.DIVERGENTE,
            f"Guia de ISS diferente do ISS retido nas notas: {brl(divergent)}.",
        )
    elif pending:
        status, why = S.PENDENTE, "Falta guia, pagamento ou informação do perfil: " + "; ".join(
            missing[:3]
        )
    else:
        status, why = (
            S.VALIDADO,
            "As guias periódicas esperadas pelo perfil estão presentes, conferem e foram pagas.",
        )
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "despesa",
                "id": str(e.id),
                "rotulo": f"{e.description[:60]} · {brl(e.amount)}",
            }
            for e, _ in d.tax_slips + d.previous_tax_slips
        ],
        missing,
        None,
        divergent,
        "MEDIA" if divergent else None,
        inputs={
            "perfil": {k: d.profile.get(k) for k in ("funcionarios_proprios", "iss_retido")},
            "guias": sorted((str(e.id), str(e.amount), _is_paid(d, e)) for e, _ in d.tax_slips),
            "iss": iss_rows,
        },
        calculation=[
            *calc,
            {"label": "Notas com ISS retido", "value": "", "formula": "", "rows": iss_rows},
        ],
    )


def des_04(d: AuditData) -> Outcome:
    groups: dict[str, list[tuple[Expense, int, int]]] = defaultdict(list)
    for e, doc in d.installment_slips:
        text = _slip_text(e, doc)
        m = PARCEL.search(text)
        if not m:
            continue
        key = PARCEL.sub("", text).replace("parcela", "").replace("parcelamento", "")
        key = " ".join(re.sub(r"[^a-z0-9 ]", " ", key).split())[:80] or "parcelamento"
        groups[key].append((e, int(m.group(1)), int(m.group(2))))
    current = {
        k: v for k, v in groups.items() if any(e.competence == d.competence for e, _, _ in v)
    }
    declared = d.profile.get("parcelamento_fiscal")
    if not current:
        if declared is False:
            return Outcome(
                S.NAO_APLICAVEL,
                "O perfil de auditoria declara que não há parcelamento fiscal e nenhuma guia de parcela foi recebida.",
                [Check("Guias de parcela", True, "Nenhuma no mês.")],
                [
                    {
                        "tipo": "perfil",
                        "id": "AUDIT",
                        "rotulo": "Perfil de auditoria: sem parcelamento fiscal",
                    }
                ],
                inputs={"perfil": declared},
            )
        need = (
            "Informe no perfil de auditoria se há parcelamento fiscal."
            if declared is None
            else "Guia da parcela do mês."
        )
        return Outcome(
            S.PENDENTE,
            "Nenhuma guia de parcela no mês: "
            + (
                "o perfil não diz se há parcelamento."
                if declared is None
                else "o perfil diz que há parcelamento."
            ),
            [Check("Guias de parcela", None, "Nenhuma no mês.")],
            missing=[need],
            inputs={"perfil": declared, "grupos": []},
        )
    checks, missing, rows = [], [], []
    ressalva = pending = 0
    for key, items in current.items():
        items.sort(key=lambda x: (x[0].competence, x[1]))
        prev = None
        for e, n, total in items:
            rows.append(
                {
                    "parcelamento": key,
                    "competencia": e.competence.strftime("%m/%Y"),
                    "parcela": f"{n:02d}/{total:02d}",
                    "valor": str(e.amount),
                    "paga": _is_paid(d, e) if e.competence == d.competence else None,
                }
            )
            if e.competence == d.competence and prev is not None:
                pn, pt = prev
                if total != pt:
                    ressalva += 1
                    missing.append(
                        f"Documento do acordo que mudou o total de parcelas de {pt} para {total} ({key})."
                    )
                    checks.append(
                        Check(
                            f"{key}: total de parcelas",
                            False,
                            f"{pn:02d}/{pt:02d} seguida de {n:02d}/{total:02d}: exige documento do novo acordo.",
                        )
                    )
                elif n != pn + 1:
                    ressalva += 1
                    missing.append(
                        f"Explique a sequência {pn:02d}/{pt:02d} → {n:02d}/{total:02d} ({key})."
                    )
                    checks.append(
                        Check(f"{key}: sequência", False, f"{pn:02d} seguida de {n:02d}.")
                    )
                else:
                    checks.append(
                        Check(
                            f"{key}: sequência", True, f"{pn:02d}/{pt:02d} → {n:02d}/{total:02d}."
                        )
                    )
            if (
                e.competence == d.competence
                and (e.due_date or e.issue_date) <= d.today
                and not _is_paid(d, e)
            ):
                pending += 1
                missing.append(f"Pagamento da parcela {n:02d}/{total:02d} ({key}).")
            prev = (n, total)
    if pending:
        status, why = S.PENDENTE, f"{pending} parcela(s) vencida(s) sem pagamento demonstrado."
    elif ressalva:
        status, why = (
            S.COM_RESSALVA,
            "Numeração das parcelas não segue a sequência: exige o documento do acordo (não prova duplicidade).",
        )
    else:
        status, why = S.VALIDADO, "Parcelas em sequência, com o mesmo total, e pagas."
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "despesa",
                "id": str(e.id),
                "rotulo": f"{e.description[:60]} · {brl(e.amount)}",
            }
            for v in current.values()
            for e, _, _ in v
        ],
        missing,
        inputs={"parcelas": rows},
        calculation=[
            {
                "label": "Parcelas por acordo",
                "value": "",
                "formula": "n/total em sequência",
                "rows": rows,
            }
        ],
    )


EVALUATORS_2 = {
    "BAN-06": ban_06,
    "BAN-07": ban_07,
    "REC-02": rec_02,
    "REC-03": rec_03,
    "REC-04": rec_04,
    "DES-02": des_02,
    "DES-03": des_03,
    "DES-04": des_04,
}
EVALUATORS.update(EVALUATORS_2)
