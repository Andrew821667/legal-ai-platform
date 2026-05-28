from __future__ import annotations

from types import SimpleNamespace

import pytest

import bot as bot_module
from handlers import business


def test_is_business_update_accepts_edited_business_message() -> None:
    update = SimpleNamespace(
        business_message=None,
        edited_business_message=SimpleNamespace(text="edited"),
        message=None,
    )

    assert bot_module._is_business_update(update) is True
    assert bot_module._extract_incoming_message(update).text == "edited"


def test_is_business_update_accepts_message_with_business_connection() -> None:
    update = SimpleNamespace(
        business_message=None,
        edited_business_message=None,
        message=SimpleNamespace(text="hello", business_connection_id="bc-123"),
    )

    assert bot_module._is_business_update(update) is True
    assert bot_module._extract_incoming_message(update).text == "hello"


@pytest.mark.asyncio
async def test_handle_business_message_accepts_message_with_business_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: False)

    async def _fake_send_message(**kwargs):
        sent.append(kwargs)

    update = SimpleNamespace(
        business_message=None,
        edited_business_message=None,
        message=SimpleNamespace(
            text="Привет",
            from_user=SimpleNamespace(id=42),
            business_connection_id="bc-123",
            chat=SimpleNamespace(id=5001),
        ),
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})

    await business.handle_business_message(update, context)

    assert sent == []


@pytest.mark.asyncio
async def test_forced_business_welcome_does_not_duplicate_greeting_welcome(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: True)
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 101)
    monkeypatch.setattr(business.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(business.database.db, "get_conversation_history", lambda user_id, limit=1: [])
    monkeypatch.setattr(business.database.db, "clear_conversation_history", lambda user_id: None)
    monkeypatch.setattr(business.database.db, "reset_user_funnel_state", lambda user_id: None)
    monkeypatch.setattr(business, "_should_process_after_forced_welcome", lambda text: True)
    monkeypatch.setattr(
        business.database.db,
        "get_lead_by_user_id",
        lambda user_id: (_ for _ in ()).throw(SystemExit("stop-after-welcome")),
    )

    async def _fake_send_message(**kwargs):
        sent.append(kwargs)

    update = SimpleNamespace(
        business_message=SimpleNamespace(
            text="Привет! Нужна помощь с автоматизацией договоров",
            from_user=SimpleNamespace(id=42, username="u42", first_name="Андрей", last_name=None),
            business_connection_id="bc-123",
            chat=SimpleNamespace(id=5001),
        ),
        edited_business_message=None,
        message=None,
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})

    with pytest.raises(SystemExit, match="stop-after-welcome"):
        await business.handle_business_message(update, context)

    assert len(sent) == 1
    assert "AI Verdict" in sent[0]["text"]


@pytest.mark.asyncio
async def test_business_social_message_is_not_answered(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []

    monkeypatch.setattr(business, "_is_business_processing_allowed", lambda message: True)
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 101)
    monkeypatch.setattr(business.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(
        business,
        "_should_force_business_welcome",
        lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit("should-not-force-welcome")),
    )

    async def _fake_send_message(**kwargs):
        sent.append(kwargs)

    update = SimpleNamespace(
        business_message=SimpleNamespace(
            text="Андрей, поздравляем тебя с Днем Рождения! Желаем большого счастья и здоровья.",
            from_user=SimpleNamespace(id=42, username="u42", first_name="Мария", last_name=None),
            business_connection_id="bc-123",
            chat=SimpleNamespace(id=5001),
        ),
        edited_business_message=None,
        message=None,
        update_id=777,
    )
    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})

    await business.handle_business_message(update, context)

    assert sent == []
