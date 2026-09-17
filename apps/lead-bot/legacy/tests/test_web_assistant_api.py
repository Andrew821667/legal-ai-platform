from __future__ import annotations

from fastapi.testclient import TestClient

import intent_router
import web_assistant_api


client = TestClient(web_assistant_api.app)


def setup_function(_fn) -> None:
    # Session store — модульный dict, общий между тестами; чистим, чтобы
    # verified-статус из одного теста не просачивался в другой.
    web_assistant_api._VERIFIED_SESSIONS.clear()


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

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
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

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
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

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
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


def test_chat_has_no_core_context_for_unverified_session(monkeypatch) -> None:
    """Пока посетитель не подтвердился через identify_returning_client,
    has_core_context остаётся False — так же, как было до этой фичи."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    captured = {}

    async def fake_classify(*, conversation_history, has_core_context):
        captured["has_core_context"] = has_core_context
        return intent_router.IntentResult(intent="sales_conversation", confidence=0.0, context_override=None)

    monkeypatch.setattr(web_assistant_api.intent_router, "classify", fake_classify)

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={"session_id": "session_never_verified", "messages": [{"role": "user", "message": "Привет"}]},
    )

    assert captured["has_core_context"] is False


def test_chat_always_offers_identify_and_case_details_tools(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)
    captured = {}

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        captured["tool_names"] = {tool["function"]["name"] for tool in (tools or [])}
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={"session_id": "session_tools_check", "messages": [{"role": "user", "message": "Привет"}]},
    )

    assert captured["tool_names"] == {"identify_returning_client", "get_full_case_details"}


def test_chat_identify_returning_client_persists_across_requests(monkeypatch) -> None:
    """Сквозной сценарий: первое сообщение подтверждает клиента через
    identify_returning_client — второе сообщение той же browser-сессии
    (тот же session_id) должно увидеть has_core_context=True без повторной
    проверки, как и полагается «второй развилке»."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)
    monkeypatch.setattr(
        web_assistant_api.assistant_tools.core_api_bridge.core_api_bridge,
        "verify_returning_client",
        lambda *, contact, agreement_number: 72001,
    )
    monkeypatch.setattr(
        web_assistant_api.platform_context.core_api_bridge,
        "enabled",
        True,
    )
    monkeypatch.setattr(
        web_assistant_api.platform_context.core_api_bridge,
        "client_portal_summary",
        lambda telegram_user_id: {"cases": [], "agreements": [], "acts": [], "nda": {"signed": True}},
    )

    async def fake_stream_first(history, funnel_context=None, tools=None, tool_executor=None):
        await tool_executor(
            "identify_returning_client", {"contact": "+79092330909", "agreement_number": "P-001"}
        )
        yield "Подтвердил вас — чем помочь?"

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream_first)
    first = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_returning_client",
            "messages": [{"role": "user", "message": "Я уже клиент, вот мой договор P-001, контакт +79092330909"}],
        },
    )
    assert first.status_code == 200
    assert web_assistant_api._get_verified_telegram_id("session_returning_client") == 72001

    captured = {}

    async def fake_stream_second(history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context
        yield "Вот детали вашего дела."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream_second)
    second = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_returning_client",
            "messages": [
                {"role": "user", "message": "Я уже клиент, вот мой договор P-001, контакт +79092330909"},
                {"role": "assistant", "message": "Подтвердил вас — чем помочь?"},
                {"role": "user", "message": "Что там с моим договором?"},
            ],
        },
    )

    assert second.status_code == 200
    assert "Собеседник уже известен платформе" in captured["funnel_context"]


def test_chat_verified_session_expires_after_ttl(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    web_assistant_api._remember_verified_session("session_stale", 72001)
    # Форсируем протухание записи без ожидания часа в реальном времени.
    telegram_id, _ = web_assistant_api._VERIFIED_SESSIONS["session_stale"]
    web_assistant_api._VERIFIED_SESSIONS["session_stale"] = (telegram_id, 0.0)

    assert web_assistant_api._get_verified_telegram_id("session_stale") is None
    assert "session_stale" not in web_assistant_api._VERIFIED_SESSIONS


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


def test_chat_rejects_non_positive_telegram_user_id(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")

    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_123",
            "messages": [{"role": "user", "message": "Привет"}],
            "telegram_user_id": 0,
        },
    )

    assert response.status_code == 422


def test_chat_signed_in_telegram_user_id_feeds_core_context(monkeypatch) -> None:
    """telegram_user_id в payload (кабинет уже проверил подпись Telegram
    Login) должен уйти в build_core_context_block напрямую — без
    identify_returning_client и без ожидания второго сообщения."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)
    captured = {}

    def fake_build_core_context_block(telegram_user_id):
        captured["telegram_user_id"] = telegram_user_id
        return "# Собеседник уже известен платформе\nЕсть договор."

    monkeypatch.setattr(web_assistant_api.platform_context, "build_core_context_block", fake_build_core_context_block)

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context
        yield "Вот статус вашего дела."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    response = client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_signed_in",
            "messages": [{"role": "user", "message": "Что с моим договором?"}],
            "telegram_user_id": 848510279,
        },
    )

    assert response.status_code == 200
    assert captured["telegram_user_id"] == 848510279
    assert "Собеседник уже известен платформе" in captured["funnel_context"]


def test_chat_signed_in_telegram_user_id_overrides_chat_session_verification(monkeypatch) -> None:
    """Приоритет payload.telegram_user_id над _VERIFIED_SESSIONS: даже если
    та же browser-сессия чата ранее подтвердила другой telegram_id внутри
    диалога, вход через /cabinet должен победить — это более сильное,
    только что полученное доверие."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)
    web_assistant_api._remember_verified_session("session_override", 111)
    captured = {}

    def fake_build_core_context_block(telegram_user_id):
        captured["telegram_user_id"] = telegram_user_id
        return ""

    monkeypatch.setattr(web_assistant_api.platform_context, "build_core_context_block", fake_build_core_context_block)

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_override",
            "messages": [{"role": "user", "message": "Привет"}],
            "telegram_user_id": 222,
        },
    )

    assert captured["telegram_user_id"] == 222


def test_chat_signed_in_context_forbids_identify_tool_and_new_client_hint(monkeypatch) -> None:
    """Текст промпта для залогиненного посетителя не должен содержать
    инструкцию про «САМ говорит, что уже наш клиент» (это правило для
    анонимного пути) и должен явно запрещать identify_returning_client."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)
    captured = {}

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        captured["funnel_context"] = funnel_context or ""
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_signed_in_context",
            "messages": [{"role": "user", "message": "Привет"}],
            "telegram_user_id": 848510279,
        },
    )

    ctx = captured["funnel_context"]
    assert "вошёл в личный кабинет сайта через Telegram" in ctx
    assert "не вызывай identify_returning_client" in ctx
    assert "САМ говорит, что уже наш клиент" not in ctx


def test_chat_signed_in_does_not_remember_chat_session_verification(monkeypatch) -> None:
    """Вход через /cabinet не должен просачиваться в _VERIFIED_SESSIONS —
    после logout (кука кабинета стёрта) анонимные сообщения того же
    browser-таба обязаны вернуться к обычному, неподтверждённому режиму."""
    monkeypatch.setenv("WEB_ASSISTANT_INTERNAL_KEY", "test-secret")
    monkeypatch.setattr(web_assistant_api.intent_router, "classify", _fake_classify_default)

    async def fake_stream(history, funnel_context=None, tools=None, tool_executor=None):
        yield "Ответ."

    monkeypatch.setattr(web_assistant_api.web_brain, "generate_response_stream", fake_stream)
    client.post(
        "/chat",
        headers={"X-Assistant-Key": "test-secret"},
        json={
            "session_id": "session_no_remember",
            "messages": [{"role": "user", "message": "Привет"}],
            "telegram_user_id": 848510279,
        },
    )

    assert web_assistant_api._get_verified_telegram_id("session_no_remember") is None
