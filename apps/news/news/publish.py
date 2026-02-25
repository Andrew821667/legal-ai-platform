from __future__ import annotations

import logging

import requests

from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _send_to_telegram(text: str, media_urls: list[str] | None) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    chat_id = settings.telegram_channel_id or settings.telegram_channel_username
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHANNEL_ID or TELEGRAM_CHANNEL_USERNAME is required")

    if media_urls:
        media = media_urls[0]
        if media.startswith("tg://"):
            requests.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto",
                data={"chat_id": chat_id, "photo": media.replace("tg://", ""), "caption": text},
                timeout=20,
            ).raise_for_status()
            return
        requests.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendPhoto",
            data={"chat_id": chat_id, "photo": media, "caption": text},
            timeout=20,
        ).raise_for_status()
        return

    requests.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=20,
    ).raise_for_status()


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    claim_response = client.claim_posts(limit=10)
    if claim_response.status_code == 204:
        logger.info("No due posts")
        return 0
    claim_response.raise_for_status()

    posts = claim_response.json()
    consecutive_errors = 0

    for post in posts:
        post_id = post["id"]
        try:
            _send_to_telegram(post["text"], post.get("media_urls"))
            patch = client.patch_post(post_id, {"status": "posted"})
            patch.raise_for_status()
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            logger.exception("Failed to publish post", extra={"post_id": post_id})
            fail = client.patch_post(post_id, {"status": "failed", "last_error": str(exc)[:500]})
            if fail.status_code >= 400:
                logger.error("Failed to mark post failed", extra={"post_id": post_id})

            if consecutive_errors >= 3:
                logger.error("Circuit breaker activated")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
