"""
Core API bridge for reader-bot feedback and deeplinks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import requests
from requests.adapters import HTTPAdapter

from app.config import settings

logger = logging.getLogger(__name__)

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
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


def reader_post_deeplink(post_id: str | UUID) -> str:
    username = (settings.reader_bot_username or "").strip().lstrip("@")
    if not username:
        return ""
    return f"https://t.me/{username}?start=post_{str(post_id)}"


def _feedback_enabled() -> bool:
    return bool((settings.core_api_url or "").strip() and (settings.api_key_news or "").strip())


def _send_feedback_sync(post_id: str, payload: dict[str, Any]) -> requests.Response:
    return _session().post(
        f"{settings.core_api_url.rstrip('/')}/api/v1/scheduled-posts/{post_id}/feedback",
        json=payload,
        headers={
            "X-API-Key": settings.api_key_news,
            "Content-Type": "application/json",
        },
        timeout=(
            float(getattr(settings, "core_api_connect_timeout_seconds", 2.5) or 2.5),
            float(getattr(settings, "core_api_read_timeout_seconds", 8.0) or 8.0),
        ),
    )


async def push_reader_feedback(
    *,
    publication_id: str | UUID,
    user_id: int,
    source: str,
    signal_key: str,
    signal_value: int,
    text: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    if not _feedback_enabled():
        return False

    try:
        post_uuid = UUID(str(publication_id))
    except ValueError:
        logger.warning("reader_feedback_invalid_publication_id", publication_id=str(publication_id))
        return False

    request_payload = {
        "source": source,
        "signal_key": signal_key,
        "signal_value": signal_value,
        "text": text,
        "telegram_user_id": int(user_id),
        "actor_name": "reader_bot",
        "payload": {
            "channel": "reader_bot",
            **(payload or {}),
        },
    }

    try:
        response = await asyncio.to_thread(_send_feedback_sync, str(post_uuid), request_payload)
        if response.status_code == 404:
            logger.info("reader_feedback_post_not_found", publication_id=str(post_uuid))
            return False
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.warning(
            "reader_feedback_push_failed",
            extra={
                "publication_id": str(post_uuid),
                "source": source,
                "signal_key": signal_key,
                "signal_value": signal_value,
                "error": str(exc),
            },
        )
        return False
