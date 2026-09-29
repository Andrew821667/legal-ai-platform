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


def _query(data: str, edited: list[str]) -> SimpleNamespace:
    async def _answer(*args, **kwargs):
        return None

    async def _edit(text, **kwargs):
        edited.append(text)

    return SimpleNamespace(
        data=data, from_user=SimpleNamespace(id=42), message=None, answer=_answer, edit_message_text=_edit
    )


CODE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_yes_links_and_no_declines_through_the_core(monkeypatch) -> None:
    asked = []

    def _decide(**kwargs):
        asked.append(kwargs)
        return {"status": "linked" if kwargs["accept"] else "declined", "email": "anna@yandex.ru"}

    monkeypatch.setattr(client_link.core_api_bridge, "decide_link", _decide)
    edited: list[str] = []
    await client_link.handle_link_callback(SimpleNamespace(callback_query=_query(f"clink:ok:{CODE_ID}", edited)), None)
    await client_link.handle_link_callback(SimpleNamespace(callback_query=_query(f"clink:no:{CODE_ID}", edited)), None)

    assert asked == [
        {"code_id": CODE_ID, "telegram_user_id": 42, "accept": True},
        {"code_id": CODE_ID, "telegram_user_id": 42, "accept": False},
    ]
    assert "объединён с учётной записью сайта anna@yandex.ru" in edited[0]
    assert "ничего не объединено" in edited[1]


@pytest.mark.asyncio
async def test_undo_unlinks_and_junk_is_ignored(monkeypatch) -> None:
    unlinked = []
    monkeypatch.setattr(
        client_link.core_api_bridge,
        "owner_unlink",
        lambda **kwargs: unlinked.append(kwargs) or {"status": "unlinked", "email": "anna@yandex.ru"},
    )
    monkeypatch.setattr(client_link.core_api_bridge, "decide_link", lambda **kwargs: None)
    edited: list[str] = []
    await client_link.handle_link_callback(SimpleNamespace(callback_query=_query(f"clink:undo:{CODE_ID}", edited)), None)
    await client_link.handle_link_callback(SimpleNamespace(callback_query=_query("clink:ok:../../x", edited)), None)
    await client_link.handle_link_callback(SimpleNamespace(callback_query=_query(f"clink:ok:{CODE_ID}", edited)), None)

    assert unlinked == [{"account_id": CODE_ID, "telegram_user_id": 42}]
    assert "Отвязано" in edited[0]
    assert "устарел" in edited[1] and "устарел" in edited[2]
