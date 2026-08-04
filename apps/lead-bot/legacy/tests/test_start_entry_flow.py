from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import user_commands


@pytest.mark.anyio
async def test_start_command_sends_one_entry_message(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[tuple[str, object | None]] = []

    async def _fake_reply_html(message, text, **kwargs) -> None:
        messages.append((text, kwargs.get("reply_markup")))

    async def _fake_process_pending_start_payload(**kwargs) -> None:
        return None

    monkeypatch.setattr(user_commands.utils, "safe_reply_html", _fake_reply_html)
    monkeypatch.setattr(user_commands, "process_pending_start_payload", _fake_process_pending_start_payload)
    monkeypatch.setattr(user_commands.database.db, "create_or_update_user", lambda **kwargs: 1)
    monkeypatch.setattr(user_commands.database.db, "set_chat_mode", lambda chat_id, mode: None)
    monkeypatch.setattr(user_commands.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(user_commands.database.db, "get_user_offer_profile", lambda user_id: None)
    monkeypatch.setattr(user_commands.database.db, "get_user_consent_state", lambda user_id: {"consent_given": True})
    monkeypatch.setattr(user_commands.database.db, "get_user_by_id", lambda user_id: {"id": user_id, "telegram_id": 42})

    update = SimpleNamespace(
        effective_user=SimpleNamespace(
            id=42,
            username="user",
            first_name="Андрей",
            last_name=None,
        ),
        effective_chat=SimpleNamespace(id=42),
        message=SimpleNamespace(),
    )
    context = SimpleNamespace(user_data={}, args=[])

    await user_commands.start_command(update, context)

    assert len(messages) == 1
    assert "это единая платформа" in messages[0][0]
    assert "С чего удобно начать" in messages[0][0]
    assert "Проверить договор" in messages[0][0]
    assert "Юридическая практика" in messages[0][0]
    assert "Инженерная практика" in messages[0][0]
    assert messages[0][1] is not None


@pytest.mark.anyio
async def test_start_command_sends_only_consent_to_new_user(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[tuple[str, object | None]] = []

    async def _fake_reply_html(message, text, **kwargs) -> None:
        messages.append((text, kwargs.get("reply_markup")))

    monkeypatch.setattr(user_commands.utils, "safe_reply_html", _fake_reply_html)
    monkeypatch.setattr(user_commands.database.db, "create_or_update_user", lambda **kwargs: 1)
    monkeypatch.setattr(user_commands.database.db, "set_chat_mode", lambda chat_id, mode: None)
    monkeypatch.setattr(user_commands.database.db, "get_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(user_commands.database.db, "get_user_offer_profile", lambda user_id: None)
    monkeypatch.setattr(user_commands.database.db, "get_user_consent_state", lambda user_id: {})
    monkeypatch.setattr(user_commands.database.db, "get_user_by_id", lambda user_id: {"id": user_id, "telegram_id": 43})

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=43, username="new_user", first_name="Иван", last_name=None),
        effective_chat=SimpleNamespace(id=43),
        message=SimpleNamespace(),
    )
    context = SimpleNamespace(user_data={}, args=[])

    await user_commands.start_command(update, context)

    assert len(messages) == 1
    assert "соглас" in messages[0][0].lower()
    assert messages[0][1] is not None
