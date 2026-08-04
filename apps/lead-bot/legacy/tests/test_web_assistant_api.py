from __future__ import annotations

from fastapi.testclient import TestClient

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


def test_chat_uses_shared_brain(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    async def fake_stream(history, funnel_context=None):
        assert history[-1] == {"role": "user", "message": "Какое направление основное?"}
        assert "автоматизацию юридической функции" in (funnel_context or "")
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
