"""Код для объединения Telegram с кабинетом на сайте: /link и /start link."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from handlers import client_link, start_payloads
from tests.test_core_api_bridge import _enable_bridge, _FakeResponse


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    async def _reply(message, text, **kwargs) -> None:
        sent.append({"text": text, **kwargs})

    monkeypatch.setattr(client_link.utils, "safe_reply_html", _reply)
    return sent


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=42, username="anna", first_name="Анна")


@pytest.mark.asyncio
async def test_start_link_sends_one_time_code_with_warning(monkeypatch, replies) -> None:
    asked = {}

    def _issue(**kwargs):
        asked.update(kwargs)
        return {"linked": False, "code": "K7M4-X9PQ", "ttl_minutes": 10}

    monkeypatch.setattr(client_link.core_api_bridge, "issue_link_code", _issue)
    context = SimpleNamespace(user_data={start_payloads.PENDING_START_PAYLOAD_KEY: "link"})

    handled = await start_payloads.process_pending_start_payload(
        message=object(), context=context, user_data={"id": 1}, user=_user()
    )

    assert handled is True
    assert asked == {"telegram_user_id": 42, "telegram_username": "anna"}
    text = replies[0]["text"]
    assert "<code>K7M4-X9PQ</code>" in text
    assert "10 минут" in text
    assert "Никому не сообщайте код" in text
    button = replies[0]["reply_markup"].inline_keyboard[0][0]
    assert button.url == client_link.config.CLIENT_CABINET_PROFILE_URL


def test_already_linked_telegram_gets_no_code() -> None:
    text = client_link.link_code_text({"linked": True, "email_masked": "a***@yandex.ru"})
    assert "уже объединён" in text and "a***@yandex.ru" in text
    assert "<code>" not in text


@pytest.mark.asyncio
async def test_core_unavailable_says_try_later(monkeypatch, replies) -> None:
    monkeypatch.setattr(client_link.core_api_bridge, "issue_link_code", lambda **kwargs: None)
    await client_link.link_command(SimpleNamespace(message=object(), effective_user=_user()), None)
    assert "не получилось выдать код" in replies[0]["text"]
    assert replies[0]["reply_markup"] is None


def test_bridge_asks_core_for_a_code(monkeypatch) -> None:
    import core_api_bridge as bridge_module

    _enable_bridge(monkeypatch, bridge_module)
    captured = {}

    def _fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"linked": False, "code": "ABCD-EFGH", "ttl_minutes": 10})

    monkeypatch.setattr(bridge_module.urllib.request, "urlopen", _fake_urlopen)
    result = bridge_module.CoreApiBridge().issue_link_code(telegram_user_id=42, telegram_username=None)

    assert result["code"] == "ABCD-EFGH"
    assert captured["url"] == "http://core-api:8000/api/v1/client-auth/telegram-link-codes"
    assert captured["body"] == {"telegram_user_id": 42, "telegram_username": None}
