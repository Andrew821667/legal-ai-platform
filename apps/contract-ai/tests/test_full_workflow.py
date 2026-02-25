# -*- coding: utf-8 -*-
"""
Comprehensive test of the complete workflow with new features:
1. Two-level analysis system (gpt-4o-mini + gpt-4o)
2. Batching (5 clauses per request)
3. LLM caching in database
4. Token tracking and cost calculation
5. Deep analysis method
"""
import sys
import os

# Set up paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import with absolute path
from src.services.llm_gateway import LLMGateway
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.models import get_db
from src.models.database import LLMCache
from config.settings import settings
from loguru import logger
import json

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_llm_gateway_with_cache():
    """Test 1: LLMGateway with caching"""
    logger.info("=" * 60)
    logger.info("TEST 1: LLMGateway with Caching")
    logger.info("=" * 60)

    db = next(get_db())
    llm = LLMGateway(model=settings.llm_quick_model)

    # First call - should hit API
    logger.info("First call (should hit API)...")
    response1 = llm.call(
        prompt="Какие риски в пункте 'Оплата производится в течение 30 дней'?",
        system_prompt="Ты юридический эксперт",
        response_format="text",
        use_cache=True,
        db_session=db
    )
    logger.info(f"Response: {response1[:100]}...")

    # Second call - should hit cache
    logger.info("\nSecond call (should hit CACHE)...")
    llm2 = LLMGateway(model=settings.llm_quick_model)
    response2 = llm2.call(
        prompt="Какие риски в пункте 'Оплата производится в течение 30 дней'?",
        system_prompt="Ты юридический эксперт",
        response_format="text",
        use_cache=True,
        db_session=db
    )
    logger.info(f"Response: {response2[:100]}...")

    # Check cache stats
    cache_count = db.query(LLMCache).count()
    logger.info(f"\n✓ Cache entries in DB: {cache_count}")

    # Token stats
    stats = llm.get_token_stats()
    logger.info(f"✓ Token stats: {stats['total_tokens']} tokens, ${stats['total_cost_usd']:.6f}")

    return True

def test_batching():
    """Test 2: Batch analysis of clauses"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Batch Analysis")
    logger.info("=" * 60)

    db = next(get_db())
    agent = ContractAnalyzerAgent(db_session=db)

    # Create mock clauses
    mock_clauses = [
        {"id": f"clause_{i}", "number": i, "title": f"Пункт {i}", "text": f"Тестовый текст пункта {i} договора", "xpath": f"/clause[{i}]"}
        for i in range(1, 8)  # 7 clauses = 2 batches (5+2)
    ]

    logger.info(f"Analyzing {len(mock_clauses)} clauses with batch_size={settings.llm_batch_size}...")
    logger.info(f"Expected: {(len(mock_clauses) + settings.llm_batch_size - 1) // settings.llm_batch_size} API calls")

    results = agent._analyze_clauses_batch(
        clauses=mock_clauses,
        rag_context={"context": "Тестовый контекст"},
        batch_size=settings.llm_batch_size
    )

    logger.info(f"✓ Analyzed {len(results)} clauses")
    logger.info(f"✓ Token stats: {agent.llm.get_token_stats()}")

    return len(results) == len(mock_clauses)

def test_deep_analysis():
    """Test 3: Deep analysis with gpt-4o"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Deep Analysis (Level 2 - gpt-4o)")
    logger.info("=" * 60)

    db = next(get_db())
    agent = ContractAnalyzerAgent(db_session=db)

    # Create mock XML with clauses
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<contract>
    <section id="payment">
        <clause id="clause_1" number="3.1">
            <title>Порядок оплаты</title>
            <text>Оплата производится в течение 30 календарных дней с момента получения акта выполненных работ. При просрочке оплаты начисляется пеня в размере 0.1% от суммы долга за каждый день просрочки.</text>
        </clause>
    </section>
</contract>"""

    logger.info(f"Running deep analysis on clause_1 with {settings.llm_deep_model}...")

    try:
        deep_results = agent.analyze_deep(
            clause_ids=["clause_1"],
            contract_id="test_contract_123",
            xml_content=mock_xml,
            rag_context={"context": "ГК РФ ст. 314, 330"}
        )

        logger.info(f"✓ Deep analysis completed for {len(deep_results)} clauses")

        if deep_results:
            result = deep_results[0]
            logger.info(f"  - Clause: {result.get('clause_number')}")
            logger.info(f"  - Risk score: {result.get('overall_risk_score', 'N/A')}/100")
            logger.info(f"  - Model used: {result.get('model_used')}")
            logger.info(f"  - Has legal analysis: {bool(result.get('deep_legal_analysis'))}")
            logger.info(f"  - Risks with precedents: {len(result.get('risks_with_precedents', []))}")
            logger.info(f"  - Alternative formulations: {len(result.get('alternative_formulations', []))}")

        return len(deep_results) > 0
    except Exception as e:
        logger.error(f"✗ Deep analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_token_tracking():
    """Test 4: Token tracking and cost calculation"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Token Tracking & Cost Calculation")
    logger.info("=" * 60)

    llm = LLMGateway(model="gpt-4o-mini")

    # Make a few calls
    for i in range(3):
        llm.call(
            prompt=f"Тестовый запрос {i+1}",
            system_prompt="Отвечай кратко",
            response_format="text"
        )

    stats = llm.get_token_stats()

    logger.info(f"✓ Input tokens: {stats['input_tokens']:,}")
    logger.info(f"✓ Output tokens: {stats['output_tokens']:,}")
    logger.info(f"✓ Total tokens: {stats['total_tokens']:,}")
    logger.info(f"✓ Input cost: ${stats['input_cost_usd']:.6f}")
    logger.info(f"✓ Output cost: ${stats['output_cost_usd']:.6f}")
    logger.info(f"✓ Total cost: ${stats['total_cost_usd']:.6f}")
    logger.info(f"✓ Model: {stats['model']}")

    return stats['total_tokens'] > 0

def main():
    """Run all tests"""
    logger.info("\n" + "🚀" * 30)
    logger.info("FULL WORKFLOW TEST - Contract AI System")
    logger.info("🚀" * 30)

    logger.info(f"\nConfiguration:")
    logger.info(f"  - Test mode: {settings.llm_test_mode}")
    logger.info(f"  - Quick model: {settings.llm_quick_model}")
    logger.info(f"  - Deep model: {settings.llm_deep_model}")
    logger.info(f"  - Batch size: {settings.llm_batch_size}")
    logger.info(f"  - Test max tokens: {settings.llm_test_max_tokens}")
    logger.info(f"  - Test max clauses: {settings.llm_test_max_clauses}")

    results = {}

    # Run tests
    try:
        results['cache'] = test_llm_gateway_with_cache()
    except Exception as e:
        logger.error(f"Cache test failed: {e}")
        results['cache'] = False

    try:
        results['batching'] = test_batching()
    except Exception as e:
        logger.error(f"Batching test failed: {e}")
        results['batching'] = False

    try:
        results['deep_analysis'] = test_deep_analysis()
    except Exception as e:
        logger.error(f"Deep analysis test failed: {e}")
        results['deep_analysis'] = False

    try:
        results['token_tracking'] = test_token_tracking()
    except Exception as e:
        logger.error(f"Token tracking test failed: {e}")
        results['token_tracking'] = False

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status} - {test_name}")

    total = len(results)
    passed = sum(results.values())
    logger.info(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")

    if passed == total:
        logger.info("\n🎉 All tests PASSED! Workflow is ready.")
        return 0
    else:
        logger.warning(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
        return 1

if __name__ == "__main__":
    exit(main())
