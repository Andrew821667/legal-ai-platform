from __future__ import annotations

import asyncio
from types import SimpleNamespace

from lead_bot import run


class _Response:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class _Message:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[tuple[str, dict[str, object]]] = []

    async def reply_text(self, text: str, **kwargs) -> None:
        self.replies.append((text, kwargs))


class _Query:
    def __init__(self, message: _Message, data: str = run._CONSENT_ACCEPT_CALLBACK) -> None:
        self.id = "callback-1"
        self.data = data
        self.message = message
        self.answers = 0
        self.edits: list[tuple[str, dict[str, object]]] = []

    async def answer(self) -> None:
        self.answers += 1

    async def edit_message_text(self, text: str, **kwargs) -> None:
        self.edits.append((text, kwargs))


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=123456789,
        username="test_user",
        first_name="Тест",
        last_name="Пользователь",
        full_name="Тест Пользователь",
    )


def test_start_with_consent_sends_one_combined_welcome(monkeypatch) -> None:
    message = _Message()
    update = SimpleNamespace(effective_user=_user(), effective_message=message, message=message)
    monkeypatch.setattr(
        run.core_client,
        "get_users",
        lambda params: _Response([{"consent_given": True, "consent_revoked": False}]),
    )
    monkeypatch.setattr(run.core_client, "post_event", lambda payload, **kwargs: _Response({}))

    asyncio.run(run.start_handler(update, SimpleNamespace()))

    assert len(message.replies) == 1
    assert "Это ассистент платформы" in message.replies[0][0]
    assert "Напишите задачу одним сообщением" in message.replies[0][0]


def test_start_without_consent_sends_only_consent_gate(monkeypatch) -> None:
    message = _Message()
    update = SimpleNamespace(effective_user=_user(), effective_message=message, message=message)
    monkeypatch.setattr(run.core_client, "get_users", lambda params: _Response([]))

    asyncio.run(run.start_handler(update, SimpleNamespace()))

    assert len(message.replies) == 1
    assert "согласие на обработку персональных данных" in message.replies[0][0]


def test_consent_callback_replaces_gate_with_welcome_without_extra_messages(monkeypatch) -> None:
    message = _Message()
    query = _Query(message)
    update = SimpleNamespace(
        effective_user=_user(),
        effective_message=message,
        message=None,
        callback_query=query,
    )
    monkeypatch.setattr(
        run.core_client,
        "post_user",
        lambda payload, **kwargs: _Response({"id": "user-1"}),
    )
    monkeypatch.setattr(run.core_client, "post_event", lambda payload, **kwargs: _Response({}))

    asyncio.run(run.consent_callback_handler(update, SimpleNamespace()))

    assert query.answers == 1
    assert len(query.edits) == 1
    assert "Напишите задачу одним сообщением" in query.edits[0][0]
    assert message.replies == []
