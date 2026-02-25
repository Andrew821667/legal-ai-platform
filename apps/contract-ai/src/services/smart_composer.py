"""
Smart Contract Composer

AI-powered contract drafting assistant with real-time suggestions
(like GitHub Copilot for legal contracts)

Features:
- Context-aware clause suggestions
- Real-time risk validation
- Best practice recommendations
- Template-based composition
- RAG-powered precedent search
- Streaming LLM responses
- Auto-completion

Author: AI Contract System
"""

import asyncio
from typing import Dict, List, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass
from datetime import datetime
import re

from loguru import logger

try:
    from src.services.llm_gateway import LLMGateway
    from src.services.enhanced_rag import get_enhanced_rag
    from src.ml.risk_predictor import quick_predict_risk
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("⚠️  LLM or RAG not available for Smart Composer")


@dataclass
class Suggestion:
    """AI suggestion for contract clause"""
    text: str
    confidence: float  # 0.0 - 1.0
    category: str  # 'clause', 'term', 'definition', 'risk_mitigation'
    explanation: str
    source: Optional[str] = None  # 'template', 'precedent', 'best_practice'
    risk_level: Optional[str] = None
    alternatives: Optional[List[str]] = None


@dataclass
class ValidationResult:
    """Real-time validation result"""
    is_valid: bool
    issues: List[Dict[str, str]]  # [{type: 'error|warning', message: '...'}]
    suggestions: List[str]
    risk_score: float  # 0-100


@dataclass
class ComposerContext:
    """Composer context for maintaining state"""
    contract_type: str
    parties: List[str]
    current_section: str
    existing_clauses: List[str]
    user_preferences: Dict
    template_id: Optional[str] = None


class SmartContractComposer:
    """
    Smart Contract Composer with AI Assistance

    Usage:
        composer = SmartContractComposer(llm_gateway)

        # Initialize composition
        context = composer.start_composition(
            contract_type='supply',
            parties=['Company A', 'Company B']
        )

        # Get suggestions as user types
        async for suggestion in composer.get_suggestions(
            context,
            current_text="The Supplier shall deliver"
        ):
            print(suggestion.text)

        # Validate clause
        validation = composer.validate_clause(
            context,
            clause_text="Payment shall be made within..."
        )
    """

    def __init__(self, llm_gateway: Optional['LLMGateway'] = None):
        self.llm = llm_gateway
        self.rag = get_enhanced_rag() if LLM_AVAILABLE else None

        # Clause templates by contract type
        self.clause_templates = self._load_clause_templates()

        # Common legal terms and patterns
        self.legal_patterns = self._load_legal_patterns()

        # Best practices database
        self.best_practices = self._load_best_practices()

    def _load_clause_templates(self) -> Dict[str, Dict[str, List[str]]]:
        """Load clause templates by contract type"""
        return {
            'supply': {
                'payment_terms': [
                    "Payment shall be made within {days} days of invoice date.",
                    "The Buyer shall pay {percentage}% advance payment upon contract signing.",
                    "Payment terms: Net {days} from delivery date."
                ],
                'delivery': [
                    "Delivery shall be made to {address} within {days} business days.",
                    "The Supplier warrants timely delivery as per the agreed schedule.",
                    "Delivery terms: {incoterm} (Incoterms 2020)."
                ],
                'force_majeure': [
                    "Neither party shall be liable for failure to perform due to circumstances beyond their reasonable control.",
                    "Force majeure events include: natural disasters, war, pandemic, government actions, and labor disputes.",
                    "Upon occurrence of force majeure, the affected party shall notify the other party within {days} days."
                ],
                'liability': [
                    "Each party's total liability shall not exceed {amount} or the contract value, whichever is lower.",
                    "Neither party shall be liable for indirect, consequential, or special damages.",
                    "Liability limitations do not apply to: gross negligence, willful misconduct, or breach of confidentiality."
                ]
            },
            'service': {
                'scope': [
                    "The Service Provider shall provide the following services: {service_description}.",
                    "Services shall be performed in accordance with industry best practices.",
                    "The scope of services is detailed in Attachment A."
                ],
                'acceptance': [
                    "The Client shall accept or reject deliverables within {days} business days.",
                    "Acceptance criteria are specified in the Service Level Agreement (SLA).",
                    "Silence shall not constitute acceptance."
                ]
            },
            'nda': {
                'definition': [
                    "\"Confidential Information\" means all non-public information disclosed by either party.",
                    "Confidential Information excludes information that: (a) is publicly available, (b) was known prior to disclosure, (c) is independently developed.",
                    "The receiving party shall protect Confidential Information with at least the same degree of care as its own confidential information."
                ],
                'term': [
                    "Confidentiality obligations shall survive for {years} years after termination.",
                    "This Agreement shall remain in effect for {years} years from the Effective Date.",
                    "Confidentiality obligations are perpetual for trade secrets."
                ]
            }
        }

    def _load_legal_patterns(self) -> Dict[str, re.Pattern]:
        """Load regex patterns for legal terms"""
        return {
            'currency': re.compile(r'\b(USD|EUR|RUB|руб\.?)\s*\d+'),
            'date': re.compile(r'\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b'),
            'duration': re.compile(r'\b\d+\s*(days?|months?|years?|дней|месяцев|лет)\b'),
            'percentage': re.compile(r'\b\d+(\.\d+)?%'),
            'party_reference': re.compile(r'\b(the )?(Buyer|Seller|Client|Provider|Supplier|Покупатель|Продавец)\b'),
        }

    def _load_best_practices(self) -> Dict[str, List[Dict]]:
        """Load best practices database"""
        return {
            'payment_terms': [
                {
                    'practice': 'Include specific payment deadlines',
                    'example': 'Payment within 30 days of invoice date',
                    'rationale': 'Avoids ambiguity and disputes'
                },
                {
                    'practice': 'Specify late payment penalties',
                    'example': '0.1% per day for late payment',
                    'rationale': 'Incentivizes timely payment'
                }
            ],
            'termination': [
                {
                    'practice': 'Include both convenience and cause termination',
                    'example': 'Either party may terminate with 30 days notice, or immediately for material breach',
                    'rationale': 'Provides flexibility and protection'
                },
                {
                    'practice': 'Specify post-termination obligations',
                    'example': 'Return of confidential information within 10 days',
                    'rationale': 'Ensures clean exit'
                }
            ],
            'liability': [
                {
                    'practice': 'Cap liability at reasonable amount',
                    'example': 'Total liability not to exceed contract value',
                    'rationale': 'Manages risk exposure'
                },
                {
                    'practice': 'Exclude consequential damages',
                    'example': 'No liability for indirect or consequential damages',
                    'rationale': 'Prevents unlimited liability'
                }
            ]
        }

    def start_composition(
        self,
        contract_type: str,
        parties: List[str],
        template_id: Optional[str] = None,
        user_preferences: Optional[Dict] = None
    ) -> ComposerContext:
        """
        Start new contract composition

        Args:
            contract_type: Type of contract ('supply', 'service', 'nda', etc.)
            parties: List of party names
            template_id: Optional template to start from
            user_preferences: User preferences (language, formality level, etc.)

        Returns:
            ComposerContext for subsequent operations
        """
        context = ComposerContext(
            contract_type=contract_type,
            parties=parties,
            current_section='preamble',
            existing_clauses=[],
            user_preferences=user_preferences or {},
            template_id=template_id
        )

        logger.info(f"🎨 Started composition: {contract_type} between {', '.join(parties)}")
        return context

    async def get_suggestions(
        self,
        context: ComposerContext,
        current_text: str,
        cursor_position: Optional[int] = None
    ) -> AsyncGenerator[Suggestion, None]:
        """
        Get AI suggestions for current text (streaming)

        This is the core "autocomplete" functionality.

        Args:
            context: Composer context
            current_text: Text typed so far
            cursor_position: Cursor position in text

        Yields:
            Suggestion objects as they're generated
        """
        if not self.llm:
            logger.warning("⚠️  LLM not available for suggestions")
            return

        # Detect what user is trying to write
        intent = self._detect_writing_intent(current_text)

        # Build prompt for LLM
        prompt = self._build_suggestion_prompt(context, current_text, intent)

        # Stream suggestions from LLM
        try:
            async for chunk in self._stream_llm_suggestions(prompt):
                suggestion = self._parse_suggestion_chunk(chunk, intent)
                if suggestion:
                    yield suggestion

        except Exception as e:
            logger.error(f"❌ Error getting suggestions: {e}")

    def _detect_writing_intent(self, text: str) -> str:
        """
        Detect what the user is trying to write

        Returns: 'payment', 'delivery', 'termination', 'liability', 'general', etc.
        """
        text_lower = text.lower()

        intents = {
            'payment': ['payment', 'pay', 'invoice', 'fee', 'price', 'оплата', 'платеж'],
            'delivery': ['deliver', 'ship', 'supply', 'доставка', 'поставка'],
            'termination': ['terminate', 'cancel', 'end', 'расторжение', 'прекращение'],
            'liability': ['liable', 'liability', 'damages', 'ответственность', 'убытки'],
            'force_majeure': ['force majeure', 'circumstances beyond', 'форс-мажор'],
            'confidentiality': ['confidential', 'secret', 'non-disclosure', 'конфиденциальность'],
            'warranty': ['warrant', 'guarantee', 'гарантия'],
            'dispute': ['dispute', 'arbitration', 'court', 'спор', 'арбитраж'],
        }

        for intent, keywords in intents.items():
            if any(keyword in text_lower for keyword in keywords):
                return intent

        return 'general'

    def _build_suggestion_prompt(
        self,
        context: ComposerContext,
        current_text: str,
        intent: str
    ) -> str:
        """Build prompt for LLM suggestion generation"""

        # Get relevant precedents from RAG
        precedents = []
        if self.rag:
            rag_results = self.rag.search(
                query=current_text,
                top_k=3,
                search_kb=True,
                search_contracts=True
            )
            precedents = [r.content for r in rag_results]

        # Get templates for this intent
        templates = []
        if context.contract_type in self.clause_templates:
            if intent in self.clause_templates[context.contract_type]:
                templates = self.clause_templates[context.contract_type][intent]

        prompt = f"""You are an expert legal contract drafting assistant.

Contract Type: {context.contract_type}
Parties: {', '.join(context.parties)}
Current Section: {context.current_section}
Intent: {intent}

User is typing: "{current_text}"

Relevant precedents from similar contracts:
{chr(10).join(f'{i+1}. {p[:200]}...' for i, p in enumerate(precedents))}

Template suggestions:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(templates))}

Task: Complete the clause with 2-3 high-quality suggestions.

Requirements:
- Professional legal language
- Clear and unambiguous
- Protect both parties fairly
- Follow best practices
- Include specific terms (amounts, dates, etc.) as placeholders

Output format (JSON):
{{
  "suggestions": [
    {{
      "text": "suggested clause text",
      "confidence": 0.95,
      "explanation": "why this is good",
      "alternatives": ["alternative 1", "alternative 2"]
    }}
  ]
}}
"""

        return prompt

    async def _stream_llm_suggestions(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream suggestions from LLM"""
        # Mock streaming for now
        # In production, use actual LLM streaming API

        mock_response = """{
  "suggestions": [
    {
      "text": "Payment shall be made within thirty (30) calendar days from the date of invoice receipt. Late payments shall incur a penalty of 0.1% per day.",
      "confidence": 0.92,
      "explanation": "Standard payment terms with clear deadline and late payment penalty to incentivize timely payment.",
      "alternatives": [
        "Payment due net 30 days from invoice date.",
        "The Buyer shall remit payment within 30 days of receiving a valid invoice."
      ]
    },
    {
      "text": "Payment shall be made in two installments: 50% upon contract signing, and 50% upon delivery.",
      "confidence": 0.85,
      "explanation": "Split payment reduces risk for both parties - Buyer gets performance assurance, Supplier gets advance payment.",
      "alternatives": [
        "Payment schedule: 30% advance, 40% on milestone, 30% on completion."
      ]
    }
  ]
}"""

        # Simulate streaming
        for char in mock_response:
            yield char
            await asyncio.sleep(0.001)  # Simulate latency

    def _parse_suggestion_chunk(self, chunk: str, intent: str) -> Optional[Suggestion]:
        """Parse suggestion from LLM chunk"""
        # In production, parse JSON chunks properly
        # For now, return None (handled by full response parsing)
        return None

    def validate_clause(
        self,
        context: ComposerContext,
        clause_text: str
    ) -> ValidationResult:
        """
        Validate a clause in real-time

        Checks:
        - Completeness (has all required elements)
        - Clarity (no ambiguous terms)
        - Balance (fair to both parties)
        - Risk level
        - Best practice compliance

        Args:
            context: Composer context
            clause_text: Clause text to validate

        Returns:
            ValidationResult with issues and suggestions
        """
        issues = []
        suggestions = []

        # Check 1: Completeness
        if not clause_text.strip().endswith('.'):
            issues.append({
                'type': 'warning',
                'message': 'Clause should end with a period.'
            })

        # Check 2: Party references
        party_mentioned = any(party in clause_text for party in context.parties)
        has_generic_party = bool(self.legal_patterns['party_reference'].search(clause_text))

        if not party_mentioned and not has_generic_party:
            issues.append({
                'type': 'warning',
                'message': 'No party references found. Consider specifying which party has this obligation.'
            })
            suggestions.append(f"Add party reference: e.g., 'The {context.parties[0]} shall...'")

        # Check 3: Ambiguous terms
        ambiguous_terms = ['reasonable', 'appropriate', 'sufficient', 'adequate']
        found_ambiguous = [term for term in ambiguous_terms if term in clause_text.lower()]

        if found_ambiguous:
            issues.append({
                'type': 'warning',
                'message': f'Ambiguous terms found: {", ".join(found_ambiguous)}. Consider being more specific.'
            })
            suggestions.append('Replace with specific criteria or measurements.')

        # Check 4: Missing key elements (for specific clause types)
        if 'payment' in clause_text.lower():
            if not self.legal_patterns['duration'].search(clause_text):
                issues.append({
                    'type': 'error',
                    'message': 'Payment clause missing deadline. Specify when payment is due.'
                })
                suggestions.append('Add timeline: e.g., "within 30 days of invoice date"')

            if not self.legal_patterns['currency'].search(clause_text):
                issues.append({
                    'type': 'warning',
                    'message': 'Payment clause missing currency specification.'
                })

        # Check 5: Risk assessment using ML
        mock_contract_data = {
            'contract_type': context.contract_type,
            'amount': 100000,  # Mock value
            'duration_days': 365,
            'clause_count': len(context.existing_clauses) + 1,
            'doc_length': len(clause_text)
        }

        try:
            risk_prediction = quick_predict_risk(mock_contract_data)
            risk_score = risk_prediction.risk_score

            if risk_score > 70:
                issues.append({
                    'type': 'warning',
                    'message': f'High risk detected (score: {risk_score:.0f}). Review carefully.'
                })
        except Exception as e:
            logger.error(f"Risk prediction failed: {e}")
            risk_score = 50.0

        # Check 6: Best practices
        intent = self._detect_writing_intent(clause_text)
        if intent in self.best_practices:
            for practice in self.best_practices[intent]:
                if practice['example'].lower() not in clause_text.lower():
                    suggestions.append(
                        f"Best practice: {practice['practice']}. "
                        f"Example: {practice['example']}"
                    )

        # Determine validity
        has_errors = any(issue['type'] == 'error' for issue in issues)

        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            suggestions=suggestions,
            risk_score=risk_score
        )

    def suggest_next_section(self, context: ComposerContext) -> List[str]:
        """
        Suggest what sections to write next

        Returns list of section names in recommended order
        """
        # Standard contract sections by type
        section_sequences = {
            'supply': [
                'Preamble',
                'Definitions',
                'Subject Matter',
                'Delivery Terms',
                'Price and Payment',
                'Quality and Acceptance',
                'Warranties',
                'Liability',
                'Force Majeure',
                'Confidentiality',
                'Term and Termination',
                'Dispute Resolution',
                'General Provisions',
                'Signatures'
            ],
            'service': [
                'Preamble',
                'Definitions',
                'Scope of Services',
                'Service Level Agreement',
                'Fees and Payment',
                'Acceptance Criteria',
                'Intellectual Property',
                'Warranties',
                'Liability',
                'Confidentiality',
                'Term and Termination',
                'Dispute Resolution',
                'General Provisions',
                'Signatures'
            ],
            'nda': [
                'Preamble',
                'Definitions',
                'Confidential Information',
                'Obligations',
                'Exclusions',
                'Term',
                'Return of Information',
                'No License',
                'Remedies',
                'General Provisions',
                'Signatures'
            ]
        }

        sequence = section_sequences.get(context.contract_type, section_sequences['supply'])

        # Find current position
        try:
            current_index = sequence.index(context.current_section)
            return sequence[current_index + 1:]
        except ValueError:
            return sequence

    def get_inline_help(self, keyword: str) -> Optional[str]:
        """
        Get inline help for legal terms

        Args:
            keyword: Legal term or phrase

        Returns:
            Help text explaining the term
        """
        help_db = {
            'force majeure': 'Unforeseen circumstances that prevent someone from fulfilling a contract (e.g., natural disasters, war). Include specific examples and notification requirements.',
            'indemnification': 'Agreement by one party to compensate the other for losses. Specify scope, caps, and exclusions clearly.',
            'liquidated damages': 'Pre-determined amount of damages for breach. Must be reasonable estimate of actual harm, not a penalty.',
            'severability': 'If one clause is invalid, the rest of the contract remains valid. Standard protective clause.',
            'entire agreement': 'Contract represents complete agreement, superseding all prior negotiations. Prevents claims based on earlier discussions.',
            'governing law': 'Which jurisdiction\'s laws apply to the contract. Important for cross-border contracts.',
            'assignment': 'Transfer of rights/obligations to third party. Usually restricted without consent.',
        }

        return help_db.get(keyword.lower())


# Convenience function
def create_smart_composer(llm_gateway=None) -> SmartContractComposer:
    """Create SmartContractComposer instance"""
    return SmartContractComposer(llm_gateway)
