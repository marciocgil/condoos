"""CNAB 240 return files, FEBRABAN layout (Itaú 341, Bradesco 237, Banco do Brasil 001).

Two services are read:
- Payments (SISPAG / Multipag / Pagamentos BB): segments A (+B) for transfers and J (+J-52)
  for boleto payments. Each confirmed payment (occurrence "00") becomes a debit.
- Collection (cobrança): segments T + U. Each liquidation (movement 06 or 17) becomes a credit.

Other records are counted as ignored. The three banks follow FEBRABAN for every field read
here; bank-specific deviations go in a function registered for that bank only.

Layout reference: FEBRABAN CNAB 240 v10.x; ``kivanio/brcobranca`` (MIT) for collection
fields. All test files are fictitious.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from app.core.br import only_digits
from app.core.money import cents, parse_ddmmyyyy
from app.db.enums import BankTransactionOrigin
from app.ingestion.bank.base import ParsedStatement, ParsedTransaction
from app.ingestion.bank.cnab.common import field as f
from app.ingestion.bank.cnab.common import register

PAID_OK = "00"
COLLECTION_LIQUIDATION = {"06", "17"}


def _doc(raw: str) -> str | None:
    digits = only_digits(raw).lstrip("0")
    if not digits:
        return None
    # Right-aligned in a wider field: CNPJ has 14 digits, CPF 11.
    return digits.zfill(14) if len(digits) > 11 else digits.zfill(11)


def _date(raw: str) -> date | None:
    try:
        return parse_ddmmyyyy(raw)
    except ValueError:
        return None


def parse_febraban_240(lines: list[str]) -> ParsedStatement:
    header = lines[0]
    statement = ParsedStatement(
        transactions=[],
        account_holder_document=_doc(f(header, 19, 32)),
    )
    bank = f(header, 1, 3)
    pending_a: dict[str, str | Decimal | date | None] | None = None
    pending_t: dict[str, str | Decimal | date | None] | None = None
    last_j: ParsedTransaction | None = None

    def flush_a() -> None:
        nonlocal pending_a
        if pending_a is not None:
            statement.transactions.append(_transfer(pending_a, bank))
            pending_a = None

    for line in lines[1:]:
        record_type = f(line, 8, 8)
        if record_type != "3":
            flush_a()
            continue
        segment = f(line, 14, 14)

        if segment == "A":
            flush_a()
            if f(line, 231, 232) != PAID_OK:
                statement.ignored_records += 1
                continue
            when = _date(f(line, 155, 162)) or _date(f(line, 94, 101))
            real = cents(f(line, 163, 177))
            pending_a = {
                "name": f(line, 44, 73).strip(),
                "our_number": f(line, 135, 154).strip() or f(line, 74, 93).strip(),
                "date": when,
                "amount": real if real > 0 else cents(f(line, 120, 134)),
                "doc": None,
            }
        elif segment == "B":
            # Complements the previous A; a B after a rejected A belongs to that rejection.
            if pending_a is not None:
                pending_a["doc"] = _doc(f(line, 19, 32))
                flush_a()
        elif segment == "J":
            flush_a()
            if f(line, 18, 19) == "52":
                # J-52 complements the previous J with the beneficiary's CNPJ/CPF.
                if last_j is not None:
                    idx = statement.transactions.index(last_j)
                    last_j = replace(
                        last_j,
                        payee_document=_doc(f(line, 77, 91)),
                        payee_name=f(line, 92, 131).strip() or last_j.payee_name,
                    )
                    statement.transactions[idx] = last_j
                continue
            if f(line, 231, 232) != PAID_OK:
                statement.ignored_records += 1
                last_j = None
                continue
            when = _date(f(line, 145, 152))
            if when is None:
                statement.ignored_records += 1
                continue
            name = f(line, 62, 91).strip()
            ref = f(line, 203, 222).strip() or f(line, 183, 202).strip() or f(line, 18, 61)
            last_j = ParsedTransaction(
                posted_at=when,
                amount=-cents(f(line, 153, 167)),
                description=f"PAG BOLETO {name}".strip()[:300],
                external_id=f"cnab240:{bank}:J:{ref}:{when.isoformat()}"[:120],
                origin=BankTransactionOrigin.CNAB,
                payee_name=name or None,
            )
            statement.transactions.append(last_j)
        elif segment == "T":
            flush_a()
            pending_t = None
            if f(line, 16, 17) not in COLLECTION_LIQUIDATION:
                statement.ignored_records += 1
                continue
            pending_t = {
                "our_number": f(line, 38, 57).strip(),
                "doc_number": f(line, 59, 73).strip(),
                "movement": f(line, 16, 17),
            }
        elif segment == "U" and pending_t is not None:
            when = _date(f(line, 146, 153)) or _date(f(line, 138, 145))
            if when is None:
                statement.ignored_records += 1
                pending_t = None
                continue
            statement.transactions.append(
                ParsedTransaction(
                    posted_at=when,
                    amount=cents(f(line, 78, 92)),
                    description=f"LIQUIDACAO BOLETO {pending_t['doc_number']}".strip()[:300],
                    external_id=(
                        f"cnab240:{bank}:T:{pending_t['our_number']}:{pending_t['movement']}"
                    )[:120],
                    origin=BankTransactionOrigin.CNAB,
                    # The payer of a collection boleto is a resident: never stored (D123).
                    payee_name=None,
                    payee_document=None,
                )
            )
            pending_t = None
        else:
            flush_a()
            statement.ignored_records += 1
    flush_a()
    return statement


def _transfer(a: dict[str, str | Decimal | date | None], bank: str) -> ParsedTransaction:
    when = a["date"]
    amount = a["amount"]
    assert isinstance(when, date) and isinstance(amount, Decimal)
    name = str(a["name"] or "")
    return ParsedTransaction(
        posted_at=when,
        amount=-amount,
        description=f"PAGAMENTO {name}".strip()[:300],
        external_id=f"cnab240:{bank}:A:{a['our_number']}:{when.isoformat()}"[:120],
        origin=BankTransactionOrigin.CNAB,
        payee_name=name or None,
        payee_document=a["doc"] if isinstance(a["doc"], str) else None,
    )


for _bank in ("001", "237", "341"):
    register(240, _bank)(parse_febraban_240)
