"""OFX reader (1.x SGML and 2.x XML). Own implementation: tags are read leniently because
Brazilian banks often emit SGML without closing tags."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from app.core.br import only_digits
from app.db.enums import BankTransactionOrigin
from app.ingestion.bank.base import BankFileError, ParsedStatement, ParsedTransaction

_TRN = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.S | re.I)
_BANKID = re.compile(r"<BANKID>\s*([^<\r\n]+)", re.I)


def decode(data: bytes) -> str:
    head = data[:600].decode("ascii", errors="ignore").upper()
    if "UTF-8" in head or 'ENCODING="UTF-8"' in head:
        return data.decode("utf-8", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>\s*([^<\r\n]*)", block, re.I)
    if not m:
        return None
    value = m.group(1).strip()
    return value or None


def _ofx_date(value: str) -> date:
    # YYYYMMDD[HHMMSS[.XXX]][[-3:BRT]]
    digits = value[:8]
    if len(digits) != 8 or not digits.isdigit():
        raise BankFileError(f"data inválida no OFX: {value!r}")
    return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))


def _ofx_amount(value: str) -> Decimal:
    v = value.strip().replace(" ", "")
    if "," in v and "." not in v:
        v = v.replace(",", ".")  # some banks use a decimal comma
    try:
        return Decimal(v).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise BankFileError(f"valor inválido no OFX: {value!r}") from exc


def looks_like_ofx(data: bytes) -> bool:
    head = data[:2000].decode("ascii", errors="ignore").upper()
    return "OFXHEADER" in head or "<OFX>" in head


def parse_ofx(data: bytes) -> ParsedStatement:
    text = decode(data)
    if "<OFX>" not in text.upper():
        raise BankFileError("O arquivo não parece ser um extrato OFX.")
    bank = _BANKID.search(text)
    statement = ParsedStatement(transactions=[], bank_code=bank.group(1).strip() if bank else None)
    seen: dict[str, int] = {}
    for block in _TRN.findall(text):
        posted, amount = _tag(block, "DTPOSTED"), _tag(block, "TRNAMT")
        if not posted or not amount:
            statement.ignored_records += 1
            continue
        name = _tag(block, "NAME")
        memo = _tag(block, "MEMO")
        fitid = _tag(block, "FITID")
        description = " ".join(p for p in (name, memo) if p) or "SEM DESCRIÇÃO"
        if fitid is None:
            # No FITID: derive one from the content; repeated identical lines get an index.
            fitid = f"{posted[:8]}|{amount}|{description}"
        base_id = f"ofx:{fitid}"
        seen[base_id] = seen.get(base_id, 0) + 1
        external_id = base_id if seen[base_id] == 1 else f"{base_id}#{seen[base_id]}"
        payee_doc = only_digits(_tag(block, "PAYEEID") or "") or None
        statement.transactions.append(
            ParsedTransaction(
                posted_at=_ofx_date(posted),
                amount=_ofx_amount(amount),
                description=description[:300],
                external_id=external_id[:120],
                origin=BankTransactionOrigin.OFX,
                payee_name=(name or None) and name[:200],
                payee_document=payee_doc if payee_doc and len(payee_doc) in (11, 14) else None,
            )
        )
    if not statement.transactions:
        raise BankFileError("Nenhum lançamento encontrado no OFX.")
    # D122: account and the closing balance as the bank states them (LEDGERBAL). OFX has no
    # opening balance: it stays empty (the previous month's closing is compared in BAN-02).
    statement.branch = _tag(text, "BRANCHID")
    statement.account_number = _tag(text, "ACCTID")
    start, end = _tag(text, "DTSTART"), _tag(text, "DTEND")
    statement.period_start = _ofx_date(start) if start else None
    statement.period_end = _ofx_date(end) if end else None
    ledger = re.search(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|$)", text, re.S | re.I)
    if ledger:
        amount, as_of = _tag(ledger.group(1), "BALAMT"), _tag(ledger.group(1), "DTASOF")
        if amount:
            statement.closing_balance = _ofx_amount(amount)
            statement.closing_date = _ofx_date(as_of) if as_of else statement.period_end
            statement.balance_source = "OFX LEDGERBAL"
    return statement
