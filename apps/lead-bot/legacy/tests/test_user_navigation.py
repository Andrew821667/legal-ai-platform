from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import user as user_handlers
from handlers import user_routing


@pytest.mark.anyio
async def test_workspace_button_bypasses_forced_welcome(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, bool] = {"menu": False, "welcome": False}

    async def _fake_menu_command(update, context) -> None:
        called["menu"] = True

    async def _unexpected_welcome(*args, **kwargs) -> None:
        called["welcome"] = True

    monkeypatch.setattr(user_handlers, "menu_command", _fake_menu_command)
    monkeypatch.setattr(user_handlers.utils, "safe_reply_html", _unexpected_welcome)
    monkeypatch.setattr(
        user_handlers.database.db,
        "get_user_by_telegram_id",
        lambda telegram_id: {"id": 1, "telegram_id": telegram_id, "username": "user"},
    )
    monkeypatch.setattr(user_handlers.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(user_handlers.database.db, "get_user_consent_state", lambda user_id: {})
    monkeypatch.setattr(user_handlers.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(user_handlers.database.db, "get_conversation_history", lambda user_id, limit=1: [])

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=42,
            username="user",
            first_name="Андрей",
            last_name=None,
        ),
        effective_message=SimpleNamespace(text="🧭 Рабочий стол"),
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(user_data={})

    await user_handlers.handle_message(update, context)

    assert called["menu"] is True
    assert called["welcome"] is False


@pytest.mark.anyio
async def test_first_touch_uses_single_workspace_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    async def _fake_reply_html(message, text, **kwargs) -> None:
        messages.append(text)

    monkeypatch.setattr(user_handlers.utils, "safe_reply_html", _fake_reply_html)
    monkeypatch.setattr(
        user_handlers.database.db,
        "get_user_by_telegram_id",
        lambda telegram_id: {"id": 1, "telegram_id": telegram_id, "username": "user"},
    )
    monkeypatch.setattr(user_handlers.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(user_handlers.database.db, "get_user_consent_state", lambda user_id: {})
    monkeypatch.setattr(user_handlers.database.db, "get_chat_mode", lambda chat_id: "bot")
    monkeypatch.setattr(user_handlers.database.db, "get_conversation_history", lambda user_id, limit=1: [])
    monkeypatch.setattr(user_handlers.database.db, "get_user_offer_profile", lambda user_id: None)
    monkeypatch.setattr(user_handlers.database.db, "create_or_update_user", lambda **kwargs: 1)
    monkeypatch.setattr(user_handlers.database.db, "set_chat_mode", lambda chat_id, mode: None)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=42,
            username="user",
            first_name="Андрей",
            last_name=None,
        ),
        effective_message=SimpleNamespace(text="Привет"),
        effective_chat=SimpleNamespace(id=42),
    )
    context = SimpleNamespace(user_data={})

    await user_handlers.handle_message(update, context)

    assert len(messages) == 1
    assert "Здравствуйте, Андрей." in messages[0]
    assert "С чего удобно начать" in messages[0]


@pytest.mark.anyio
async def test_first_substantive_message_is_not_swallowed_by_entry_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"workspace": False}

    async def _unexpected_workspace(*args, **kwargs) -> None:
        called["workspace"] = True

    monkeypatch.setattr(user_routing, "send_workspace_entry", _unexpected_workspace)

    handled = await user_routing.maybe_handle_initial_entry(
        original_message=SimpleNamespace(),
        message_text="Нужно автоматизировать согласование договоров и входящих запросов",
        user=SimpleNamespace(id=42, first_name="Андрей"),
        user_data={"id": 1},
        lead=None,
        history_exists=False,
    )

    assert handled is False
    assert called["workspace"] is False
