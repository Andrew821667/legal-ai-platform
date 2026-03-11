"""
Lightweight performance logging for legacy lead-bot.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

from telegram import Update

from config import Config

logger = logging.getLogger("lead_perf")
config = Config()
T = TypeVar("T")


def perf_enabled() -> bool:
    return bool(getattr(config, "LEAD_PERF_LOGGING_ENABLED", True))


def perf_start() -> float:
    return time.perf_counter()


def _slow_update_threshold_ms() -> float:
    return max(50.0, float(getattr(config, "LEAD_PERF_SLOW_UPDATE_MS", 1200) or 1200))


def _slow_span_threshold_ms() -> float:
    return max(20.0, float(getattr(config, "LEAD_PERF_SLOW_SPAN_MS", 250) or 250))


def _log_all_updates() -> bool:
    return bool(getattr(config, "LEAD_PERF_LOG_ALL_UPDATES", False))


def _fmt(value: object, *, limit: int = 96) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "-"
    raw = " ".join(raw.split()).replace("=", ":")
    if len(raw) > limit:
        raw = raw[: limit - 3] + "..."
    return raw


def _event_context(update: Update) -> dict[str, str]:
    callback = getattr(update, "callback_query", None)
    business_message = getattr(update, "business_message", None)
    message = getattr(update, "message", None)

    if callback is not None:
        return {
            "update_type": "callback_query",
            "action": _fmt(getattr(callback, "data", None)),
            "user_id": _fmt(getattr(getattr(callback, "from_user", None), "id", None)),
            "chat_id": _fmt(getattr(getattr(getattr(callback, "message", None), "chat", None), "id", None)),
        }
    if business_message is not None:
        return {
            "update_type": "business_message",
            "action": _fmt(getattr(business_message, "text", None) or getattr(business_message, "caption", None)),
            "user_id": _fmt(getattr(getattr(business_message, "from_user", None), "id", None)),
            "chat_id": _fmt(getattr(getattr(business_message, "chat", None), "id", None)),
        }
    return {
        "update_type": "message",
        "action": _fmt(getattr(message, "text", None) or getattr(message, "caption", None)),
        "user_id": _fmt(getattr(getattr(message, "from_user", None), "id", None)),
        "chat_id": _fmt(getattr(getattr(message, "chat", None), "id", None)),
    }


def log_update_timing(update: Update, started_at: float, *, ok: bool, error: str | None = None) -> None:
    if not perf_enabled():
        return
    duration_ms = (time.perf_counter() - started_at) * 1000.0
    if ok and not _log_all_updates() and duration_ms < _slow_update_threshold_ms():
        return

    meta = _event_context(update)
    status = "ok" if ok else "error"
    extra = f" error={_fmt(error, limit=48)}" if error else ""
    logger.info(
        "lead_update_perf update_type=%s action=%s user_id=%s chat_id=%s duration_ms=%.1f status=%s%s",
        meta["update_type"],
        meta["action"],
        meta["user_id"],
        meta["chat_id"],
        duration_ms,
        status,
        extra,
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
    parts = [f"{key}={_fmt(value)}" for key, value in sorted(context.items()) if value is not None]
    if error:
        parts.append(f"error={_fmt(error, limit=48)}")
    suffix = f" {' '.join(parts)}" if parts else ""
    logger.info(
        "lead_span_perf span=%s duration_ms=%.1f status=%s%s",
        _fmt(span, limit=80),
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


def measure_sync(span: str, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    started_at = perf_start()
    try:
        result = func(*args, **kwargs)
        log_span_timing(span, started_at, ok=True)
        return result
    except Exception as exc:
        log_span_timing(span, started_at, ok=False, error=type(exc).__name__, force=True)
        raise
