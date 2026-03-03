from __future__ import annotations

import logging
import time

from news.control_plane import enabled_map, generate_interval_seconds, generate_limit, load_news_controls
from news.core_client import CoreClient
from news.generate import run_generation
from news.logging_config import setup_logging
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1

    client = CoreClient(settings.core_api_url, settings.api_key_news)
    while True:
        sleep_for = settings.news_generate_interval_seconds
        try:
            rows = load_news_controls(client)
            controls = enabled_map(rows)
            sleep_for = generate_interval_seconds(rows)
            limit = generate_limit(rows)
            if controls.get("news.generate.enabled", True):
                run_generation(limit, dry_run=False)
            else:
                logger.info("generate_loop_disabled_by_control_plane")
        except Exception as exc:
            logger.exception("generate_loop_iteration_failed", extra={"error": str(exc)})
            sleep_for = min(60, sleep_for)
        time.sleep(max(15, sleep_for))


if __name__ == "__main__":
    raise SystemExit(main())
