from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _slot_times(now_msk: datetime) -> list[datetime]:
    slots = [(10, 0), (13, 0), (17, 0)]
    results: list[datetime] = []
    for hour, minute in slots:
        candidate = now_msk.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_msk:
            candidate += timedelta(days=1)
        results.append(candidate)
    return results


def _build_drafts() -> list[dict]:
    sources = [s.strip() for s in settings.news_source_urls.split(",") if s.strip()]
    if not sources:
        sources = ["https://example.com/legal-ai-news"]

    msk_now = datetime.now(ZoneInfo(settings.tz_name))
    slots = _slot_times(msk_now)

    drafts: list[dict] = []
    for index, source in enumerate(sources[:3]):
        slot = slots[index % len(slots)]
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        drafts.append(
            {
                "title": f"Обзор Legal AI #{index + 1}",
                "text": f"Источник: {source}\nКраткий обзор важных новостей и кейсов.",
                "source_url": source,
                "source_hash": source_hash,
                "channel_id": settings.telegram_channel_id or None,
                "channel_username": settings.telegram_channel_username or None,
                "publish_at": slot.astimezone(timezone.utc).isoformat(),
                "status": "scheduled",
            }
        )
    return drafts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scheduled posts")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    drafts = _build_drafts()

    created = 0
    for draft in drafts:
        if args.dry_run:
            draft["status"] = "draft"
        response = client.create_scheduled_post(draft)
        if response.status_code in (200, 201):
            created += 1
            logger.info("Scheduled post created", extra={"source_url": draft.get("source_url")})
        elif response.status_code == 409:
            logger.info("Duplicate post skipped")
        else:
            logger.error("Failed to create post", extra={"status": response.status_code, "body": response.text})

    logger.info("Generation completed", extra={"created": created, "dry_run": args.dry_run})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
