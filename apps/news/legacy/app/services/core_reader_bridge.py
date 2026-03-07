"""
Core API bridge for reader-bot personalization, saved posts, CTA and mini-app links.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
import time
from typing import Any
from uuid import UUID

import requests
from requests.adapters import HTTPAdapter

from app.config import settings

logger = logging.getLogger(__name__)

_SESSION: requests.Session | None = None
_SESSION_LOCK = threading.Lock()

_CACHE: dict[str, tuple[float, float, Any]] = {}
_CACHE_LOCK = threading.Lock()

_FAIL_FAST_UNTIL = 0.0
_FAIL_FAST_LOCK = threading.Lock()


def _enabled() -> bool:
    return bool((settings.core_api_url or "").strip() and (settings.api_key_news or "").strip())


def _headers() -> dict[str, str]:
    return {
        "X-API-Key": settings.api_key_news,
        "Content-Type": "application/json",
    }


def _core_url(path: str) -> str:
    return f"{settings.core_api_url.rstrip('/')}{path}"


def _timeout() -> tuple[float, float]:
    connect_timeout = float(getattr(settings, "core_api_connect_timeout_seconds", 2.5) or 2.5)
    read_timeout = float(getattr(settings, "core_api_read_timeout_seconds", 8.0) or 8.0)
    return (max(0.5, connect_timeout), max(0.5, read_timeout))


def _cache_ttl() -> int:
    return max(1, int(getattr(settings, "core_api_read_cache_ttl_seconds", 20) or 20))


def _cache_stale_seconds() -> int:
    return max(0, int(getattr(settings, "core_api_read_cache_stale_seconds", 180) or 180))


def _fail_fast_seconds() -> int:
    return max(1, int(getattr(settings, "core_api_fail_fast_seconds", 10) or 10))


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is not None:
        return _SESSION
    with _SESSION_LOCK:
        if _SESSION is not None:
            return _SESSION
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=max(4, int(getattr(settings, "core_api_pool_connections", 20) or 20)),
            pool_maxsize=max(8, int(getattr(settings, "core_api_pool_maxsize", 50) or 50)),
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _SESSION = session
        return _SESSION


def _set_fail_fast() -> None:
    global _FAIL_FAST_UNTIL
    with _FAIL_FAST_LOCK:
        _FAIL_FAST_UNTIL = time.monotonic() + float(_fail_fast_seconds())


def _is_fail_fast_active() -> bool:
    with _FAIL_FAST_LOCK:
        return time.monotonic() < _FAIL_FAST_UNTIL


def _cache_get(key: str, *, allow_stale: bool = False) -> Any | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        row = _CACHE.get(key)
    if row is None:
        return None
    expires_at, stale_until, payload = row
    if now <= expires_at or (allow_stale and now <= stale_until):
        return copy.deepcopy(payload)
    return None


def _cache_set(key: str, payload: Any, *, ttl_seconds: int | None = None) -> None:
    ttl = max(1, int(ttl_seconds or _cache_ttl()))
    now = time.monotonic()
    expires_at = now + float(ttl)
    stale_until = expires_at + float(_cache_stale_seconds())
    with _CACHE_LOCK:
        _CACHE[key] = (expires_at, stale_until, copy.deepcopy(payload))


def _cache_invalidate_user(user_id: int) -> None:
    prefix = f"user:{int(user_id)}:"
    with _CACHE_LOCK:
        keys_to_drop = [key for key in _CACHE.keys() if key.startswith(prefix)]
        for key in keys_to_drop:
            _CACHE.pop(key, None)


def _request_sync(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> requests.Response:
    if _is_fail_fast_active():
        raise RuntimeError("core_api_fail_fast_active")

    session = _get_session()
    try:
        response = session.request(
            method=method.upper(),
            url=_core_url(path),
            params=params,
            json=json,
            headers=_headers(),
            timeout=_timeout(),
        )
    except Exception:
        _set_fail_fast()
        raise

    if response.status_code >= 500:
        _set_fail_fast()
    return response


async def _cached_get_json(
    *,
    cache_key: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> Any | None:
    cached = _cache_get(cache_key, allow_stale=False)
    if cached is not None:
        return cached

    try:
        response = await asyncio.to_thread(_request_sync, "GET", path, params=params)
        response.raise_for_status()
        payload = response.json()
        _cache_set(cache_key, payload)
        return payload
    except Exception:
        return _cache_get(cache_key, allow_stale=True)


async def push_reader_preferences(
    *,
    user_id: int,
    topics: list[str] | None = None,
    digest_frequency: str | None = None,
    expertise_level: str | None = None,
) -> bool:
    if not _enabled():
        return False

    payload: dict[str, Any] = {"telegram_user_id": int(user_id)}
    if topics is not None:
        payload["topics"] = list(topics)
    if digest_frequency is not None:
        payload["digest_frequency"] = digest_frequency
    if expertise_level is not None:
        payload["expertise_level"] = expertise_level

    try:
        response = await asyncio.to_thread(
            _request_sync,
            "PATCH",
            "/api/v1/reader/preferences",
            json=payload,
        )
        response.raise_for_status()
        _cache_invalidate_user(int(user_id))
        return True
    except Exception as exc:
        logger.warning(
            "reader_preferences_push_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return False


async def fetch_reader_feed(*, user_id: int, limit: int = 5, days: int = 14) -> list[dict[str, Any]] | None:
    if not _enabled():
        return None

    cache_key = f"user:{int(user_id)}:feed:{int(limit)}:{int(days)}"
    try:
        payload = await _cached_get_json(
            cache_key=cache_key,
            path="/api/v1/reader/feed",
            params={"telegram_user_id": int(user_id), "limit": int(limit), "days": int(days)},
        )
        if payload is None:
            return None
        if isinstance(payload, list):
            return payload
        return []
    except Exception as exc:
        logger.warning(
            "reader_feed_fetch_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return None


async def fetch_reader_saved(*, user_id: int, limit: int = 20) -> list[dict[str, Any]] | None:
    if not _enabled():
        return None

    cache_key = f"user:{int(user_id)}:saved:{int(limit)}"
    try:
        payload = await _cached_get_json(
            cache_key=cache_key,
            path="/api/v1/reader/saved",
            params={"telegram_user_id": int(user_id), "limit": int(limit)},
        )
        if payload is None:
            return None
        if isinstance(payload, list):
            return payload
        return []
    except Exception as exc:
        logger.warning(
            "reader_saved_fetch_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return None


async def fetch_reader_miniapp_profile(*, user_id: int) -> dict[str, Any] | None:
    if not _enabled():
        return None

    cache_key = f"user:{int(user_id)}:miniapp_profile"
    try:
        payload = await _cached_get_json(
            cache_key=cache_key,
            path="/api/v1/reader/miniapp/profile",
            params={"telegram_user_id": int(user_id)},
        )
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload
        return {}
    except Exception as exc:
        logger.warning(
            "reader_miniapp_profile_fetch_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return None


async def fetch_reader_continue_state(*, user_id: int) -> dict[str, Any] | None:
    if not _enabled():
        return None

    cache_key = f"user:{int(user_id)}:continue_state"
    try:
        payload = await _cached_get_json(
            cache_key=cache_key,
            path="/api/v1/reader/continue-state",
            params={"telegram_user_id": int(user_id)},
        )
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload
        return {}
    except Exception as exc:
        logger.warning(
            "reader_continue_state_fetch_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return None


async def fetch_reader_conversion_funnel(*, hours: int = 24 * 7) -> dict[str, Any] | None:
    if not _enabled():
        return None

    cache_key = f"global:conversion_funnel:{int(hours)}"
    try:
        payload = await _cached_get_json(
            cache_key=cache_key,
            path="/api/v1/reader/conversion-funnel",
            params={"hours": int(hours)},
        )
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload
        return {}
    except Exception as exc:
        logger.warning(
            "reader_conversion_funnel_fetch_failed",
            extra={"hours": int(hours), "error": str(exc)},
        )
        return None


async def push_reader_save_state(*, user_id: int, publication_id: str, saved: bool) -> bool:
    if not _enabled():
        return False

    payload = {
        "telegram_user_id": int(user_id),
        "post_id": str(publication_id),
        "saved": bool(saved),
    }

    try:
        response = await asyncio.to_thread(
            _request_sync,
            "POST",
            "/api/v1/reader/save",
            json=payload,
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        _cache_invalidate_user(int(user_id))
        return True
    except Exception as exc:
        logger.warning(
            "reader_save_sync_failed",
            extra={
                "user_id": int(user_id),
                "publication_id": str(publication_id),
                "saved": bool(saved),
                "error": str(exc),
            },
        )
        return False


async def push_reader_cta_click(
    *,
    user_id: int,
    publication_id: str | None = None,
    cta_type: str | None = None,
    context: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    if not _enabled():
        return False

    body = {
        "telegram_user_id": int(user_id),
        "post_id": publication_id,
        "cta_type": cta_type,
        "context": context,
        "payload": payload or {},
    }

    try:
        response = await asyncio.to_thread(
            _request_sync,
            "POST",
            "/api/v1/reader/cta-click",
            json=body,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning(
            "reader_cta_click_push_failed",
            extra={
                "user_id": int(user_id),
                "publication_id": publication_id,
                "cta_type": cta_type,
                "error": str(exc),
            },
        )
        return False


async def push_reader_lead_intent(
    *,
    user_id: int,
    intent_type: str,
    publication_id: str | None = None,
    message: str | None = None,
    contact: str | None = None,
    name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not _enabled():
        return None

    body = {
        "telegram_user_id": int(user_id),
        "post_id": publication_id,
        "intent_type": intent_type,
        "message": message,
        "contact": contact,
        "name": name,
        "payload": payload or {},
    }

    try:
        response = await asyncio.to_thread(
            _request_sync,
            "POST",
            "/api/v1/reader/lead-intent",
            json=body,
        )
        response.raise_for_status()
        _cache_invalidate_user(int(user_id))
        data = response.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception as exc:
        logger.warning(
            "reader_lead_intent_push_failed",
            extra={
                "user_id": int(user_id),
                "publication_id": publication_id,
                "intent_type": intent_type,
                "error": str(exc),
            },
        )
        return None


def _fallback_deeplink(*, user_id: int, source: str, screen: str | None) -> str | None:
    fallback_base = (settings.reader_miniapp_base_url or "").strip()
    if not fallback_base:
        return None
    separator = "&" if "?" in fallback_base else "?"
    fallback_screen = (screen or "home").strip() or "home"
    return f"{fallback_base}{separator}tg={int(user_id)}&src={source}&screen={fallback_screen}"


async def build_reader_miniapp_deeplink(
    *,
    user_id: int,
    source: str = "reader.bot",
    screen: str | None = None,
    action: str | None = None,
    post_id: str | UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> str | None:
    """
    Build tracked mini-app deeplink through core-api.
    Falls back to configured public URL when core-api is unavailable.
    """
    if not _enabled():
        return _fallback_deeplink(user_id=int(user_id), source=source, screen=screen)

    body: dict[str, Any] = {
        "telegram_user_id": int(user_id),
        "source": (source or "reader.bot").strip() or "reader.bot",
        "screen": (screen or "home").strip() or "home",
        "action": (action or "").strip() or None,
        "payload": payload or {},
    }
    if post_id is not None:
        body["post_id"] = str(post_id)

    try:
        response = await asyncio.to_thread(
            _request_sync,
            "POST",
            "/api/v1/reader/miniapp/deeplink",
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            url = data.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    except Exception as exc:
        logger.warning(
            "reader_miniapp_deeplink_build_failed",
            extra={
                "user_id": int(user_id),
                "source": source,
                "screen": screen,
                "error": str(exc),
            },
        )

    return _fallback_deeplink(user_id=int(user_id), source=source, screen=screen)
