from __future__ import annotations

import asyncio

import pytest
from telegram.error import BadRequest

from news.admin_bot import NewsAdminBot, _STATE_DRAFT_EDIT, _STATE_PENDING_EDIT
from news.settings import settings


class _Message:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.replies.append(text)


class _Query:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = _Message()

    async def answer(self, text: str | None = None, show_alert: bool = False) -> None:
        return None


class _Update:
    def __init__(self, query: _Query) -> None:
        self.callback_query = query


class _Response:
    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self) -> None:
        self.patches: list[tuple[str, dict]] = []

    def patch_post(self, post_id: str, payload: dict) -> _Response:
        self.patches.append((post_id, payload))
        return _Response()


class _Bot:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict] = []

    async def edit_message_text(self, **kwargs) -> None:  # noqa: ANN003
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


class _Context:
    def __init__(self, bot: _Bot) -> None:
        self.bot = bot
        self.user_data: dict[str, object] = {}


def _make_bot(monkeypatch, post: dict) -> tuple[NewsAdminBot, _Client, list[str]]:  # noqa: ANN001
    bot = NewsAdminBot()
    client = _Client()
    shown: list[str] = []

    async def _ensure_admin(_update) -> bool:  # noqa: ANN001
        return True

    async def _safe_edit(_query, text: str, reply_markup=None) -> None:  # noqa: ANN001
        shown.append(text)

    monkeypatch.setattr(bot, "client", client)
    monkeypatch.setattr(bot, "_ensure_admin", _ensure_admin)
    monkeypatch.setattr(bot, "_sync_ui_hints_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "_safe_edit_message_text", _safe_edit)
    monkeypatch.setattr(bot, "_get_post", lambda _post_id: post)
    monkeypatch.setattr(bot, "_invalidate_post_caches", lambda: None)
    monkeypatch.setattr(bot, "_post_card_text", lambda _post: "карточка")
    monkeypatch.setattr(bot, "_post_card_keyboard", lambda *args: None)
    monkeypatch.setattr(settings, "telegram_channel_id", "-100123")
    return bot, client, shown


def _with_draft(context: _Context, text: str = "Новый текст поста.") -> None:
    context.user_data[_STATE_DRAFT_EDIT] = {"post_id": "p1", "text": text, "status": "posted", "offset": 0}
    context.user_data[_STATE_PENDING_EDIT] = {"post_id": "p1"}


def test_saving_edit_of_published_post_updates_channel_then_database(monkeypatch) -> None:
    post = {"id": "p1", "status": "posted", "telegram_message_id": 806, "text": "Старый текст."}
    bot, client, shown = _make_bot(monkeypatch, post)
    telegram = _Bot()
    context = _Context(telegram)
    _with_draft(context)

    asyncio.run(bot.cb_posts(_Update(_Query("ps:p1:posted:0")), context))

    assert len(telegram.calls) == 1
    call = telegram.calls[0]
    assert call["chat_id"] == "-100123"
    assert call["message_id"] == 806
    assert call["parse_mode"] == "HTML"
    assert "Новый текст поста." in call["text"]
    assert client.patches and client.patches[0][0] == "p1"
    assert shown and shown[0].startswith("Пост обновлён в канале.")
    assert _STATE_DRAFT_EDIT not in context.user_data


def test_failed_channel_edit_leaves_database_and_draft_untouched(monkeypatch) -> None:
    """Если Telegram отказал, в базе должен остаться текст, который реально
    висит в канале, а черновик — сохраниться для повторной попытки."""
    post = {"id": "p1", "status": "posted", "telegram_message_id": 806, "text": "Старый текст."}
    bot, client, _shown = _make_bot(monkeypatch, post)
    telegram = _Bot(error=BadRequest("Message can't be edited"))
    context = _Context(telegram)
    _with_draft(context)
    query = _Query("ps:p1:posted:0")

    asyncio.run(bot.cb_posts(_Update(query), context))

    assert client.patches == []
    assert _STATE_DRAFT_EDIT in context.user_data
    assert any("Пост в канале не изменён" in reply for reply in query.message.replies)


def test_unchanged_text_is_not_an_error(monkeypatch) -> None:
    """Telegram отвечает «message is not modified», если текст совпал с
    опубликованным, — для пользователя это успех, а не ошибка."""
    post = {"id": "p1", "status": "posted", "telegram_message_id": 806, "text": "Тот же текст."}
    bot, client, shown = _make_bot(monkeypatch, post)
    telegram = _Bot(error=BadRequest("Message is not modified: specified new message content is the same"))
    context = _Context(telegram)
    _with_draft(context, text="Тот же текст.")

    asyncio.run(bot.cb_posts(_Update(_Query("ps:p1:posted:0")), context))

    assert client.patches
    assert shown and shown[0].startswith("Пост обновлён в канале.")


def test_saving_edit_of_unpublished_post_does_not_touch_channel(monkeypatch) -> None:
    post = {"id": "p1", "status": "review", "telegram_message_id": None, "text": "Черновик."}
    bot, client, shown = _make_bot(monkeypatch, post)
    telegram = _Bot()
    context = _Context(telegram)
    _with_draft(context)

    asyncio.run(bot.cb_posts(_Update(_Query("ps:p1:review:0")), context))

    assert telegram.calls == []
    assert client.patches
    assert shown and shown[0].startswith("Изменения сохранены.")


@pytest.mark.parametrize(
    ("post", "fragment"),
    [
        ({"status": "posted", "telegram_message_id": None}, "нет id сообщения"),
        ({"status": "posted", "telegram_message_id": 5, "media_urls": ["tgphoto://x"]}, "с медиа"),
    ],
)
def test_published_edit_refuses_what_cannot_be_edited_honestly(monkeypatch, post: dict, fragment: str) -> None:
    bot = NewsAdminBot()
    monkeypatch.setattr(settings, "telegram_channel_id", "-100123")
    context = _Context(_Bot())

    with pytest.raises(RuntimeError, match=fragment):
        asyncio.run(bot._edit_published_message(context, post, "Текст."))

    assert context.bot.calls == []
