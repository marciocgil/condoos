"""Monthly report and decision trail as PDF (ReportLab, BSD).

Printed documents use a light layout (the dark Design System theme is for screens); the
lime accent appears only as a thin rule. Every page carries the AI footer (spec §11).
"""

import io
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.money import brl
from app.reports.data import (
    ACTION_LABEL,
    FOOTER,
    SEVERITY_LABEL,
    STATUS_LABEL,
    MonthReport,
)

TZ = ZoneInfo("America/Sao_Paulo")
INK = colors.HexColor("#14181C")
MUTED = colors.HexColor("#5B636B")
LINE = colors.HexColor("#D5D9DD")
ACCENT = colors.HexColor("#B8E62E")
SEVERITY_COLOR = {
    "alta": colors.HexColor("#C0392B"),
    "media": colors.HexColor("#B7791F"),
    "baixa": colors.HexColor("#2F6FA3"),
}
MONTHS = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

_base = getSampleStyleSheet()
H1 = ParagraphStyle(
    "h1",
    parent=_base["Title"],
    fontSize=18,
    leading=22,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=2,
)
H2 = ParagraphStyle(
    "h2",
    parent=_base["Heading2"],
    fontSize=13,
    leading=16,
    textColor=INK,
    spaceBefore=10,
    spaceAfter=6,
)
BODY = ParagraphStyle("body", parent=_base["BodyText"], fontSize=9.5, leading=13, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11)


def _esc(text: Any) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def month_name(month: Any) -> str:
    return f"{MONTHS[month.month - 1]} de {month.year}"


def _local(dt: datetime) -> str:
    return dt.astimezone(TZ).strftime("%d/%m/%Y %H:%M")


def _footer(title: str, text: str = FOOTER) -> Callable[[Any, Any], None]:
    def draw(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(LINE)
        canvas.line(18 * mm, 16 * mm, width - 18 * mm, 16 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 11.5 * mm, text)
        canvas.drawRightString(width - 18 * mm, 7.5 * mm, f"{title} · página {doc.page}")
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(2)
        canvas.line(18 * mm, A4[1] - 12 * mm, 40 * mm, A4[1] - 12 * mm)
        canvas.restoreState()

    return draw


def _doc(buffer: io.BytesIO, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
        title=title,
        author="CondoOS",
    )


def _table(rows: list[list[Any]], widths: list[float], header: bool = True) -> Table:
    data = [[c if isinstance(c, Paragraph) else Paragraph(_esc(c), CELL) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F3F5")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


def _severity(sev: str) -> Paragraph:
    color = SEVERITY_COLOR.get(sev, MUTED).hexval()[2:]
    return Paragraph(f'<font color="#{color}">●</font> {SEVERITY_LABEL.get(sev, sev)}', CELL)


def month_report_pdf(r: MonthReport) -> bytes:
    title = f"Relatório de {month_name(r.month)}"
    buffer = io.BytesIO()
    doc = _doc(buffer, f"{title} — {r.condominium}")
    story: list[Any] = []

    # Page 1: summary
    story.append(Paragraph(_esc(r.condominium), H1))
    story.append(
        Paragraph(
            f"CNPJ {_esc(r.condominium_cnpj)} · Competência {r.month:%m/%Y} "
            f"({'fechada' if not r.preview else 'em aberto — prévia'}) · "
            f"Gerado em {_local(r.generated_at)}",
            SMALL,
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph(title, H2))
    kpis = [
        ["Valor em risco", "Achados", "Graves", "Médios", "Baixos", "Despesas do mês"],
        [
            brl(r.amount_at_risk),
            str(len(r.findings)),
            str(r.by_severity["alta"]),
            str(r.by_severity["media"]),
            str(r.by_severity["baixa"]),
            f"{brl(r.expenses_total)} ({len(r.expenses)})",
        ],
    ]
    story.append(_table(kpis, [32 * mm, 20 * mm, 18 * mm, 18 * mm, 18 * mm, 68 * mm]))
    story.append(
        Paragraph("Valor em risco soma os achados ainda em análise (ignorados não entram).", SMALL)
    )
    if r.coverage:
        story.append(Paragraph("Cobertura deste relatório", H2))
        for line in r.coverage:
            story.append(Paragraph(_esc(line), SMALL))
    story.append(Paragraph("Principais achados", H2))
    if r.top:
        rows: list[list[Any]] = [["Gravidade", "Achado", "Fornecedor", "Valor em risco"]]
        for f in r.top:
            rows.append([_severity(f.severity), f.title, f.supplier or "—", brl(f.amount_at_risk)])
        story.append(_table(rows, [24 * mm, 82 * mm, 42 * mm, 26 * mm]))
    else:
        story.append(Paragraph("Nenhum achado nesta competência.", BODY))

    # Following pages: one block per finding
    if r.findings:
        story.append(PageBreak())
        story.append(Paragraph("Achados", H2))
        for i, f in enumerate(r.findings, start=1):
            block: list[Any] = [
                Paragraph(
                    f"<b>{i}. {_esc(f.title)}</b>",
                    ParagraphStyle("ft", parent=BODY, fontSize=10.5, leading=14),
                ),
                Paragraph(
                    f"{SEVERITY_LABEL.get(f.severity, f.severity)} · Regra {f.rule_code} · "
                    f"{_esc(f.category or 'Sem categoria')} · {_esc(f.supplier or 'Sem fornecedor')}"
                    f" · Valor em risco <b>{brl(f.amount_at_risk)}</b> · "
                    f"Status: {STATUS_LABEL.get(f.status, f.status)}",
                    SMALL,
                ),
                Spacer(1, 3),
                Paragraph(_esc(f.explanation), BODY),
            ]
            if f.evidence:
                block.append(Paragraph("<b>Evidências</b>", SMALL))
                block += [Paragraph(f"• {_esc(e)}", SMALL) for e in f.evidence]
            if f.decisions:
                block.append(Paragraph("<b>Decisões</b>", SMALL))
                for d in f.decisions:
                    comment = f" — “{_esc(d.comment)}”" if d.comment else ""
                    block.append(
                        Paragraph(
                            f"• {ACTION_LABEL.get(d.action, d.action)} por {_esc(d.user_name)} "
                            f"em {_local(d.decided_at)}{comment}",
                            SMALL,
                        )
                    )
            else:
                block.append(Paragraph("Sem decisão registrada até a geração.", SMALL))
            block.append(Spacer(1, 10))
            story.append(KeepTogether(block))

    # Annex: documents analysed
    story.append(PageBreak())
    story.append(Paragraph("Anexo — documentos analisados", H2))
    if r.documents:
        rows = [["Documento", "Tipo", "Recebido em", "Situação"]]
        rows += [[d.name, d.doc_type, _local(d.received_at), d.status] for d in r.documents]
        story.append(_table(rows, [74 * mm, 34 * mm, 30 * mm, 36 * mm]))
    else:
        story.append(
            Paragraph(
                "Nenhum documento fiscal foi vinculado às despesas desta competência; a "
                "análise usou os lançamentos, os contratos e o extrato.",
                BODY,
            )
        )
    footer = _footer(f"{r.condominium} — {r.month:%m/%Y}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def trail_pdf(condominium: str, items: list[dict[str, Any]], generated_at: datetime) -> bytes:
    """Decision trail for the assembly: every decision, oldest first."""
    buffer = io.BytesIO()
    doc = _doc(buffer, f"Trilha de decisões — {condominium}")
    story: list[Any] = [
        Paragraph(_esc(condominium), H1),
        Paragraph(f"Trilha de decisões · gerada em {_local(generated_at)}", SMALL),
        Spacer(1, 10),
    ]
    if items:
        rows: list[list[Any]] = [["Data", "Competência", "Achado", "Decisão", "Por", "Comentário"]]
        for it in items:
            rows.append(
                [
                    _local(it["decided_at"]),
                    f"{it['competence']:%m/%Y}",
                    f"{it['rule_code']} · {it['title']}",
                    ACTION_LABEL.get(it["action"], it["action"]),
                    it["user_name"],
                    it["comment"] or "—",
                ]
            )
        story.append(_table(rows, [24 * mm, 18 * mm, 50 * mm, 24 * mm, 26 * mm, 32 * mm]))
    else:
        story.append(Paragraph("Nenhuma decisão registrada.", BODY))
    if items:
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"{len(items)} decisão(ões) registrada(s).", SMALL))
    footer = _footer(f"{condominium} — trilha de decisões")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


DOSSIER_FOOTER = (
    "Dossiê gerado pelo CondoOS com apoio de IA. Mostra só o que está registrado; "
    "não é laudo nem parecer técnico ou jurídico."
)


def compliance_dossier_pdf(d: dict[str, Any], generated_at: datetime) -> bytes:
    """One compliance obligation (D109, CAP-08.06): situation, who decided it applies and why,
    the documents and dates registered (and how each date was obtained) and the history."""
    buffer = io.BytesIO()
    title = f"Dossiê — {d['name']}"
    doc = _doc(buffer, title)
    s = d["situation"]
    story: list[Any] = [
        Paragraph(_esc(d["name"]), H1),
        Paragraph(f"{_esc(d['condominium'])} · gerado em {_local(generated_at)}", SMALL),
        Spacer(1, 8),
        Paragraph(f"<b>Situação:</b> {_esc(s['label'])} — {_esc(s['text'])}", BODY),
    ]
    if s.get("to_confirm"):
        story.append(Paragraph(f"Atenção: {_esc(s['to_confirm'])}.", BODY))
    period = d["periodicity_months"]
    rows: list[list[Any]] = [
        ["Área", d["category_label"]],
        ["Se aplica", d["applicability_label"]],
        ["Decidido por", d["validated_by"] or "—"],
        ["Quando", _local(d["validated_at"]) if d["validated_at"] else "—"],
        ["Motivo (onde consta)", d["validation_reason"] or "—"],
        ["Renovação", f"a cada {period} meses" if period else "não informada"],
        ["Aviso", f"{d['lead_days']} dias antes do vencimento"],
        ["Responsável", d["responsible"] or "—"],
        [
            "Base normativa",
            "Não informada pelo CondoOS: confirmar com o responsável técnico ou jurídico.",
        ],
    ]
    story += [Paragraph("Dados da obrigação", H2), _table(rows, [45 * mm, 129 * mm], header=False)]
    story.append(Paragraph("Documentos e datas registrados", H2))
    if d["evidence"]:
        ev_rows: list[list[Any]] = [["Registrado em", "Emissão", "Validade", "Origem", "Documento"]]
        for e in d["evidence"]:
            ev_rows.append(
                [
                    _local(e["created_at"]),
                    e["issued_on"] or "—",
                    e["valid_until"] or "—",
                    e["source_label"],
                    e["document"] or "—",
                ]
            )
        story.append(_table(ev_rows, [30 * mm, 22 * mm, 22 * mm, 46 * mm, 54 * mm]))
    else:
        story.append(Paragraph("Nenhum documento registrado no CondoOS.", BODY))
    story.append(Paragraph("Histórico", H2))
    hist: list[list[Any]] = [["Quando", "O quê", "Por"]]
    for e in d["events"]:
        hist.append([_local(e["at"]), e["label"], e["by"] or "sistema"])
    story.append(_table(hist, [34 * mm, 90 * mm, 50 * mm]))
    footer = _footer(title, DOSSIER_FOOTER)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
