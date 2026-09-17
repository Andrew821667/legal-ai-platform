"""Фоновое обновление памяти тем разговора — пункт 4 «умного ассистента».
Планируется независимо от обработки лида: применимо и там, где лид не
заводится (platform_question, browsing и т.п.)."""
import asyncio

import pytest

from handlers import user_ai_response


@pytest.mark.asyncio
async def test_schedule_topic_memory_update_stores_summary(monkeypatch):
    calls = []

    async def _fake_summarize(history):
        return "Интересовался ценами на проверку договоров."

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "summarize_topics_async", _fake_summarize)
    monkeypatch.setattr(
        user_ai_response.database.db,
        "update_topic_memory",
        lambda user_id, summary: calls.append((user_id, summary)),
    )

    user_ai_response._schedule_topic_memory_update(
        user_data={"id": 55, "telegram_id": 1}, conversation_history=[{"role": "user", "message": "Сколько стоит?"}]
    )
    await asyncio.sleep(0)  # даём фоновой задаче выполниться

    assert calls == [(55, "Интересовался ценами на проверку договоров.")]


@pytest.mark.asyncio
async def test_schedule_topic_memory_update_skips_write_when_no_summary(monkeypatch):
    calls = []

    async def _fake_summarize(history):
        return None

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "summarize_topics_async", _fake_summarize)
    monkeypatch.setattr(user_ai_response.database.db, "update_topic_memory", lambda user_id, summary: calls.append(1))

    user_ai_response._schedule_topic_memory_update(user_data={"id": 55}, conversation_history=[])
    await asyncio.sleep(0)

    assert calls == []


@pytest.mark.asyncio
async def test_schedule_topic_memory_update_swallows_llm_failure(monkeypatch):
    async def _boom(history):
        raise RuntimeError("llm down")

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "summarize_topics_async", _boom)

    user_ai_response._schedule_topic_memory_update(user_data={"id": 55}, conversation_history=[])
    await asyncio.sleep(0)  # не должно поднять исключение наружу


@pytest.mark.asyncio
async def test_schedule_topic_memory_update_swallows_db_failure(monkeypatch):
    async def _fake_summarize(history):
        return "Тема"

    def _boom_write(user_id, summary):
        raise ValueError("db error")

    monkeypatch.setattr(user_ai_response.ai_brain.ai_brain, "summarize_topics_async", _fake_summarize)
    monkeypatch.setattr(user_ai_response.database.db, "update_topic_memory", _boom_write)

    user_ai_response._schedule_topic_memory_update(user_data={"id": 55}, conversation_history=[])
    await asyncio.sleep(0)  # не должно поднять исключение наружу
