from __future__ import annotations

from fastapi.testclient import TestClient

import intent_router
import web_assistant_api


client = TestClient(web_assistant_api.app)


def test_health_is_public() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "website-assistant"}


def test_chat_requires_internal_key(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    response = client.post(
        "/chat",
        json={"session_id": "session_123", "messages": [{"role": "user", "message": "Привет"}]},
    )

    assert response.status_code == 401


async def _fake_classify_default(*, conversation_history, has_core_context):
    return intent_router.IntentResult(intent="sales_conversation", confidence=0.0, context_override=None)


def test_chat_uses_shared_brain(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)

    async def fake_stream(history, funnel_context=None):
        assert history[-1] == {"role": "user", "message": "Какое направление основное?"}
        ctx = (funnel_context or "").lower()
        assert "автоматизацию юридической функции" in ctx
        assert "юридическая и инженерная практики" in ctx
        assert "основное совместное направление" in ctx
        yield "Основное направление — "
        yield "автоматизация юридической функции."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [{"role": "user", "message": "Какое направление основное?"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["reply"].endswith("автоматизация юридической функции.")


def test_chat_rejects_non_user_final_message(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [{"role": "assistant", "message": "Чем помочь?"}],
        },
    )

    assert response.status_code == 422


def test_chat_accepts_long_assistant_context(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)

    async def fake_stream(history, funnel_context=None):
        assert len(history[0]["message"]) == 2000
        yield "Продолжаем диалог."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [
                {"role": "assistant", "message": "А" * 2000},
                {"role": "user", "message": "Продолжим"},
            ],
        },
    )

    assert response.status_code == 200


def test_chat_uses_intent_override_when_present(monkeypatch) -> None:
    """Если intent_router распознал конкретное намерение (не sales_conversation
    по умолчанию) — на сайте должен использоваться его override, а не WEB_CONTEXT,
    так же, как в Telegram."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    async def fake_classify(*, conversation_history, has_core_context):
        return intent_router.IntentResult(
            intent="dev_task",
            confidence=0.9,
            context_override="# Задача на разработку\nОсобый контекст для dev_task.",
        )

    monkeypatch.setattr(web_assistant_api.intent_router, "classify", fake_classify)

    async def fake_stream(history, funnel_context=None):
        assert funnel_context == "# Задача на разработку\nОсобый контекст для dev_task."
        yield "Окей, разберём задачу."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [{"role": "user", "message": "Нужен бот для CRM"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Окей, разберём задачу."


def test_chat_never_passes_core_context_to_intent_router(monkeypatch) -> None:
    """У сайта нет способа опознать посетителя — has_core_context всегда False,
    иначе intent_router мог бы отдать continuing_own_matter без реальных данных."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    captured = {}

    async def fake_classify(*, conversation_history, has_core_context):
        captured["has_core_context"] = has_core_context
        return intent_router.IntentResult(intent="sales_conversation", confidence=0.0, context_override=None)

    monkeypatch.setattr(web_assistant_api.intent_router, "classify", fake_classify)

    async def fake_stream(history, funnel_context=None):
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={"session_id": "session_123", "messages": [{"role": "user", "message": "Привет"}]},
    )

    assert captured["has_core_context"] is False


def test_chat_rejects_long_user_message(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [{"role": "user", "message": "А" * 1601}],
        },
    )

    assert response.status_code == 422
