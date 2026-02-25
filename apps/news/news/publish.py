from __future__ import annotations

import logging
import time
from typing import Any

import requests

from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _split_text_for_telegram(text: str, limit: int = 4000) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if len(normalized) <= limit:
        return [normalized]

    parts: list[str] = []
    rest = normalized
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < int(limit * 0.5):
            cut = rest.rfind(" ", 0, limit)
        if cut < int(limit * 0.5):
            cut = limit
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    return [part for part in parts if part]


def _telegram_request(method: str, payload: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, data=payload, timeout=20)
            if response.status_code == 429:
                retry_after = 3
                try:
                    body = response.json()
                    retry_after = int(body.get("parameters", {}).get("retry_after", retry_after))
                except Exception:
                    pass
                logger.warning("telegram_rate_limited", extra={"method": method, "retry_after": retry_after})
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            body = response.json()
            if not body.get("ok", False):
                description = body.get("description") or "unknown telegram error"
                raise RuntimeError(f"Telegram API error: {description}")
            return body
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)
                continue
            break

    raise RuntimeError(f"Telegram request failed: {last_error}")


def _send_to_telegram(text: str, media_urls: list[str] | None) -> None:
    chat_id = settings.telegram_channel_id or settings.telegram_channel_username
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_USERNAME is required")

    normalized_text = (text or "").strip()
    if not normalized_text:
        raise RuntimeError("Post text is empty")

    if media_urls:
        media = media_urls[0]
        caption = normalized_text[:1020]
        remainder = normalized_text[1020:].strip()

        photo_value = media.replace("tg://", "") if media.startswith("tg://") else media
        _telegram_request(
            "sendPhoto",
            {
                "chat_id": chat_id,
                "photo": photo_value,
                "caption": caption,
            },
        )

        if remainder:
            for part in _split_text_for_telegram(remainder):
                _telegram_request("sendMessage", {"chat_id": chat_id, "text": part})
        return

    for part in _split_text_for_telegram(normalized_text):
        _telegram_request("sendMessage", {"chat_id": chat_id, "text": part})


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    claim_response = client.claim_posts(limit=10)
    if claim_response.status_code == 204:
        logger.info("no_due_posts")
        return 0
    claim_response.raise_for_status()

    posts = claim_response.json()
    consecutive_errors = 0

    for post in posts:
        post_id = post["id"]
        try:
            _send_to_telegram(post["text"], post.get("media_urls"))
            patch = client.patch_post(post_id, {"status": "posted", "last_error": None})
            patch.raise_for_status()
            consecutive_errors = 0
            logger.info("post_published", extra={"post_id": post_id})
        except Exception as exc:
            consecutive_errors += 1
            logger.exception("post_publish_failed", extra={"post_id": post_id, "error": str(exc)})
            fail = client.patch_post(post_id, {"status": "failed", "last_error": str(exc)[:500]})
            if fail.status_code >= 400:
                logger.error("post_failed_patch_error", extra={"post_id": post_id, "status": fail.status_code})

            if consecutive_errors >= 3:
                logger.error("publisher_circuit_breaker_activated")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
