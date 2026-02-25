# -*- coding: utf-8 -*-
"""
Disagreement Processor Agent - Generate objections to external contracts
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from lxml import etree
from loguru import logger

from .base_agent import BaseAgent, AgentResult
from ..services.llm_gateway import LLMGateway
from ..models.disagreement_models import Disagreement, DisagreementObjection
from ..models.analyzer_models import ContractRisk, ContractRecommendation
from ..models.database import Contract, AnalysisResult

# Optional RAG import
try:
    from ..services.rag_system import RAGSystem
except ImportError:
    RAGSystem = None


class DisagreementProcessorAgent(BaseAgent):
    """
    Agent for generating disagreements/objections to external contracts
    
    Capabilities:
    - LLM-based objection generation with RAG support
    - Full traceability (objection ↔ risks ↔ contract clauses)
    - Automatic prioritization + user override
    - Alternative formulations with reasoning
    - Legal basis and precedents from RAG
    - Neutral-business tone
    - Multiple export formats (XML, DOCX, JSON)
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        db_session,
        rag_system: Optional['RAGSystem'] = None
    ):
        super().__init__(llm_gateway, db_session)
        self.rag_system = rag_system

    def get_name(self) -> str:
        return "DisagreementProcessorAgent"

    def get_system_prompt(self) -> str:
        return """You are a legal expert specializing in contract objections and negotiations.

Your task is to generate formal objections to problematic contract clauses.

For each objection, provide:
1. ISSUE DESCRIPTION: Clear explanation of the problem
2. LEGAL BASIS: References to relevant laws, regulations, court precedents
3. RISK EXPLANATION: How this issue creates risks for our organization
4. ALTERNATIVE FORMULATION: Suggested improved wording
5. ALTERNATIVE REASONING: Why this formulation is better

Tone: Neutral-business (professional, factual, not aggressive)
Format: Structured JSON output
References: Use RAG sources when available (precedents, similar cases, legal norms)
"""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute disagreement generation workflow
        
        Expected state:
        - contract_id: ID of contract to object to
        - analysis_id: ID of analysis with identified risks
        - mode: 'auto' (triggered by critical risks) or 'manual' (user request)
        - user_id: ID of user creating disagreement (optional)
        - tone: 'neutral_business' (default)
        
        Returns:
        - disagreement_id: ID of created disagreement
        - objections: List of generated objections
        - next_action: 'review' (user selects objections)
        """
        try:
            contract_id = state.get('contract_id')
            analysis_id = state.get('analysis_id')
            mode = state.get('mode', 'manual')
            user_id = state.get('user_id')
            tone = state.get('tone', 'neutral_business')

            if not contract_id or not analysis_id:
                return AgentResult(
                    success=False,
                    data={},
                    error="Missing contract_id or analysis_id"
                )

            logger.info(f"Starting disagreement generation for contract {contract_id} (mode: {mode})")

            # 1. Get contract and analysis
            contract = self.db.query(Contract).filter(
                Contract.id == contract_id
            ).first()

            if not contract:
                return AgentResult(
                    success=False,
                    data={},
                    error=f"Contract {contract_id} not found"
                )

            analysis = self.db.query(AnalysisResult).filter(
                AnalysisResult.id == analysis_id
            ).first()

            if not analysis:
                return AgentResult(
                    success=False,
                    data={},
                    error=f"Analysis {analysis_id} not found"
                )

            # 2. Get risks from analyzer
            risks = self.db.query(ContractRisk).filter(
                ContractRisk.analysis_id == analysis_id
            ).all()

            if not risks:
                logger.warning(f"No risks found for analysis {analysis_id}")
                return AgentResult(
                    success=False,
                    data={},
                    error="No risks identified - nothing to object to"
                )

            # 3. Get recommendations
            recommendations = self.db.query(ContractRecommendation).filter(
                ContractRecommendation.analysis_id == analysis_id
            ).all()

            # 4. Create disagreement record
            disagreement = self._create_disagreement_record(
                contract_id, analysis_id, user_id, tone
            )

            # 5. Get RAG context for objections
            rag_context = self._get_rag_context_for_objections(risks, contract)

            # 6. Generate objections for each risk
            objections = []
            for risk in risks:
                try:
                    objection = self._generate_objection(
                        risk, recommendations, rag_context, tone
                    )
                    objection.disagreement_id = disagreement.id
                    objections.append(objection)
                except Exception as e:
                    logger.error(f"Failed to generate objection for risk {risk.id}: {e}")

            # 7. Save objections to DB
            self._save_objections(objections)

            # 8. Update disagreement with summary
            disagreement.generated_content = {
                'total_objections': len(objections),
                'by_priority': self._count_by_priority(objections),
                'generation_mode': mode,
                'generation_timestamp': datetime.utcnow().isoformat()
            }
            self.db.commit()
            self.db.refresh(disagreement)

            logger.info(f"Disagreement generated: {len(objections)} objections")

            return AgentResult(
                success=True,
                data={
                    'disagreement_id': disagreement.id,
                    'objections': [self._objection_to_dict(obj) for obj in objections],
                    'total_objections': len(objections),
                    'by_priority': self._count_by_priority(objections)
                },
                next_action='review',
                metadata={'message': f"Generated {len(objections)} objections - ready for lawyer review"}
            )

        except Exception as e:
            logger.error(f"Disagreement generation failed: {e}")
            import traceback
            traceback.print_exc()
            return AgentResult(
                success=False,
                data={},
                error=str(e)
            )

    def _create_disagreement_record(
        self, contract_id: str, analysis_id: str, user_id: Optional[str], tone: str
    ) -> Disagreement:
        """Create disagreement record in draft status"""
        disagreement = Disagreement(
            contract_id=contract_id,
            analysis_id=analysis_id,
            status='draft',
            tone=tone,
            created_by=user_id
        )
        self.db.add(disagreement)
        self.db.commit()
        self.db.refresh(disagreement)
        return disagreement

    def _get_rag_context_for_objections(
        self, risks: List[ContractRisk], contract: Contract
    ) -> Dict[str, Any]:
        """Get RAG context for objection generation"""
        if not self.rag_system:
            return {'sources': [], 'context': ''}

        try:
            # Build query from risks
            risk_descriptions = [f"{r.title}: {r.description}" for r in risks[:5]]
            query = "Возражения по договору. " + " ".join(risk_descriptions)

            # Search in objections collection + general collection
            results = self.rag_system.search(
                query=query,
                n_results=15,
                filter_metadata={'type': ['objection', 'precedent', 'legal_norm']}
            )

            context = "\n\n".join([
                f"[{r['metadata'].get('type', 'unknown')}] {r['text']}"
                for r in results
            ])

            return {
                'sources': results,
                'context': context
            }

        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return {'sources': [], 'context': ''}

    def _generate_objection(
        self,
        risk: ContractRisk,
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any],
        tone: str
    ) -> DisagreementObjection:
        """Generate single objection using LLM"""
        try:
            # Build prompt
            prompt = self._build_objection_prompt(risk, recommendations, rag_context, tone)

            # Call LLM
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )

            # Parse JSON response
            objection_data = json.loads(response)

            # Determine auto priority based on risk severity
            auto_priority = self._calculate_auto_priority(risk)

            # Create objection object
            objection = DisagreementObjection(
                related_risk_ids=[risk.id],
                contract_section_xpath=risk.xpath_location,
                contract_section_text=objection_data.get('contract_section_text', ''),
                issue_description=objection_data.get('issue_description', ''),
                legal_basis=objection_data.get('legal_basis', ''),
                precedents=objection_data.get('precedents', []),
                risk_explanation=objection_data.get('risk_explanation', ''),
                alternative_formulation=objection_data.get('alternative_formulation', ''),
                alternative_reasoning=objection_data.get('alternative_reasoning', ''),
                alternative_variants=objection_data.get('alternative_variants', []),
                priority=self._severity_to_priority(risk.severity),
                auto_priority=auto_priority,
                user_selected=False,
                original_content=response
            )

            return objection

        except Exception as e:
            logger.error(f"Objection generation failed for risk {risk.id}: {e}")
            # Return minimal objection
            return DisagreementObjection(
                related_risk_ids=[risk.id],
                contract_section_xpath=risk.xpath_location,
                issue_description=f"Риск: {risk.title}. {risk.description}",
                alternative_formulation="Требуется доработка формулировки",
                priority=self._severity_to_priority(risk.severity),
                auto_priority=50
            )

    def _build_objection_prompt(
        self,
        risk: ContractRisk,
        recommendations: List[ContractRecommendation],
        rag_context: Dict[str, Any],
        tone: str
    ) -> str:
        """Build LLM prompt for objection generation"""
        prompt = "Generate a formal objection to a problematic contract clause.\n\n"

        prompt += "IDENTIFIED RISK:\n"
        prompt += json.dumps({
            'type': risk.risk_type,
            'severity': risk.severity,
            'title': risk.title,
            'description': risk.description,
            'consequences': risk.consequences,
            'xpath': risk.xpath_location,
            'section': risk.section_name
        }, ensure_ascii=False, indent=2)
        prompt += "\n\n"

        # Add relevant recommendations
        relevant_recs = [r for r in recommendations if r.related_risk_id == risk.id]
        if relevant_recs:
            prompt += "RECOMMENDATIONS:\n"
            for rec in relevant_recs:
                prompt += f"- {rec.title}: {rec.description}\n"
            prompt += "\n"

        # Add RAG context
        if rag_context.get('context'):
            prompt += "LEGAL PRECEDENTS AND REFERENCES:\n"
            prompt += rag_context['context'][:2000]
            prompt += "\n\n"

        prompt += f"""Generate objection with tone: {tone}

Return JSON:
{{
  "contract_section_text": "Quoted problematic text from contract",
  "issue_description": "Clear explanation of what is wrong (2-3 sentences)",
  "legal_basis": "References to laws, regulations, court precedents that support objection",
  "risk_explanation": "How this clause creates specific risks for our organization",
  "alternative_formulation": "Suggested improved wording of the clause",
  "alternative_reasoning": "Why this alternative is better and addresses the risks",
  "alternative_variants": [
    {{
      "variant": "Alternative formulation option 2",
      "reasoning": "Why this variant works"
    }}
  ],
  "precedents": ["Precedent 1 from RAG", "Precedent 2 from RAG"]
}}

Return ONLY valid JSON, no additional text."""

        return prompt

    def _calculate_auto_priority(self, risk: ContractRisk) -> int:
        """Calculate automatic priority score (1-100)"""
        base_score = 50

        # Severity contribution
        severity_scores = {
            'critical': 40,
            'significant': 25,
            'minor': 10
        }
        base_score += severity_scores.get(risk.severity, 10)

        # Probability contribution
        probability_scores = {
            'high': 10,
            'medium': 5,
            'low': 0
        }
        base_score += probability_scores.get(risk.probability, 0)

        return min(100, base_score)

    def _severity_to_priority(self, severity: str) -> str:
        """Map risk severity to objection priority"""
        mapping = {
            'critical': 'critical',
            'significant': 'high',
            'minor': 'medium'
        }
        return mapping.get(severity, 'medium')

    def _count_by_priority(self, objections: List[DisagreementObjection]) -> Dict[str, int]:
        """Count objections by priority"""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for obj in objections:
            counts[obj.priority] = counts.get(obj.priority, 0) + 1
        return counts

    def _save_objections(self, objections: List[DisagreementObjection]):
        """Save objections to database"""
        for objection in objections:
            self.db.add(objection)
        self.db.commit()

    def _objection_to_dict(self, objection: DisagreementObjection) -> Dict[str, Any]:
        """Convert objection to dict for response"""
        return {
            'id': objection.id,
            'priority': objection.priority,
            'auto_priority': objection.auto_priority,
            'contract_section_xpath': objection.contract_section_xpath,
            'issue_description': objection.issue_description,
            'legal_basis': objection.legal_basis,
            'alternative_formulation': objection.alternative_formulation,
            'alternative_reasoning': objection.alternative_reasoning,
            'user_selected': objection.user_selected
        }

    def update_user_selection(
        self, disagreement_id: int, selected_objection_ids: List[int], priority_order: Optional[List[int]] = None
    ) -> AgentResult:
        """
        Update which objections user selected and their priority order
        
        Args:
            disagreement_id: ID of disagreement
            selected_objection_ids: List of objection IDs to include
            priority_order: Optional custom order (list of objection IDs)
        """
        try:
            disagreement = self.db.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                return AgentResult(success=False, data={}, error="Disagreement not found")

            # Update objections
            objections = self.db.query(DisagreementObjection).filter(
                DisagreementObjection.disagreement_id == disagreement_id
            ).all()

            for obj in objections:
                obj.user_selected = (obj.id in selected_objection_ids)

            # Update disagreement
            disagreement.selected_objections = selected_objection_ids
            disagreement.priority_order = priority_order or selected_objection_ids
            disagreement.status = 'review'

            self.db.commit()

            logger.info(f"User selected {len(selected_objection_ids)} objections")

            return AgentResult(
                success=True,
                data={
                    'disagreement_id': disagreement_id,
                    'selected_count': len(selected_objection_ids)
                },
                next_action='approve',
                metadata={'message': f"Selected {len(selected_objection_ids)} objections for review"}
            )

        except Exception as e:
            logger.error(f"Failed to update user selection: {e}")
            self.db.rollback()
            return AgentResult(success=False, data={}, error=str(e))

    def generate_xml_document(self, disagreement_id: int) -> AgentResult:
        """Generate structured XML document with objections"""
        try:
            disagreement = self.db.query(Disagreement).filter(
                Disagreement.id == disagreement_id
            ).first()

            if not disagreement:
                return AgentResult(success=False, data={}, error="Disagreement not found")

            # Get selected objections in priority order
            selected_ids = disagreement.priority_order or disagreement.selected_objections
            objections = self.db.query(DisagreementObjection).filter(
                DisagreementObjection.id.in_(selected_ids)
            ).all()

            # Sort by priority order
            objections_dict = {obj.id: obj for obj in objections}
            sorted_objections = [objections_dict[oid] for oid in selected_ids if oid in objections_dict]

            # Build XML
            root = etree.Element("disagreement")

            # Header
            header = etree.SubElement(root, "header")
            etree.SubElement(header, "contract_id").text = str(disagreement.contract_id)
            etree.SubElement(header, "date").text = datetime.utcnow().strftime("%Y-%m-%d")
            etree.SubElement(header, "tone").text = disagreement.tone

            # Objections
            objections_elem = etree.SubElement(root, "objections")
            for i, obj in enumerate(sorted_objections, 1):
                obj_elem = etree.SubElement(objections_elem, "objection", number=str(i))
                etree.SubElement(obj_elem, "priority").text = obj.priority
                etree.SubElement(obj_elem, "contract_section_xpath").text = obj.contract_section_xpath or ''
                etree.SubElement(obj_elem, "issue").text = obj.issue_description or ''
                etree.SubElement(obj_elem, "legal_basis").text = obj.legal_basis or ''
                etree.SubElement(obj_elem, "risk_explanation").text = obj.risk_explanation or ''
                etree.SubElement(obj_elem, "alternative").text = obj.alternative_formulation or ''
                etree.SubElement(obj_elem, "reasoning").text = obj.alternative_reasoning or ''

            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_str += etree.tostring(root, encoding='unicode', pretty_print=True)

            # Save to disagreement
            disagreement.xml_content = xml_str
            self.db.commit()

            logger.info(f"Generated XML document for disagreement {disagreement_id}")

            return AgentResult(
                success=True,
                data={
                    'disagreement_id': disagreement_id,
                    'xml_content': xml_str,
                    'objection_count': len(sorted_objections)
                },
                next_action='export',
                metadata={'message': "XML document generated"}
            )

        except Exception as e:
            logger.error(f"XML generation failed: {e}")
            import traceback
            traceback.print_exc()
            return AgentResult(success=False, data={}, error=str(e))


__all__ = ["DisagreementProcessorAgent"]
