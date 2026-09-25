"""Кнопка «Спросить юриста» под постом в канале.

Закрепляется: ведёт в бота-ассистента с номером поста; стоит под последним
сообщением поста; у альбома без текстового хвоста её нет (sendMediaGroup
кнопок не принимает); выключается настройкой.
"""

from __future__ import annotations

import json

import pytest
from news import publish
from news.settings import settings

POST_ID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    sent: list[tuple[str, dict]] = []

    def fake(method: str, payload: dict, retries: int = 3) -> dict:
        sent.append((method, payload))
        return {"result": {"message_id": len(sent)}} if method != "sendMediaGroup" else {"result": [{"message_id": 1}]}

    monkeypatch.setattr(publish, "_telegram_request", fake)
    monkeypatch.setattr(settings, "telegram_channel_id", "@channel")
    monkeypatch.setattr(settings, "news_helper_bot_username", "@legal_ai_helper_new_bot")
    monkeypatch.setattr(settings, "news_channel_ask_button_enabled", True)
    return sent


def _markup_calls(sent):
    return [index for index, (_, payload) in enumerate(sent) if "reply_markup" in payload]


def test_button_leads_to_helper_bot_with_post_id(calls) -> None:
    markup = json.loads(publish._ask_lawyer_markup(POST_ID))
    button = markup["inline_keyboard"][0][0]
    assert button["url"] == f"https://t.me/legal_ai_helper_new_bot?start=chq_{POST_ID}"
    assert button["text"]
    assert publish._ask_lawyer_markup("not-a-uuid") is None


def test_button_is_under_the_last_part_of_a_long_post(calls) -> None:
    text = ("Абзац про новость. " * 400).strip()
    publish._send_to_telegram(text, None, reply_markup=publish._ask_lawyer_markup(POST_ID))
    assert len(calls) > 1
    assert _markup_calls(calls) == [len(calls) - 1]


def test_single_photo_post_gets_the_button(calls) -> None:
    publish._send_to_telegram("Короткий пост", ["tgphoto://abc"], reply_markup=publish._ask_lawyer_markup(POST_ID))
    assert [m for m, _ in calls] == ["sendPhoto"]
    assert _markup_calls(calls) == [0]


def test_album_button_goes_to_text_tail_or_nowhere(calls) -> None:
    markup = publish._ask_lawyer_markup(POST_ID)
    publish._send_to_telegram("Короткий пост", ["tgphoto://a", "tgphoto://b"], reply_markup=markup)
    assert [m for m, _ in calls] == ["sendMediaGroup"]
    assert _markup_calls(calls) == []

    calls.clear()
    publish._send_to_telegram("Длинный пост. " * 200, ["tgphoto://a", "tgphoto://b"], reply_markup=markup)
    assert calls[0][0] == "sendMediaGroup"
    assert _markup_calls(calls) == [len(calls) - 1]


def test_can_be_turned_off(calls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "news_channel_ask_button_enabled", False)
    assert publish._ask_lawyer_markup(POST_ID) is None
