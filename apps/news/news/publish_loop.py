from __future__ import annotations

import logging
import time

from news.control_plane import publish_interval_seconds, load_news_controls
from news.logging_config import setup_logging
from news.publish import main as publish_once
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = None
    if settings.core_api_url and settings.api_key_news:
        from news.core_client import CoreClient

        client = CoreClient(settings.core_api_url, settings.api_key_news)

    while True:
        sleep_for = settings.news_publish_interval_seconds
        try:
            if client is not None:
                rows = load_news_controls(client)
                sleep_for = publish_interval_seconds(rows)
            publish_once()
        except Exception as exc:
            logger.exception("publish_loop_iteration_failed", extra={"error": str(exc)})
            sleep_for = min(60, sleep_for)
        time.sleep(max(15, sleep_for))


if __name__ == "__main__":
    raise SystemExit(main())
