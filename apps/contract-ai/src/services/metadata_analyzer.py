# -*- coding: utf-8 -*-
"""
Metadata Analyzer - Contract metadata and auxiliary analysis

Анализирует метаданные договора: контрагенты, шаблоны, споры, следующие действия
"""
from typing import Dict, Any, List, Optional
import json
from loguru import logger
from lxml import etree

from ..services.llm_gateway import LLMGateway
from ..models.analyzer_models import ContractRisk
from ..utils.xml_security import parse_xml_safely


class MetadataAnalyzer:
    """
    Analyzes contract metadata and performs auxiliary checks

    Supports:
    - Counterparty verification via external APIs
    - Dispute probability prediction
    - Template comparison and compliance
    - Next action determination for workflow
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        counterparty_service: Optional[Any] = None,
        template_manager: Optional[Any] = None,
        system_prompt: str = ""
    ):
        """
        Initialize metadata analyzer

        Args:
            llm_gateway: LLM gateway for analysis
            counterparty_service: Service for counterparty checks
            template_manager: Manager for contract templates
            system_prompt: Optional system prompt for LLM calls
        """
        self.llm = llm_gateway
        self.counterparty_service = counterparty_service
        self.template_manager = template_manager
        self.system_prompt = system_prompt or "You are a legal contract analysis expert."

    def check_counterparties(
        self,
        xml_content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check counterparty information via external APIs

        Verifies:
        - INN validity
        - Bankruptcy status
        - Company registration
        - Financial reliability (if available)

        Args:
            xml_content: Raw XML content with party information
            metadata: Contract metadata

        Returns:
            Dict with counterparty check results
        """
        if not self.counterparty_service:
            logger.warning("Counterparty service not available")
            return {}

        try:
            root = parse_xml_safely(xml_content)
            parties = root.findall('.//party')

            results = {}
            for party in parties:
                inn = party.findtext('inn', '').strip()
                name = party.findtext('name', '')

                if inn:
                    logger.info(f"Checking counterparty: {name} (INN: {inn})")
                    check_result = self.counterparty_service.check_counterparty(
                        inn=inn,
                        check_bankruptcy=True
                    )
                    results[name] = check_result

            logger.info(f"✓ Checked {len(results)} counterparties")
            return results

        except Exception as e:
            logger.error(f"Counterparty check failed: {e}")
            return {}

    def predict_disputes(
        self,
        xml_content: str,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict probability of disputes arising from contract

        Uses:
        - Identified risks
        - Historical precedents
        - Clause analysis
        - Legal context

        Args:
            xml_content: Raw XML content
            risks: List of identified risks
            rag_context: RAG context with precedents

        Returns:
            Dict with dispute prediction (score, level, reasoning, prone clauses)
        """
        try:
            prompt = self._build_dispute_prediction_prompt(risks, rag_context)

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_format="json",
                temperature=0.3
            )

            result = response if isinstance(response, dict) else json.loads(response)
            logger.info(f"✓ Dispute prediction: {result.get('level', 'unknown')} (score: {result.get('overall_score', 0)})")
            return result

        except Exception as e:
            logger.error(f"Dispute prediction failed: {e}")
            return {
                'overall_score': 50,
                'level': 'medium',
                'reasoning': 'Analysis failed',
                'dispute_prone_clauses': []
            }

    def compare_with_templates(
        self,
        xml_content: str,
        contract_type: Optional[str]
    ) -> Dict[str, Any]:
        """
        Compare contract structure with standard templates

        Checks:
        - Missing required sections
        - Extra sections (not in template)
        - Overall match percentage

        Args:
            xml_content: Raw XML content
            contract_type: Type of contract (e.g., 'supply', 'service')

        Returns:
            Dict with comparison results
        """
        if not contract_type:
            return {'compared': False, 'reason': 'No contract type specified'}

        if not self.template_manager:
            logger.warning("Template manager not available")
            return {'compared': False, 'reason': 'Template manager not configured'}

        try:
            template = self.template_manager.get_template(contract_type)

            if not template:
                return {
                    'compared': False,
                    'reason': f'No template for type {contract_type}'
                }

            root = parse_xml_safely(xml_content)
            template_root = etree.fromstring(template.xml_content.encode('utf-8'))

            contract_tags = set([elem.tag for elem in root.iter()])
            template_tags = set([elem.tag for elem in template_root.iter()])

            missing_sections = template_tags - contract_tags
            extra_sections = contract_tags - template_tags

            match_percentage = (
                len(contract_tags & template_tags) / len(template_tags) * 100
                if template_tags else 0
            )

            logger.info(f"✓ Template comparison: {match_percentage:.1f}% match with {template.name}")

            return {
                'compared': True,
                'template_name': template.name,
                'template_version': template.version,
                'missing_sections': list(missing_sections),
                'extra_sections': list(extra_sections),
                'match_percentage': match_percentage
            }

        except Exception as e:
            logger.error(f"Template comparison failed: {e}")
            return {'compared': False, 'reason': str(e)}

    def determine_next_action(
        self,
        risks: List[ContractRisk],
        dispute_prediction: Dict[str, Any]
    ) -> str:
        """
        Determine next workflow action based on analysis results

        Decision logic:
        - Critical risks → review_queue
        - High dispute risk → review_queue
        - Otherwise → export

        Args:
            risks: List of identified risks
            dispute_prediction: Dispute prediction results

        Returns:
            Next action: 'review_queue' or 'export'
        """
        has_critical = any(r.severity == 'critical' for r in risks)
        high_dispute_risk = dispute_prediction.get('level') in ['high', 'critical']

        if has_critical or high_dispute_risk:
            logger.info("⚠ Critical issues detected → routing to review queue")
            return 'review_queue'

        logger.info("✓ No critical issues → ready for export")
        return 'export'

    def _build_dispute_prediction_prompt(
        self,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> str:
        """Build prompt for dispute prediction"""
        prompt = "Predict the probability of disputes arising from this contract.\n\n"

        prompt += "IDENTIFIED RISKS:\n"
        prompt += json.dumps([
            {'type': r.risk_type, 'severity': r.severity, 'title': r.title}
            for r in risks
        ], ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "PRECEDENTS:\n"
            prompt += rag_context['context'][:1500]
            prompt += "\n\n"

        prompt += """Analyze dispute probability.

Return JSON:
{
  "overall_score": 0-100,
  "level": "low|medium|high|critical",
  "reasoning": "Why this score",
  "dispute_prone_clauses": [
    {
      "clause": "Clause description",
      "reason": "Why disputes may arise",
      "probability": "low|medium|high"
    }
  ]
}

Return ONLY valid JSON."""

        return prompt


__all__ = ['MetadataAnalyzer']
