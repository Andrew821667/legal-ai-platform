from __future__ import annotations

import logging
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo

from news.control_plane import enabled_map, generate_limit, generate_schedule_times, load_news_controls, review_retention_days
from news.core_client import CoreClient
from news.generate import run_generation
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _cleanup_expired_review_posts(client: CoreClient, retention_days: int) -> int:
    response = client.list_posts(limit=100, status="review", newest_first=False)
    response.raise_for_status()
    cutoff = datetime.now(ZoneInfo(settings.tz_name)) - timedelta(days=max(1, retention_days))
    cleaned = 0
    for row in response.json():
        created_raw = str(row.get("created_at") or "").strip()
        post_id = str(row.get("id") or "").strip()
        if not created_raw or not post_id:
            continue
        try:
            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).astimezone(ZoneInfo(settings.tz_name))
        except ValueError:
            continue
        if created_at > cutoff:
            continue
        patch = {
            "status": "failed",
            "last_error": "expired_review_cleanup",
        }
        client.patch_post(post_id, patch).raise_for_status()
        cleaned += 1
    if cleaned:
        logger.info("expired_review_posts_cleaned", extra={"count": cleaned, "retention_days": retention_days})
    return cleaned


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    last_generation_slot_key = ""
    last_cleanup_date = ""
    while True:
        sleep_for = 30
        try:
            rows = load_news_controls(client)
            controls = enabled_map(rows)
            limit = generate_limit(rows)
            retention_days = review_retention_days(rows)
            now_local = datetime.now(ZoneInfo(settings.tz_name))
            today_key = now_local.date().isoformat()
            if today_key != last_cleanup_date:
                _cleanup_expired_review_posts(client, retention_days)
                last_cleanup_date = today_key
            if controls.get("news.generate.enabled", True):
                for slot in generate_schedule_times(rows):
                    slot_key = f"{today_key}:{slot}"
                    if slot_key == last_generation_slot_key:
                        continue
                    if now_local.strftime("%H:%M") != slot:
                        continue
                    logger.info("generate_loop_slot_triggered", extra={"slot": slot, "limit": limit})
                    run_generation(limit, dry_run=False)
                    last_generation_slot_key = slot_key
                    break
            else:
                logger.info("generate_loop_disabled_by_control_plane")
        except Exception as exc:
            logger.exception("generate_loop_iteration_failed", extra={"error": str(exc)})
            sleep_for = 60
        time.sleep(max(15, sleep_for))


if __name__ == "__main__":
    raise SystemExit(main())
