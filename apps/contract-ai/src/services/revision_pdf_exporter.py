# -*- coding: utf-8 -*-
"""
PDF exporter for RevisionDiffReport.

Produces a landscape-A3 PDF whose look matches the xlsx exporter
(`revision_xlsx_exporter`): same dark-blue header row, Arial 10pt body
text, same 12 columns. Followed by a "Краткие выводы" section.

Why landscape A3: at 12 columns the report is unreadable on portrait A4.
A3 landscape keeps the table legible without truncating Russian text.

Font handling:
- Tries to register a Unicode-capable TTF (DejaVuSans, Liberation,
  Arial). Falls back to Helvetica with a warning — the report will
  still render but Cyrillic may look ugly. This is exactly the same
  trade-off the existing PDFGenerator makes.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from loguru import logger
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepInFrame,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .revision_comparator import (
    ASSESSMENT_LABELS_RU,
    PERSPECTIVE_LABELS_RU,
    RISK_LABELS_RU,
    RevisionDiffReport,
    RevisionDiffRow,
)


# Same colour as the xlsx header so xlsx + pdf + future UI all share it.
HEADER_BG_HEX = "#1F4E78"
HEADER_TEXT_HEX = "#FFFFFF"
LABEL_BG_HEX = "#D9EAF7"          # summary labels, mirrors xlsx
ROW_GRID_HEX = "#BFBFBF"          # subtle horizontal rules between rows

# Column widths in mm, totalling ~390mm (A3 landscape = 420 - 2*15 = 390 usable).
# Matches the relative proportions of the xlsx column widths.
DIFF_COL_WIDTHS_MM = (10, 22, 28, 35, 50, 50, 50, 18, 18, 50, 45, 25)

DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"
UNICODE_FONT = "RevisionBody"
UNICODE_FONT_BOLD = "RevisionBodyBold"


def _try_register_unicode_fonts() -> tuple[str, str]:
    """Register a Cyrillic-capable TTF if we can find one on the system.

    Returns the (regular, bold) font names actually usable. Falls back to
    Helvetica when no TTF is locatable — the PDF still renders, just with
    poorer Cyrillic glyphs.
    """
    candidates = (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        # macOS — bundled fonts that ship with the system
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    )
    for regular_path, bold_path in candidates:
        if os.path.isfile(regular_path):
            try:
                pdfmetrics.registerFont(TTFont(UNICODE_FONT, regular_path))
                if os.path.isfile(bold_path):
                    pdfmetrics.registerFont(TTFont(UNICODE_FONT_BOLD, bold_path))
                    return UNICODE_FONT, UNICODE_FONT_BOLD
                return UNICODE_FONT, UNICODE_FONT
            except Exception:
                logger.warning("Failed to register %s, trying next candidate", regular_path)
    logger.warning("No Unicode-capable TTF found, falling back to Helvetica (Cyrillic may look poor)")
    return DEFAULT_FONT, DEFAULT_FONT_BOLD


def export_report(
    report: RevisionDiffReport,
    output_path: Union[str, Path],
    *,
    old_revision_label: str = "Редакция 1",
    new_revision_label: str = "Редакция 2",
) -> Path:
    """Render `report` to a PDF at `output_path`. Overwrites if exists."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    body_font, bold_font = _try_register_unicode_fonts()
    styles = _build_styles(body_font, bold_font)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=landscape(A3),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=report.summary.title,
    )

    story: list = []
    story.extend(_summary_block(report, styles))
    story.append(Spacer(1, 8 * mm))
    story.append(_diff_table(report, old_revision_label, new_revision_label, styles))

    doc.build(story)
    return out


# --- styles ---------------------------------------------------------------

def _build_styles(body_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=14,
            textColor=colors.HexColor(HEADER_TEXT_HEX),
            backColor=colors.HexColor(HEADER_BG_HEX),
            alignment=1,
            leading=18,
            spaceAfter=4,
            borderPadding=8,
        ),
        "label": ParagraphStyle(
            "Label",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=10,
            textColor=colors.HexColor("#1A1A1A"),
            backColor=colors.HexColor(LABEL_BG_HEX),
            leading=13,
            borderPadding=4,
        ),
        "value": ParagraphStyle(
            "Value",
            parent=base["Normal"],
            fontName=body_font,
            fontSize=10,
            textColor=colors.HexColor("#1A1A1A"),
            leading=13,
            borderPadding=4,
        ),
        "th": ParagraphStyle(
            "TH",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=9.5,
            textColor=colors.HexColor(HEADER_TEXT_HEX),
            alignment=1,
            leading=12,
        ),
        "td": ParagraphStyle(
            "TD",
            parent=base["Normal"],
            fontName=body_font,
            fontSize=9,
            textColor=colors.HexColor("#1A1A1A"),
            leading=11,
        ),
        "td_center": ParagraphStyle(
            "TDC",
            parent=base["Normal"],
            fontName=body_font,
            fontSize=9,
            textColor=colors.HexColor("#1A1A1A"),
            alignment=1,
            leading=11,
        ),
    }


# --- summary block --------------------------------------------------------

def _summary_block(report: RevisionDiffReport, styles: dict[str, ParagraphStyle]) -> list:
    s = report.summary
    parts: list = [Paragraph(_escape(s.title), styles["title"])]

    label_value_rows = [
        ("Дата подготовки", s.prepared_at.strftime("%d.%m.%Y %H:%M UTC")),
        ("Точка зрения", PERSPECTIVE_LABELS_RU[report.perspective]),
        ("Сравниваемые документы", s.documents_compared),
        ("Общий вывод", s.overall_verdict),
        ("Ключевые плюсы", _bulleted(s.key_pros)),
        ("Ключевые риски", _bulleted(s.key_risks)),
        ("Что править перед подписанием", _bulleted(s.pre_signature_edits)),
    ]
    for label, value in s.source_files.items():
        if value:
            label_value_rows.append((label, value))

    data = [
        [Paragraph(_escape(label), styles["label"]),
         Paragraph(_escape(value), styles["value"])]
        for label, value in label_value_rows
    ]
    table = Table(data, colWidths=[60 * mm, 320 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(LABEL_BG_HEX)),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(ROW_GRID_HEX)),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    parts.append(Spacer(1, 4 * mm))
    parts.append(table)
    return parts


# --- diff table -----------------------------------------------------------

def _diff_table(
    report: RevisionDiffReport,
    old_label: str,
    new_label: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    perspective_label = PERSPECTIVE_LABELS_RU[report.perspective]
    headers = (
        "№",
        "Пункт",
        "Блок",
        "Условие",
        old_label,
        new_label,
        "Изменение / несоответствие",
        f"Оценка для «{perspective_label}»",
        "Риск",
        "Комплексное влияние на договор",
        "Рекомендация",
        "Источник",
    )

    rows: list = [[Paragraph(_escape(h), styles["th"]) for h in headers]]
    for r in report.rows:
        rows.append(_format_row(r, styles))

    col_widths = [w * mm for w in DIFF_COL_WIDTHS_MM]
    table = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(HEADER_BG_HEX)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (1, -1), "CENTER"),    # №, Пункт
        ("ALIGN", (7, 1), (8, -1), "CENTER"),    # Оценка, Риск
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor(HEADER_BG_HEX)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor(ROW_GRID_HEX)),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _format_row(r: RevisionDiffRow, styles: dict[str, ParagraphStyle]) -> list:
    center = styles["td_center"]
    body = styles["td"]
    return [
        Paragraph(str(r.number), center),
        Paragraph(_escape(r.clause_pair_label), center),
        Paragraph(_escape(r.block), body),
        Paragraph(_escape(r.condition), body),
        Paragraph(_escape(r.old_text or "—"), body),
        Paragraph(_escape(r.new_text or "—"), body),
        Paragraph(_escape(r.change_summary), body),
        Paragraph(_escape(ASSESSMENT_LABELS_RU[r.assessment]), center),
        Paragraph(_escape(RISK_LABELS_RU[r.risk_level]), center),
        Paragraph(_escape(r.complex_impact), body),
        Paragraph(_escape(r.recommendation), body),
        Paragraph(_escape(r.source), body),
    ]


# --- helpers --------------------------------------------------------------

def _bulleted(items: list[str]) -> str:
    if not items:
        return "—"
    return "<br/>".join(f"• {_escape(item)}" for item in items)


def _escape(text: str) -> str:
    """Escape XML-special chars for reportlab Paragraph; preserve newlines."""
    if text is None:
        return ""
    escaped = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return escaped.replace("\n", "<br/>")


__all__ = ["export_report"]
