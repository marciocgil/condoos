"""Monthly report as XLSX (openpyxl, MIT): sheets Achados, Despesas, Fornecedores and
Contratos (spec §11). Each sheet repeats the AI notice in its first row and in the
printed page footer."""

import io
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.reports.data import ACTION_LABEL, FOOTER, SEVERITY_LABEL, STATUS_LABEL, MonthReport

MONEY = '"R$" #,##0.00'
DATE = "DD/MM/YYYY"
HEADER_FILL = PatternFill("solid", fgColor="E9ECEF")


def _sheet(ws: Worksheet, title: str, headers: list[str], widths: list[int]) -> None:
    ws.append([FOOTER])
    ws["A1"].font = Font(italic=True, color="5B636B")
    ws.append([title])
    ws["A2"].font = Font(bold=True, size=12)
    ws.append(headers)
    for i, width in enumerate(widths, start=1):
        cell = ws.cell(row=3, column=i)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A4"
    footer = ws.oddFooter
    if footer is not None:
        footer.center.text = FOOTER
        footer.center.size = 8


def _format(ws: Worksheet, money_cols: list[int], date_cols: list[int]) -> None:
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if cell.column in money_cols:
                cell.number_format = MONEY
            if cell.column in date_cols:
                cell.number_format = DATE


def month_report_xlsx(r: MonthReport) -> bytes:
    wb = Workbook()
    title = f"{r.condominium} — competência {r.month:%m/%Y}" + (" (prévia)" if r.preview else "")

    ws = wb.active
    assert ws is not None
    ws.title = "Achados"
    _sheet(
        ws,
        title,
        [
            "Gravidade",
            "Regra",
            "Achado",
            "Fornecedor",
            "Categoria",
            "Valor em risco",
            "Status",
            "Última decisão",
            "Explicação",
            "Evidências",
        ],
        [11, 8, 40, 32, 16, 15, 16, 28, 60, 50],
    )
    for f in r.findings:
        last = f.decisions[-1] if f.decisions else None
        decision = (
            f"{ACTION_LABEL.get(last.action, last.action)} por {last.user_name}"
            + (f": {last.comment}" if last.comment else "")
            if last
            else ""
        )
        ws.append(
            [
                SEVERITY_LABEL.get(f.severity, f.severity),
                f.rule_code,
                f.title,
                f.supplier or "",
                f.category or "",
                f.amount_at_risk,
                STATUS_LABEL.get(f.status, f.status),
                decision,
                f.explanation,
                "\n".join(f.evidence),
            ]
        )
    _format(ws, [6], [])

    ws = wb.create_sheet("Despesas")
    _sheet(
        ws,
        title,
        [
            "Emissão",
            "Vencimento",
            "Fornecedor",
            "CNPJ",
            "Categoria",
            "Descrição",
            "Nota fiscal",
            "Valor",
            "Pago em",
        ],
        [12, 12, 34, 20, 16, 44, 14, 14, 12],
    )
    for e in r.expenses:
        row: list[Any] = [
            e.issue_date,
            e.due_date,
            e.supplier or "",
            e.supplier_cnpj or "",
            e.category,
            e.description,
            e.invoice_number or "",
            e.amount,
            e.paid_on,
        ]
        ws.append(row)
    ws.append([None, None, None, None, None, "Total", None, r.expenses_total, None])
    ws.cell(row=ws.max_row, column=6).font = Font(bold=True)
    _format(ws, [8], [1, 2, 9])

    ws = wb.create_sheet("Fornecedores")
    _sheet(
        ws,
        title,
        ["Fornecedor", "CNPJ", "Situação cadastral", "Despesas no mês", "Total no mês", "Achados"],
        [40, 20, 18, 16, 16, 10],
    )
    for s in r.suppliers:
        ws.append([s.name, s.cnpj, s.status or "", s.expenses, s.total, s.findings])
    _format(ws, [5], [])

    ws = wb.create_sheet("Contratos")
    _sheet(
        ws,
        title,
        [
            "Fornecedor",
            "Objeto",
            "Valor mensal (contrato)",
            "Índice",
            "Mês do reajuste",
            "Início",
            "Fim",
        ],
        [34, 44, 20, 10, 14, 12, 12],
    )
    for c in r.contracts:
        ws.append([c.supplier, c.object, c.monthly_value, c.index, c.base_month, c.start, c.end])
    _format(ws, [3], [6, 7])

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
