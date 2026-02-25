# -*- coding: utf-8 -*-
"""
Contract Generator Agent - Generate new contracts from templates

Responsibilities:
- Extract parameters from user request (LLM)
- Find suitable template (type + semantic + legal analysis via RAG)
- Generate contract using template + LLM + RAG context
- Validate generated contract (mandatory sections, legal compliance)
- Create feedback collection mechanism
"""
import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..agents.base_agent import BaseAgent, AgentResult
from ..services.template_manager import TemplateManager
from ..models.database import Template, Contract
from ..utils.xml_security import parse_xml_safely, XMLSecurityError

# Optional RAG import
try:
    from ..services.rag_system import RAGSystem
except ImportError:
    RAGSystem = None


class ContractGeneratorAgent(BaseAgent):
    """
    Contract Generator Agent - Generate contracts from templates

    Workflow:
    1. Extract parameters from request (LLM)
    2. Find template (type + semantic + legal analysis)
    3. Generate contract (LLM + template + RAG)
    4. Validate contract
    5. Save and route to review/export
    """

    def __init__(self, llm_gateway, db_session, template_manager: TemplateManager = None, rag_system = None):
        super().__init__(llm_gateway, db_session)
        self.template_manager = template_manager or TemplateManager(db_session)
        self.rag_system = rag_system

    def get_name(self) -> str:
        return "ContractGeneratorAgent"

    def get_system_prompt(self) -> str:
        return """You are a legal contract generation expert.
You create legally compliant contracts based on templates and user requirements.
Follow Russian civil law (ГК РФ) and relevant regulations.
Be precise, thorough, and legally accurate."""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute contract generation workflow

        Required state:
        - contract_id: str
        - parsed_xml: str (user request)
        - metadata: dict (from onboarding)

        Returns state with:
        - generated_contract_xml: str
        - template_used: str
        - validation_results: dict
        - generation_params: dict (for feedback)
        - review_required: bool
        """
        start_time = datetime.utcnow()

        try:
            # Validate input
            self.validate_state(state, ['contract_id', 'parsed_xml'])

            contract_id = state['contract_id']
            parsed_xml = state['parsed_xml']
            metadata = state.get('metadata', {})

            logger.info(f"Generating contract {contract_id}")

            # Step 1: Extract parameters from request
            params = self._extract_parameters(parsed_xml, metadata)
            logger.info(f"Parameters extracted: {params.get('contract_type', 'unknown')}")

            # Step 2: Find suitable template
            template = self._find_template(params)

            if not template:
                # No template found - request user selection
                logger.warning(f"No template found for type: {params.get('contract_type')}")
                return self._create_template_selection_request(contract_id, params)

            logger.info(f"Template found: {template.name} (ID: {template.id})")

            # Step 3: Get RAG context (formulations, precedents, legal norms)
            rag_context = self._get_rag_context(params, template) if self.rag_system else {}

            # Step 4: Generate contract content
            contract_xml = self._generate_contract(template, params, rag_context)

            # Step 5: Validate generated contract
            validation_results = self._validate_contract(contract_xml, params)

            # Step 6: Prepare result
            result_data = {
                'contract_id': contract_id,
                'generated_contract_xml': contract_xml,
                'template_used': template.name,
                'template_id': template.id,
                'validation_results': validation_results,
                'generation_params': params,  # For feedback collection
                'review_required': True,  # Default: send to review queue
                'generation_complete': True
            }

            duration = (datetime.utcnow() - start_time).total_seconds()
            self.log_execution('contract_generation', state, result_data, duration)

            # Determine next action
            next_action = 'review' if validation_results.get('passed', True) else 'review'

            return self.create_success_result(
                data=result_data,
                next_action=next_action,
                metadata={'duration': duration, 'validation_passed': validation_results.get('passed', True)}
            )

        except Exception as e:
            logger.error(f"Contract generation failed: {e}")
            import traceback
            traceback.print_exc()
            return self.create_error_result(
                error=str(e),
                data={'contract_id': state.get('contract_id')}
            )

    def _extract_parameters(self, parsed_xml: str, metadata: Dict) -> Dict[str, Any]:
        """Extract contract parameters from request using LLM"""
        logger.info("Extracting contract parameters with LLM")

        # Use existing metadata as base
        contract_type = metadata.get('contract_type', 'general')

        # Truncate XML for LLM
        xml_sample = parsed_xml[:4000] if len(parsed_xml) > 4000 else parsed_xml

        metadata_str = json.dumps(metadata, ensure_ascii=False)

        prompt = "Extract contract parameters from this request in JSON format.\n\n"
        prompt += f"Request XML:\n{xml_sample}\n\n"
        prompt += f"Known metadata: {metadata_str}\n\n"
        prompt += "Extract and return ONLY valid JSON with example structure for parties with bank_details.\n"
        prompt += "Return ONLY the JSON, no additional text."

        try:
            response = self.call_llm(prompt, temperature=0.1)

            # Extract JSON from response
            response = response.strip()
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()

            params = json.loads(response)
            logger.info(f"Parameters extracted successfully: {params.get('contract_type')}")
            return params

        except Exception as e:
            logger.warning(f"LLM parameter extraction failed: {e}, using metadata")
            # Fallback to basic params from metadata
            return {
                "contract_type": contract_type,
                "parties": metadata.get('parties', [{"name": "Unknown"}]),
                "subject": metadata.get('subject', 'Contract'),
                "price": {"amount": 0, "currency": "RUB", "vat_included": True},
                "term": {"start_date": None, "end_date": None},
                "special_conditions": [],
                "penalties": {},
                "liability": {},
                "payment_terms": {}
            }

    def _find_template(self, params: Dict) -> Optional[Template]:
        """Find suitable template using type + semantic + legal analysis"""
        logger.info(f"Finding template for: {params.get('contract_type')}")

        contract_type = params.get('contract_type', 'general')

        # Try to find by type first
        template = self.template_manager.get_template(contract_type)

        if template:
            logger.info(f"Template found by type: {template.name}")
            return template

        # If RAG available, try semantic search
        if self.rag_system:
            logger.info("Trying semantic search via RAG")
            # Search for similar templates
            query = f"Шаблон договора {contract_type} {params.get('subject', '')}"
            results = self.rag_system.search(query, top_k=1)

            if results and len(results) > 0:
                # Try to get template by ID from metadata
                template_id = results[0].get('metadata', {}).get('template_id')
                if template_id:
                    template = self.db.query(Template).filter(Template.id == template_id).first()
                    if template:
                        logger.info(f"Template found via RAG: {template.name}")
                        return template

        logger.warning(f"No template found for type: {contract_type}")
        return None

    def _get_rag_context(self, params: Dict, template: Template) -> Dict[str, Any]:
        """Get RAG context: formulations, precedents, legal norms"""
        logger.info("Getting RAG context for generation")

        contract_type = params.get('contract_type', 'general')

        context = {
            'formulations': [],
            'precedents': [],
            'legal_norms': []
        }

        try:
            # Search for best formulations
            formulation_query = f"Лучшие формулировки для раздела ответственность договора {contract_type}"
            formulations = self.rag_system.search(formulation_query, top_k=3)
            context['formulations'] = [r.get('text', '') for r in formulations]

            # Search for precedents
            precedent_query = f"Примеры договоров {contract_type} сумма {params.get('price', {}).get('amount', 0)}"
            precedents = self.rag_system.search(precedent_query, top_k=2)
            context['precedents'] = [r.get('text', '') for r in precedents]

            # Search for legal norms
            legal_query = f"Правовые нормы ГК РФ для договора {contract_type}"
            legal_norms = self.rag_system.search(legal_query, top_k=3)
            context['legal_norms'] = [r.get('text', '') for r in legal_norms]

            logger.info(f"RAG context: {len(context['formulations'])} formulations, {len(context['precedents'])} precedents, {len(context['legal_norms'])} norms")

        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")

        return context

    def _generate_contract(self, template: Template, params: Dict, rag_context: Dict) -> str:
        """Generate contract using template + LLM + RAG context"""
        logger.info(f"Generating contract from template: {template.name}")

        # Prepare RAG context for prompt
        rag_text = ""
        if rag_context.get('formulations'):
            rag_text += "\n\nПримеры лучших формулировок:\n" + "\n".join(rag_context['formulations'][:2])
        if rag_context.get('legal_norms'):
            rag_text += "\n\nПрименимые правовые нормы:\n" + "\n".join(rag_context['legal_norms'][:2])

        params_str = json.dumps(params, ensure_ascii=False, indent=2)
        template_sample = template.xml_content[:3000]

        prompt = f"Generate a complete contract based on this template and parameters.\n\n"
        prompt += f"TEMPLATE:\n{template_sample}\n\n"
        prompt += f"PARAMETERS:\n{params_str}\n"
        prompt += rag_text + "\n\n"
        prompt += "Instructions:\n"
        prompt += "1. Fill the template with provided parameters\n"
        prompt += "2. Adapt formulations to match the specific case\n"
        prompt += "3. Ensure legal compliance with ГК РФ\n"
        prompt += "4. Use provided RAG context for best practices\n"
        prompt += "5. Generate complete contract in XML format\n\n"
        prompt += "Return ONLY XML contract, no additional text."

        try:
            response = self.call_llm(prompt, temperature=0.3)

            # Extract XML from response
            if '<?xml' in response:
                contract_xml = response[response.find('<?xml'):]
                if '</contract>' in contract_xml:
                    contract_xml = contract_xml[:contract_xml.find('</contract>') + len('</contract>')]
            else:
                # Wrap in basic XML structure
                from lxml import etree
                root = etree.Element("contract")
                content_elem = etree.SubElement(root, "content")
                content_elem.text = response
                contract_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
                contract_xml += etree.tostring(root, encoding='unicode', pretty_print=True)

            logger.info(f"Contract generated: {len(contract_xml)} chars")
            return contract_xml

        except Exception as e:
            logger.error(f"Contract generation failed: {e}")
            raise

    def _validate_contract(self, contract_xml: str, params: Dict) -> Dict[str, Any]:
        """Validate generated contract"""
        logger.info("Validating generated contract")

        validation = {
            'passed': True,
            'errors': [],
            'warnings': []
        }

        # Check 1: XML structure (with XXE protection)
        try:
            parse_xml_safely(contract_xml)
        except (XMLSecurityError, Exception) as e:
            validation['errors'].append(f"Invalid XML structure: {e}")
            validation['passed'] = False

        # Check 2: Mandatory sections (basic check)
        mandatory_keywords = ['договор', 'стороны', 'предмет', 'цена', 'срок']
        contract_lower = contract_xml.lower()

        for keyword in mandatory_keywords:
            if keyword not in contract_lower:
                validation['warnings'].append(f"Missing keyword: {keyword}")

        # Check 3: Parties present
        parties = params.get('parties', [])
        for party in parties:
            party_name = party.get('name', '')
            if party_name and party_name.lower() not in contract_lower:
                validation['warnings'].append(f"Party not found in contract: {party_name}")

        # Check 4: Price present
        price = params.get('price', {}).get('amount')
        if price and str(price) not in contract_xml:
            validation['warnings'].append(f"Price not found: {price}")

        logger.info(f"Validation: {len(validation['errors'])} errors, {len(validation['warnings'])} warnings")

        return validation

    def _create_template_selection_request(self, contract_id: str, params: Dict) -> AgentResult:
        """Create request for user to select/create template"""
        logger.info("Creating template selection request")

        return self.create_success_result(
            data={
                'contract_id': contract_id,
                'template_selection_required': True,
                'extracted_params': params,
                'message': f"Шаблон для типа '{params.get('contract_type')}' не найден. Требуется выбор пользователя."
            },
            next_action='review',  # Send to review with special status
            metadata={'status': 'template_selection_required'}
        )


__all__ = ["ContractGeneratorAgent"]
