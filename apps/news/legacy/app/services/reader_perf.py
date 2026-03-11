"""
Lightweight performance logging for reader bot updates and internal spans.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, TypeVar

from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings

logger = logging.getLogger("reader_perf")
T = TypeVar("T")


def perf_enabled() -> bool:
    return bool(getattr(settings, "reader_perf_logging_enabled", True))


def perf_start() -> float:
    return time.perf_counter()


def _slow_update_threshold_ms() -> float:
    return max(50.0, float(getattr(settings, "reader_perf_slow_update_ms", 1200) or 1200))


def _slow_span_threshold_ms() -> float:
    return max(20.0, float(getattr(settings, "reader_perf_slow_span_ms", 250) or 250))


def _log_all_updates() -> bool:
    return bool(getattr(settings, "reader_perf_log_all_updates", False))


def _format_value(value: object, *, limit: int = 96) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    raw = " ".join(raw.split())
    raw = raw.replace("=", ":")
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _event_context(event: TelegramObject | Any) -> dict[str, str]:
    update_type = event.__class__.__name__.lower()
    user_id = "-"
    chat_id = "-"
    action = "-"

    if isinstance(event, CallbackQuery):
        update_type = "callback_query"
        action = _format_value(event.data)
        if event.from_user is not None:
            user_id = str(event.from_user.id)
        if event.message is not None and event.message.chat is not None:
            chat_id = str(event.message.chat.id)
    elif isinstance(event, Message):
        update_type = "message"
        text = event.text or event.caption or ""
        action = _format_value(text)
        if event.from_user is not None:
            user_id = str(event.from_user.id)
        if event.chat is not None:
            chat_id = str(event.chat.id)

    return {
        "update_type": update_type,
        "user_id": user_id,
        "chat_id": chat_id,
        "action": action,
    }


def log_update_timing(
    event: TelegramObject | Any,
    started_at: float,
    *,
    ok: bool,
    error: str | None = None,
) -> None:
    if not perf_enabled():
        return

    duration_ms = (time.perf_counter() - started_at) * 1000.0
    if ok and not _log_all_updates() and duration_ms < _slow_update_threshold_ms():
        return

    meta = _event_context(event)
    status = "ok" if ok else "error"
    error_part = f" error={_format_value(error, limit=48)}" if error else ""
    logger.info(
        "reader_update_perf update_type=%s action=%s user_id=%s chat_id=%s duration_ms=%.1f status=%s%s",
        meta["update_type"],
        meta["action"],
        meta["user_id"],
        meta["chat_id"],
        duration_ms,
        status,
        error_part,
    )


def log_span_timing(
    span: str,
    started_at: float,
    *,
    ok: bool = True,
    error: str | None = None,
    force: bool = False,
    **context: object,
) -> None:
    if not perf_enabled():
        return

    duration_ms = (time.perf_counter() - started_at) * 1000.0
    if not force and ok and not _log_all_updates() and duration_ms < _slow_span_threshold_ms():
        return

    status = "ok" if ok else "error"
    parts = [f"{key}={_format_value(value)}" for key, value in sorted(context.items()) if value is not None]
    if error:
        parts.append(f"error={_format_value(error, limit=48)}")
    suffix = f" {' '.join(parts)}" if parts else ""
    logger.info(
        "reader_span_perf span=%s duration_ms=%.1f status=%s%s",
        _format_value(span, limit=80),
        duration_ms,
        status,
        suffix,
    )


async def measure_async(span: str, awaitable: Awaitable[T], **context: object) -> T:
    started_at = perf_start()
    try:
        result = await awaitable
        log_span_timing(span, started_at, ok=True, **context)
        return result
    except Exception as exc:
        log_span_timing(span, started_at, ok=False, error=type(exc).__name__, force=True, **context)
        raise
