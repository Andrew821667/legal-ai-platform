from __future__ import annotations

import asyncio

from telegram.error import BadRequest, TimedOut

from news.admin_bot import NewsAdminBot, _safe_callback_answer


class _CallbackQuery:
    data = "sections"

    def __init__(self, errors: list[Exception] | None = None) -> None:
        self.errors = list(errors or [])
        self.answer_calls = 0
        self.edit_calls = 0
        self.message = None

    async def answer(self, *args, **kwargs) -> None:
        _ = args, kwargs
        self.answer_calls += 1
        if self.errors:
            raise self.errors.pop(0)

    async def edit_message_text(self, text: str, *, reply_markup=None) -> None:
        _ = text, reply_markup
        self.edit_calls += 1
        if self.errors:
            raise self.errors.pop(0)


def test_callback_timeout_does_not_block_handler() -> None:
    query = _CallbackQuery([TimedOut()])

    assert asyncio.run(_safe_callback_answer(query)) is False
    assert query.answer_calls == 1


def test_expired_callback_is_ignored() -> None:
    query = _CallbackQuery([BadRequest("Query is too old and response timeout expired")])

    assert asyncio.run(_safe_callback_answer(query)) is False


def test_message_edit_retries_after_timeout() -> None:
    bot = object.__new__(NewsAdminBot)
    query = _CallbackQuery([TimedOut()])

    result = asyncio.run(bot._safe_edit_message_text(query, "screen"))

    assert result is True
    assert query.edit_calls == 2


def test_message_edit_accepts_first_delivery_after_uncertain_timeout() -> None:
    bot = object.__new__(NewsAdminBot)
    query = _CallbackQuery([TimedOut(), BadRequest("Message is not modified")])

    result = asyncio.run(bot._safe_edit_message_text(query, "screen"))

    assert result is True
    assert query.edit_calls == 2


class _Bot:
    """Бот, у которого установка меню команд всегда завершается ошибкой."""

    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    async def set_my_commands(self, commands) -> None:
        _ = commands
        self.calls += 1
        raise self.error


class _App:
    def __init__(self, bot: _Bot) -> None:
        self.bot = bot
        self.tasks: list[str] = []

    def create_task(self, coro, name: str | None = None):
        coro.close()
        self.tasks.append(name or "")
        return None


def _run_post_init(error: Exception) -> _Bot:
    bot = _Bot(error)
    app = _App(bot)
    admin = NewsAdminBot.__new__(NewsAdminBot)
    asyncio.run(NewsAdminBot._post_init(admin, app))
    return bot


def test_set_my_commands_timeout_does_not_stop_startup() -> None:
    """Таймаут при установке меню не должен прерывать запуск модератора.

    Меню команд — украшение интерфейса. Раньше исключение здесь роняло бот
    в перезапуск, хотя опрос обновлений был возможен.
    """
    bot = _run_post_init(TimedOut())

    assert bot.calls == 1


def test_set_my_commands_network_error_does_not_stop_startup() -> None:
    """То же самое для обрыва сети, а не только таймаута."""
    from telegram.error import NetworkError

    bot = _run_post_init(NetworkError("connection failed"))

    assert bot.calls == 1
