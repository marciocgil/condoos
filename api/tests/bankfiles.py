"""Builders for fictitious bank files (CNAB 240/400, OFX, CSV) used in tests.

Lines are assembled field by field from 1-indexed positions, the way the bank manuals print
them. Every name, CNPJ and amount here is invented.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


def line(width: int, fields: dict[tuple[int, int], str], fill: str = " ") -> str:
    buf = [fill] * width
    for (start, end), value in fields.items():
        size = end - start + 1
        if len(value) > size:
            raise ValueError(f"value {value!r} too long for {start}-{end}")
        text = value.ljust(size) if not value.isdigit() else value.rjust(size, "0")
        buf[start - 1 : end] = list(text)
    out = "".join(buf)
    assert len(out) == width
    return out


def num(value: Decimal, size: int) -> str:
    return str(int((value * 100).quantize(Decimal("1")))).rjust(size, "0")


def ddmmyyyy(d: date) -> str:
    return d.strftime("%d%m%Y")


def ddmmyy(d: date) -> str:
    return d.strftime("%d%m%y")


@dataclass
class Payment:
    kind: str  # "A" (transfer) or "J" (boleto)
    name: str
    amount: Decimal
    when: date
    doc: str  # payee CNPJ
    ref: str
    occurrence: str = "00"


@dataclass
class Liquidation:
    our_number: str
    doc_number: str
    amount: Decimal
    when: date
    occurrence: str = "06"
    payer_name: str = "MORADOR FICTICIO"
    payer_doc: str = "52998224725"


def cnab240(
    bank: str,
    company_cnpj: str,
    payments: Sequence[Payment] = (),
    liquidations: Sequence[Liquidation] = (),
) -> bytes:
    rows = [
        line(
            240,
            {
                (1, 3): bank,
                (4, 7): "0000",
                (8, 8): "0",
                (18, 18): "2",
                (19, 32): company_cnpj,
                (73, 102): "CONDOMINIO FICTICIO",
                (143, 143): "2",
                (144, 151): "05112026",
            },
        )
    ]
    seq = 0
    if payments:
        rows.append(
            line(240, {(1, 3): bank, (4, 7): "0001", (8, 8): "1", (9, 9): "C", (10, 11): "20"})
        )
        for p in payments:
            seq += 1
            if p.kind == "A":
                rows.append(
                    line(
                        240,
                        {
                            (1, 3): bank,
                            (4, 7): "0001",
                            (8, 8): "3",
                            (9, 13): str(seq).zfill(5),
                            (14, 14): "A",
                            (44, 73): p.name[:30],
                            (74, 93): p.ref,
                            (94, 101): ddmmyyyy(p.when),
                            (120, 134): num(p.amount, 15),
                            (135, 154): f"NN{p.ref}",
                            (155, 162): ddmmyyyy(p.when),
                            (163, 177): num(p.amount, 15),
                            (231, 240): p.occurrence,
                        },
                    )
                )
                seq += 1
                rows.append(
                    line(
                        240,
                        {
                            (1, 3): bank,
                            (4, 7): "0001",
                            (8, 8): "3",
                            (9, 13): str(seq).zfill(5),
                            (14, 14): "B",
                            (18, 18): "2",
                            (19, 32): p.doc,
                        },
                    )
                )
            else:
                rows.append(
                    line(
                        240,
                        {
                            (1, 3): bank,
                            (4, 7): "0001",
                            (8, 8): "3",
                            (9, 13): str(seq).zfill(5),
                            (14, 14): "J",
                            (18, 61): "3419" + "1" * 40,
                            (62, 91): p.name[:30],
                            (92, 99): ddmmyyyy(p.when),
                            (100, 114): num(p.amount, 15),
                            (145, 152): ddmmyyyy(p.when),
                            (153, 167): num(p.amount, 15),
                            (183, 202): p.ref,
                            (203, 222): f"NN{p.ref}",
                            (231, 240): p.occurrence,
                        },
                    )
                )
                seq += 1
                rows.append(
                    line(
                        240,
                        {
                            (1, 3): bank,
                            (4, 7): "0001",
                            (8, 8): "3",
                            (9, 13): str(seq).zfill(5),
                            (14, 14): "J",
                            (18, 19): "52",
                            (20, 20): "2",
                            (21, 35): company_cnpj,
                            (76, 76): "2",
                            (77, 91): p.doc,
                            (92, 131): p.name,
                        },
                    )
                )
        rows.append(line(240, {(1, 3): bank, (4, 7): "0001", (8, 8): "5"}))
    if liquidations:
        rows.append(
            line(240, {(1, 3): bank, (4, 7): "0002", (8, 8): "1", (9, 9): "T", (10, 11): "01"})
        )
        for liq in liquidations:
            seq += 1
            rows.append(
                line(
                    240,
                    {
                        (1, 3): bank,
                        (4, 7): "0002",
                        (8, 8): "3",
                        (9, 13): str(seq).zfill(5),
                        (14, 14): "T",
                        (16, 17): liq.occurrence,
                        (38, 57): liq.our_number,
                        (59, 73): liq.doc_number,
                        (74, 81): ddmmyyyy(liq.when),
                        (82, 96): num(liq.amount, 15),
                        (133, 133): "1",
                        (134, 148): liq.payer_doc,
                        (149, 188): liq.payer_name,
                    },
                )
            )
            seq += 1
            rows.append(
                line(
                    240,
                    {
                        (1, 3): bank,
                        (4, 7): "0002",
                        (8, 8): "3",
                        (9, 13): str(seq).zfill(5),
                        (14, 14): "U",
                        (16, 17): liq.occurrence,
                        (78, 92): num(liq.amount, 15),
                        (138, 145): ddmmyyyy(liq.when),
                        (146, 153): ddmmyyyy(liq.when),
                    },
                )
            )
        rows.append(line(240, {(1, 3): bank, (4, 7): "0002", (8, 8): "5"}))
    rows.append(line(240, {(1, 3): bank, (4, 7): "9999", (8, 8): "9"}))
    return ("\r\n".join(rows) + "\r\n").encode("latin-1")


# Positions per bank for CNAB 400 (mirror of the parser's table, written independently).
CNAB400_POS: dict[str, dict[str, Any]] = {
    "341": {"type": "1", "our": (63, 70), "credit": (296, 301), "payer": (325, 354)},
    "237": {"type": "1", "our": (71, 82), "credit": (296, 301), "payer": None},
    "001": {"type": "7", "our": (64, 80), "credit": (176, 181), "payer": None},
}


def cnab400(bank: str, company_cnpj: str, liquidations: list[Liquidation]) -> bytes:
    pos = CNAB400_POS[bank]
    rows = [
        line(
            400,
            {
                (1, 1): "0",
                (2, 2): "2",
                (3, 9): "RETORNO",
                (10, 11): "01",
                (12, 26): "COBRANCA",
                (77, 79): bank,
                (95, 100): "051126",
            },
        )
    ]
    for i, liq in enumerate(liquidations, start=2):
        fields = {
            (1, 1): pos["type"],
            (2, 3): "02",
            (4, 17): company_cnpj,
            pos["our"]: liq.our_number,
            (109, 110): liq.occurrence,
            (111, 116): ddmmyy(liq.when),
            (117, 126): liq.doc_number,
            (147, 152): ddmmyy(liq.when),
            (153, 165): num(liq.amount, 13),
            (254, 266): num(liq.amount, 13),
            pos["credit"]: ddmmyy(liq.when),
            (395, 400): str(i).zfill(6),
        }
        if pos["payer"]:
            fields[pos["payer"]] = liq.payer_name[:30]
        rows.append(line(400, fields))
    rows.append(line(400, {(1, 1): "9", (395, 400): str(len(rows) + 1).zfill(6)}))
    return ("\r\n".join(rows) + "\r\n").encode("latin-1")


def ofx_sgml(entries: list[tuple[date, Decimal, str, str]]) -> bytes:
    """entries: (date, amount, fitid, memo)."""
    trns = "".join(
        f"<STMTTRN>\n<TRNTYPE>{'DEBIT' if amt < 0 else 'CREDIT'}\n<DTPOSTED>{d:%Y%m%d}120000[-3:BRT]\n"
        f"<TRNAMT>{amt}\n<FITID>{fitid}\n<MEMO>{memo}\n</STMTTRN>\n"
        for d, amt, fitid, memo in entries
    )
    text = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\n"
        "CHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
        "<OFX>\n<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n<CURDEF>BRL\n<BANKACCTFROM>\n"
        "<BANKID>0341\n<ACCTID>12345-6\n</BANKACCTFROM>\n<BANKTRANLIST>\n"
        f"{trns}</BANKTRANLIST>\n</STMTRS>\n</STMTTRNRS>\n</BANKMSGSRSV1>\n</OFX>\n"
    )
    return text.encode("cp1252")
