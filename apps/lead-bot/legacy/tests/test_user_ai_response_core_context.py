"""Контекст ядра должен доходить до модели: build_core_context_block кладётся
перед funnel_context (стадийным или интент-переопределением), который уходит
в generate_response_stream."""
from types import SimpleNamespace

import pytest

import intent_router
from handlers import user_ai_response


def _stub_sales_intent(monkeypatch):
    """По умолчанию классификатор отключён — воронка ведёт себя как раньше."""

    async def _fake_classify(*, conversation_history, has_core_context):
        return intent_router.IntentResult(intent="sales_conversation", confidence=0.0, context_override=None)

    monkeypatch.setattr(user_ai_response.intent_router, "classify", _fake_classify)


@pytest.mark.asyncio
async def test_core_context_is_prepended_to_funnel_context(monkeypatch):
    monkeypatch.setattr(user_ai_response.config, "STREAMING_PREVIEW", False)
    monkeypatch.setattr(
        user_ai_response.platform_context,
        "build_core_context_block",
        lambda telegram_id: f"# Собеседник уже известен платформе\nNDA подписан ({telegram_id}).",
    )
    _stub_sales_intent(monkeypatch)

    captured = {}

    async def _fake_stream(conversation_history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context
        yield "Привет"

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "generate_response_stream", _fake_stream)

    async def _send_action(**kwargs):
        return None

    original_message = SimpleNamespace(chat=SimpleNamespace(send_action=_send_action))
    user_data = {"telegram_id": 275782221, "first_name": "Алёна"}

    full_response, sent_message, intent_result = await user_ai_response._stream_response_text(
        original_message=original_message,
        user_data=user_data,
        user_first_name="Алёна",
        conversation_history=[],
        response_stage="discover",
        cta_variant="A",
        cta_shown=False,
    )

    assert full_response == "Привет"
    assert intent_result.intent == "sales_conversation"
    assert captured["funnel_context"].startswith("# Собеседник уже известен платформе")
    assert "NDA подписан (275782221)" in captured["funnel_context"]
    # Стадийная инструкция по-прежнему на месте, за блоком контекста.
    assert "Текущий этап: discover." in captured["funnel_context"]


@pytest.mark.asyncio
async def test_no_core_context_leaves_funnel_context_unchanged(monkeypatch):
    monkeypatch.setattr(user_ai_response.config, "STREAMING_PREVIEW", False)
    monkeypatch.setattr(user_ai_response.platform_context, "build_core_context_block", lambda telegram_id: "")
    _stub_sales_intent(monkeypatch)

    captured = {}

    async def _fake_stream(conversation_history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context
        yield "Привет"

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "generate_response_stream", _fake_stream)

    async def _send_action(**kwargs):
        return None

    original_message = SimpleNamespace(chat=SimpleNamespace(send_action=_send_action))
    user_data = {"telegram_id": 1, "first_name": "Клиент"}

    await user_ai_response._stream_response_text(
        original_message=original_message,
        user_data=user_data,
        user_first_name="Клиент",
        conversation_history=[],
        response_stage="discover",
        cta_variant="A",
        cta_shown=False,
    )

    assert captured["funnel_context"].startswith("Текущий этап: discover.")


@pytest.mark.asyncio
async def test_intent_override_replaces_stage_context(monkeypatch):
    """Не продажный интент — стадийная воронка не подмешивается вообще."""
    monkeypatch.setattr(user_ai_response.config, "STREAMING_PREVIEW", False)
    monkeypatch.setattr(user_ai_response.platform_context, "build_core_context_block", lambda telegram_id: "")

    async def _fake_classify(*, conversation_history, has_core_context):
        return intent_router.IntentResult(
            intent="platform_question", confidence=0.9, context_override="# Вопрос о платформе\nОтветь прямо."
        )

    monkeypatch.setattr(user_ai_response.intent_router, "classify", _fake_classify)

    captured = {}

    async def _fake_stream(conversation_history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context
        yield "Мы делаем..."

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "generate_response_stream", _fake_stream)

    async def _send_action(**kwargs):
        return None

    original_message = SimpleNamespace(chat=SimpleNamespace(send_action=_send_action))
    user_data = {"telegram_id": 5, "first_name": "Гость"}

    full_response, sent_message, intent_result = await user_ai_response._stream_response_text(
        original_message=original_message,
        user_data=user_data,
        user_first_name="Гость",
        conversation_history=[],
        response_stage="discover",
        cta_variant="A",
        cta_shown=False,
    )

    assert intent_result.intent == "platform_question"
    assert captured["funnel_context"].startswith("# Вопрос о платформе")
    assert "Текущий этап" not in captured["funnel_context"]
