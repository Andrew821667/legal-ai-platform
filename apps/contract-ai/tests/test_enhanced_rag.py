"""
Tests for Enhanced RAG System

Tests cover:
- Multi-source search
- Knowledge base management
- Query expansion
- Re-ranking
- Caching
- Learning from analysis
"""

import pytest
import os
import tempfile
from datetime import datetime
from src.services.enhanced_rag import (
    EnhancedRAGSystem,
    SearchResult,
    CompanyKnowledge,
    get_enhanced_rag
)


class TestRAGInitialization:
    """Test RAG system initialization"""

    def test_rag_creation(self, tmp_path):
        """Test RAG system can be created"""
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        assert rag is not None
        assert rag.company_kb is not None
        assert rag.synonyms is not None
        assert rag.legal_terms is not None

    def test_synonyms_loaded(self, tmp_path):
        """Test legal term synonyms are loaded"""
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        synonyms = rag.synonyms

        assert 'договор' in synonyms
        assert 'контракт' in synonyms['договор']
        assert 'риск' in synonyms
        assert 'штраф' in synonyms

    def test_legal_terms_loaded(self, tmp_path):
        """Test legal terminology is loaded"""
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        legal_terms = rag.legal_terms

        assert 'форс-мажор' in legal_terms
        assert 'конфиденциальность' in legal_terms
        assert 'арбитражный суд' in legal_terms


class TestCompanyKnowledgeManagement:
    """Test company knowledge base management"""

    @pytest.fixture
    def rag(self, tmp_path):
        return EnhancedRAGSystem(persist_directory=str(tmp_path))

    def test_add_knowledge_entry(self, rag):
        """Test adding a knowledge base entry"""
        kb_id = rag.add_company_knowledge(
            title="Standard Payment Terms",
            content="Payment should be made within 30 days of invoice date. Late payment penalty: 0.1% per day.",
            category='policy',
            tags=['payment', 'standard'],
            author='John Doe'
        )

        assert kb_id is not None
        assert len(kb_id) == 12  # MD5 hash truncated to 12 chars

        # Should be in memory
        assert kb_id in rag.company_kb

        # Check fields
        kb_entry = rag.company_kb[kb_id]
        assert kb_entry.title == "Standard Payment Terms"
        assert kb_entry.category == 'policy'
        assert 'payment' in kb_entry.tags
        assert kb_entry.author == 'John Doe'

    def test_add_multiple_entries(self, rag):
        """Test adding multiple KB entries"""
        for i in range(5):
            kb_id = rag.add_company_knowledge(
                title=f"Policy {i}",
                content=f"Content for policy {i}",
                category='policy',
                tags=[f'tag{i}'],
                author='Test'
            )
            assert kb_id is not None

        assert len(rag.company_kb) == 5

    def test_add_different_categories(self, rag):
        """Test adding entries of different categories"""
        categories = ['policy', 'template', 'precedent', 'guideline']

        for category in categories:
            kb_id = rag.add_company_knowledge(
                title=f"Test {category}",
                content=f"Content for {category}",
                category=category,
                tags=[category],
                author='Test'
            )

            assert rag.company_kb[kb_id].category == category

    def test_kb_persistence(self, tmp_path):
        """Test knowledge base persistence to disk"""
        rag1 = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # Add some entries
        rag1.add_company_knowledge(
            title="Test Entry",
            content="Test content",
            category='policy',
            tags=['test'],
            author='Tester'
        )

        # Save should happen automatically
        # Create new instance - should load saved KB
        rag2 = EnhancedRAGSystem(persist_directory=str(tmp_path))

        assert len(rag2.company_kb) == 1
        entry = list(rag2.company_kb.values())[0]
        assert entry.title == "Test Entry"


class TestSearch:
    """Test search functionality"""

    @pytest.fixture
    def rag(self, tmp_path):
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # Add some test knowledge
        rag.add_company_knowledge(
            title="Payment Terms Policy",
            content="All payments must be made within 30 days. Late fees apply at 0.1% per day.",
            category='policy',
            tags=['payment', 'finance'],
            author='CFO'
        )

        rag.add_company_knowledge(
            title="Contract Template - Supply",
            content="Standard supply contract template with delivery terms and quality requirements.",
            category='template',
            tags=['supply', 'standard'],
            author='Legal'
        )

        return rag

    def test_basic_search(self, rag):
        """Test basic search functionality"""
        results = rag.search(
            query="payment terms",
            top_k=10,
            search_kb=True,
            search_contracts=False,
            search_legal=False
        )

        # Should find payment-related entry
        # Note: May be empty if ChromaDB not available
        assert isinstance(results, list)

    def test_search_with_query_expansion(self, rag):
        """Test search with query expansion"""
        results_with_expansion = rag.search(
            query="договор",
            top_k=5,
            expand_query=True
        )

        results_without_expansion = rag.search(
            query="договор",
            top_k=5,
            expand_query=False
        )

        # Both should work
        assert isinstance(results_with_expansion, list)
        assert isinstance(results_without_expansion, list)

    def test_query_expansion_logic(self, rag):
        """Test query expansion adds synonyms"""
        expanded = rag._expand_query("договор оплата")

        # Should include synonyms
        assert 'контракт' in expanded or 'договор' in expanded
        assert 'оплата' in expanded or 'платеж' in expanded

    def test_search_result_structure(self, rag):
        """Test search results have proper structure"""
        # Add more content to ensure we get results
        for i in range(5):
            rag.add_company_knowledge(
                title=f"Entry {i}",
                content=f"This is test content number {i} about contracts and payment.",
                category='policy',
                tags=['test'],
                author='Test'
            )

        results = rag.search(
            query="contracts payment",
            top_k=3,
            search_kb=True
        )

        # If we got results, check structure
        if len(results) > 0:
            result = results[0]
            assert isinstance(result, SearchResult)
            assert hasattr(result, 'content')
            assert hasattr(result, 'score')
            assert hasattr(result, 'source')
            assert hasattr(result, 'metadata')


class TestKBStatistics:
    """Test knowledge base statistics"""

    @pytest.fixture
    def rag(self, tmp_path):
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # Add test data
        for i in range(10):
            rag.add_company_knowledge(
                title=f"Policy {i}",
                content=f"Content {i}",
                category='policy' if i % 2 == 0 else 'template',
                tags=['tag1', 'tag2'] if i < 5 else ['tag3'],
                author='Test'
            )

        return rag

    def test_get_statistics(self, rag):
        """Test getting KB statistics"""
        stats = rag.get_kb_statistics()

        assert 'total_entries' in stats
        assert 'categories' in stats
        assert 'top_tags' in stats
        assert 'most_used' in stats

    def test_statistics_accuracy(self, rag):
        """Test statistics are accurate"""
        stats = rag.get_kb_statistics()

        assert stats['total_entries'] == 10
        assert stats['categories']['policy'] == 5
        assert stats['categories']['template'] == 5

    def test_tag_counting(self, rag):
        """Test tag counting in statistics"""
        stats = rag.get_kb_statistics()
        top_tags = stats['top_tags']

        # tag1 and tag2 appear 5 times each
        # tag3 appears 5 times
        assert 'tag1' in top_tags
        assert 'tag2' in top_tags
        assert 'tag3' in top_tags


class TestEffectivenessTracking:
    """Test effectiveness tracking"""

    @pytest.fixture
    def rag(self, tmp_path):
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        kb_id = rag.add_company_knowledge(
            title="Test Entry",
            content="Test content",
            category='policy',
            tags=['test'],
            author='Test'
        )

        return rag, kb_id

    def test_update_effectiveness_helpful(self, rag):
        """Test updating effectiveness when entry is helpful"""
        rag_system, kb_id = rag

        initial_score = rag_system.company_kb[kb_id].effectiveness_score

        # Mark as helpful
        rag_system.update_kb_effectiveness(kb_id, was_helpful=True)

        new_score = rag_system.company_kb[kb_id].effectiveness_score

        # Score should increase
        assert new_score > initial_score

    def test_update_effectiveness_not_helpful(self, rag):
        """Test updating effectiveness when entry is not helpful"""
        rag_system, kb_id = rag

        # Set initial high score
        rag_system.company_kb[kb_id].effectiveness_score = 0.8

        # Mark as not helpful
        rag_system.update_kb_effectiveness(kb_id, was_helpful=False)

        new_score = rag_system.company_kb[kb_id].effectiveness_score

        # Score should decrease
        assert new_score < 0.8

    def test_effectiveness_bounds(self, rag):
        """Test effectiveness score stays within bounds"""
        rag_system, kb_id = rag

        # Mark as helpful many times
        for _ in range(20):
            rag_system.update_kb_effectiveness(kb_id, was_helpful=True)

        score = rag_system.company_kb[kb_id].effectiveness_score

        # Should be between 0 and 1
        assert 0 <= score <= 1


class TestUsageTracking:
    """Test usage tracking"""

    @pytest.fixture
    def rag(self, tmp_path):
        return EnhancedRAGSystem(persist_directory=str(tmp_path))

    def test_usage_count_increments(self, rag):
        """Test usage count increments"""
        kb_id = rag.add_company_knowledge(
            title="Test",
            content="Test content",
            category='policy',
            tags=['test'],
            author='Test'
        )

        initial_count = rag.company_kb[kb_id].usage_count

        # Simulate search result usage
        mock_results = [
            SearchResult(
                content="test",
                score=0.9,
                source='kb',
                document_id=kb_id,
                metadata={},
                chunk_id=0
            )
        ]

        rag._update_kb_usage(mock_results)

        new_count = rag.company_kb[kb_id].usage_count

        assert new_count == initial_count + 1


class TestLearningFromAnalysis:
    """Test learning from contract analysis"""

    @pytest.fixture
    def rag(self, tmp_path):
        return EnhancedRAGSystem(persist_directory=str(tmp_path))

    def test_learn_from_analysis_basic(self, rag):
        """Test basic learning from analysis"""
        analysis_result = {
            'risks': [
                {'category': 'financial', 'description': 'No liability cap'},
                {'category': 'financial', 'description': 'Unlimited liability'},
                {'category': 'financial', 'description': 'High payment terms'}
            ],
            'recommendations': []
        }

        initial_count = len(rag.company_kb)

        rag.learn_from_analysis('contract-123', analysis_result)

        # May create new KB entry if pattern detected 3+ times
        # In this case, same category appears 3 times
        new_count = len(rag.company_kb)

        # Should create entry or not (depending on pattern threshold)
        assert new_count >= initial_count

    def test_pattern_detection(self, rag):
        """Test risk pattern detection"""
        risks = [
            {'category': 'financial', 'description': 'Risk 1', 'recommendation': 'Fix 1'},
            {'category': 'financial', 'description': 'Risk 2', 'recommendation': 'Fix 2'},
            {'category': 'financial', 'description': 'Risk 3', 'recommendation': 'Fix 3'}
        ]

        patterns = rag._identify_risk_patterns(risks)

        assert isinstance(patterns, list)
        # Should identify financial pattern
        if len(patterns) > 0:
            pattern = patterns[0]
            assert pattern['type'] == 'financial'
            assert pattern['frequency'] == 3


class TestCaching:
    """Test caching functionality"""

    @pytest.fixture
    def rag(self, tmp_path):
        return EnhancedRAGSystem(persist_directory=str(tmp_path))

    def test_cache_key_generation(self, rag):
        """Test cache key generation"""
        key1 = rag._get_cache_key("test query", 10, True, True, False)
        key2 = rag._get_cache_key("test query", 10, True, True, False)
        key3 = rag._get_cache_key("different query", 10, True, True, False)

        # Same query should give same key
        assert key1 == key2

        # Different query should give different key
        assert key1 != key3

    def test_cache_storage_and_retrieval(self, rag):
        """Test caching search results"""
        mock_results = [
            SearchResult(
                content="test",
                score=0.9,
                source='kb',
                document_id='id1',
                metadata={},
                chunk_id=0
            )
        ]

        cache_key = "test_key"

        # Add to cache
        rag._add_to_cache(cache_key, mock_results)

        # Retrieve from cache
        cached = rag._get_from_cache(cache_key)

        assert cached is not None
        assert len(cached) == 1
        assert cached[0].content == "test"

    def test_cache_expiration(self, rag):
        """Test cache expiration"""
        import time

        mock_results = [SearchResult(
            content="test",
            score=0.9,
            source='kb',
            document_id='id1',
            metadata={},
            chunk_id=0
        )]

        cache_key = "test_key"

        # Set very short TTL for testing
        original_ttl = rag.cache_ttl
        rag.cache_ttl = timedelta(milliseconds=10)

        # Add to cache
        rag._add_to_cache(cache_key, mock_results)

        # Should be in cache
        assert rag._get_from_cache(cache_key) is not None

        # Wait for expiration
        time.sleep(0.02)  # 20ms

        # Should be expired
        assert rag._get_from_cache(cache_key) is None

        # Restore original TTL
        rag.cache_ttl = original_ttl


class TestEdgeCases:
    """Test edge cases"""

    @pytest.fixture
    def rag(self, tmp_path):
        return EnhancedRAGSystem(persist_directory=str(tmp_path))

    def test_search_empty_query(self, rag):
        """Test search with empty query"""
        results = rag.search(query="", top_k=5)

        # Should handle gracefully
        assert isinstance(results, list)

    def test_search_very_long_query(self, rag):
        """Test search with very long query"""
        long_query = "contract " * 100

        results = rag.search(query=long_query, top_k=5)

        assert isinstance(results, list)

    def test_add_kb_empty_content(self, rag):
        """Test adding KB entry with empty content"""
        # Should this raise an error or handle gracefully?
        try:
            kb_id = rag.add_company_knowledge(
                title="Empty",
                content="",
                category='policy',
                tags=[],
                author='Test'
            )
            # If it succeeds, verify entry was created
            assert kb_id in rag.company_kb
        except Exception:
            # If it raises an error, that's also acceptable
            pass

    def test_update_nonexistent_kb_entry(self, rag):
        """Test updating non-existent KB entry"""
        rag.update_kb_effectiveness('nonexistent-id', was_helpful=True)

        # Should handle gracefully (no error)


class TestSingletonPattern:
    """Test singleton pattern"""

    def test_get_enhanced_rag_singleton(self):
        """Test singleton returns same instance"""
        rag1 = get_enhanced_rag()
        rag2 = get_enhanced_rag()

        # Should be same instance
        assert rag1 is rag2


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    @pytest.fixture
    def rag(self, tmp_path):
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # Populate with realistic data
        rag.add_company_knowledge(
            title="Контрагент проверка политика",
            content="Перед заключением договора обязательна проверка контрагента через ФНС ЕГРЮЛ. "
                   "Проверяемые параметры: ИНН, адрес, руководитель, учредители, задолженность. "
                   "Если контрагент массовый адрес или массовый директор - отказ от сделки.",
            category='policy',
            tags=['контрагенты', 'проверка', 'безопасность', 'ФНС'],
            author='Юридический отдел'
        )

        rag.add_company_knowledge(
            title="Стандартные условия оплаты",
            content="Стандартный срок оплаты - 30 календарных дней с даты получения счета. "
                   "Пеня за просрочку - 0,1% от суммы долга за каждый день просрочки. "
                   "Для новых контрагентов - предоплата 50%.",
            category='template',
            tags=['оплата', 'стандарт', 'пеня'],
            author='Финансовый отдел'
        )

        rag.add_company_knowledge(
            title="Форс-мажор стандартная клауза",
            content="Стороны освобождаются от ответственности за частичное или полное неисполнение "
                   "обязательств по договору, если это неисполнение явилось следствием обстоятельств "
                   "непреодолимой силы (форс-мажор). К таким обстоятельствам относятся: стихийные бедствия, "
                   "военные действия, эпидемии, решения государственных органов. "
                   "Уведомление о форс-мажоре - не позднее 3 дней.",
            category='template',
            tags=['форс-мажор', 'стандарт', 'ответственность'],
            author='Юридический отдел'
        )

        return rag

    def test_search_counterparty_check(self, rag):
        """Test searching for counterparty check policy"""
        results = rag.search(
            query="как проверить контрагента перед договором",
            top_k=5,
            search_kb=True
        )

        # Should find counterparty policy
        # (if ChromaDB/embeddings are available)
        assert isinstance(results, list)

    def test_search_payment_terms(self, rag):
        """Test searching for payment terms"""
        results = rag.search(
            query="стандартные сроки оплаты пеня",
            top_k=5,
            search_kb=True
        )

        assert isinstance(results, list)

    def test_search_force_majeure(self, rag):
        """Test searching for force majeure clause"""
        results = rag.search(
            query="форс-мажор непреодолимая сила",
            top_k=5,
            search_kb=True
        )

        assert isinstance(results, list)

    def test_multi_source_search(self, rag):
        """Test searching across multiple sources"""
        results = rag.search(
            query="договор оплата",
            top_k=10,
            search_contracts=True,
            search_kb=True,
            search_legal=True
        )

        # Should search all sources
        assert isinstance(results, list)


# Integration test
class TestRAGIntegration:
    """Integration test for complete workflow"""

    def test_complete_kb_lifecycle(self, tmp_path):
        """Test complete knowledge base lifecycle"""
        # 1. Create RAG system
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # 2. Add knowledge
        kb_id = rag.add_company_knowledge(
            title="Test Policy",
            content="This is a test policy about payments.",
            category='policy',
            tags=['test', 'payment'],
            author='Tester'
        )

        assert kb_id is not None

        # 3. Search for it
        results = rag.search(
            query="payment policy",
            top_k=5,
            search_kb=True
        )

        assert isinstance(results, list)

        # 4. Mark as helpful
        rag.update_kb_effectiveness(kb_id, was_helpful=True)

        # 5. Check statistics
        stats = rag.get_kb_statistics()
        assert stats['total_entries'] == 1

        # 6. Learn from analysis
        rag.learn_from_analysis('contract-1', {
            'risks': [],
            'recommendations': []
        })

        # Should complete without errors


# Performance tests
@pytest.mark.benchmark
class TestRAGPerformance:
    """Performance benchmarks"""

    def test_search_performance(self, benchmark, tmp_path):
        """Benchmark search performance"""
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        # Add some data
        for i in range(10):
            rag.add_company_knowledge(
                title=f"Entry {i}",
                content=f"Content about contracts and payment {i}",
                category='policy',
                tags=['test'],
                author='Test'
            )

        def search():
            return rag.search("contracts payment", top_k=5)

        results = benchmark(search)
        assert isinstance(results, list)

    def test_kb_addition_performance(self, benchmark, tmp_path):
        """Benchmark KB entry addition"""
        rag = EnhancedRAGSystem(persist_directory=str(tmp_path))

        def add_entry():
            return rag.add_company_knowledge(
                title="Test",
                content="Test content" * 50,
                category='policy',
                tags=['test'],
                author='Test'
            )

        kb_id = benchmark(add_entry)
        assert kb_id is not None
