# -*- coding: utf-8 -*-
"""
Recommendation Generator - Generate recommendations and suggested changes

Создает рекомендации и предложения по исправлению рисков в договорах
"""
from typing import Dict, Any, List
import json
from loguru import logger

from ..services.llm_gateway import LLMGateway
from ..models.analyzer_models import (
    ContractRisk,
    ContractRecommendation,
    ContractSuggestedChange,
    ContractAnnotation
)


class RecommendationGenerator:
    """
    Generates recommendations and suggested changes for contract risks

    Supports:
    - Risk-based recommendations with LLM
    - Automatic suggested text changes
    - Contract annotations for highlighting
    - Priority and complexity assessment
    """

    def __init__(self, llm_gateway: LLMGateway, system_prompt: str = ""):
        """
        Initialize recommendation generator

        Args:
            llm_gateway: LLM gateway for generation
            system_prompt: Optional system prompt for LLM calls
        """
        self.llm = llm_gateway
        self.system_prompt = system_prompt or "You are a legal contract analysis expert."

    def generate_recommendations(
        self,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> List[ContractRecommendation]:
        """
        Generate recommendations based on identified risks

        Args:
            risks: List of identified contract risks
            rag_context: RAG context with legal references

        Returns:
            List of ContractRecommendation objects
        """
        try:
            prompt = self._build_recommendations_prompt(risks, rag_context)

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_format="json",
                temperature=0.3
            )

            recommendations_data = response if isinstance(response, dict) else json.loads(response)

            recommendations = []
            for rec_dict in recommendations_data.get('recommendations', []):
                try:
                    recommendation = ContractRecommendation(
                        category=rec_dict.get('category', 'general'),
                        priority=rec_dict.get('priority', 'medium'),
                        title=rec_dict.get('title', ''),
                        description=rec_dict.get('description', ''),
                        reasoning=rec_dict.get('reasoning'),
                        expected_benefit=rec_dict.get('expected_benefit'),
                        implementation_complexity=rec_dict.get('implementation_complexity')
                    )
                    recommendations.append(recommendation)
                except Exception as e:
                    logger.error(f"Failed to create recommendation object: {e}")
                    continue

            logger.info(f"✓ Generated {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    def generate_suggested_changes(
        self,
        xml_content: str,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any]
    ) -> List[ContractSuggestedChange]:
        """
        Generate specific text changes to fix identified risks

        Args:
            xml_content: Raw XML content (for reference)
            structure: Contract structure with sections
            risks: Identified risks
            recommendations: Generated recommendations
            rag_context: Legal context and references

        Returns:
            List of ContractSuggestedChange objects
        """
        try:
            prompt = self._build_suggested_changes_prompt(
                structure, risks, rag_context
            )

            response = self.llm.call(
                prompt=prompt,
                system_prompt=self.system_prompt,
                response_format="json",
                temperature=0.4
            )

            changes_data = response if isinstance(response, dict) else json.loads(response)

            changes = []
            for change_dict in changes_data.get('changes', []):
                try:
                    change = ContractSuggestedChange(
                        xpath_location=change_dict.get('xpath_location', ''),
                        section_name=change_dict.get('section_name'),
                        original_text=change_dict.get('original_text', ''),
                        suggested_text=change_dict.get('suggested_text', ''),
                        change_type=change_dict.get('change_type'),
                        issue=change_dict.get('issue', ''),
                        reasoning=change_dict.get('reasoning', ''),
                        legal_basis=change_dict.get('legal_basis'),
                        status='pending'
                    )
                    changes.append(change)
                except Exception as e:
                    logger.error(f"Failed to create suggested change object: {e}")
                    continue

            logger.info(f"✓ Generated {len(changes)} suggested changes")
            return changes

        except Exception as e:
            logger.error(f"Suggested changes generation failed: {e}")
            return []

    def generate_annotations(
        self,
        risks: List[ContractRisk],
        recommendations: List[ContractRecommendation],
        suggested_changes: List[ContractSuggestedChange]
    ) -> List[ContractAnnotation]:
        """
        Generate annotations for document sections

        Creates visual markers for:
        - Critical risks (red highlights)
        - Warnings (yellow highlights)
        - Suggestions (yellow highlights)

        Args:
            risks: List of risks to annotate
            recommendations: List of recommendations
            suggested_changes: List of suggested changes

        Returns:
            List of ContractAnnotation objects
        """
        annotations = []

        # Add risk annotations
        for risk in risks:
            if risk.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=risk.xpath_location,
                    section_name=risk.section_name,
                    annotation_type='risk' if risk.severity == 'critical' else 'warning',
                    content=f"{risk.title}: {risk.description}",
                    highlight_color='red' if risk.severity == 'critical' else 'yellow'
                )
                annotations.append(annotation)

        # Add suggested change annotations
        for change in suggested_changes:
            if change.xpath_location:
                annotation = ContractAnnotation(
                    xpath_location=change.xpath_location,
                    section_name=change.section_name,
                    annotation_type='suggestion',
                    content=f"Предложение: {change.issue}",
                    highlight_color='yellow'
                )
                annotations.append(annotation)

        logger.info(f"✓ Generated {len(annotations)} annotations")
        return annotations

    def _build_recommendations_prompt(
        self,
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> str:
        """Build prompt for recommendations generation"""
        prompt = "Based on identified risks, generate recommendations.\n\n"

        prompt += "IDENTIFIED RISKS:\n"
        risks_summary = [
            {
                'id': i,
                'type': r.risk_type,
                'severity': r.severity,
                'title': r.title,
                'description': r.description
            }
            for i, r in enumerate(risks)
        ]
        prompt += json.dumps(risks_summary, ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "LEGAL CONTEXT:\n"
            prompt += rag_context['context'][:2000]
            prompt += "\n\n"

        prompt += """Generate recommendations for each risk.

Return JSON:
{
  "recommendations": [
    {
      "category": "legal_compliance|risk_mitigation|financial_optimization|etc",
      "priority": "critical|high|medium|low",
      "title": "Short title",
      "description": "What to do",
      "reasoning": "Why this recommendation",
      "expected_benefit": "Expected outcome",
      "related_risk_id": 0,
      "implementation_complexity": "easy|medium|hard"
    }
  ]
}

Return ONLY valid JSON."""

        return prompt

    def _build_suggested_changes_prompt(
        self,
        structure: Dict[str, Any],
        risks: List[ContractRisk],
        rag_context: Dict[str, Any]
    ) -> str:
        """Build prompt for suggested changes generation"""
        prompt = "Generate specific text changes to fix identified risks.\n\n"

        prompt += "RISKS:\n"
        prompt += json.dumps([
            {'id': i, 'title': r.title, 'description': r.description, 'xpath': r.xpath_location}
            for i, r in enumerate(risks)
        ], ensure_ascii=False, indent=2)
        prompt += "\n\n"

        prompt += "CONTRACT SECTIONS:\n"
        prompt += json.dumps(structure.get('sections', [])[:20], ensure_ascii=False, indent=2)
        prompt += "\n\n"

        if rag_context.get('context'):
            prompt += "LEGAL REFERENCES:\n"
            prompt += rag_context['context'][:2000]
            prompt += "\n\n"

        prompt += """For each risk that can be fixed by changing contract text, provide:

{
  "changes": [
    {
      "xpath_location": "XPath to section",
      "section_name": "Section name",
      "original_text": "Current problematic text",
      "suggested_text": "Improved version",
      "change_type": "addition|modification|deletion|clarification",
      "issue": "What's the problem",
      "reasoning": "Why this change fixes it",
      "legal_basis": "Reference to law/article if applicable",
      "related_risk_id": 0
    }
  ]
}

Return ONLY valid JSON."""

        return prompt


__all__ = ['RecommendationGenerator']
