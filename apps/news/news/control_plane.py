from __future__ import annotations

from typing import Any

from news.core_client import CoreClient
from news.settings import settings


def load_news_controls(client: CoreClient) -> list[dict[str, Any]]:
    response = client.list_automation_controls(scope="news")
    response.raise_for_status()
    return list(response.json())


def controls_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row.get("key") or ""): row for row in rows if str(row.get("key") or "")}


def enabled_map(rows: list[dict[str, Any]]) -> dict[str, bool]:
    return {key: bool(row.get("enabled", True)) for key, row in controls_map(rows).items()}


def generate_interval_seconds(rows: list[dict[str, Any]]) -> int:
    row = controls_map(rows).get("news.generate.enabled") or {}
    config = row.get("config") or {}
    value = config.get("interval_seconds")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_generate_interval_seconds


def _generate_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = controls_map(rows).get("news.generate.enabled") or {}
    config = row.get("config") or {}
    return config if isinstance(config, dict) else {}


def _telegram_ingest_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = controls_map(rows).get("news.telegram_ingest.enabled") or {}
    config = row.get("config") or {}
    return config if isinstance(config, dict) else {}


def generate_schedule_times(rows: list[dict[str, Any]]) -> list[str]:
    config = _generate_config(rows)
    morning = str(config.get("morning_time") or settings.news_generate_morning_slot).strip()
    evening = str(config.get("evening_time") or settings.news_generate_evening_slot).strip()
    result: list[str] = []
    for item in (morning, evening):
        if item and item not in result:
            result.append(item)
    return result or [settings.news_generate_morning_slot, settings.news_generate_evening_slot]


def generate_slot_grace_minutes(rows: list[dict[str, Any]]) -> int:
    config = _generate_config(rows)
    value = config.get("slot_grace_minutes")
    if isinstance(value, int):
        return max(5, min(value, 120))
    return 35


def review_retention_days(rows: list[dict[str, Any]]) -> int:
    config = _generate_config(rows)
    value = config.get("retention_days")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_review_retention_days


def telegram_ingest_schedule_times(rows: list[dict[str, Any]]) -> list[str]:
    config = _telegram_ingest_config(rows)
    morning = str(config.get("morning_time") or settings.news_telegram_ingest_morning_slot).strip()
    evening = str(config.get("evening_time") or settings.news_telegram_ingest_evening_slot).strip()
    result: list[str] = []
    for item in (morning, evening):
        if item and item not in result:
            result.append(item)
    return result or [settings.news_telegram_ingest_morning_slot, settings.news_telegram_ingest_evening_slot]


def telegram_ingest_slot_grace_minutes(rows: list[dict[str, Any]]) -> int:
    config = _telegram_ingest_config(rows)
    value = config.get("slot_grace_minutes")
    if isinstance(value, int):
        return max(5, min(value, 120))
    return 30


def telegram_ingest_fetch_limit(rows: list[dict[str, Any]]) -> int:
    config = _telegram_ingest_config(rows)
    value = config.get("fetch_limit")
    if isinstance(value, int) and value > 0:
        return max(10, min(value, 200))
    return max(10, min(settings.telegram_fetch_limit, 200))


def enabled_telegram_channels(rows: list[dict[str, Any]]) -> list[str]:
    controls = enabled_map(rows)
    result: list[str] = []
    for channel in settings.telegram_channels_list:
        slug = channel.strip().lstrip("@").lower()
        if not slug:
            continue
        if controls.get(f"news.telegram_channel.{slug}.enabled", True):
            result.append(channel)
    return result


def publish_interval_seconds(rows: list[dict[str, Any]]) -> int:
    row = controls_map(rows).get("news.publish.enabled") or {}
    config = row.get("config") or {}
    value = config.get("interval_seconds")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_publish_interval_seconds


def publish_claim_limit(rows: list[dict[str, Any]]) -> int:
    row = controls_map(rows).get("news.publish.enabled") or {}
    config = row.get("config") or {}
    value = config.get("claim_limit")
    if isinstance(value, int) and value > 0:
        return min(max(value, 1), 50)
    return max(settings.news_publish_claim_limit, 1)


def generate_limit(rows: list[dict[str, Any]]) -> int:
    config = _generate_config(rows)
    value = config.get("generate_limit")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_generate_limit
