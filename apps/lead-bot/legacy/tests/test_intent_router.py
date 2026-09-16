"""Интент-роутер: тихий откат к продажной воронке при любом сбое/сомнении,
своя инструкция для явно классифицированных не-продажных сообщений."""
import pytest

import intent_router


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_sales_conversation(monkeypatch):
    async def _boom(history):
        raise RuntimeError("llm down")

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _boom)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "sales_conversation"
    assert result.context_override is None


@pytest.mark.asyncio
async def test_none_response_falls_back_to_sales_conversation(monkeypatch):
    async def _none(history):
        return None

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _none)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "sales_conversation" and result.context_override is None


@pytest.mark.asyncio
async def test_unknown_intent_value_falls_back(monkeypatch):
    async def _weird(history):
        return {"intent": "buy_a_yacht", "confidence": 0.99}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _weird)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "sales_conversation" and result.context_override is None


@pytest.mark.asyncio
async def test_low_confidence_falls_back_even_with_known_intent(monkeypatch):
    async def _unsure(history):
        return {"intent": "platform_question", "confidence": 0.2}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _unsure)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "sales_conversation"
    assert result.context_override is None


@pytest.mark.asyncio
async def test_confident_platform_question_gets_override(monkeypatch):
    async def _confident(history):
        return {"intent": "platform_question", "confidence": 0.8}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _confident)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "platform_question"
    assert result.context_override is not None
    assert "платформ" in result.context_override.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["new_legal_task", "dev_task", "browsing"])
async def test_each_non_sales_intent_gets_its_own_override(monkeypatch, intent):
    async def _fake(history):
        return {"intent": intent, "confidence": 0.9}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _fake)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == intent
    assert result.context_override is not None


@pytest.mark.asyncio
async def test_continuing_own_matter_without_core_context_falls_back(monkeypatch):
    """Модель решила «продолжение дела», но своих данных о человеке нет —
    не рискуем подставить неверный кадр."""

    async def _fake(history):
        return {"intent": "continuing_own_matter", "confidence": 0.95}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _fake)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.intent == "continuing_own_matter"
    assert result.context_override is None


@pytest.mark.asyncio
async def test_continuing_own_matter_with_core_context_gets_override(monkeypatch):
    async def _fake(history):
        return {"intent": "continuing_own_matter", "confidence": 0.95}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _fake)

    result = await intent_router.classify(conversation_history=[], has_core_context=True)

    assert result.intent == "continuing_own_matter"
    assert result.context_override is not None
    assert "дискавери-вопросов" in result.context_override


@pytest.mark.asyncio
async def test_sales_conversation_intent_gives_no_override(monkeypatch):
    async def _fake(history):
        return {"intent": "sales_conversation", "confidence": 0.99}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _fake)

    result = await intent_router.classify(conversation_history=[], has_core_context=True)

    assert result.intent == "sales_conversation"
    assert result.context_override is None


@pytest.mark.asyncio
async def test_non_numeric_confidence_treated_as_zero(monkeypatch):
    async def _fake(history):
        return {"intent": "platform_question", "confidence": "very sure"}

    monkeypatch.setattr(intent_router.ai_brain.ai_brain, "classify_intent_async", _fake)

    result = await intent_router.classify(conversation_history=[], has_core_context=False)

    assert result.confidence == 0.0
    assert result.intent == "sales_conversation"
