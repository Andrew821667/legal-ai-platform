from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import user as user_handlers


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
