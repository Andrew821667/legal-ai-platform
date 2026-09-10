"""Реальные ошибки должны доезжать до Sentry, а сетевой шум — нет.

error_handler уже отличает рутинные обрывы polling от настоящих ошибок (та же
классификация защищает логи от шума). Здесь проверяется, что Sentry получает
ровно то, что проходит этот фильтр, — не больше и не меньше.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from telegram.error import Conflict, NetworkError

import handlers.common as common


@pytest.mark.anyio
async def test_real_error_reaches_sentry(monkeypatch) -> None:
    captured = []
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda err: captured.append(err))

    error = ValueError("что-то пошло не так")
    context = SimpleNamespace(error=error)
    update = SimpleNamespace(effective_message=None, callback_query=None)

    await common.error_handler(update, context)

    assert captured == [error]


@pytest.mark.anyio
async def test_transient_polling_noise_does_not_reach_sentry(monkeypatch) -> None:
    """Update отсутствует и ошибка сетевая — это ровно тот шум, ради которого
    существует _is_transient_polling_error."""
    captured = []
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda err: captured.append(err))

    context = SimpleNamespace(error=NetworkError("временный обрыв"))
    await common.error_handler(None, context)

    assert captured == []


@pytest.mark.anyio
async def test_conflict_does_not_reach_sentry(monkeypatch) -> None:
    """Conflict означает второй запущенный процесс бота — известная эксплуатационная
    ситуация, не повод заводить событие в трекере ошибок."""
    captured = []
    import sentry_sdk

    monkeypatch.setattr(sentry_sdk, "capture_exception", lambda err: captured.append(err))

    context = SimpleNamespace(error=Conflict("другой процесс уже опрашивает Telegram"))
    update = SimpleNamespace(effective_message=None, callback_query=None)
    await common.error_handler(update, context)

    assert captured == []


@pytest.mark.anyio
async def test_sentry_failure_does_not_break_the_handler(monkeypatch) -> None:
    """Сбой отправки в Sentry не должен мешать обработчику сообщить пользователю."""
    import sentry_sdk

    def _boom(_error):
        raise RuntimeError("Sentry недоступен")

    monkeypatch.setattr(sentry_sdk, "capture_exception", _boom)

    replies = []

    async def _reply(message, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(common.utils, "safe_reply_text", _reply)

    message = SimpleNamespace()
    update = SimpleNamespace(effective_message=message, callback_query=None)
    context = SimpleNamespace(error=ValueError("настоящая ошибка"))

    await common.error_handler(update, context)

    assert replies  # пользователь всё равно получил ответ
