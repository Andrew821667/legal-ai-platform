from __future__ import annotations

from types import SimpleNamespace

import pytest
from handlers import user_commands


def _update() -> SimpleNamespace:
    return SimpleNamespace(
        effective_user=SimpleNamespace(
            id=42,
            username="user",
            first_name="Андрей",
            last_name=None,
        ),
        effective_chat=SimpleNamespace(id=42),
        message=SimpleNamespace(),
    )


@pytest.mark.anyio
async def test_start_command_requires_consent_before_persisting_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[tuple[str, object | None]] = []

    async def _fake_reply_html(message, text, **kwargs) -> None:
        messages.append((text, kwargs.get("reply_markup")))

    def _unexpected_create(**kwargs):
        raise AssertionError("user must not be persisted before consent")

    monkeypatch.setattr(user_commands.utils, "safe_reply_html", _fake_reply_html)
    monkeypatch.setattr(
        user_commands.database.db,
        "get_local_user_by_telegram_id",
        lambda telegram_id: None,
    )
    monkeypatch.setattr(user_commands.database.db, "create_or_update_user", _unexpected_create)

    await user_commands.start_command(_update(), SimpleNamespace(user_data={}, args=[]))

    assert len(messages) == 1
    assert "обработ" in messages[0][0].lower()
    assert messages[0][1] is not None


@pytest.mark.anyio
async def test_start_command_sends_one_entry_for_consented_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages: list[tuple[str, object | None]] = []

    async def _fake_reply_html(message, text, **kwargs) -> None:
        messages.append((text, kwargs.get("reply_markup")))

    async def _fake_process_pending_start_payload(**kwargs) -> None:
        return None

    monkeypatch.setattr(user_commands.utils, "safe_reply_html", _fake_reply_html)
    monkeypatch.setattr(
        user_commands,
        "process_pending_start_payload",
        _fake_process_pending_start_payload,
    )
    monkeypatch.setattr(
        user_commands.database.db,
        "get_local_user_by_telegram_id",
        lambda telegram_id: {"id": 1, "telegram_id": telegram_id},
    )
    monkeypatch.setattr(
        user_commands.database.db,
        "get_user_consent_state",
        lambda user_id: {"consent_given": True},
    )
    monkeypatch.setattr(user_commands.database.db, "create_or_update_user", lambda **kwargs: 1)
    monkeypatch.setattr(user_commands.database.db, "set_chat_mode", lambda chat_id, mode: None)
    monkeypatch.setattr(user_commands.database.db, "get_local_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(user_commands.database.db, "get_user_offer_profile", lambda user_id: None)
    monkeypatch.setattr(
        user_commands.database.db,
        "get_local_user_by_id",
        lambda user_id: {"id": user_id, "telegram_id": 42},
    )

    await user_commands.start_command(_update(), SimpleNamespace(user_data={}, args=[]))

    assert len(messages) == 1
    assert "С чего удобно начать" in messages[0][0]
    assert "Проверить договор" in messages[0][0]
    assert messages[0][1] is not None
