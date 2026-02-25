# -*- coding: utf-8 -*-
"""
Full Onboarding Agent - Document intake, parsing, and classification

Responsibilities:
- Parse documents (all formats: DOCX, DOC, PDF, RTF, ODT, XML)
- Extract metadata (parties, contract type, date, number)
- Extract tracked changes (if present)
- Classify document type using LLM
- Determine next agent (analyzer/generator/disagreement/changes)
"""
import os
import json
from typing import Dict, Any
from datetime import datetime
from pathlib import Path
from loguru import logger

from ..agents.base_agent import BaseAgent, AgentResult
from ..services.document_parser_extended import ExtendedDocumentParser


class OnboardingAgentFull(BaseAgent):
    """
    Full Onboarding Agent - First agent in workflow

    Workflow:
    1. Parse document to XML
    2. Extract tracked changes
    3. Extract basic metadata
    4. Classify document with LLM
    5. Route to next agent
    """

    def get_name(self) -> str:
        return "OnboardingAgent"

    def get_system_prompt(self) -> str:
        return """You are a legal document classification expert.
Analyze contracts and determine their type and purpose.
Be precise and concise in your analysis."""

    def execute(self, state: Dict[str, Any]) -> AgentResult:
        """
        Execute onboarding workflow

        Required state:
        - contract_id: str
        - file_path: str

        Returns state with:
        - parsed_xml: str
        - metadata: dict (parties, contract_type, date, number)
        - has_tracked_changes: bool
        - tracked_changes: list (if present)
        - document_classification: str (contract/new_contract/disagreement/tracked_changes)
        - next_action: str (analyzer/generator/disagreement/changes)
        """
        start_time = datetime.utcnow()

        try:
            # Validate input
            self.validate_state(state, ['contract_id', 'file_path'])

            contract_id = state['contract_id']
            file_path = state['file_path']

            logger.info(f"Onboarding contract {contract_id}: {file_path}")

            # Step 1: Parse document
            parsed_xml = self._parse_document(file_path)

            # Step 2: Extract tracked changes
            tracked_changes = self._extract_tracked_changes(file_path)
            has_tracked_changes = len(tracked_changes) > 0

            # Step 3: Extract metadata with LLM
            metadata = self._extract_metadata(parsed_xml)

            # Step 4: Classify document with LLM
            classification = self._classify_document(parsed_xml, metadata, has_tracked_changes)

            # Step 5: Determine next action
            next_action = self._determine_next_action(classification, has_tracked_changes)

            # Prepare result data
            result_data = {
                'contract_id': contract_id,
                'parsed_xml': parsed_xml,
                'metadata': metadata,
                'has_tracked_changes': has_tracked_changes,
                'tracked_changes': tracked_changes,
                'document_classification': classification,
                'onboarding_complete': True
            }

            duration = (datetime.utcnow() - start_time).total_seconds()
            self.log_execution('onboarding', state, result_data, duration)

            return self.create_success_result(
                data=result_data,
                next_action=next_action,
                metadata={'duration': duration, 'format': Path(file_path).suffix}
            )

        except Exception as e:
            logger.error(f"Onboarding failed: {e}")
            return self.create_error_result(
                error=str(e),
                data={'contract_id': state.get('contract_id')}
            )

    def _parse_document(self, file_path: str) -> str:
        """Parse document to XML"""
        logger.info(f"Parsing document: {file_path}")

        parser = ExtendedDocumentParser()
        xml_content = parser.parse(file_path, enable_ocr=True)

        logger.info(f"Document parsed: {len(xml_content)} chars")
        return xml_content

    def _extract_tracked_changes(self, file_path: str) -> list:
        """Extract tracked changes from document"""
        ext = Path(file_path).suffix.lower()

        if ext not in ['.docx', '.doc']:
            return []

        try:
            parser = ExtendedDocumentParser()
            changes = parser.extract_tracked_changes(file_path)
            logger.info(f"Extracted {len(changes)} tracked changes")
            return changes
        except Exception as e:
            logger.warning(f"Could not extract tracked changes: {e}")
            return []

    def _extract_metadata(self, xml_content: str) -> Dict[str, Any]:
        """Extract metadata using LLM"""
        logger.info("Extracting metadata with LLM")

        # Truncate XML for LLM (first 3000 chars usually enough for metadata)
        xml_sample = xml_content[:3000] if len(xml_content) > 3000 else xml_content

        prompt = f"""Analyze this contract XML and extract key metadata in JSON format.

XML:
{xml_sample}

Extract and return ONLY valid JSON with these fields:
{{
  "parties": ["Company A", "Company B"],
  "contract_type": "supply_agreement",
  "contract_date": "2024-01-15",
  "contract_number": "123/2024",
  "subject": "brief description"
}}

Return ONLY the JSON, no additional text."""

        try:
            response = self.call_llm(prompt, temperature=0.1)

            # Extract JSON from response
            response = response.strip()
            if '```json' in response:
                response = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                response = response.split('```')[1].split('```')[0].strip()

            metadata = json.loads(response)
            logger.info(f"Extracted metadata: {metadata.get('contract_type', 'unknown')}")
            return metadata

        except Exception as e:
            logger.warning(f"LLM metadata extraction failed: {e}, using defaults")
            return {
                "parties": ["Unknown"],
                "contract_type": "general",
                "contract_date": None,
                "contract_number": None,
                "subject": "Contract document"
            }

    def _classify_document(self, xml_content: str, metadata: Dict, has_tracked_changes: bool) -> str:
        """
        Classify document type with LLM

        Returns: contract | new_contract | disagreement | tracked_changes
        """
        logger.info("Classifying document with LLM")

        xml_sample = xml_content[:2000] if len(xml_content) > 2000 else xml_content

        prompt = f"""Classify this legal document into ONE category:

Document metadata: {json.dumps(metadata)}
Has tracked changes: {has_tracked_changes}

XML sample:
{xml_sample}

Categories:
- contract: Existing contract for analysis/review
- new_contract: Request to generate a new contract
- disagreement: Document with disagreement/counterproposal
- tracked_changes: Document focused on reviewing changes

Return ONLY the category name, no explanation."""

        try:
            response = self.call_llm(prompt, temperature=0.0).strip().lower()

            # Map response to valid categories
            if 'new_contract' in response or 'generate' in response or 'request' in response:
                classification = 'new_contract'
            elif 'disagreement' in response or 'counterproposal' in response:
                classification = 'disagreement'
            elif 'tracked_changes' in response or 'changes' in response and has_tracked_changes:
                classification = 'tracked_changes'
            else:
                classification = 'contract'

            logger.info(f"Document classified as: {classification}")
            return classification

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, defaulting to 'contract'")
            return 'contract'

    def _determine_next_action(self, classification: str, has_tracked_changes: bool) -> str:
        """
        Determine next agent based on classification

        Returns: analyzer | generator | disagreement | changes
        """
        routing = {
            'contract': 'analyzer',
            'new_contract': 'generator',
            'disagreement': 'disagreement',
            'tracked_changes': 'changes' if has_tracked_changes else 'analyzer'
        }

        next_action = routing.get(classification, 'analyzer')
        logger.info(f"Next action: {next_action}")
        return next_action


__all__ = ["OnboardingAgentFull"]
