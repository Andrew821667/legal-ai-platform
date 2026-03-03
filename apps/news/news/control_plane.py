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


def publish_interval_seconds(rows: list[dict[str, Any]]) -> int:
    row = controls_map(rows).get("news.publish.enabled") or {}
    config = row.get("config") or {}
    value = config.get("interval_seconds")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_publish_interval_seconds


def generate_limit(rows: list[dict[str, Any]]) -> int:
    row = controls_map(rows).get("news.generate.enabled") or {}
    config = row.get("config") or {}
    value = config.get("generate_limit")
    if isinstance(value, int) and value > 0:
        return value
    return settings.news_generate_limit
