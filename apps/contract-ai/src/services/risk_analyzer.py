# -*- coding: utf-8 -*-
"""
Risk Analyzer - Identify and assess contract risks

Анализирует риски в договорах используя LLM и RAG
"""
from typing import Dict, Any, List, Optional
import json
from loguru import logger

from ..services.llm_gateway import LLMGateway
from ..models.analyzer_models import ContractRisk


class RiskAnalyzer:
    """
    Analyzes contract clauses to identify risks

    Supports:
    - Batch clause analysis
    - Individual deep analysis
    - RAG-enhanced risk identification
    - Multiple risk types (financial, legal, operational, reputational)
    """

    def __init__(self, llm_gateway: LLMGateway):
        """
        Initialize risk analyzer

        Args:
            llm_gateway: LLM gateway for analysis
        """
        self.llm = llm_gateway

    def analyze_clauses_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]] = None,
        batch_size: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple clauses in batches

        Args:
            clauses: List of clause dicts
            rag_context: Optional RAG context with precedents/norms
            batch_size: Clauses per batch (default: 15)

        Returns:
            List of clause analyses with risks
        """
        all_analyses: List[Dict[str, Any]] = []

        # Process in batches
        for i in range(0, len(clauses), batch_size):
            batch = clauses[i:i + batch_size]
            logger.info(f"Analyzing batch {i//batch_size + 1}: clauses {i+1}-{i+len(batch)}")

            try:
                batch_analyses = self._analyze_batch(batch, rag_context)
                all_analyses.extend(batch_analyses)
            except Exception as e:
                logger.error(f"Batch analysis failed: {e}")
                # Add fallback analyses
                for clause in batch:
                    all_analyses.append(self._get_fallback_analysis(clause))

        return all_analyses

    def analyze_clause_detailed(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform detailed analysis of single clause

        Args:
            clause: Clause dict with text, type, xpath
            rag_context: Optional RAG context

        Returns:
            Detailed analysis with risks, recommendations
        """
        try:
            prompt = self._build_detailed_analysis_prompt(clause, rag_context)

            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You are a contract risk analysis expert. Provide detailed risk assessment in JSON format.",
                temperature=0.0,
                max_tokens=2000,
                response_format="json"
            )

            analysis = json.loads(response)
            analysis['clause_id'] = clause['id']
            analysis['clause_xpath'] = clause.get('xpath', '')

            return analysis

        except Exception as e:
            logger.error(f"Detailed analysis failed for clause {clause['id']}: {e}")
            return self._get_fallback_analysis(clause)

    def identify_risks(
        self,
        analyses: List[Dict[str, Any]]
    ) -> List[ContractRisk]:
        """
        Extract and structure risks from analyses

        Args:
            analyses: List of clause analyses

        Returns:
            List of ContractRisk objects
        """
        risks: List[ContractRisk] = []

        for analysis in analyses:
            clause_risks = analysis.get('risks', [])

            for risk_data in clause_risks:
                try:
                    risk = ContractRisk(
                        type=risk_data.get('type', 'general'),
                        severity=risk_data.get('severity', 'medium'),
                        description=risk_data.get('description', ''),
                        clause_reference=analysis.get('clause_id', ''),
                        xpath_location=analysis.get('clause_xpath', ''),
                        probability=risk_data.get('probability', 'medium'),
                        impact_description=risk_data.get('impact', ''),
                        mitigation_strategy=risk_data.get('mitigation', ''),
                        legal_basis=risk_data.get('legal_basis', ''),
                        related_precedents=risk_data.get('precedents', [])
                    )
                    risks.append(risk)

                except Exception as e:
                    logger.error(f"Failed to create risk object: {e}")
                    continue

        logger.info(f"Identified {len(risks)} total risks")
        return risks

    def _analyze_batch(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze batch of clauses"""
        prompt = self._build_batch_analysis_prompt(clauses, rag_context)

        response = self.llm.generate(
            prompt=prompt,
            system_prompt="You are a contract analysis expert. Analyze clauses and identify risks in JSON format.",
            temperature=0.0,
            max_tokens=4000,
            response_format="json"
        )

        try:
            result = json.loads(response)
            analyses = result.get('analyses', [])

            # Ensure we have analysis for each clause
            if len(analyses) < len(clauses):
                logger.warning(f"Expected {len(clauses)} analyses, got {len(analyses)}")
                # Fill missing with fallbacks
                while len(analyses) < len(clauses):
                    analyses.append(self._get_fallback_analysis(clauses[len(analyses)]))

            return analyses

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode failed: {e}")
            return [self._get_fallback_analysis(c) for c in clauses]

    def _build_batch_analysis_prompt(
        self,
        clauses: List[Dict[str, Any]],
        rag_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for batch analysis"""
        clauses_text = "\n\n".join([
            f"CLAUSE {i+1} [{clause['type']}]:\nTitle: {clause['title']}\nText: {clause['text'][:500]}"
            for i, clause in enumerate(clauses)
        ])

        rag_info = ""
        if rag_context:
            rag_info = f"\n\nRELEVANT PRECEDENTS:\n{rag_context.get('precedents', '')[:500]}"
            rag_info += f"\n\nLEGAL NORMS:\n{rag_context.get('norms', '')[:500]}"

        prompt = f"""Analyze these contract clauses for risks:

{clauses_text}{rag_info}

For each clause, identify:
1. Risks (type, severity, probability, impact, mitigation)
2. Issues (legal compliance, clarity, fairness)

Return JSON:
{{
  "analyses": [
    {{
      "clause_number": 1,
      "risks": [
        {{
          "type": "financial|legal|operational|reputational",
          "severity": "critical|high|medium|low",
          "probability": "high|medium|low",
          "description": "...",
          "impact": "...",
          "mitigation": "...",
          "legal_basis": "..."
        }}
      ],
      "issues": ["..."],
      "overall_risk_level": "critical|high|medium|low"
    }}
  ]
}}"""

        return prompt

    def _build_detailed_analysis_prompt(
        self,
        clause: Dict[str, Any],
        rag_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for detailed single clause analysis"""
        rag_info = ""
        if rag_context:
            rag_info = f"\n\nRELEVANT CONTEXT:\nPrecedents: {rag_context.get('precedents', '')[:300]}\nNorms: {rag_context.get('norms', '')[:300]}"

        prompt = f"""Perform deep analysis of this contract clause:

CLAUSE: {clause['title']}
TYPE: {clause['type']}
TEXT: {clause['text']}{rag_info}

Provide comprehensive risk assessment in JSON:
{{
  "risks": [
    {{
      "type": "financial|legal|operational|reputational",
      "severity": "critical|high|medium|low",
      "probability": "high|medium|low",
      "description": "Detailed risk description",
      "impact": "Detailed impact analysis",
      "mitigation": "Mitigation strategy",
      "legal_basis": "Relevant laws/articles",
      "precedents": ["Case 1", "Case 2"]
    }}
  ],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "recommendations": ["..."],
  "overall_risk_level": "critical|high|medium|low"
}}"""

        return prompt

    def _get_fallback_analysis(self, clause: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback analysis if LLM fails"""
        return {
            'clause_number': clause.get('number', 0),
            'clause_id': clause.get('id', ''),
            'risks': [],
            'issues': [],
            'overall_risk_level': 'unknown',
            'error': 'Analysis failed - fallback used'
        }


__all__ = ['RiskAnalyzer']
