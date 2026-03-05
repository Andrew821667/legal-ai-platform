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
_WORKER_ID = "news-generate"
_TICK_HEARTBEAT_SECONDS = 600


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


def _send_worker_heartbeat(client: CoreClient, info: dict[str, object]) -> None:
    try:
        client.worker_heartbeat(_WORKER_ID, info).raise_for_status()
    except Exception as exc:
        logger.warning("worker_heartbeat_failed", extra={"worker_id": _WORKER_ID, "error": str(exc)})


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    _send_worker_heartbeat(
        client,
        {
            "action": "startup",
            "component": "generate_loop",
            "tz": settings.tz_name,
        },
    )
    last_generation_slot_key = ""
    last_cleanup_date = ""
    last_tick_heartbeat_at = 0.0
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
                    _send_worker_heartbeat(
                        client,
                        {
                            "action": "generate_slot_start",
                            "slot": slot,
                            "limit": limit,
                            "date": today_key,
                        },
                    )
                    result_code = run_generation(limit, dry_run=False)
                    _send_worker_heartbeat(
                        client,
                        {
                            "action": "generate_slot_done",
                            "slot": slot,
                            "limit": limit,
                            "result_code": result_code,
                            "date": today_key,
                        },
                    )
                    last_generation_slot_key = slot_key
                    break
            else:
                logger.info("generate_loop_disabled_by_control_plane")

            now_ts = time.time()
            heartbeat_info: dict[str, object] = {"mode": "poll", "limit": limit}
            if now_ts - last_tick_heartbeat_at >= _TICK_HEARTBEAT_SECONDS:
                heartbeat_info["action"] = "tick"
                heartbeat_info["slot_times"] = generate_schedule_times(rows)
                last_tick_heartbeat_at = now_ts
            _send_worker_heartbeat(client, heartbeat_info)
        except Exception as exc:
            logger.exception("generate_loop_iteration_failed", extra={"error": str(exc)})
            _send_worker_heartbeat(
                client,
                {
                    "action": "iteration_error",
                    "error": str(exc)[:400],
                },
            )
            sleep_for = 60
        time.sleep(max(15, sleep_for))


if __name__ == "__main__":
    raise SystemExit(main())
