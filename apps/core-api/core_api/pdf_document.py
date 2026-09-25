"""PDF договора и допсоглашения — точный текст и лист «Сведения о подписании».

Клиенту договор уходил текстовым файлом .txt: так выглядит служебная выгрузка,
а не документ, под которым ставят подпись. Здесь тот же точный текст — ровно
тот, чья контрольная сумма зафиксирована, — в PDF, и последним листом —
сведения из системы: кто, когда и каким способом подписал.

Лист сведений собирается из журнала системы и в текст документа не входит:
подписывается текст, а лист лишь показывает, что с ним происходило.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Шрифт с кириллицей: в образе ядра — DejaVu из пакетов Debian (см. Dockerfile),
# на машине разработчика — системный. Путь можно задать и явно.
_REGULAR = (
    os.environ.get("PDF_FONT_PATH", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)
_BOLD = (
    os.environ.get("PDF_FONT_BOLD_PATH", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)

_MSK = timezone(timedelta(hours=3))


class FontMissing(RuntimeError):
    """Нет шрифта с кириллицей — PDF собрать нельзя, отдаём текст."""


def _first_existing(paths: tuple[str, ...]) -> str | None:
    return next((p for p in paths if p and Path(p).is_file()), None)


def msk(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(_MSK).strftime("%d.%m.%Y %H:%M МСК")


class _Document(FPDF):
    def __init__(self, footer_label: str) -> None:
        super().__init__(format="A4")
        self._footer_label = footer_label

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Body", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, f"{self._footer_label} · стр. {self.page_no()} из {{nb}}", align="C")
        self.set_text_color(0, 0, 0)


def render(
    *,
    text: str,
    footer_label: str,
    certificate_title: str,
    certificate_rows: list[tuple[str, str]],
    certificate_note: str,
) -> bytes:
    """Точный текст документа и лист сведений — в один PDF."""
    regular = _first_existing(_REGULAR)
    if regular is None:
        raise FontMissing("no Cyrillic font for PDF")
    bold = _first_existing(_BOLD) or regular

    pdf = _Document(footer_label)
    pdf.set_title(footer_label)
    pdf.set_creator("AI Verdict")
    pdf.add_font("Body", "", regular)
    pdf.add_font("Body", "B", bold)
    # В DejaVu знак рубля есть, в части системных шрифтов — нет: там он
    # пропал бы из суммы молча. Лучше «руб.», чем «100 000 ».
    if 0x20BD not in getattr(pdf.fonts.get("body"), "cmap", {0x20BD: 0}):
        text = text.replace("₽", "руб.")
        certificate_rows = [(label, value.replace("₽", "руб.")) for label, value in certificate_rows]
    pdf.set_margins(18, 16, 18)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages()

    pdf.add_page()
    lines = text.splitlines()
    for index, line in enumerate(lines):
        # Первая строка — заголовок документа («ДОГОВОР …», «ДОПОЛНИТЕЛЬНОЕ
        # СОГЛАШЕНИЕ …»): его выделяем, остальное идёт как есть — текст
        # подписан ровно таким.
        if index == 0:
            pdf.set_font("Body", "B", 12)
            pdf.multi_cell(0, 6, line, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
            continue
        pdf.set_font("Body", "", 10)
        if not line.strip():
            pdf.ln(3)
            continue
        pdf.multi_cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.add_page()
    pdf.set_font("Body", "B", 12)
    pdf.multi_cell(0, 6, certificate_title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)
    label_width = 58
    for label, value in certificate_rows:
        pdf.set_font("Body", "B", 9)
        y = pdf.get_y()
        pdf.multi_cell(label_width, 5, label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        label_bottom = pdf.get_y()
        pdf.set_xy(pdf.l_margin + label_width + 2, y)
        pdf.set_font("Body", "", 9)
        pdf.multi_cell(0, 5, value or "—", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_y(max(label_bottom, pdf.get_y()) + 1.5)
    pdf.ln(3)
    pdf.set_font("Body", "", 8)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 4.5, certificate_note, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    return bytes(pdf.output())


def text_hash(text: str) -> str:
    """Та же сумма, что считается при создании документа (service_agreement.document_hash)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
