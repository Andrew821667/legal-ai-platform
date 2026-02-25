# -*- coding: utf-8 -*-
"""
Simplified Integration Tests for Disagreement Processor Agent
Testing basic workflow without complex mocking
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.disagreement_processor_agent import DisagreementProcessorAgent


class TestDisagreementProcessorBasic:
    """Basic integration tests"""

    def test_agent_imports(self):
        """Test that agent can be imported"""
        assert DisagreementProcessorAgent is not None

    def test_agent_name(self):
        """Test agent name property"""
        # Create with minimal mocking
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_db = Mock()

        agent = DisagreementProcessorAgent(
            llm_gateway=mock_llm,
            db_session=mock_db
        )

        assert agent.get_name() == "DisagreementProcessorAgent"

    def test_agent_system_prompt(self):
        """Test system prompt generation"""
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_db = Mock()

        agent = DisagreementProcessorAgent(
            llm_gateway=mock_llm,
            db_session=mock_db
        )

        prompt = agent.get_system_prompt()
        assert "legal expert" in prompt.lower()
        assert "objection" in prompt.lower()

    def test_severity_to_priority_mapping(self):
        """Test risk severity to priority mapping"""
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_db = Mock()

        agent = DisagreementProcessorAgent(
            llm_gateway=mock_llm,
            db_session=mock_db
        )

        assert agent._severity_to_priority('critical') == 'critical'
        assert agent._severity_to_priority('significant') == 'high'
        assert agent._severity_to_priority('minor') == 'medium'
        assert agent._severity_to_priority('unknown') == 'medium'

    def test_execute_validates_state(self):
        """Test that execute validates required state parameters"""
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_db = Mock()

        agent = DisagreementProcessorAgent(
            llm_gateway=mock_llm,
            db_session=mock_db
        )

        # Missing contract_id and analysis_id
        result = agent.execute({})

        assert result.success is False
        assert "Missing" in result.error

    def test_execute_missing_contract(self):
        """Test execute when contract not found"""
        from unittest.mock import Mock
        mock_llm = Mock()
        mock_db = Mock()

        # Mock query to return None
        mock_db.query.return_value.filter.return_value.first.return_value = None

        agent = DisagreementProcessorAgent(
            llm_gateway=mock_llm,
            db_session=mock_db
        )

        result = agent.execute({
            'contract_id': 'nonexistent',
            'analysis_id': 'nonexistent'
        })

        assert result.success is False
        assert "not found" in result.error.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
