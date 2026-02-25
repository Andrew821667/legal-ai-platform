# -*- coding: utf-8 -*-
"""
Change Report Generator - Generate PDF reports for contract changes
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from loguru import logger


class ChangeReportGenerator:
    """
    Generator for PDF reports of contract changes

    Features:
    - Executive summary
    - Detailed change analysis
    - Statistics and charts
    - Recommendations

    Note: This is a stub. Real implementation would use reportlab or weasyprint
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.output_dir = self.config.get('output_dir', 'data/reports')
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(
        self,
        analysis_result: Dict[str, Any],
        changes: List[Dict[str, Any]],
        output_filename: Optional[str] = None
    ) -> str:
        """
        Generate PDF report for change analysis

        Args:
            analysis_result: ChangeAnalysisResult data
            changes: List of ContractChange data
            output_filename: Optional custom filename

        Returns:
            Path to generated PDF
        """
        try:
            logger.info("Generating change analysis report PDF")

            if not output_filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f"change_report_{timestamp}.pdf"

            output_path = os.path.join(self.output_dir, output_filename)

            # Use PDFGenerator for professional PDF
            try:
                from ..utils.pdf_generator import PDFGenerator

                # Prepare data for PDF
                pdf_data = {
                    'summary': analysis_result.get('executive_summary', 'Анализ изменений договора'),
                    'statistics': self._prepare_statistics(analysis_result),
                    'risks': self._prepare_risks_from_changes(changes),
                    'recommendations': self._prepare_recommendations(analysis_result)
                }

                # Metadata
                metadata = {
                    'Тип отчёта': 'Анализ изменений договора',
                    'Дата создания': datetime.now().strftime('%d.%m.%Y %H:%M'),
                    'Всего изменений': analysis_result.get('total_changes', 0),
                    'Общая оценка': analysis_result.get('overall_assessment', 'N/A')
                }

                # Generate PDF
                generator = PDFGenerator()
                generator.generate_contract_report(
                    output_path=output_path,
                    title='Отчёт об изменениях в договоре',
                    data=pdf_data,
                    metadata=metadata
                )

                logger.info(f"PDF report generated successfully: {output_path}")
                return output_path

            except ImportError as ie:
                logger.warning(f"PDFGenerator not available: {ie}. Falling back to text report.")
                # Fallback to text report
                report_content = self._generate_text_report(analysis_result, changes)
                text_path = output_path.replace('.pdf', '.txt')
                with open(text_path, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                logger.info(f"Text report generated: {text_path}")
                return text_path

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            raise

    def _prepare_statistics(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare statistics for PDF"""
        stats = {
            'Общая оценка': analysis_result.get('overall_assessment', 'N/A'),
            'Изменение рисков': analysis_result.get('overall_risk_change', 'N/A'),
            'Всего изменений': analysis_result.get('total_changes', 0),
        }

        # Add by_type statistics
        by_type = analysis_result.get('by_type', {})
        for change_type, count in by_type.items():
            stats[f'Тип "{change_type}"'] = count

        # Add by_impact statistics
        by_impact = analysis_result.get('by_impact', {})
        for impact, count in by_impact.items():
            stats[f'Влияние "{impact}"'] = count

        # Add objections tracking if present
        if analysis_result.get('accepted_objections', 0) > 0:
            stats['Принято возражений'] = analysis_result.get('accepted_objections', 0)
            stats['Отклонено возражений'] = analysis_result.get('rejected_objections', 0)
            stats['Частично принято'] = analysis_result.get('partial_objections', 0)

        return stats

    def _prepare_risks_from_changes(self, changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract risks from changes for PDF"""
        risks = []

        for change in changes[:20]:  # Limit to 20
            impact = change.get('impact_assessment', {})
            if impact and impact.get('severity') in ['high', 'critical']:
                risks.append({
                    'severity': impact.get('severity', 'medium'),
                    'type': change.get('change_category', 'general'),
                    'description': change.get('semantic_description', 'Нет описания'),
                    'impact': f"Направление: {impact.get('direction', 'N/A')}",
                    'recommendation': impact.get('recommendation', '')
                })

        return risks

    def _prepare_recommendations(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Prepare recommendations for PDF"""
        recommendations = []

        # Main recommendations
        if analysis_result.get('recommendations'):
            recommendations.append(analysis_result['recommendations'])

        # Critical changes
        critical = analysis_result.get('critical_changes', [])
        if critical:
            recommendations.append(
                f'Обратите особое внимание на {len(critical)} критических изменений'
            )

        # Risk change
        risk_change = analysis_result.get('overall_risk_change', '')
        if 'увеличение' in risk_change.lower() or 'increase' in risk_change.lower():
            recommendations.append(
                'Общий уровень рисков увеличился - рекомендуется детальная проверка юристом'
            )

        return recommendations if recommendations else ['Специальных рекомендаций нет']

    def _generate_text_report(
        self,
        analysis_result: Dict[str, Any],
        changes: List[Dict[str, Any]]
    ) -> str:
        """
        Generate text version of report (stub for PDF)

        Real implementation would use reportlab:
        ```python
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch

        pdf = SimpleDocTemplate(output_path, pagesize=A4)
        story = []

        # Add title
        styles = getSampleStyleSheet()
        title = Paragraph("Contract Change Analysis Report", styles['Title'])
        story.append(title)

        # Add summary
        # Add statistics table
        # Add detailed changes
        # Add recommendations

        pdf.build(story)
        ```
        """
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("ОТЧЁТ ОБ ИЗМЕНЕНИЯХ В ДОГОВОРЕ")
        lines.append("=" * 80)
        lines.append(f"Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        lines.append("")

        # Executive Summary
        lines.append("РЕЗЮМЕ")
        lines.append("-" * 80)
        lines.append(f"Общая оценка: {analysis_result.get('overall_assessment', 'N/A')}")
        lines.append(f"Изменение рисков: {analysis_result.get('overall_risk_change', 'N/A')}")
        lines.append(f"Всего изменений: {analysis_result.get('total_changes', 0)}")
        lines.append("")

        if analysis_result.get('executive_summary'):
            lines.append(analysis_result['executive_summary'])
            lines.append("")

        # Statistics
        lines.append("СТАТИСТИКА")
        lines.append("-" * 80)

        by_type = analysis_result.get('by_type', {})
        if by_type:
            lines.append("По типам:")
            for change_type, count in by_type.items():
                lines.append(f"  - {change_type}: {count}")
            lines.append("")

        by_impact = analysis_result.get('by_impact', {})
        if by_impact:
            lines.append("По влиянию:")
            for impact, count in by_impact.items():
                lines.append(f"  - {impact}: {count}")
            lines.append("")

        # Disagreement tracking
        if analysis_result.get('accepted_objections', 0) > 0:
            lines.append("ПРИНЯТЫЕ ВОЗРАЖЕНИЯ")
            lines.append("-" * 80)
            lines.append(f"Принято: {analysis_result.get('accepted_objections', 0)}")
            lines.append(f"Отклонено: {analysis_result.get('rejected_objections', 0)}")
            lines.append(f"Частично: {analysis_result.get('partial_objections', 0)}")
            lines.append("")

        # Critical changes
        critical = analysis_result.get('critical_changes', [])
        if critical:
            lines.append("КРИТИЧЕСКИЕ ИЗМЕНЕНИЯ")
            lines.append("-" * 80)
            for i, change_id in enumerate(critical, 1):
                # Find change by ID
                change = next((c for c in changes if c.get('id') == change_id), None)
                if change:
                    lines.append(f"{i}. {change.get('semantic_description', 'N/A')}")
                    lines.append(f"   Раздел: {change.get('section_name', 'N/A')}")
                    lines.append("")

        # Detailed changes
        lines.append("ДЕТАЛЬНЫЙ АНАЛИЗ ИЗМЕНЕНИЙ")
        lines.append("-" * 80)

        for i, change in enumerate(changes[:20], 1):  # Limit to 20 for stub
            lines.append(f"{i}. {change.get('change_type', 'N/A').upper()}")
            lines.append(f"   Раздел: {change.get('section_name', 'N/A')}")
            lines.append(f"   Категория: {change.get('change_category', 'N/A')}")

            if change.get('semantic_description'):
                lines.append(f"   Описание: {change['semantic_description']}")

            impact = change.get('impact_assessment', {})
            if impact:
                lines.append(f"   Влияние: {impact.get('direction', 'N/A')} ({impact.get('severity', 'N/A')})")
                if impact.get('recommendation'):
                    lines.append(f"   Рекомендация: {impact['recommendation']}")

            lines.append("")

        # Recommendations
        if analysis_result.get('recommendations'):
            lines.append("РЕКОМЕНДАЦИИ")
            lines.append("-" * 80)
            lines.append(analysis_result['recommendations'])
            lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("Отчёт создан автоматически системой Contract AI")
        lines.append("=" * 80)

        return "\n".join(lines)


__all__ = ["ChangeReportGenerator"]
