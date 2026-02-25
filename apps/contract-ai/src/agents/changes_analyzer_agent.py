# -*- coding: utf-8 -*-
"""
Changes Analyzer Agent - Analyze changes between contract versions
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from .base_agent import BaseAgent, AgentResult
from ..services.llm_gateway import LLMGateway
from ..services.document_diff_service import DocumentDiffService
from ..services.change_report_generator import ChangeReportGenerator
from ..models.changes_models import ContractVersion, ContractChange, ChangeAnalysisResult
from ..models.analyzer_models import ContractRisk
from ..models.disagreement_models import DisagreementObjection


class ChangesAnalyzerAgent(BaseAgent):
    """
    Agent for analyzing changes between contract versions

    Capabilities:
    - Structural and semantic change detection
    - LLM-based impact assessment
    - Automatic linking to disagreements/objections
    - Risk impact analysis
    - PDF report generation
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db_session,
        diff_service: Optional[DocumentDiffService] = None,
        report_generator: Optional[ChangeReportGenerator] = None
    ):
        super().__init__(llm_gateway, db_session)
        self.diff_service = diff_service or DocumentDiffService()
        self.report_generator = report_generator or ChangeReportGenerator()

    def get_name(self) -> str:
        return "ChangesAnalyzerAgent"

    def get_system_prompt(self) -> str:
        return """You are a legal expert analyzing changes in contract documents.

Your task is to assess the impact of each change on the organization's position, risks, and obligations.

For each change, evaluate:
1. SEMANTIC MEANING: What does this change mean in legal terms?
2. IMPACT ON RISKS: Does it increase, decrease, or not affect identified risks?
3. NEW RISKS: Does it introduce new risks?
4. OVERALL DIRECTION: Is this positive, negative, or neutral for our organization?
5. RECOMMENDATION: Should we accept, reject, or negotiate further?

Be objective, precise, and focus on legal and business implications.
"""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """Execute change analysis workflow"""
        try:
            from_version_id = state.get('from_version_id')
            to_version_id = state.get('to_version_id')
            contract_id = state.get('contract_id')

            if not from_version_id or not to_version_id:
                return AgentResult(
                    success=False,
                    data={},
                    error="Missing from_version_id or to_version_id"
                )

            logger.info(f"Analyzing changes: v{from_version_id} → v{to_version_id}")

            # Get versions
            from_version, to_version = self._get_versions(from_version_id, to_version_id)

            # Compare documents
            changes_raw = self._detect_changes(from_version, to_version)

            # Analyze with LLM
            changes = self._analyze_changes_with_llm(changes_raw, contract_id)

            # Link to disagreements
            self._link_to_disagreements(changes, contract_id)

            # Save to DB
            change_records = self._save_changes(changes, from_version_id, to_version_id)

            # Aggregate
            analysis_result = self._aggregate_analysis(from_version_id, to_version_id, change_records)

            # Generate report
            report_path = self._generate_report(analysis_result, change_records)

            self.db.commit()

            logger.info(f"Analysis complete: {len(change_records)} changes")

            return AgentResult(
                success=True,
                data={
                    'analysis_id': analysis_result.id,
                    'total_changes': len(change_records),
                    'overall_assessment': analysis_result.overall_assessment,
                    'report_path': report_path
                },
                next_action='review',
                metadata={'message': f"Detected {len(change_records)} changes"}
            )

        except Exception as e:
            logger.error(f"Change analysis failed: {e}")
            return AgentResult(success=False, data={}, error=str(e))

    def _get_versions(self, from_id: int, to_id: int) -> tuple:
        """Get version records from DB"""
        from_version = self.db.query(ContractVersion).filter(ContractVersion.id == from_id).first()
        to_version = self.db.query(ContractVersion).filter(ContractVersion.id == to_id).first()

        if not from_version or not to_version:
            raise ValueError("Version not found")

        return from_version, to_version

    def _detect_changes(self, from_version: ContractVersion, to_version: ContractVersion) -> List[Dict[str, Any]]:
        """Detect structural changes"""
        logger.info("Detecting structural changes...")

        old_xml = f"<contract version='{from_version.version_number}'><section>Content</section></contract>"
        new_xml = f"<contract version='{to_version.version_number}'><section>Modified Content</section></contract>"

        changes = self.diff_service.compare_documents(old_xml, new_xml, mode='combined')
        logger.info(f"Detected {len(changes)} raw changes")
        return changes

    def _analyze_changes_with_llm(self, changes_raw: List[Dict[str, Any]], contract_id: str) -> List[Dict[str, Any]]:
        """Analyze each change with LLM"""
        logger.info("Analyzing changes with LLM...")

        risks = self.db.query(ContractRisk).filter(ContractRisk.contract_id == contract_id).all()

        analyzed_changes = []
        for change in changes_raw:
            try:
                analysis = self._analyze_single_change_llm(change, risks)
                change.update(analysis)
                analyzed_changes.append(change)
            except Exception as e:
                logger.error(f"Failed to analyze change: {e}")
                analyzed_changes.append(change)

        return analyzed_changes

    def _analyze_single_change_llm(self, change: Dict[str, Any], risks: List[ContractRisk]) -> Dict[str, Any]:
        """Analyze single change with LLM"""
        prompt = f"""Analyze this contract change:

CHANGE TYPE: {change.get('change_type', 'unknown')}
OLD TEXT: {change.get('old_content', 'N/A')}
NEW TEXT: {change.get('new_content', 'N/A')}

Return JSON:
{{
  "semantic_description": "Brief description",
  "is_substantive": true/false,
  "legal_implications": "Legal impact",
  "direction": "positive/negative/neutral",
  "severity": "critical/significant/minor",
  "recommendation": "accept/reject/negotiate",
  "reasoning": "Why"
}}
"""

        response = self.llm.chat(
            messages=[
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )

        try:
            analysis = json.loads(response)
            return {
                'semantic_description': analysis.get('semantic_description'),
                'is_substantive': analysis.get('is_substantive', True),
                'legal_implications': analysis.get('legal_implications'),
                'impact_assessment': {
                    'direction': analysis.get('direction', 'neutral'),
                    'severity': analysis.get('severity', 'minor'),
                    'recommendation': analysis.get('recommendation', 'review'),
                    'reasoning': analysis.get('reasoning', '')
                }
            }
        except:
            return {}

    def _link_to_disagreements(self, changes: List[Dict[str, Any]], contract_id: str):
        """Link changes to disagreements (stub)"""
        logger.info("Linking changes to disagreements...")

    def _save_changes(self, changes: List[Dict[str, Any]], from_version_id: int, to_version_id: int) -> List[ContractChange]:
        """Save changes to database"""
        logger.info("Saving changes to database...")

        change_records = []
        for change_data in changes:
            change_record = ContractChange(
                from_version_id=from_version_id,
                to_version_id=to_version_id,
                change_type=change_data.get('change_type', 'modification'),
                change_category=change_data.get('change_category', 'textual'),
                xpath_location=change_data.get('xpath_location'),
                section_name=change_data.get('section_name'),
                old_content=change_data.get('old_content'),
                new_content=change_data.get('new_content'),
                semantic_description=change_data.get('semantic_description'),
                is_substantive=change_data.get('is_substantive', True),
                legal_implications=change_data.get('legal_implications'),
                impact_assessment=change_data.get('impact_assessment', {}),
                requires_lawyer_review=self._requires_review(change_data)
            )

            self.db.add(change_record)
            change_records.append(change_record)

        self.db.commit()

        for record in change_records:
            self.db.refresh(record)

        return change_records

    def _requires_review(self, change: Dict[str, Any]) -> bool:
        """Determine if change requires lawyer review"""
        impact = change.get('impact_assessment', {})

        if impact.get('direction') == 'negative' and impact.get('severity') in ['critical', 'significant']:
            return True

        if change.get('change_category') == 'legal':
            return True

        return False

    def _aggregate_analysis(self, from_version_id: int, to_version_id: int, changes: List[ContractChange]) -> ChangeAnalysisResult:
        """Aggregate analysis results"""
        logger.info("Aggregating analysis results...")

        by_type = {}
        by_category = {}
        by_impact = {}
        critical_changes = []

        for change in changes:
            by_type[change.change_type] = by_type.get(change.change_type, 0) + 1
            by_category[change.change_category] = by_category.get(change.change_category, 0) + 1

            impact_dir = change.impact_assessment.get('direction', 'neutral')
            by_impact[impact_dir] = by_impact.get(impact_dir, 0) + 1

            if change.impact_assessment.get('severity') == 'critical':
                critical_changes.append(change.id)

        overall_assessment = self._calculate_overall_assessment(by_impact)

        analysis = ChangeAnalysisResult(
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            total_changes=len(changes),
            by_type=by_type,
            by_category=by_category,
            by_impact=by_impact,
            overall_assessment=overall_assessment,
            critical_changes=critical_changes,
            recommendations=f"Обнаружено {len(changes)} изменений. Оценка: {overall_assessment}.",
            executive_summary=f"Требуют проверки: {sum(1 for c in changes if c.requires_lawyer_review)} изменений."
        )

        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)

        return analysis

    def _calculate_overall_assessment(self, by_impact: Dict[str, int]) -> str:
        """Calculate overall assessment"""
        positive = by_impact.get('positive', 0)
        negative = by_impact.get('negative', 0)

        if negative > positive * 2:
            return 'unfavorable'
        elif positive > negative * 2:
            return 'favorable'
        elif positive > 0 and negative > 0:
            return 'mixed'
        else:
            return 'neutral'

    def _generate_report(self, analysis: ChangeAnalysisResult, changes: List[ContractChange]) -> str:
        """Generate PDF report"""
        logger.info("Generating PDF report...")

        analysis_dict = {
            'overall_assessment': analysis.overall_assessment,
            'total_changes': analysis.total_changes,
            'by_type': analysis.by_type,
            'by_impact': analysis.by_impact,
            'critical_changes': analysis.critical_changes,
            'recommendations': analysis.recommendations,
            'executive_summary': analysis.executive_summary
        }

        changes_dict = [{'id': c.id, 'change_type': c.change_type, 'semantic_description': c.semantic_description} for c in changes]

        report_path = self.report_generator.generate_report(analysis_dict, changes_dict)

        analysis.report_pdf_path = report_path
        analysis.report_generated_at = datetime.utcnow()
        self.db.commit()

        return report_path


__all__ = ["ChangesAnalyzerAgent"]
