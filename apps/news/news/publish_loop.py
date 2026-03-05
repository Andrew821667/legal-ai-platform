from __future__ import annotations

import logging
import time

from news.control_plane import publish_interval_seconds, load_news_controls
from news.logging_config import setup_logging
from news.publish import main as publish_once
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)
_WORKER_ID = "news-publish"
_TICK_HEARTBEAT_SECONDS = 600


def _send_worker_heartbeat(client: "CoreClient", info: dict[str, object]) -> None:
    try:
        client.worker_heartbeat(_WORKER_ID, info).raise_for_status()
    except Exception as exc:
        logger.warning("worker_heartbeat_failed", extra={"worker_id": _WORKER_ID, "error": str(exc)})


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = None
    if settings.core_api_url and settings.api_key_news:
        from news.core_client import CoreClient

        client = CoreClient(settings.core_api_url, settings.api_key_news)
        _send_worker_heartbeat(
            client,
            {
                "action": "startup",
                "component": "publish_loop",
            },
        )

    last_tick_heartbeat_at = 0.0
    while True:
        sleep_for = settings.news_publish_interval_seconds
        try:
            if client is not None:
                rows = load_news_controls(client)
                sleep_for = publish_interval_seconds(rows)
            result_code = publish_once()
            if client is not None:
                now_ts = time.time()
                heartbeat_info: dict[str, object] = {"mode": "poll", "result_code": result_code}
                if now_ts - last_tick_heartbeat_at >= _TICK_HEARTBEAT_SECONDS:
                    heartbeat_info["action"] = "tick"
                    heartbeat_info["publish_interval"] = sleep_for
                    last_tick_heartbeat_at = now_ts
                _send_worker_heartbeat(client, heartbeat_info)
        except Exception as exc:
            logger.exception("publish_loop_iteration_failed", extra={"error": str(exc)})
            if client is not None:
                _send_worker_heartbeat(
                    client,
                    {
                        "action": "iteration_error",
                        "error": str(exc)[:400],
                    },
                )
            sleep_for = min(60, sleep_for)
        time.sleep(max(15, sleep_for))


if __name__ == "__main__":
    raise SystemExit(main())
