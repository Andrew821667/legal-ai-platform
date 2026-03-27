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
