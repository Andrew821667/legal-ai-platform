# -*- coding: utf-8 -*-
"""
Tests for Disagreement Processor Agent
"""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
from src.models.database import Contract, AnalysisResult
from src.models.analyzer_models import ContractRisk, ContractRecommendation
from src.models.disagreement_models import Disagreement, DisagreementObjection


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = Mock()
    session.query = Mock()
    session.add = Mock()
    session.commit = Mock()
    session.rollback = Mock()
    session.refresh = Mock()
    return session


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway"""
    gateway = Mock()
    gateway.chat = Mock()
    return gateway


@pytest.fixture
def mock_rag_system():
    """Mock RAG System"""
    rag = Mock()
    rag.search = Mock(return_value={
        'results': [
            {'text': 'Судебная практика по договорам', 'metadata': {'source': 'court_case_123'}},
            {'text': 'Статья 421 ГК РФ о свободе договора', 'metadata': {'source': 'law_gk_421'}}
        ],
        'context': 'Согласно судебной практике и статье 421 ГК РФ...'
    })
    return rag


@pytest.fixture
def sample_contract():
    """Sample contract for testing"""
    return Contract(
        id='test-contract-123',
        file_name='contract_supply.docx',
        file_path='/path/to/contract.docx',
        document_type='contract',
        contract_type='supply',
        status='analyzing'
    )


@pytest.fixture
def sample_analysis():
    """Sample analysis result"""
    return AnalysisResult(
        id='analysis-123',
        contract_id='test-contract-123'
    )


@pytest.fixture
def sample_risks():
    """Sample risks from analyzer"""
    return [
        ContractRisk(
            id='risk-1',
            analysis_id='analysis-123',
            risk_type='payment',
            severity='critical',
            probability='high',
            description='Отсутствует ограничение ответственности поставщика',
            affected_clauses=['section_3_clause_1'],
            legal_references=['ст. 15 ГК РФ', 'ст. 393 ГК РФ'],
            mitigation_strategy='Добавить пункт об ограничении ответственности'
        ),
        ContractRisk(
            id='risk-2',
            analysis_id='analysis-123',
            risk_type='termination',
            severity='significant',
            probability='medium',
            description='Несимметричные условия расторжения',
            affected_clauses=['section_7_clause_2'],
            legal_references=['ст. 450 ГК РФ'],
            mitigation_strategy='Уравнять условия расторжения для обеих сторон'
        )
    ]


@pytest.fixture
def sample_recommendations():
    """Sample recommendations"""
    return [
        ContractRecommendation(
            id='rec-1',
            analysis_id='analysis-123',
            recommendation_type='add_clause',
            priority='high',
            title='Добавить ограничение ответственности',
            description='Необходимо ограничить ответственность размером договора',
            suggested_text='Ответственность Поставщика ограничивается суммой настоящего договора.',
            legal_basis='ст. 15, 393 ГК РФ',
            related_risk_ids=['risk-1']
        )
    ]


class TestDisagreementProcessorAgent:
    """Test suite for Disagreement Processor Agent"""

    def test_agent_initialization(self, mock_db_session, mock_llm_gateway, mock_rag_system):
        """Test agent initialization"""
        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        assert agent.db_session == mock_db_session
        assert agent.llm_gateway == mock_llm_gateway
        assert agent.rag_system == mock_rag_system
        assert agent.name == "DisagreementProcessor"

    def test_execute_basic_flow(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system,
        sample_contract,
        sample_analysis,
        sample_risks,
        sample_recommendations
    ):
        """Test basic execution flow"""
        # Setup mocks
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_contract,  # First call - get contract
            sample_analysis   # Second call - get analysis
        ]
        mock_db_session.query.return_value.filter.return_value.all.side_effect = [
            sample_risks,           # First call - get risks
            sample_recommendations  # Second call - get recommendations
        ]

        # Mock LLM response
        mock_llm_gateway.chat.return_value = json.dumps({
            'issue_description': 'Отсутствует ограничение ответственности, что создает риск неограниченных убытков',
            'legal_basis': 'Согласно ст. 15 и 393 ГК РФ, ответственность может быть ограничена договором',
            'precedents': [
                {'case': 'Дело А40-123456/2020', 'court': 'АС Москвы', 'summary': 'Суд признал законным ограничение'}
            ],
            'risk_explanation': 'В случае нарушения поставщиком условий, убытки могут превысить стоимость договора',
            'alternative_formulation': 'Ответственность Поставщика по настоящему договору ограничивается суммой договора.',
            'alternative_reasoning': 'Данная формулировка соответствует судебной практике и защищает интересы Покупателя',
            'alternative_variants': [
                'Вариант 1: Ответственность ограничена суммой договора',
                'Вариант 2: Ответственность ограничена 50% суммы договора'
            ],
            'priority': 'critical',
            'tone': 'neutral_business'
        })

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        state = {
            'contract_id': 'test-contract-123',
            'analysis_id': 'analysis-123',
            'user_id': 'test-user'
        }

        result = agent.execute(state)

        # Assertions
        assert result.success is True
        assert result.agent_name == "DisagreementProcessor"
        assert 'disagreement_id' in result.data
        assert 'objections_generated' in result.data
        assert result.data['objections_generated'] > 0

        # Verify DB calls
        assert mock_db_session.add.called
        assert mock_db_session.commit.called

    def test_execute_missing_contract(self, mock_db_session, mock_llm_gateway, mock_rag_system):
        """Test execution with missing contract"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        state = {
            'contract_id': 'nonexistent-contract',
            'user_id': 'test-user'
        }

        result = agent.execute(state)

        assert result.success is False
        assert 'not found' in result.error.lower()

    def test_execute_no_risks(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system,
        sample_contract,
        sample_analysis
    ):
        """Test execution when no risks found"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_contract,
            sample_analysis
        ]
        mock_db_session.query.return_value.filter.return_value.all.return_value = []

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        state = {
            'contract_id': 'test-contract-123',
            'analysis_id': 'analysis-123',
            'user_id': 'test-user'
        }

        result = agent.execute(state)

        assert result.success is False
        assert 'no risks' in result.error.lower()

    def test_update_user_selection(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system
    ):
        """Test updating user selection of objections"""
        # Create mock disagreement with objections
        disagreement = Disagreement(
            id=1,
            contract_id='test-contract-123',
            status='draft'
        )

        objections = [
            DisagreementObjection(id=1, disagreement_id=1, user_selected=False),
            DisagreementObjection(id=2, disagreement_id=1, user_selected=False),
            DisagreementObjection(id=3, disagreement_id=1, user_selected=False)
        ]

        mock_db_session.query.return_value.filter.return_value.first.return_value = disagreement
        mock_db_session.query.return_value.filter.return_value.all.return_value = objections

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        selected_ids = [1, 3]
        priority_order = [3, 1]  # User wants objection 3 first

        result = agent.update_user_selection(
            disagreement_id=1,
            selected_objection_ids=selected_ids,
            priority_order=priority_order
        )

        assert result.success is True
        assert objections[0].user_selected is True
        assert objections[1].user_selected is False
        assert objections[2].user_selected is True
        assert disagreement.status == 'review'
        assert mock_db_session.commit.called

    def test_generate_xml_document(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system
    ):
        """Test XML document generation"""
        disagreement = Disagreement(
            id=1,
            contract_id='test-contract-123',
            selected_objections=[1, 2],
            priority_order=[2, 1]
        )

        objections = [
            DisagreementObjection(
                id=1,
                disagreement_id=1,
                issue_description='Проблема 1',
                legal_basis='Основание 1',
                alternative_formulation='Альтернатива 1',
                priority='critical'
            ),
            DisagreementObjection(
                id=2,
                disagreement_id=1,
                issue_description='Проблема 2',
                legal_basis='Основание 2',
                alternative_formulation='Альтернатива 2',
                priority='significant'
            )
        ]

        mock_db_session.query.return_value.filter.return_value.first.return_value = disagreement
        mock_db_session.query.return_value.filter.return_value.all.return_value = objections

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        result = agent.generate_xml_document(disagreement_id=1)

        assert result.success is True
        assert disagreement.xml_content is not None
        assert '<disagreement>' in disagreement.xml_content
        assert 'Проблема 1' in disagreement.xml_content
        assert 'Проблема 2' in disagreement.xml_content
        assert disagreement.xml_content is not None
        assert mock_db_session.commit.called

    def test_rag_integration(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system,
        sample_risks
    ):
        """Test RAG system integration"""
        contract = Contract(
            id='test-contract-123',
            contract_type='supply',
            parsed_content={'text': 'Contract text'}
        )

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        rag_context = agent._get_rag_context_for_objections(sample_risks, contract)

        # Verify RAG was called
        assert mock_rag_system.search.called
        assert 'context' in rag_context
        assert 'results' in rag_context

    def test_error_handling_llm_failure(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system,
        sample_contract,
        sample_analysis,
        sample_risks,
        sample_recommendations
    ):
        """Test error handling when LLM fails"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_contract,
            sample_analysis
        ]
        mock_db_session.query.return_value.filter.return_value.all.side_effect = [
            sample_risks,
            sample_recommendations
        ]

        # Mock LLM to raise exception
        mock_llm_gateway.chat.side_effect = Exception("LLM API Error")

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        state = {
            'contract_id': 'test-contract-123',
            'analysis_id': 'analysis-123',
            'user_id': 'test-user'
        }

        result = agent.execute(state)

        assert result.success is False
        assert 'error' in result.error.lower()
        assert mock_db_session.rollback.called

    def test_tone_variations(
        self,
        mock_db_session,
        mock_llm_gateway,
        mock_rag_system,
        sample_contract,
        sample_analysis,
        sample_risks,
        sample_recommendations
    ):
        """Test different tone settings"""
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            sample_contract,
            sample_analysis
        ]
        mock_db_session.query.return_value.filter.return_value.all.side_effect = [
            sample_risks,
            sample_recommendations
        ]

        mock_llm_gateway.chat.return_value = json.dumps({
            'issue_description': 'Test',
            'legal_basis': 'Test',
            'alternative_formulation': 'Test',
            'alternative_reasoning': 'Test',
            'priority': 'critical'
        })

        agent = DisagreementProcessorAgent(
            db_session=mock_db_session,
            llm_gateway=mock_llm_gateway,
            rag_system=mock_rag_system
        )

        # Test with different tone
        state = {
            'contract_id': 'test-contract-123',
            'analysis_id': 'analysis-123',
            'user_id': 'test-user',
            'tone': 'formal_respectful'
        }

        result = agent.execute(state)

        assert result.success is True
        # Verify tone was passed to LLM prompt
        call_args = mock_llm_gateway.chat.call_args
        messages = call_args[1]['messages']
        assert any('formal_respectful' in str(msg) for msg in messages)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
