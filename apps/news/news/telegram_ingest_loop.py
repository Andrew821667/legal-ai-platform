from __future__ import annotations

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from news.control_plane import (
    enabled_map,
    enabled_telegram_channels,
    load_news_controls,
    telegram_ingest_fetch_limit,
    telegram_ingest_schedule_times,
)
from news.core_client import CoreClient
from news.logging_config import setup_logging
from news.settings import settings
from news.telegram_ingest import fetch_telegram_articles, save_telegram_articles_cache

setup_logging()
logger = logging.getLogger(__name__)

_WORKER_ID = "news-telegram-ingest"
_TICK_HEARTBEAT_SECONDS = 600


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
            "component": "telegram_ingest_loop",
            "tz": settings.tz_name,
        },
    )

    last_slot_key = ""
    last_tick_heartbeat_at = 0.0

    while True:
        sleep_for = 30
        try:
            rows = load_news_controls(client)
            controls = enabled_map(rows)
            slot_times = telegram_ingest_schedule_times(rows)
            channel_list = enabled_telegram_channels(rows)
            fetch_limit = telegram_ingest_fetch_limit(rows)
            ingest_enabled = controls.get("news.telegram_ingest.enabled", True) and settings.telegram_fetch_enabled
            now_local = datetime.now(ZoneInfo(settings.tz_name))
            today_key = now_local.date().isoformat()

            if ingest_enabled:
                for slot in slot_times:
                    slot_key = f"{today_key}:{slot}"
                    if slot_key == last_slot_key:
                        continue
                    if now_local.strftime("%H:%M") != slot:
                        continue
                    _send_worker_heartbeat(
                        client,
                        {
                            "action": "telegram_fetch_slot_start",
                            "slot": slot,
                            "date": today_key,
                            "channels": len(channel_list),
                            "fetch_limit": fetch_limit,
                        },
                    )
                    articles = fetch_telegram_articles(channel_list, fetch_limit=fetch_limit)
                    info: dict[str, object] = {
                        "action": "telegram_fetch_slot_done",
                        "slot": slot,
                        "date": today_key,
                        "channels": len(channel_list),
                        "fetch_limit": fetch_limit,
                        "count": len(articles),
                    }
                    if articles:
                        cache_path = save_telegram_articles_cache(articles, channels=channel_list)
                        info["cache_path"] = str(cache_path)
                    _send_worker_heartbeat(client, info)
                    last_slot_key = slot_key
                    break
            else:
                logger.info("telegram_ingest_loop_disabled_by_control_plane")

            now_ts = time.time()
            heartbeat_info: dict[str, object] = {
                "mode": "poll",
                "enabled": ingest_enabled,
                "channels": len(channel_list),
                "fetch_limit": fetch_limit,
            }
            if now_ts - last_tick_heartbeat_at >= _TICK_HEARTBEAT_SECONDS:
                heartbeat_info["action"] = "tick"
                heartbeat_info["slot_times"] = slot_times
                last_tick_heartbeat_at = now_ts
            _send_worker_heartbeat(client, heartbeat_info)
        except Exception as exc:
            logger.exception("telegram_ingest_loop_iteration_failed", extra={"error": str(exc)})
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
