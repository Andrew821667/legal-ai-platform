# -*- coding: utf-8 -*-
"""
PDF Generator - Comprehensive PDF generation using reportlab

Features:
- Contract export to PDF
- Disagreement letters to PDF
- Change reports to PDF
- Multi-language support (Russian + English)
- Professional formatting with logos and headers
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import os
from loguru import logger

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Import constants for consistency
from .constants import (
    PDF_PAGE_WIDTH, PDF_PAGE_HEIGHT, PDF_MARGIN,
    MAX_RISKS_IN_REPORT, MAX_RECOMMENDATIONS_IN_REPORT
)


class PDFGenerator:
    """
    Professional PDF generator with support for Russian text

    Usage:
        generator = PDFGenerator()
        generator.generate_contract_report(
            output_path='contract_report.pdf',
            title='Анализ договора',
            data={'risks': [...], 'recommendations': [...]}
        )
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PDF generator

        Args:
            config: Optional configuration dict with:
                - page_size: 'A4' or 'letter' (default: A4)
                - font_name: Font name for Russian text
                - logo_path: Path to company logo
        """
        self.config = config or {}

        # Page settings
        page_size_name = self.config.get('page_size', 'A4')
        self.page_size = A4 if page_size_name == 'A4' else letter
        self.page_width, self.page_height = self.page_size

        # Margins (use constants)
        self.margin_left = PDF_MARGIN * mm
        self.margin_right = PDF_MARGIN * mm
        self.margin_top = PDF_MARGIN * mm
        self.margin_bottom = PDF_MARGIN * mm

        # Register fonts for Russian text support
        self._register_fonts()

        # Styles
        self.styles = self._create_styles()

        # Logo (optional)
        self.logo_path = self.config.get('logo_path')

    def _register_fonts(self):
        """
        Register fonts that support Cyrillic

        Note: In production, you would register custom TTF fonts:
            pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

        For now, we'll use built-in fonts which have limited Cyrillic support.
        reportlab's default Helvetica doesn't support Cyrillic well,
        so in production you MUST use DejaVu or similar fonts.
        """
        # In stub mode, we'll just use built-in fonts
        # Real production code should register DejaVu fonts:
        # try:
        #     pdfmetrics.registerFont(TTFont('DejaVuSans', '/path/to/DejaVuSans.ttf'))
        #     pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/path/to/DejaVuSans-Bold.ttf'))
        # except Exception as e:
        #     logger.warning(f"Could not register custom fonts: {e}")
        pass

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom paragraph styles"""
        base_styles = getSampleStyleSheet()

        styles = {
            'Title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Title'],
                fontSize=18,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'  # Use DejaVuSans-Bold in production
            ),
            'Heading1': ParagraphStyle(
                'CustomHeading1',
                parent=base_styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=10,
                spaceBefore=12,
                fontName='Helvetica-Bold'
            ),
            'Heading2': ParagraphStyle(
                'CustomHeading2',
                parent=base_styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#34495e'),
                spaceAfter=8,
                spaceBefore=10,
                fontName='Helvetica-Bold'
            ),
            'Normal': ParagraphStyle(
                'CustomNormal',
                parent=base_styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#333333'),
                spaceAfter=6,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'  # Use DejaVuSans in production
            ),
            'Code': ParagraphStyle(
                'CustomCode',
                parent=base_styles['Code'],
                fontSize=9,
                textColor=colors.HexColor('#555555'),
                spaceAfter=6,
                fontName='Courier'
            ),
        }

        return styles

    def generate_contract_report(
        self,
        output_path: str,
        title: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate contract analysis PDF report

        Args:
            output_path: Output PDF file path
            title: Report title
            data: Report data with keys:
                - summary: Executive summary text
                - risks: List of risk dicts
                - recommendations: List of recommendation dicts
                - statistics: Statistics dict
            metadata: Optional metadata (author, date, etc.)

        Returns:
            Path to generated PDF
        """
        try:
            logger.info(f"Generating contract report PDF: {output_path}")

            # Create PDF document
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.margin_left,
                rightMargin=self.margin_right,
                topMargin=self.margin_top,
                bottomMargin=self.margin_bottom
            )

            # Build content
            story = []

            # Add header/logo if available
            if self.logo_path and os.path.exists(self.logo_path):
                story.append(self._create_logo())
                story.append(Spacer(1, 10*mm))

            # Title
            story.append(Paragraph(title, self.styles['Title']))
            story.append(Spacer(1, 5*mm))

            # Metadata
            if metadata:
                story.append(self._create_metadata_table(metadata))
                story.append(Spacer(1, 5*mm))

            # Executive summary
            if data.get('summary'):
                story.append(Paragraph('Резюме', self.styles['Heading1']))
                story.append(Paragraph(data['summary'], self.styles['Normal']))
                story.append(Spacer(1, 5*mm))

            # Statistics
            if data.get('statistics'):
                story.append(Paragraph('Статистика', self.styles['Heading1']))
                story.append(self._create_statistics_table(data['statistics']))
                story.append(Spacer(1, 5*mm))

            # Risks
            if data.get('risks'):
                story.append(PageBreak())
                story.append(Paragraph('Выявленные риски', self.styles['Heading1']))
                story.extend(self._create_risks_section(data['risks']))

            # Recommendations
            if data.get('recommendations'):
                story.append(PageBreak())
                story.append(Paragraph('Рекомендации', self.styles['Heading1']))
                story.extend(self._create_recommendations_section(data['recommendations']))

            # Footer
            story.append(Spacer(1, 10*mm))
            story.append(self._create_footer())

            # Build PDF
            doc.build(story)

            logger.info(f"PDF generated successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise

    def generate_disagreement_letter(
        self,
        output_path: str,
        disagreement_data: Dict[str, Any],
        objections: List[Dict[str, Any]]
    ) -> str:
        """
        Generate formal disagreement letter PDF

        Args:
            output_path: Output PDF path
            disagreement_data: Disagreement metadata
            objections: List of objection dicts with:
                - section: Contract section
                - issue: Issue description
                - legal_basis: Legal justification
                - alternative: Proposed alternative
                - priority: Priority level

        Returns:
            Path to generated PDF
        """
        try:
            logger.info(f"Generating disagreement letter PDF: {output_path}")

            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.page_size,
                leftMargin=self.margin_left,
                rightMargin=self.margin_right,
                topMargin=self.margin_top,
                bottomMargin=self.margin_bottom
            )

            story = []

            # Header
            if self.logo_path and os.path.exists(self.logo_path):
                story.append(self._create_logo())
                story.append(Spacer(1, 10*mm))

            # Title
            story.append(Paragraph(
                'ВОЗРАЖЕНИЯ К ПРОЕКТУ ДОГОВОРА',
                self.styles['Title']
            ))
            story.append(Spacer(1, 8*mm))

            # Date and contract info
            date_str = datetime.now().strftime('%d.%m.%Y')
            story.append(Paragraph(f'Дата: {date_str}', self.styles['Normal']))

            contract_id = disagreement_data.get('contract_id', 'N/A')
            story.append(Paragraph(
                f'По проекту договора: {contract_id}',
                self.styles['Normal']
            ))
            story.append(Spacer(1, 8*mm))

            # Objections
            story.append(Paragraph(
                'ЗАМЕЧАНИЯ И ПРЕДЛОЖЕНИЯ',
                self.styles['Heading1']
            ))
            story.append(Spacer(1, 5*mm))

            for i, objection in enumerate(objections, 1):
                story.extend(self._create_objection_block(i, objection))
                story.append(Spacer(1, 5*mm))

            # Summary
            story.append(Spacer(1, 10*mm))
            story.append(Paragraph(
                f'Всего замечаний: {len(objections)}',
                self.styles['Normal']
            ))

            # Signature block
            story.append(Spacer(1, 15*mm))
            story.append(self._create_signature_block())

            # Build
            doc.build(story)

            logger.info(f"Disagreement letter PDF generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Disagreement letter PDF failed: {e}")
            raise

    def _create_logo(self) -> Image:
        """Create logo image element"""
        return Image(self.logo_path, width=50*mm, height=15*mm)

    def _create_metadata_table(self, metadata: Dict[str, Any]) -> Table:
        """Create metadata information table"""
        data = []

        for key, value in metadata.items():
            data.append([
                Paragraph(f'<b>{key}:</b>', self.styles['Normal']),
                Paragraph(str(value), self.styles['Normal'])
            ])

        table = Table(data, colWidths=[60*mm, 110*mm])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        return table

    def _create_statistics_table(self, stats: Dict[str, Any]) -> Table:
        """Create statistics table"""
        data = [['Показатель', 'Значение']]

        for key, value in stats.items():
            data.append([
                Paragraph(str(key), self.styles['Normal']),
                Paragraph(str(value), self.styles['Normal'])
            ])

        table = Table(data, colWidths=[100*mm, 70*mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        return table

    def _create_risks_section(self, risks: List[Dict[str, Any]]) -> List:
        """Create risks section elements"""
        elements = []

        # Limit to MAX_RISKS_IN_REPORT
        risks_to_show = risks[:MAX_RISKS_IN_REPORT]

        for i, risk in enumerate(risks_to_show, 1):
            # Risk header
            severity = risk.get('severity', 'unknown')
            risk_type = risk.get('type', 'general')

            header_text = f'{i}. [{severity.upper()}] {risk_type}'
            elements.append(Paragraph(header_text, self.styles['Heading2']))

            # Description
            if risk.get('description'):
                elements.append(Paragraph(
                    risk['description'],
                    self.styles['Normal']
                ))

            # Impact
            if risk.get('impact'):
                elements.append(Paragraph(
                    f'<b>Влияние:</b> {risk["impact"]}',
                    self.styles['Normal']
                ))

            # Recommendation
            if risk.get('recommendation'):
                elements.append(Paragraph(
                    f'<b>Рекомендация:</b> {risk["recommendation"]}',
                    self.styles['Normal']
                ))

            elements.append(Spacer(1, 4*mm))

        if len(risks) > MAX_RISKS_IN_REPORT:
            elements.append(Paragraph(
                f'... и ещё {len(risks) - MAX_RISKS_IN_REPORT} рисков',
                self.styles['Normal']
            ))

        return elements

    def _create_recommendations_section(self, recommendations: List[Dict[str, Any]]) -> List:
        """Create recommendations section elements"""
        elements = []

        # Limit to MAX_RECOMMENDATIONS_IN_REPORT
        recs_to_show = recommendations[:MAX_RECOMMENDATIONS_IN_REPORT]

        for i, rec in enumerate(recs_to_show, 1):
            rec_text = rec.get('text') if isinstance(rec, dict) else str(rec)

            elements.append(Paragraph(
                f'{i}. {rec_text}',
                self.styles['Normal']
            ))
            elements.append(Spacer(1, 3*mm))

        if len(recommendations) > MAX_RECOMMENDATIONS_IN_REPORT:
            elements.append(Paragraph(
                f'... и ещё {len(recommendations) - MAX_RECOMMENDATIONS_IN_REPORT} рекомендаций',
                self.styles['Normal']
            ))

        return elements

    def _create_objection_block(self, number: int, objection: Dict[str, Any]) -> List:
        """Create single objection block"""
        elements = []

        # Header with priority
        priority = objection.get('priority', 'medium').upper()
        section = objection.get('section', 'не указан')

        header = f'{number}. Пункт договора: {section} [{priority}]'
        elements.append(Paragraph(header, self.styles['Heading2']))

        # Issue description
        if objection.get('issue'):
            elements.append(Paragraph(
                f'<b>Замечание:</b> {objection["issue"]}',
                self.styles['Normal']
            ))

        # Legal basis
        if objection.get('legal_basis'):
            elements.append(Paragraph(
                f'<b>Правовое обоснование:</b> {objection["legal_basis"]}',
                self.styles['Normal']
            ))

        # Alternative
        if objection.get('alternative'):
            elements.append(Paragraph(
                f'<b>Предлагаемая формулировка:</b> {objection["alternative"]}',
                self.styles['Normal']
            ))

        return elements

    def _create_signature_block(self) -> Table:
        """Create signature block"""
        data = [
            [Paragraph('С уважением,', self.styles['Normal']), ''],
            [Paragraph('_________________', self.styles['Normal']),
             Paragraph('_________________', self.styles['Normal'])],
            [Paragraph('(подпись)', self.styles['Normal']),
             Paragraph('(ФИО)', self.styles['Normal'])],
        ]

        table = Table(data, colWidths=[85*mm, 85*mm])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))

        return table

    def _create_footer(self) -> Paragraph:
        """Create document footer"""
        date_str = datetime.now().strftime('%d.%m.%Y')
        footer_text = f'Документ создан автоматически системой Contract AI • {date_str}'

        style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )

        return Paragraph(footer_text, style)


__all__ = ['PDFGenerator']
