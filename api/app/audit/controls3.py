"""Controls of cycle 3 (D124): CON-01, CON-02, CON-03 (A7, contracts and execution), BAN-08,
BAN-09, GOV-01 (A8, funds, investments and budget), GOV-02 (A7/A8, insurance and technical
obligations) and DOC-03 (formal approval of the accounts).

Deterministic, with the calculation memory of each result. Global rules hold: a contract,
an approval or a document that was not presented is "não apresentado" (PENDENTE), never
"inexistente"; a positive fund balance is not segregated backing; a budget variance is not
an error, only an unexplained one is a reservation.
"""

import re
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.audit.controls import EVALUATORS, Check, Outcome, _pct
from app.audit.data import INVESTMENT_KINDS, ZERO, AccountView, AuditData, ExpenseView, Line
from app.core.money import brl
from app.core.time import add_months
from app.db.enums import (
    AccountsApprovalBody,
    ApprovalKind,
    BoardPosition,
    ComplianceApplicability,
    ContractNature,
    ControlStatus,
)
from app.db.models import Contract
from app.matching.categories import category_label
from app.rules.contracts import contract_value_at, terms_at

S = ControlStatus
CENT = Decimal("0.01")
PARCEL = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")
R12_EXEMPT = ["energia", "agua", "gas", "tributos"]
BUDGET_TOLERANCE_PCT = Decimal("10")  # GOV-01, rule 1.0: variance above this needs a note
PAIR_DAYS = 3  # BAN-09: an investment and its counterpart within this many days


def _calc(label: str, value: Any, formula: str = "") -> dict[str, Any]:
    return {"label": label, "value": str(value), "formula": formula}


def _expense_ref(e: ExpenseView, **extra: Any) -> dict[str, Any]:
    x = e.expense
    return {
        "tipo": "despesa",
        "id": str(x.id),
        "rotulo": f"{x.description[:60]} · {brl(x.amount)}",
        **extra,
    }


def _contract_ref(c: Contract) -> dict[str, Any]:
    who = c.supplier_name or "fornecedor do cadastro"
    return {
        "tipo": "contrato",
        "id": str(c.id),
        "rotulo": f"{c.object[:60]} · {who[:40]}",
        "documento_id": str(c.source_document_id) if c.source_document_id else None,
    }


def _month_end(month: date) -> date:
    return add_months(month, 1) - timedelta(days=1)


# --------------------------------------------------------------------------- contracts (A7)


def contract_end(d: AuditData, c: Contract) -> date | None:
    """The end date in force at the competence: the latest amendment that set one, else the
    contract's own (D66)."""
    ends = [
        a
        for a in d.c3.amendments.get(c.id, [])
        if a.end_date is not None and a.effective_date.replace(day=1) <= d.competence
    ]
    if ends:
        latest = max(ends, key=lambda a: (a.effective_date, a.created_at or a.effective_date))
        return latest.end_date
    return c.end_date


def in_force(d: AuditData, c: Contract) -> bool:
    end = contract_end(d, c)
    return c.start_date <= d.month_end and (end is None or end >= d.competence)


def contract_of(d: AuditData, e: ExpenseView) -> tuple[Contract | None, str]:
    """The contract an expense is billed under: the one linked to it, else the only contract
    of the same supplier in force. Two candidates is ambiguous (never chosen at random)."""
    by_id = {c.id: c for c in d.c3.contracts}
    if e.expense.contract_id is not None and e.expense.contract_id in by_id:
        return by_id[e.expense.contract_id], "vinculado"
    if e.expense.supplier_id is None:
        return None, ""
    same = [c for c in d.c3.contracts if c.supplier_id == e.expense.supplier_id and in_force(d, c)]
    if len(same) == 1:
        return same[0], "mesmo fornecedor"
    if len(same) > 1:
        return None, "ambiguo"
    return None, ""


def _billing_due(c: Contract, month: date) -> bool:
    if c.nature != ContractNature.CONTINUO.value or not c.billing_frequency_months:
        return False
    start = c.start_date.replace(day=1)
    months = (month.year - start.year) * 12 + month.month - start.month
    return months >= 0 and months % c.billing_frequency_months == 0


def con_01(d: AuditData) -> Outcome:
    contracts = [c for c in d.c3.contracts if in_force(d, c)]
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    above: list[str] = []
    below: list[str] = []
    expired: list[str] = []
    ambiguous: list[str] = []
    no_index: list[str] = []
    no_scope: set[uuid.UUID] = set()
    billed: set[uuid.UUID] = set()
    diff_total = ZERO
    compared = 0
    for e in d.expenses:
        contract, how = contract_of(d, e)
        if how == "ambiguo":
            ambiguous.append(e.expense.description[:60])
            evidence.append(_expense_ref(e, situacao="mais de um contrato vigente do fornecedor"))
            continue
        if contract is None:
            continue
        billed.add(contract.id)
        compared += 1
        amount = e.expense.amount
        row: dict[str, Any] = {
            "despesa": e.expense.description[:60],
            "contrato": contract.object[:60],
            "vinculo": how,
            "valor_nota": str(amount),
        }
        if not (contract.object or contract.scope_items):
            no_scope.add(contract.id)
        if not in_force(d, contract):
            end = contract_end(d, contract)
            expired.append(e.expense.description[:60])
            row["situacao"] = (
                f"fora da vigência (até {end:%d/%m/%Y})" if end else "fora da vigência"
            )
        elif contract.nature == ContractNature.PONTUAL.value:
            total = contract.total_value or ZERO
            row["valor_contrato"] = str(total)
            row["situacao"] = "pontual: parcelas em CON-03"
        else:
            expected = contract_value_at(
                contract, d.c3.amendments.get(contract.id, []), d.competence, d.c3.index_table
            )
            base, since = terms_at(contract, d.c3.amendments.get(contract.id, []), d.competence)
            row["valor_base"] = str(base) if base is not None else ""
            row["aditivo_desde"] = since.isoformat() if since else ""
            if expected is None:
                no_index.append(e.expense.description[:60])
                row["situacao"] = "reajuste sem índice disponível"
            else:
                expected = expected.quantize(CENT, ROUND_HALF_UP)
                diff = amount - expected
                row["valor_contratado"] = str(expected)
                row["diferenca"] = str(diff)
                if diff > 0:
                    above.append(e.expense.description[:60])
                    diff_total += diff
                    row["situacao"] = "acima do valor contratado"
                elif diff < 0:
                    below.append(e.expense.description[:60])
                    row["situacao"] = "abaixo do valor contratado"
                else:
                    row["situacao"] = "confere"
        rows.append(row)
        evidence.append(_expense_ref(e, situacao=row["situacao"]))
    missing_billing = [c for c in contracts if _billing_due(c, d.competence) and c.id not in billed]
    evidence += [_contract_ref(c) for c in contracts]
    checks = [
        Check(
            "Contrato aplicável à competência",
            not expired and not ambiguous,
            f"{compared} nota(s) de contrato; {len(expired)} fora da vigência; "
            f"{len(ambiguous)} com mais de um contrato possível.",
        ),
        Check(
            "Valor bruto conferido com o contratado (com aditivos e reajuste)",
            None if no_index else not above and not below,
            f"{len(above)} acima, {len(below)} abaixo, {len(no_index)} sem índice do reajuste.",
        ),
        Check(
            "Escopo declarado no contrato",
            not no_scope,
            (
                "Objeto ou itens de escopo presentes em todos os contratos usados."
                if not no_scope
                else f"{len(no_scope)} contrato(s) sem objeto nem escopo."
            ),
        ),
        Check(
            "Faturamento esperado do mês apresentado",
            not missing_billing,
            (
                "Todos os contratos com faturamento no mês têm nota."
                if not missing_billing
                else "Sem nota no mês: " + ", ".join(c.object[:40] for c in missing_billing[:5])
            ),
        ),
    ]
    missing = [f"Nota do mês do contrato: {c.object[:60]}." for c in missing_billing]
    missing += [f"Defina o contrato da despesa: {x}." for x in ambiguous]
    if not contracts and not compared and not ambiguous:
        status, why = (
            S.NAO_APLICAVEL,
            "Nenhum contrato vigente na competência e nenhuma nota de contrato.",
        )
    elif above:
        status, why = (
            S.DIVERGENTE,
            f"{len(above)} nota(s) acima do valor contratado em vigor, somando "
            f"{brl(diff_total)} de diferença.",
        )
    elif expired or ambiguous or below or no_index or missing_billing or no_scope:
        status, why = (
            S.COM_RESSALVA,
            "Preço conferido, com pontos de atenção: "
            + "; ".join(
                part
                for part in (
                    f"{len(expired)} nota(s) fora da vigência" if expired else "",
                    f"{len(ambiguous)} sem contrato definido" if ambiguous else "",
                    f"{len(below)} abaixo do contratado" if below else "",
                    f"{len(no_index)} sem índice do reajuste" if no_index else "",
                    (
                        f"{len(missing_billing)} faturamento(s) não apresentado(s)"
                        if missing_billing
                        else ""
                    ),
                    f"{len(no_scope)} contrato(s) sem escopo" if no_scope else "",
                )
                if part
            )
            + ".",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Notas de contrato dentro da vigência e iguais ao valor contratado em vigor "
            "(aditivos e reajuste aplicados).",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence[:300],
        missing,
        _pct(compared - len(above) - len(expired), compared) if compared else None,
        diff_total,
        "ALTA" if above else None,
        inputs={"linhas": rows, "contratos": sorted(str(c.id) for c in contracts)},
        calculation=[
            _calc("Contratos vigentes", len(contracts)),
            _calc("Notas comparadas", compared),
            _calc("Diferença acima do contratado", diff_total, "Σ (valor da nota − contratado)"),
            {
                "label": "Notas de contrato",
                "value": str(len(rows)),
                "formula": "contratado = valor do contrato ou do aditivo × reajuste do índice",
                "rows": rows[:200],
            },
        ],
    )


def _exempt(d: AuditData) -> set[str]:
    params = d.c3.rule_params.get("R12") or {}
    return set(params.get("exempt_categories", R12_EXEMPT))


def con_02(d: AuditData) -> Outcome:
    if not d.expenses:
        return Outcome(
            S.PENDENTE,
            "Nenhuma despesa registrada no mês: sem elas não há serviço extraordinário a testar.",
            [Check("Despesas do mês", None, "Nenhuma recebida.")],
            missing=["Envie as notas do mês."],
            inputs={"despesas": []},
        )
    limits = d.c3.limits or {}
    by_category = limits.get("by_category", {})
    exempt = _exempt(d)
    extra = [
        e
        for e in d.expenses
        if contract_of(d, e) == (None, "") and e.expense.category not in exempt
    ]
    if not extra:
        return Outcome(
            S.NAO_APLICAVEL,
            "Nenhum serviço extraordinário no mês: toda despesa é de contrato ou de categoria "
            "isenta (consumo e tributos).",
            [Check("Serviço extraordinário", True, "Nenhum no mês.")],
            [_expense_ref(e) for e in d.expenses[:50]],
            inputs={"despesas": sorted(str(e.expense.id) for e in d.expenses)},
        )
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    no_limit: list[str] = []
    no_auth: list[str] = []
    late: list[str] = []
    no_doc: list[str] = []
    no_accept: list[str] = []
    within = 0
    for e in extra:
        x = e.expense
        raw = by_category.get(x.category, limits.get("default"))
        approvals = d.c3.approvals.get(x.id, [])
        auth = [a for a in approvals if a.kind == ApprovalKind.AUTORIZACAO.value]
        accept = [a for a in approvals if a.kind == ApprovalKind.ACEITE.value]
        row: dict[str, Any] = {
            "despesa": x.description[:60],
            "categoria": category_label(x.category),
            "valor": str(x.amount),
            "alcada": str(raw) if raw is not None else "",
            "autorizacao": auth[0].approved_at.isoformat() if auth else "",
            "aceite": accept[0].approved_at.isoformat() if accept else "",
        }
        if raw is None:
            no_limit.append(x.description[:60])
            row["situacao"] = "sem alçada configurada"
        elif x.amount <= Decimal(str(raw)):
            within += 1
            row["situacao"] = "dentro da alçada do síndico"
        elif not auth:
            no_auth.append(x.description[:60])
            row["situacao"] = "autorização não apresentada"
        else:
            first = min(auth, key=lambda a: a.approved_at)
            situations = []
            if first.approved_at > x.issue_date:
                late.append(x.description[:60])
                situations.append("autorizada depois da nota")
            if not any(a.source_document_id for a in auth):
                no_doc.append(x.description[:60])
                situations.append("autorização sem documento")
            if not accept:
                no_accept.append(x.description[:60])
                situations.append("aceite não registrado")
            row["situacao"] = "; ".join(situations) or "autorizada e aceita"
        rows.append(row)
        evidence.append(_expense_ref(e, situacao=row["situacao"]))
    checks = [
        Check(
            "Alçada configurada",
            not no_limit,
            (
                "Alçada definida para todas as categorias."
                if not no_limit
                else f"{len(no_limit)} despesa(s) sem alçada para a categoria."
            ),
        ),
        Check(
            "Autorização dentro da alçada, antes do serviço",
            not no_auth and not late,
            f"{len(no_auth)} sem autorização apresentada; {len(late)} autorizada(s) depois "
            "da nota.",
        ),
        Check(
            "Documento da autorização (proposta, ata ou ordem de serviço)",
            not no_doc,
            f"{len(no_doc)} autorização(ões) sem documento.",
        ),
        Check(
            "Aceite do serviço registrado",
            not no_accept,
            f"{len(no_accept)} serviço(s) acima da alçada sem aceite.",
        ),
    ]
    missing = [f"Autorização (proposta aprovada ou ata) de: {x}." for x in no_auth]
    missing += [f"Aceite do serviço: {x}." for x in no_accept]
    missing += [f"Documento da autorização: {x}." for x in no_doc]
    if no_limit:
        missing.append("Configure as alçadas de aprovação do condomínio (Configurações).")
    if no_auth or no_accept or no_limit:
        status, why = (
            S.PENDENTE,
            "Serviço extraordinário acima da alçada sem autorização ou aceite apresentado "
            "(não apresentado não quer dizer que não exista).",
        )
    elif late or no_doc:
        status, why = (
            S.COM_RESSALVA,
            "Serviços autorizados e aceitos, com ressalva: "
            + "; ".join(
                p
                for p in (
                    f"{len(late)} autorizado(s) depois da nota (ratificação)" if late else "",
                    f"{len(no_doc)} autorização(ões) sem documento" if no_doc else "",
                )
                if p
            )
            + ".",
        )
    else:
        status, why = (
            S.VALIDADO,
            f"{len(extra)} serviço(s) extraordinário(s): dentro da alçada ou autorizados antes "
            "e aceitos.",
        )
    ok = within + (len(extra) - within - len(no_auth) - len(no_accept) - len(no_limit))
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(max(ok, 0), len(extra)),
        inputs={
            "linhas": rows,
            "alcadas_versao": d.c3.limits_version,
        },
        calculation=[
            _calc("Serviços extraordinários", len(extra)),
            _calc("Dentro da alçada do síndico", within),
            {
                "label": "Despesas avulsas",
                "value": str(len(rows)),
                "formula": "acima da alçada: autorização antes da nota + documento + aceite",
                "rows": rows,
            },
        ],
    )


def _installment_numbers(text: str) -> tuple[int, int] | None:
    m = PARCEL.search(text)
    if not m:
        return None
    n, total = int(m.group(1)), int(m.group(2))
    return (n, total) if 1 <= n <= total else None


def con_03(d: AuditData) -> Outcome:
    candidates = [
        c
        for c in d.c3.contracts
        if c.nature == ContractNature.PONTUAL.value
        and (c.installments or 0) >= 2
        and (in_force(d, c) or d.c3.contract_expenses.get(c.id))
    ]
    if not candidates:
        return Outcome(
            S.NAO_APLICAVEL,
            "Nenhum contrato pontual parcelado ativo na competência.",
            [Check("Contrato parcelado", True, "Nenhum.")],
            [_contract_ref(c) for c in d.c3.contracts[:20]]
            or [{"tipo": "nota", "id": "-", "rotulo": "sem contratos"}],
            inputs={"contratos": []},
        )
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    over: list[str] = []
    dup: list[str] = []
    gap: list[str] = []
    off_value: list[str] = []
    diff_total = ZERO
    for c in candidates:
        total = c.total_value or ZERO
        n = c.installments or 1
        expected = (total / n).quantize(CENT, ROUND_HALF_UP)
        paid = d.c3.contract_expenses.get(c.id, [])
        billed = sum((e.amount for e in paid), ZERO)
        numbers: list[int] = []
        for i, e in enumerate(paid, start=1):
            parsed = _installment_numbers(f"{e.description} {e.invoice_number or ''}")
            numbers.append(parsed[0] if parsed else i)
        situations = []
        if billed > total or len(paid) > n:
            over.append(c.object[:60])
            diff_total += max(billed - total, ZERO)
            situations.append("cobrado acima do total ou do número de parcelas")
        if len(set(numbers)) != len(numbers):
            dup.append(c.object[:60])
            situations.append("parcela repetida")
        elif numbers and sorted(numbers) != list(range(1, max(numbers) + 1)):
            gap.append(c.object[:60])
            situations.append("parcela fora de sequência")
        last_value = total - expected * (n - 1)
        wrong = [
            e
            for e, k in zip(paid, numbers, strict=True)
            if e.amount != (last_value if k == n else expected)
        ]
        if wrong:
            off_value.append(c.object[:60])
            situations.append(f"{len(wrong)} parcela(s) com valor diferente do cronograma")
        row = {
            "contrato": c.object[:60],
            "total": str(total),
            "parcelas": n,
            "valor_parcela": str(expected),
            "cobradas": len(paid),
            "numeros": ", ".join(str(k) for k in numbers),
            "total_cobrado": str(billed),
            "saldo_futuro": str(total - billed),
            "situacao": "; ".join(situations) or "confere",
        }
        rows.append(row)
        evidence.append(_contract_ref(c) | {"situacao": row["situacao"]})
    checks = [
        Check(
            "Total e número de parcelas",
            not over,
            f"{len(over)} contrato(s) cobrado(s) acima do total ou das parcelas.",
        ),
        Check(
            "Sequência das parcelas",
            not dup and not gap,
            f"{len(dup)} com parcela repetida; {len(gap)} fora de sequência.",
        ),
        Check(
            "Valor de cada parcela pelo cronograma",
            not off_value,
            f"{len(off_value)} contrato(s) com parcela de valor diferente.",
        ),
        Check("Saldo futuro calculado", True, "Total do contrato − total cobrado, por contrato."),
    ]
    if over or dup:
        status, why = (
            S.DIVERGENTE,
            "Parcela repetida ou cobrança acima do total contratado"
            + (f" ({brl(diff_total)} acima)." if diff_total else "."),
        )
    elif gap or off_value:
        status, why = (
            S.COM_RESSALVA,
            "Parcelas dentro do total, com sequência ou valores diferentes do cronograma.",
        )
    else:
        status, why = S.VALIDADO, "Parcelas em sequência, no valor do cronograma e dentro do total."
    return Outcome(
        status,
        why,
        checks,
        evidence,
        [],
        _pct(len(candidates) - len(over) - len(dup), len(candidates)),
        diff_total,
        "ALTA" if over or dup else None,
        inputs={"linhas": rows},
        calculation=[
            _calc("Contratos parcelados", len(candidates)),
            {
                "label": "Cronograma",
                "value": str(len(rows)),
                "formula": "parcela = total ÷ nº de parcelas (a última absorve os centavos); "
                "saldo futuro = total − cobrado",
                "rows": rows,
            },
        ],
    )


# --------------------------------------------------------------------------- funds (A8)


def _account_closing(view: AccountView) -> Decimal | None:
    st = view.statement
    return st.closing_balance if st is not None else None


def ban_08(d: AuditData) -> Outcome:
    funds = d.c3.funds
    if not funds:
        return Outcome(
            S.PENDENTE,
            "Nenhum fundo cadastrado: sem os saldos por fundo do demonstrativo não há lastro a "
            "testar (saldo positivo do caixa não é lastro de fundo).",
            [Check("Saldos por fundo", None, "Nenhum fundo cadastrado.")],
            missing=["Cadastre os fundos e importe os saldos do demonstrativo do mês."],
            inputs={"fundos": []},
        )
    balances = d.c3.fund_balances
    without = [f for f in funds if f.id not in balances]
    views = {a.account.id: a for a in d.accounts if a.account is not None}
    rows: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    arithmetic_bad: list[str] = []
    arithmetic_open: list[str] = []
    continuity_bad: list[str] = []
    for f in funds:
        fb = balances.get(f.id)
        if fb is None:
            continue
        prev = d.c3.previous_fund_balances.get(f.id)
        row: dict[str, Any] = {
            "fundo": f.name,
            "saldo_inicial": str(fb.opening) if fb.opening is not None else "",
            "entradas": str(fb.inflows) if fb.inflows is not None else "",
            "saidas": str(fb.outflows) if fb.outflows is not None else "",
            "rendimentos": str(fb.yield_amount) if fb.yield_amount is not None else "",
            "saldo_final": str(fb.closing),
        }
        parts = (fb.opening, fb.inflows, fb.outflows, fb.yield_amount)
        if any(p is None for p in parts):
            arithmetic_open.append(f.name)
            row["conta_do_fundo"] = "valores do mês incompletos no demonstrativo"
        else:
            calc = fb.opening + fb.inflows - fb.outflows + fb.yield_amount  # type: ignore[operator]
            row["saldo_calculado"] = str(calc)
            if calc != fb.closing:
                arithmetic_bad.append(f.name)
                row["conta_do_fundo"] = f"diferença {brl(fb.closing - calc)}"
            else:
                row["conta_do_fundo"] = "confere"
        if prev is not None and fb.opening is not None and prev.closing != fb.opening:
            continuity_bad.append(f.name)
            row["continuidade"] = f"abertura difere do fechamento anterior ({brl(prev.closing)})"
        elif prev is not None:
            row["continuidade"] = "confere"
        rows.append(row)
        evidence.append(
            {
                "tipo": "saldo_fundo",
                "id": str(fb.id),
                "rotulo": f"{f.name} · saldo final {brl(fb.closing)}",
                "documento_id": str(fb.source_document_id) if fb.source_document_id else None,
            }
        )
    # Backing: funds that share the same set of accounts are tested together.
    groups: dict[frozenset[uuid.UUID], list[Any]] = defaultdict(list)
    unbacked: list[str] = []
    for f in funds:
        accs = frozenset(d.c3.fund_accounts.get(f.id, set()))
        if not accs:
            unbacked.append(f.name)
        elif f.id in balances:
            groups[accs].append(f)
    shortfall = ZERO
    short: list[str] = []
    not_segregated: list[str] = []
    no_statement: list[str] = []
    backing_rows: list[dict[str, Any]] = []
    for accs, members in groups.items():
        names = ", ".join(f.name for f in members)
        need = sum((balances[f.id].closing for f in members), ZERO)
        acc_views = [views.get(a) for a in accs]
        closings = [_account_closing(v) if v else None for v in acc_views]
        labels = ", ".join(v.label if v else "conta sem extrato" for v in acc_views)
        if any(c is None for c in closings):
            no_statement.append(names)
            backing_rows.append(
                {
                    "fundos": names,
                    "contas": labels,
                    "saldo_fundos": str(need),
                    "lastro": "sem extrato",
                }
            )
            continue
        have = sum((c for c in closings if c is not None), ZERO)
        segregated = all(v is not None and v.account.kind in INVESTMENT_KINDS for v in acc_views)  # type: ignore[union-attr]
        situation = "suficiente" if have >= need else f"falta {brl(need - have)}"
        if have < need:
            short.append(names)
            shortfall += need - have
        elif not segregated:
            not_segregated.append(names)
            situation += " (na conta corrente, junto ao caixa)"
        backing_rows.append(
            {
                "fundos": names,
                "contas": labels,
                "saldo_fundos": str(need),
                "saldo_contas": str(have),
                "lastro": situation,
            }
        )
        for v in acc_views:
            if v is not None and v.statement is not None:
                evidence.append(
                    {
                        "tipo": "extrato",
                        "id": str(v.statement.id),
                        "documento_id": (
                            str(v.statement.document_id) if v.statement.document_id else None
                        ),
                        "rotulo": f"Extrato {v.label}",
                    }
                )
    checks = [
        Check(
            "Saldo de cada fundo no demonstrativo",
            None if without else True,
            (
                "Sem saldo do mês: " + ", ".join(f.name for f in without)
                if without
                else f"{len(funds)} fundo(s) com saldo do mês."
            ),
        ),
        Check(
            "Conta do fundo (inicial + entradas − saídas + rendimentos = final)",
            None if arithmetic_open else not arithmetic_bad,
            f"{len(arithmetic_bad)} com diferença; {len(arithmetic_open)} com valores incompletos.",
        ),
        Check(
            "Continuidade com o mês anterior",
            not continuity_bad,
            f"{len(continuity_bad)} fundo(s) com abertura diferente do fechamento anterior.",
        ),
        Check(
            "Lastro próprio de cada fundo",
            None if unbacked or no_statement else not short and not not_segregated,
            f"{len(unbacked)} sem conta de lastro; {len(no_statement)} grupo(s) sem extrato; "
            f"{len(short)} com lastro insuficiente; {len(not_segregated)} na conta corrente.",
        ),
    ]
    missing = [f"Saldo do mês do fundo {f.name} (demonstrativo)." for f in without]
    missing += [f"Indique a conta que guarda o fundo {n}." for n in unbacked]
    missing += [f"Extrato da conta de lastro de: {n}." for n in no_statement]
    if without or no_statement:
        status, why = S.PENDENTE, "Falta saldo do fundo ou extrato da conta de lastro do mês."
    elif short or arithmetic_bad or continuity_bad:
        status, why = (
            S.DIVERGENTE,
            "Lastro insuficiente ou conta do fundo que não fecha"
            + (f" (faltam {brl(shortfall)} de lastro)." if shortfall else "."),
        )
    elif unbacked or not_segregated or arithmetic_open:
        status, why = (
            S.COM_RESSALVA,
            "Saldo positivo não é lastro segregado: há fundo sem conta própria, guardado na "
            "conta corrente ou com valores incompletos no demonstrativo.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Cada fundo tem lastro próprio em conta separada, a conta do fundo fecha e "
            "continua do mês anterior.",
        )
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(funds) - len(without) - len(unbacked), len(funds)),
        shortfall,
        "ALTA" if short else None,
        inputs={"fundos": rows, "lastro": backing_rows},
        calculation=[
            _calc("Fundos", len(funds)),
            _calc(
                "Lastro faltante", shortfall, "Σ saldo dos fundos − Σ saldo das contas de lastro"
            ),
            {
                "label": "Conta de cada fundo",
                "value": str(len(rows)),
                "formula": "inicial + entradas − saídas + rendimentos = final",
                "rows": rows,
            },
            {
                "label": "Lastro",
                "value": str(len(backing_rows)),
                "formula": "saldo das contas de lastro ≥ soma dos fundos que elas guardam",
                "rows": backing_rows,
            },
        ],
    )


def _pair(sources: list[Line], targets: list[Line], sign: int) -> tuple[list[Line], set[uuid.UUID]]:
    """Each source line paired with one target of the opposite sign and the same absolute
    amount within PAIR_DAYS. Returns the unpaired sources and the ids of used targets."""
    used: set[uuid.UUID] = set()
    unpaired: list[Line] = []
    for s in sorted(sources, key=lambda ln: ln.trn.posted_at):
        match = next(
            (
                t
                for t in sorted(targets, key=lambda ln: ln.trn.posted_at)
                if t.trn.id not in used
                and t.amount == sign * -s.amount
                and abs((t.trn.posted_at - s.trn.posted_at).days) <= PAIR_DAYS
            ),
            None,
        )
        if match is None:
            unpaired.append(s)
        else:
            used.add(match.trn.id)
    return unpaired, used


def ban_09(d: AuditData) -> Outcome:
    inv = [a for a in d.accounts if a.account is not None and a.account.kind in INVESTMENT_KINDS]
    checking = [a for a in d.accounts if a not in inv]
    out_lines = [ln for a in checking for ln in a.lines if ln.kind == "aplicacao"]
    back_lines = [ln for a in checking for ln in a.lines if ln.kind == "resgate"]
    yield_checking = [ln for a in checking for ln in a.lines if ln.kind == "rendimento"]
    if not inv and not (out_lines or back_lines or yield_checking):
        return Outcome(
            S.NAO_APLICAVEL,
            "Nenhuma conta de aplicação cadastrada e nenhuma aplicação, resgate ou rendimento "
            "no extrato do mês.",
            [Check("Aplicação financeira", True, "Nenhuma movimentação de aplicação.")],
            [{"tipo": "extrato", "id": a.key, "rotulo": f"Extrato {a.label}"} for a in d.accounts]
            or [{"tipo": "nota", "id": "-", "rotulo": "sem extrato de aplicação"}],
            inputs={"contas": [a.key for a in d.accounts]},
        )
    if not inv:
        return Outcome(
            S.PENDENTE,
            "Há aplicação, resgate ou rendimento no extrato da conta corrente, mas não o "
            "extrato próprio da aplicação.",
            [Check("Extrato próprio da aplicação", None, "Nenhuma conta de aplicação.")],
            missing=[
                "Envie o extrato da aplicação do mês e marque a conta como aplicação "
                "(Auditoria → Conciliação)."
            ],
            inputs={"linhas": sorted(str(ln.trn.id) for ln in out_lines + back_lines)},
        )
    no_statement = [a for a in inv if a.statement is None]
    inv_in = [ln for a in inv for ln in a.lines if ln.kind == "aporte"]
    inv_out = [ln for a in inv for ln in a.lines if ln.kind == "saida_aplicacao"]
    unpaired_out, used_in = _pair(out_lines, inv_in, 1)
    unpaired_back, used_out = _pair(back_lines, inv_out, 1)
    orphan_in = [ln for ln in inv_in if ln.trn.id not in used_in]
    orphan_out = [ln for ln in inv_out if ln.trn.id not in used_out]
    rows: list[dict[str, Any]] = []
    diverging: list[str] = []
    open_balance: list[str] = []
    for a in inv:
        bc = a.balance_check()
        yields = sum((ln.amount for ln in a.lines if ln.kind == "rendimento"), ZERO)
        taxes = sum((-ln.amount for ln in a.lines if ln.kind == "tributo_bancario"), ZERO)
        rows.append(
            {
                "conta": a.label,
                "saldo_inicial": bc.get("saldo_inicial", ""),
                "aportes": str(sum((ln.amount for ln in a.lines if ln.kind == "aporte"), ZERO)),
                "resgates": str(
                    sum((-ln.amount for ln in a.lines if ln.kind == "saida_aplicacao"), ZERO)
                ),
                "rendimentos": str(yields),
                "ir_iof": str(taxes),
                "saldo_final_declarado": bc.get("saldo_final_declarado", ""),
                "saldo_final_calculado": bc.get("saldo_final_calculado", ""),
                "situacao": bc["situacao"],
            }
        )
        if bc["situacao"] == "diverge":
            diverging.append(a.label)
        elif bc["situacao"] != "confere":
            open_balance.append(a.label)
    diff = sum((-ln.amount for ln in unpaired_out), ZERO) + sum(
        (ln.amount for ln in unpaired_back), ZERO
    )
    checks = [
        Check(
            "Extrato próprio de cada aplicação",
            None if no_statement else True,
            (
                "Sem extrato: " + ", ".join(a.label for a in no_statement)
                if no_statement
                else f"{len(inv)} conta(s) de aplicação com extrato."
            ),
        ),
        Check(
            "Saldo da aplicação (inicial + aportes − resgates + rendimentos − IR/IOF = final)",
            None if open_balance else not diverging,
            f"{len(diverging)} conta(s) com diferença; {len(open_balance)} sem saldos declarados.",
        ),
        Check(
            "Aplicações e resgates com contrapartida",
            not unpaired_out and not unpaired_back,
            f"{len(unpaired_out)} aplicação(ões) sem aporte na aplicação; {len(unpaired_back)} "
            f"resgate(s) sem saída na aplicação (até {PAIR_DAYS} dias).",
        ),
        Check(
            "Origem dos aportes e destino dos resgates",
            not orphan_in and not orphan_out,
            f"{len(orphan_in)} aporte(s) e {len(orphan_out)} resgate(s) sem contrapartida na "
            "conta corrente apresentada.",
        ),
    ]
    missing = [f"Extrato do mês de {a.label}." for a in no_statement]
    if no_statement:
        status, why = S.PENDENTE, "Falta o extrato próprio de aplicação do mês."
    elif diverging or unpaired_out or unpaired_back:
        status, why = (
            S.DIVERGENTE,
            "Saldo da aplicação não fecha ou dinheiro saiu da conta corrente sem chegar à "
            "aplicação (ou o contrário).",
        )
    elif open_balance or orphan_in or orphan_out:
        status, why = (
            S.COM_RESSALVA,
            "Aplicação conferida em parte: saldos não declarados ou contrapartida em conta "
            "não apresentada.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Aportes, resgates, rendimentos e IR/IOF conciliados, com o saldo de cada aplicação "
            "fechando ao centavo.",
        )
    evidence: list[dict[str, Any]] = [
        {
            "tipo": "extrato",
            "id": str(a.statement.id),
            "documento_id": str(a.statement.document_id) if a.statement.document_id else None,
            "rotulo": f"Extrato {a.label}",
        }
        for a in inv
        if a.statement is not None
    ]
    return Outcome(
        status,
        why,
        checks,
        evidence,
        missing,
        _pct(len(inv) - len(no_statement), len(inv)),
        diff,
        "ALTA" if diff else None,
        inputs={
            "aplicacoes": rows,
            "pares": sorted(str(ln.trn.id) for ln in unpaired_out + unpaired_back),
        },
        calculation=[
            _calc("Contas de aplicação", len(inv)),
            _calc(
                "Sem contrapartida",
                diff,
                f"aplicações e resgates da conta corrente sem par na aplicação em até {PAIR_DAYS} dias",
            ),
            {
                "label": "Aplicações",
                "value": str(len(rows)),
                "formula": "inicial + aportes − resgates + rendimentos − IR/IOF = final",
                "rows": rows,
            },
        ],
    )


# --------------------------------------------------------------------------- budget (A8)


def gov_01(d: AuditData) -> Outcome:
    budget = d.c3.budget
    if budget is None:
        return Outcome(
            S.PENDENTE,
            f"Orçamento aprovado de {d.competence.year} não apresentado: sem ele não há orçado "
            "× realizado.",
            [Check("Orçamento aprovado", None, "Não importado.")],
            missing=[
                f"Importe o orçamento aprovado de {d.competence.year} (Auditoria → Orçamento)."
            ],
            inputs={"orcamento": None},
        )
    month_lines = [ln for ln in d.c3.budget_lines if ln.month == d.competence]
    budgeted: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for ln in month_lines:
        budgeted[ln.category] += ln.amount
    realized: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for e in d.expenses:
        realized[e.expense.category] += e.expense.amount
    noted = {n.category for n in d.c3.budget_notes}
    rows: list[dict[str, Any]] = []
    unexplained: list[str] = []
    explained = 0
    for cat in sorted(set(budgeted) | set(realized)):
        b, r = budgeted[cat], realized[cat]
        dev = r - b
        pct = (dev / b * 100).quantize(Decimal("0.1"), ROUND_HALF_UP) if b else None
        over = (b == 0 and r > 0) or (pct is not None and abs(pct) > BUDGET_TOLERANCE_PCT)
        situacao = "dentro da tolerância"
        if over:
            if cat in noted:
                explained += 1
                situacao = "desvio explicado"
            else:
                unexplained.append(category_label(cat))
                situacao = "desvio sem explicação"
        rows.append(
            {
                "categoria": category_label(cat),
                "orcado": str(b),
                "realizado": str(r),
                "desvio": str(dev),
                "desvio_pct": f"{pct}%" if pct is not None else "fora do orçamento",
                "situacao": situacao,
            }
        )
    month_total_b = sum(budgeted.values(), ZERO)
    month_total_r = sum(realized.values(), ZERO)
    ytd = sum((e.amount for e in d.c3.year_expenses), ZERO)
    rest = sum((ln.amount for ln in d.c3.budget_lines if ln.month > d.competence), ZERO)
    annual = sum((ln.amount for ln in d.c3.budget_lines), ZERO)
    projection = ytd + rest
    checking = [a for a in d.accounts if a.account is not None and a.account.kind == "corrente"]
    cash = [a.statement.closing_balance for a in checking if a.statement is not None]
    next_month = sum(
        (ln.amount for ln in d.c3.budget_lines if ln.month == add_months(d.competence, 1)), ZERO
    )
    cash_lines = []
    if cash and all(c is not None for c in cash):
        total_cash = sum((c for c in cash if c is not None), ZERO)
        cash_lines.append(_calc("Caixa no fim do mês (contas correntes)", total_cash))
        if next_month:
            cash_lines.append(
                _calc(
                    "Cobertura do mês seguinte",
                    (total_cash / next_month).quantize(Decimal("0.01")),
                    "caixa ÷ orçado do mês seguinte (meses)",
                )
            )
    approved = budget.approved_on is not None and budget.source_document_id is not None
    checks = [
        Check(
            "Orçamento aprovado com documento",
            approved,
            f"Versão {budget.version} de {budget.year}"
            + (
                f", aprovada em {budget.approved_on:%d/%m/%Y}."
                if budget.approved_on
                else ", sem data de aprovação."
            )
            + ("" if budget.source_document_id else " Sem a ata ou o documento da aprovação."),
        ),
        Check(
            f"Desvios acima de {BUDGET_TOLERANCE_PCT}% explicados",
            not unexplained,
            (
                "Todos os desvios dentro da tolerância ou explicados."
                if not unexplained
                else "Sem explicação: " + ", ".join(unexplained)
            ),
        ),
        Check(
            "Projeção do ano com premissas declaradas",
            True,
            "Realizado até a competência + orçado dos meses seguintes (premissa: os meses "
            "seguintes seguem o orçado; nenhuma inflação ou receita extra é presumida).",
        ),
    ]
    missing = [f"Explique o desvio de {c} no mês (Auditoria → Orçamento)." for c in unexplained]
    if not approved:
        missing.append("Ligue a ata ou o documento que aprovou o orçamento.")
    if unexplained or not approved:
        status, why = (
            S.COM_RESSALVA,
            "Orçado × realizado calculado, com desvio sem explicação ou orçamento sem "
            "documento de aprovação (desvio não é erro; só a falta de explicação é ressalva).",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Orçamento aprovado, desvios dentro da tolerância ou explicados e projeção com "
            "premissas declaradas.",
        )
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "orcamento",
                "id": str(budget.id),
                "rotulo": f"Orçamento {budget.year} (versão {budget.version})",
                "documento_id": (
                    str(budget.source_document_id) if budget.source_document_id else None
                ),
            }
        ],
        missing,
        _pct(len(rows) - len(unexplained), len(rows)) if rows else None,
        inputs={
            "orcamento": str(budget.id),
            "linhas": rows,
            "notas": sorted(str(n.id) for n in d.c3.budget_notes),
        },
        calculation=[
            _calc("Orçado no mês", month_total_b),
            _calc("Realizado no mês", month_total_r),
            _calc("Desvio do mês", month_total_r - month_total_b, "realizado − orçado"),
            _calc("Realizado no ano até a competência", ytd),
            _calc("Orçado dos meses seguintes", rest),
            _calc("Projeção do ano", projection, "realizado até aqui + orçado dos meses seguintes"),
            _calc("Orçamento anual", annual),
            _calc("Desvio projetado do ano", projection - annual, "projeção − orçamento anual"),
            *cash_lines,
            {
                "label": "Por categoria",
                "value": str(len(rows)),
                "formula": f"desvio acima de {BUDGET_TOLERANCE_PCT}% precisa de explicação",
                "rows": rows,
            },
        ],
    )


# --------------------------------------------------------------------------- obligations


def gov_02(d: AuditData) -> Outcome:
    rows_all = d.c3.obligations
    applicable = [
        r for r in rows_all if r.obligation.applicability == ComplianceApplicability.APLICAVEL.value
    ]
    to_validate = [
        r for r in rows_all if r.obligation.applicability == ComplianceApplicability.A_VALIDAR.value
    ]
    if not rows_all:
        return Outcome(
            S.PENDENTE,
            "Nenhuma obrigação cadastrada em Conformidade: seguro, AVCB e laudos não foram "
            "apresentados.",
            [Check("Obrigações cadastradas", None, "Nenhuma.")],
            missing=["Ative a Conformidade e valide quais obrigações se aplicam."],
            inputs={"obrigacoes": []},
        )
    insurance = [r for r in applicable if r.obligation.category == "seguro"]
    rows: list[dict[str, Any]] = []
    missing_docs: list[str] = []
    to_confirm: list[str] = []
    no_plan: list[str] = []
    for r in applicable:
        sit = r.situation
        ob = r.obligation
        situacao = sit.label
        if sit.code in ("sem_documento", "sem_validade", "vencido"):
            missing_docs.append(ob.name)
        elif sit.code == "vence_em_breve" and not (ob.responsible or ob.supplier_id):
            no_plan.append(ob.name)
            situacao += " · sem responsável pela renovação"
        if sit.to_confirm and sit.code not in ("sem_documento",):
            to_confirm.append(ob.name)
        rows.append(
            {
                "obrigacao": ob.name,
                "situacao": situacao,
                "valida_ate": sit.valid_until.isoformat() if sit.valid_until else "",
                "a_confirmar": sit.to_confirm or "",
                "responsavel": "sim" if (ob.responsible or ob.supplier_id) else "não",
            }
        )
    checks = [
        Check(
            "Obrigações validadas por uma pessoa",
            not to_validate,
            f"{len(applicable)} se aplicam; {len(to_validate)} a validar.",
        ),
        Check(
            "Seguro da edificação cadastrado",
            bool(insurance),
            "Seguro aplicável cadastrado." if insurance else "Nenhum seguro validado.",
        ),
        Check(
            "Documento vigente na competência",
            not missing_docs,
            (
                "Todos com documento vigente."
                if not missing_docs
                else "Sem documento vigente apresentado: " + ", ".join(missing_docs[:8])
            ),
        ),
        Check(
            "Datas confirmadas por uma pessoa",
            not to_confirm,
            f"{len(to_confirm)} data(s) lida(s) do documento a confirmar.",
        ),
        Check(
            "Plano de renovação do que vence em breve",
            not no_plan,
            f"{len(no_plan)} vencendo sem responsável pela renovação.",
        ),
    ]
    missing = [f"Documento vigente de: {n}." for n in missing_docs]
    missing += [f"Valide se se aplica: {r.obligation.name}." for r in to_validate[:10]]
    if not insurance:
        missing.append("Cadastre e valide o seguro da edificação.")
    if missing_docs or not insurance or (to_validate and not applicable):
        status, why = (
            S.PENDENTE,
            "Documento vigente não apresentado ou obrigação a validar (ausência de registro "
            "não quer dizer que a obrigação não foi cumprida).",
        )
    elif to_validate or to_confirm or no_plan:
        status, why = (
            S.COM_RESSALVA,
            "Documentos vigentes, com ressalva: obrigação a validar, data a confirmar ou "
            "renovação sem responsável.",
        )
    else:
        status, why = (
            S.VALIDADO,
            "Seguro e obrigações técnicas com documento vigente na competência, datas "
            "confirmadas e renovação com responsável.",
        )
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "obrigacao",
                "id": str(r.obligation.id),
                "rotulo": f"{r.obligation.name} · {r.situation.label}",
                "documento_id": (
                    str(r.evidence.document_id)
                    if r.evidence is not None and r.evidence.document_id
                    else None
                ),
            }
            for r in applicable
        ],
        missing,
        _pct(len(applicable) - len(missing_docs), len(applicable)) if applicable else None,
        inputs={"linhas": rows, "a_validar": len(to_validate)},
        calculation=[
            _calc("Obrigações que se aplicam", len(applicable)),
            _calc("A validar", len(to_validate)),
            {
                "label": "Situação no fim da competência",
                "value": str(len(rows)),
                "formula": "situação calculada pela Conformidade na data de fim do mês",
                "rows": rows,
            },
        ],
    )


# --------------------------------------------------------------------------- DOC-03


def _member_in_office(d: AuditData, member_id: str | None, on: date) -> Any:
    for m in d.c3.board:
        if (
            str(m.id) == str(member_id)
            and m.term_start <= on
            and (m.term_end is None or m.term_end >= on)
        ):
            return m
    return None


def doc_03(d: AuditData) -> Outcome:
    approvals = d.c3.accounts_approvals
    if not approvals:
        return Outcome(
            S.PENDENTE,
            "Aprovação das contas da competência não apresentada (parecer do conselho ou ata "
            "da assembleia). Ela costuma vir depois do mês: a revalidação histórica atualiza "
            "este controle quando chegar.",
            [Check("Termo, ata ou parecer de aprovação", None, "Nenhum cobre a competência.")],
            missing=["Registre a aprovação das contas que cobre a competência, com o documento."],
            inputs={"aprovacoes": []},
        )
    a = approvals[-1]
    signers = a.signatories or []
    names: list[str] = []
    out_of_office: list[str] = []
    sindico_signed = False
    for s in signers:
        if a.body == AccountsApprovalBody.ASSEMBLEIA.value:
            names.append(f"{s.get('papel', 'mesa')}: {s.get('nome', '')}".strip())
            continue
        m = _member_in_office(d, s.get("board_member_id"), a.approved_on)
        if m is None:
            out_of_office.append(s.get("nome") or "signatário")
            continue
        names.append(f"{m.full_name} ({m.position})")
        if m.position == BoardPosition.SINDICO.value:
            sindico_signed = True
    enough = (
        len(signers) >= 2
        if a.body == AccountsApprovalBody.ASSEMBLEIA.value
        else len(signers) - len(out_of_office) >= 1
    )
    after = a.approved_on >= d.month_end
    checks = [
        Check("Documento da aprovação", True, "Documento ligado ao registro."),
        Check(
            "Signatários",
            enough and not out_of_office,
            ("; ".join(names) or "nenhum")
            + (
                f". Fora do mandato ou fora do corpo diretivo: {len(out_of_office)}."
                if out_of_office
                else ""
            ),
        ),
        Check(
            "Poderes (o síndico não aprova as próprias contas)",
            not sindico_signed,
            (
                "Assinado pelo conselho ou pela assembleia."
                if not sindico_signed
                else "O síndico aparece entre quem aprovou."
            ),
        ),
        Check(
            "Data e abrangência",
            after,
            f"Aprovada em {a.approved_on:%d/%m/%Y}, cobrindo {a.period_start:%m/%Y} a "
            f"{a.period_end:%m/%Y}." + ("" if after else " Data anterior ao fim da competência."),
        ),
        Check(
            "Sem ressalvas",
            not a.with_reservations,
            "Aprovada sem ressalvas." if not a.with_reservations else "Aprovada com ressalvas.",
        ),
    ]
    body = {
        "conselho_fiscal": "conselho fiscal",
        "conselho_consultivo": "conselho consultivo",
        "assembleia": "assembleia",
    }[a.body]
    if not enough or out_of_office or sindico_signed or not after:
        status, why = (
            S.COM_RESSALVA,
            f"Aprovação pelo {body} apresentada, com ponto de atenção nos signatários, nos "
            "poderes ou na data.",
        )
    elif a.with_reservations:
        status, why = S.COM_RESSALVA, f"Contas aprovadas pelo {body} com ressalvas."
    else:
        status, why = (
            S.VALIDADO,
            f"Contas da competência aprovadas pelo {body} em {a.approved_on:%d/%m/%Y}, com "
            "signatários no mandato.",
        )
    return Outcome(
        status,
        why,
        checks,
        [
            {
                "tipo": "documento",
                "id": str(a.document_id),
                "rotulo": f"Aprovação das contas ({body}) de {a.approved_on:%d/%m/%Y}",
            }
        ],
        [],
        Decimal("1"),
        inputs={
            "aprovacao": str(a.id),
            "signatarios": len(signers),
            "mandatos": sorted((str(m.id), str(m.term_start), str(m.term_end)) for m in d.c3.board),
        },
        calculation=[
            _calc("Órgão", body),
            _calc("Período coberto", f"{a.period_start:%m/%Y} a {a.period_end:%m/%Y}"),
            _calc("Signatários", len(signers)),
        ],
    )


EVALUATORS_3 = {
    "CON-01": con_01,
    "CON-02": con_02,
    "CON-03": con_03,
    "BAN-08": ban_08,
    "BAN-09": ban_09,
    "GOV-01": gov_01,
    "GOV-02": gov_02,
    "DOC-03": doc_03,
}
EVALUATORS.update(EVALUATORS_3)
