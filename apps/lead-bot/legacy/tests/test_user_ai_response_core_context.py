"""Контекст ядра должен доходить до модели: build_core_context_block кладётся
перед стадийным funnel_context, который уходит в generate_response_stream."""
import asyncio
from types import SimpleNamespace

import pytest

from handlers import user_ai_response


@pytest.mark.asyncio
async def test_core_context_is_prepended_to_funnel_context(monkeypatch):
    monkeypatch.setattr(user_ai_response.config, "STREAMING_PREVIEW", False)
    monkeypatch.setattr(
        user_ai_response.platform_context,
        "build_core_context_block",
        lambda telegram_id: f"# Собеседник уже известен платформе\nNDA подписан ({telegram_id}).",
    )

    captured = {}

    async def _fake_stream(conversation_history, funnel_context=None):
        captured["funnel_context"] = funnel_context
        yield "Привет"

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "generate_response_stream", _fake_stream)

    async def _send_action(**kwargs):
        return None

    original_message = SimpleNamespace(chat=SimpleNamespace(send_action=_send_action))
    user_data = {"telegram_id": 275782221, "first_name": "Алёна"}

    full_response, sent_message = await user_ai_response._stream_response_text(
        original_message=original_message,
        user_data=user_data,
        user_first_name="Алёна",
        conversation_history=[],
        response_stage="discover",
        cta_variant="A",
        cta_shown=False,
    )

    assert full_response == "Привет"
    assert captured["funnel_context"].startswith("# Собеседник уже известен платформе")
    assert "NDA подписан (275782221)" in captured["funnel_context"]
    # Стадийная инструкция по-прежнему на месте, за блоком контекста.
    assert "Текущий этап: discover." in captured["funnel_context"]


@pytest.mark.asyncio
async def test_no_core_context_leaves_funnel_context_unchanged(monkeypatch):
    monkeypatch.setattr(user_ai_response.config, "STREAMING_PREVIEW", False)
    monkeypatch.setattr(user_ai_response.platform_context, "build_core_context_block", lambda telegram_id: "")

    captured = {}

    async def _fake_stream(conversation_history, funnel_context=None):
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
