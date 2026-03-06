"""
Core API bridge for reader bot personalization/saved flow.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return bool((settings.core_api_url or "").strip() and (settings.api_key_news or "").strip())


def _headers() -> dict[str, str]:
    return {
        "X-API-Key": settings.api_key_news,
        "Content-Type": "application/json",
    }


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

    def _send() -> requests.Response:
        return requests.patch(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/preferences",
            json=payload,
            headers=_headers(),
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
        response.raise_for_status()
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

    def _send() -> requests.Response:
        return requests.get(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/feed",
            params={"telegram_user_id": int(user_id), "limit": int(limit), "days": int(days)},
            headers={"X-API-Key": settings.api_key_news},
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
        response.raise_for_status()
        payload = response.json()
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

    def _send() -> requests.Response:
        return requests.get(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/saved",
            params={"telegram_user_id": int(user_id), "limit": int(limit)},
            headers={"X-API-Key": settings.api_key_news},
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return []
    except Exception as exc:
        logger.warning(
            "reader_saved_fetch_failed",
            extra={"user_id": int(user_id), "error": str(exc)},
        )
        return None


async def push_reader_save_state(*, user_id: int, publication_id: str, saved: bool) -> bool:
    if not _enabled():
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

    def _send() -> requests.Response:
        return requests.post(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/cta-click",
            json=body,
            headers=_headers(),
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
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

    def _send() -> requests.Response:
        return requests.post(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/lead-intent",
            json=body,
            headers=_headers(),
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
        response.raise_for_status()
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

    payload = {
        "telegram_user_id": int(user_id),
        "post_id": str(publication_id),
        "saved": bool(saved),
    }

    def _send() -> requests.Response:
        return requests.post(
            f"{settings.core_api_url.rstrip('/')}/api/v1/reader/save",
            json=payload,
            headers=_headers(),
            timeout=8,
        )

    try:
        response = await asyncio.to_thread(_send)
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning(
            "reader_save_sync_failed",
            extra={"user_id": int(user_id), "publication_id": str(publication_id), "saved": bool(saved), "error": str(exc)},
        )
        return False
