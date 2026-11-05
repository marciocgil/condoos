"""CNAB 400 collection (cobrança) return files: Itaú 341, Bradesco 237, Banco do Brasil 001.

Each liquidated boleto becomes a credit (condo fees received). Positions per bank are in
``LAYOUTS`` so a difference between banks is a table change, not new code.

References: bank manuals for CNAB 400 cobrança and ``kivanio/brcobranca`` (MIT) as a
layout reference. All test files are fictitious.
"""

from dataclasses import dataclass

from app.core.br import only_digits
from app.core.money import cents, parse_ddmmyyyy
from app.db.enums import BankTransactionOrigin
from app.ingestion.bank.base import ParsedStatement, ParsedTransaction
from app.ingestion.bank.cnab.common import CnabParser, register
from app.ingestion.bank.cnab.common import field as f

Span = tuple[int, int]


@dataclass(frozen=True)
class Layout400:
    detail_types: frozenset[str]
    liquidation: frozenset[str]
    company_doc: Span | None
    our_number: Span
    occurrence: Span
    occurrence_date: Span
    doc_number: Span
    amount_paid: Span
    credit_date: Span
    payer_name: Span | None = None


LAYOUTS: dict[str, Layout400] = {
    "341": Layout400(  # Itaú
        detail_types=frozenset({"1"}),
        liquidation=frozenset({"06", "07", "08", "10"}),
        company_doc=(4, 17),
        our_number=(63, 70),
        occurrence=(109, 110),
        occurrence_date=(111, 116),
        doc_number=(117, 126),
        amount_paid=(254, 266),
        credit_date=(296, 301),
        payer_name=(325, 354),
    ),
    "237": Layout400(  # Bradesco
        detail_types=frozenset({"1"}),
        liquidation=frozenset({"06", "15", "17"}),
        company_doc=(4, 17),
        our_number=(71, 82),
        occurrence=(109, 110),
        occurrence_date=(111, 116),
        doc_number=(117, 126),
        amount_paid=(254, 266),
        credit_date=(296, 301),
    ),
    "001": Layout400(  # Banco do Brasil (convênio de 7 posições: registro "7")
        detail_types=frozenset({"7"}),
        liquidation=frozenset({"05", "06", "07", "08", "15"}),
        company_doc=(4, 17),
        our_number=(64, 80),
        occurrence=(109, 110),
        occurrence_date=(111, 116),
        doc_number=(117, 126),
        amount_paid=(254, 266),
        credit_date=(176, 181),
    ),
}


def _span(line: str, span: Span) -> str:
    return f(line, span[0], span[1])


def _parse(bank: str, lines: list[str]) -> ParsedStatement:
    layout = LAYOUTS[bank]
    statement = ParsedStatement(transactions=[])
    for line in lines[1:]:
        kind = line[0]
        if kind == "9":  # trailer
            continue
        if kind not in layout.detail_types:
            statement.ignored_records += 1
            continue
        if statement.account_holder_document is None and layout.company_doc:
            doc = only_digits(_span(line, layout.company_doc))
            statement.account_holder_document = doc if len(doc) == 14 else None
        occurrence = _span(line, layout.occurrence)
        if occurrence not in layout.liquidation:
            statement.ignored_records += 1
            continue
        try:
            when = parse_ddmmyyyy(_span(line, layout.credit_date)) or parse_ddmmyyyy(
                _span(line, layout.occurrence_date)
            )
        except ValueError:
            when = None
        if when is None:
            statement.ignored_records += 1
            continue
        our_number = _span(line, layout.our_number).strip()
        doc_number = _span(line, layout.doc_number).strip()
        payer = _span(line, layout.payer_name).strip() if layout.payer_name else ""
        statement.transactions.append(
            ParsedTransaction(
                posted_at=when,
                amount=cents(_span(line, layout.amount_paid)),
                description=f"LIQUIDACAO BOLETO {doc_number}".strip()[:300],
                external_id=f"cnab400:{bank}:{our_number}:{occurrence}"[:120],
                origin=BankTransactionOrigin.CNAB,
                payee_name=payer or None,
            )
        )
    return statement


def _parser_for(bank: str) -> CnabParser:
    def parse(lines: list[str]) -> ParsedStatement:
        return _parse(bank, lines)

    return parse


for _bank in LAYOUTS:
    register(400, _bank)(_parser_for(_bank))
