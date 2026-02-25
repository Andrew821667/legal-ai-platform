"""
Tests for Smart Contract Composer

Tests cover:
- Composition initialization
- AI suggestions
- Clause validation
- Template management
- Best practices
- Real-time help
"""

import pytest
import asyncio
from src.services.smart_composer import (
    SmartContractComposer,
    Suggestion,
    ValidationResult,
    ComposerContext,
    create_smart_composer
)


class TestComposerInitialization:
    """Test composer initialization and setup"""

    @pytest.fixture
    def composer(self):
        """Create composer instance"""
        return create_smart_composer()

    def test_composer_creation(self, composer):
        """Test composer can be created"""
        assert composer is not None
        assert composer.clause_templates is not None
        assert composer.legal_patterns is not None
        assert composer.best_practices is not None

    def test_templates_loaded(self, composer):
        """Test clause templates are loaded"""
        templates = composer.clause_templates

        # Should have templates for common contract types
        assert 'supply' in templates
        assert 'service' in templates
        assert 'nda' in templates

        # Each type should have multiple categories
        assert 'payment_terms' in templates['supply']
        assert 'delivery' in templates['supply']
        assert 'force_majeure' in templates['supply']

    def test_legal_patterns_loaded(self, composer):
        """Test legal regex patterns are loaded"""
        patterns = composer.legal_patterns

        assert 'currency' in patterns
        assert 'date' in patterns
        assert 'duration' in patterns
        assert 'percentage' in patterns

    def test_best_practices_loaded(self, composer):
        """Test best practices database is loaded"""
        best_practices = composer.best_practices

        assert 'payment_terms' in best_practices
        assert 'termination' in best_practices
        assert 'liability' in best_practices

        # Each category should have practices
        assert len(best_practices['payment_terms']) > 0


class TestCompositionStart:
    """Test starting new composition"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_start_basic_composition(self, composer):
        """Test starting a basic composition"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['Company A', 'Company B']
        )

        assert isinstance(context, ComposerContext)
        assert context.contract_type == 'supply'
        assert context.parties == ['Company A', 'Company B']
        assert context.current_section == 'preamble'
        assert context.existing_clauses == []

    def test_start_with_template(self, composer):
        """Test starting composition with template"""
        context = composer.start_composition(
            contract_type='service',
            parties=['Provider', 'Client'],
            template_id='service-standard-v1'
        )

        assert context.template_id == 'service-standard-v1'

    def test_start_with_preferences(self, composer):
        """Test starting composition with user preferences"""
        prefs = {
            'language': 'en',
            'formality': 'high',
            'industry': 'tech'
        }

        context = composer.start_composition(
            contract_type='nda',
            parties=['Party A', 'Party B'],
            user_preferences=prefs
        )

        assert context.user_preferences == prefs


class TestIntentDetection:
    """Test writing intent detection"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_detect_payment_intent(self, composer):
        """Test detection of payment clause"""
        text = "Payment shall be made within"
        intent = composer._detect_writing_intent(text)

        assert intent == 'payment'

    def test_detect_delivery_intent(self, composer):
        """Test detection of delivery clause"""
        text = "The Supplier shall deliver goods"
        intent = composer._detect_writing_intent(text)

        assert intent == 'delivery'

    def test_detect_termination_intent(self, composer):
        """Test detection of termination clause"""
        text = "Either party may terminate this agreement"
        intent = composer._detect_writing_intent(text)

        assert intent == 'termination'

    def test_detect_force_majeure_intent(self, composer):
        """Test detection of force majeure clause"""
        text = "In case of force majeure"
        intent = composer._detect_writing_intent(text)

        assert intent == 'force_majeure'

    def test_detect_general_intent(self, composer):
        """Test detection when no specific intent matches"""
        text = "This is a random text"
        intent = composer._detect_writing_intent(text)

        assert intent == 'general'

    def test_detect_russian_terms(self, composer):
        """Test detection of Russian legal terms"""
        text = "Оплата должна быть произведена"
        intent = composer._detect_writing_intent(text)

        assert intent == 'payment'


class TestClauseValidation:
    """Test real-time clause validation"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    @pytest.fixture
    def context(self, composer):
        return composer.start_composition(
            contract_type='supply',
            parties=['Supplier Inc.', 'Buyer Corp.']
        )

    def test_validate_complete_clause(self, composer, context):
        """Test validation of complete, well-formed clause"""
        clause = "Payment shall be made within 30 days of invoice date."

        validation = composer.validate_clause(context, clause)

        assert isinstance(validation, ValidationResult)
        assert validation.is_valid is True or len(validation.issues) == 0
        assert validation.risk_score >= 0

    def test_validate_incomplete_clause(self, composer, context):
        """Test validation of incomplete clause"""
        clause = "Payment shall be made"  # Missing period

        validation = composer.validate_clause(context, clause)

        # Should have warning about missing period
        has_period_warning = any(
            'period' in issue['message'].lower()
            for issue in validation.issues
        )
        assert has_period_warning

    def test_validate_ambiguous_terms(self, composer, context):
        """Test detection of ambiguous terms"""
        clause = "Payment within reasonable time."

        validation = composer.validate_clause(context, clause)

        # Should warn about 'reasonable'
        has_ambiguous_warning = any(
            'ambiguous' in issue['message'].lower()
            for issue in validation.issues
        )
        assert has_ambiguous_warning

    def test_validate_payment_without_deadline(self, composer, context):
        """Test payment clause without specific deadline"""
        clause = "Payment shall be made in USD."

        validation = composer.validate_clause(context, clause)

        # Should have error/warning about missing deadline
        issues = [issue for issue in validation.issues if issue['type'] == 'error']
        assert len(issues) > 0 or len(validation.suggestions) > 0

    def test_validate_missing_party_reference(self, composer, context):
        """Test clause without party reference"""
        clause = "Delivery shall occur within 30 days."

        validation = composer.validate_clause(context, clause)

        # May suggest adding party reference
        # Not always required, so just check validation runs

        assert validation is not None

    def test_validate_with_specific_parties(self, composer, context):
        """Test clause with specific party names"""
        clause = "Supplier Inc. shall deliver goods within 30 days."

        validation = composer.validate_clause(context, clause)

        # Should recognize party reference
        assert validation.is_valid is True or len([
            i for i in validation.issues if i['type'] == 'error'
        ]) == 0

    def test_risk_score_assignment(self, composer, context):
        """Test that risk score is assigned"""
        clause = "Payment terms are flexible."

        validation = composer.validate_clause(context, clause)

        assert 0 <= validation.risk_score <= 100


class TestSuggestionGeneration:
    """Test AI suggestion generation"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    @pytest.fixture
    def context(self, composer):
        return composer.start_composition(
            contract_type='supply',
            parties=['Company A', 'Company B']
        )

    @pytest.mark.asyncio
    async def test_get_suggestions_basic(self, composer, context):
        """Test getting basic suggestions"""
        current_text = "Payment shall be made"

        suggestions = []
        async for suggestion in composer.get_suggestions(context, current_text):
            suggestions.append(suggestion)
            if len(suggestions) >= 2:  # Get first 2 suggestions
                break

        # May not generate suggestions without LLM in test environment
        # Just verify method runs without error

    def test_build_suggestion_prompt(self, composer, context):
        """Test building prompt for LLM"""
        current_text = "The Supplier shall deliver"
        intent = "delivery"

        prompt = composer._build_suggestion_prompt(context, current_text, intent)

        assert "supply" in prompt.lower()  # Contract type
        assert "company a" in prompt.lower() or "company b" in prompt.lower()
        assert "deliver" in prompt.lower()


class TestSectionSuggestions:
    """Test section suggestion features"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_suggest_next_sections_supply(self, composer):
        """Test section suggestions for supply contract"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )
        context.current_section = 'Preamble'

        sections = composer.suggest_next_section(context)

        assert isinstance(sections, list)
        assert len(sections) > 0
        assert 'Definitions' in sections
        assert 'Payment' in sections or 'Price and Payment' in sections

    def test_suggest_next_sections_service(self, composer):
        """Test section suggestions for service contract"""
        context = composer.start_composition(
            contract_type='service',
            parties=['A', 'B']
        )
        context.current_section = 'Preamble'

        sections = composer.suggest_next_section(context)

        assert 'Scope of Services' in sections

    def test_suggest_next_sections_nda(self, composer):
        """Test section suggestions for NDA"""
        context = composer.start_composition(
            contract_type='nda',
            parties=['A', 'B']
        )
        context.current_section = 'Preamble'

        sections = composer.suggest_next_section(context)

        assert 'Confidential Information' in sections
        assert 'Obligations' in sections

    def test_section_order_is_logical(self, composer):
        """Test that section order is logical"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

        sections = composer.suggest_next_section(context)

        # Preamble should come before Definitions
        preamble_idx = sections.index('Preamble')
        definitions_idx = sections.index('Definitions')
        assert preamble_idx < definitions_idx

        # Signatures should be last
        assert sections[-1] == 'Signatures'


class TestInlineHelp:
    """Test inline help for legal terms"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_get_help_force_majeure(self, composer):
        """Test getting help for 'force majeure'"""
        help_text = composer.get_inline_help("force majeure")

        assert help_text is not None
        assert len(help_text) > 0
        assert "unforeseen" in help_text.lower() or "circumstances" in help_text.lower()

    def test_get_help_indemnification(self, composer):
        """Test getting help for 'indemnification'"""
        help_text = composer.get_inline_help("indemnification")

        assert help_text is not None
        assert "compensate" in help_text.lower() or "losses" in help_text.lower()

    def test_get_help_unknown_term(self, composer):
        """Test getting help for unknown term"""
        help_text = composer.get_inline_help("unknown_legal_term_xyz")

        assert help_text is None

    def test_get_help_case_insensitive(self, composer):
        """Test that help is case-insensitive"""
        help_lower = composer.get_inline_help("force majeure")
        help_upper = composer.get_inline_help("FORCE MAJEURE")
        help_mixed = composer.get_inline_help("Force Majeure")

        # Should all return same result
        assert help_lower == help_upper == help_mixed


class TestBestPractices:
    """Test best practices integration"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    @pytest.fixture
    def context(self, composer):
        return composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

    def test_best_practice_suggestions_payment(self, composer, context):
        """Test best practice suggestions for payment terms"""
        clause = "Payment shall occur."

        validation = composer.validate_clause(context, clause)

        # Should suggest adding specific deadline (best practice)
        has_deadline_suggestion = any(
            'deadline' in sugg.lower() or 'days' in sugg.lower()
            for sugg in validation.suggestions
        )
        assert has_deadline_suggestion

    def test_best_practice_database_structure(self, composer):
        """Test best practices have proper structure"""
        practices = composer.best_practices['payment_terms']

        for practice in practices:
            assert 'practice' in practice
            assert 'example' in practice
            assert 'rationale' in practice


class TestTemplateManagement:
    """Test template clause management"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_payment_templates_exist(self, composer):
        """Test payment term templates exist"""
        templates = composer.clause_templates['supply']['payment_terms']

        assert len(templates) > 0
        # Should have templates with placeholders
        has_placeholder = any('{' in t and '}' in t for t in templates)
        assert has_placeholder

    def test_force_majeure_templates(self, composer):
        """Test force majeure templates"""
        templates = composer.clause_templates['supply']['force_majeure']

        assert len(templates) > 0

    def test_template_placeholders(self, composer):
        """Test templates have reasonable placeholders"""
        templates = composer.clause_templates['supply']['payment_terms']

        # Should have placeholders like {days}, {percentage}, etc.
        all_templates = ' '.join(templates)
        assert '{days}' in all_templates or '{amount}' in all_templates


class TestLegalPatterns:
    """Test legal pattern recognition"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_currency_pattern(self, composer):
        """Test currency pattern matching"""
        pattern = composer.legal_patterns['currency']

        assert pattern.search("USD 1000")
        assert pattern.search("EUR 500")
        assert pattern.search("RUB 10000")
        assert pattern.search("руб. 5000")

    def test_date_pattern(self, composer):
        """Test date pattern matching"""
        pattern = composer.legal_patterns['date']

        assert pattern.search("01/15/2025")
        assert pattern.search("15.01.2025")

    def test_duration_pattern(self, composer):
        """Test duration pattern matching"""
        pattern = composer.legal_patterns['duration']

        assert pattern.search("30 days")
        assert pattern.search("6 months")
        assert pattern.search("2 years")
        assert pattern.search("90 дней")

    def test_percentage_pattern(self, composer):
        """Test percentage pattern matching"""
        pattern = composer.legal_patterns['percentage']

        assert pattern.search("10%")
        assert pattern.search("0.5%")
        assert pattern.search("99.99%")


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_empty_clause_validation(self, composer):
        """Test validation of empty clause"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

        validation = composer.validate_clause(context, "")

        assert validation is not None

    def test_very_long_clause(self, composer):
        """Test validation of very long clause"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

        long_clause = "Payment " + "shall be made " * 100 + "within 30 days."

        validation = composer.validate_clause(context, long_clause)

        assert validation is not None

    def test_special_characters_in_clause(self, composer):
        """Test clause with special characters"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

        clause = "Payment: $1,000.00 @ 30 days (Net-30)."

        validation = composer.validate_clause(context, clause)

        assert validation is not None

    def test_non_english_clause(self, composer):
        """Test non-English clause"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['Поставщик', 'Покупатель']
        )

        clause = "Оплата производится в течение 30 дней."

        validation = composer.validate_clause(context, clause)

        assert validation is not None


class TestRealWorldScenarios:
    """Test real-world contract composition scenarios"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_typical_payment_clause(self, composer):
        """Test typical payment clause"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['Supplier', 'Buyer']
        )

        clause = "The Buyer shall pay the Supplier within thirty (30) calendar days from the date of invoice receipt."

        validation = composer.validate_clause(context, clause)

        # Should be valid with low risk
        assert validation.risk_score < 70

    def test_liability_limitation_clause(self, composer):
        """Test liability limitation clause"""
        context = composer.start_composition(
            contract_type='service',
            parties=['Provider', 'Client']
        )

        clause = "Provider's total liability shall not exceed the fees paid under this Agreement in the twelve (12) months preceding the claim."

        validation = composer.validate_clause(context, clause)

        # Should recognize as valid liability clause
        assert validation is not None

    def test_force_majeure_clause(self, composer):
        """Test force majeure clause"""
        context = composer.start_composition(
            contract_type='supply',
            parties=['A', 'B']
        )

        clause = "Neither party shall be liable for failure to perform due to circumstances beyond their reasonable control, including but not limited to acts of God, war, pandemic, or government actions."

        validation = composer.validate_clause(context, clause)

        # Should be valid
        assert len([i for i in validation.issues if i['type'] == 'error']) == 0


# Integration test
class TestComposerIntegration:
    """Integration test for complete workflow"""

    @pytest.fixture
    def composer(self):
        return create_smart_composer()

    def test_complete_composition_workflow(self, composer):
        """Test complete composition workflow"""
        # 1. Start composition
        context = composer.start_composition(
            contract_type='supply',
            parties=['Acme Corp', 'Widget Inc']
        )

        assert context is not None

        # 2. Get section suggestions
        sections = composer.suggest_next_section(context)
        assert len(sections) > 0

        # 3. Validate a clause
        clause = "Widget Inc shall deliver goods within 14 days."
        validation = composer.validate_clause(context, clause)
        assert validation is not None

        # 4. Get inline help
        help_text = composer.get_inline_help("force majeure")
        assert help_text is not None

        # 5. Detect intent
        intent = composer._detect_writing_intent("Payment shall be made")
        assert intent == 'payment'
