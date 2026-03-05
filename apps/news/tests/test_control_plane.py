from __future__ import annotations

from news.control_plane import (
    generate_limit,
    generate_schedule_times,
    publish_claim_limit,
    review_retention_days,
    telegram_ingest_fetch_limit,
    telegram_ingest_schedule_times,
)


def test_generate_schedule_times_defaults() -> None:
    rows: list[dict[str, object]] = []
    assert generate_schedule_times(rows) == ["08:00", "17:00"]


def test_generate_schedule_times_from_control_config() -> None:
    rows = [
        {
            "key": "news.generate.enabled",
            "config": {
                "morning_time": "07:30",
                "evening_time": "16:30",
            },
        }
    ]
    assert generate_schedule_times(rows) == ["07:30", "16:30"]


def test_generate_limit_and_retention_defaults() -> None:
    rows: list[dict[str, object]] = []
    assert generate_limit(rows) == 5
    assert review_retention_days(rows) == 3


def test_generate_limit_and_retention_from_control_config() -> None:
    rows = [
        {
            "key": "news.generate.enabled",
            "config": {
                "generate_limit": 7,
                "retention_days": 5,
            },
        }
    ]
    assert generate_limit(rows) == 7
    assert review_retention_days(rows) == 5


def test_publish_claim_limit_defaults_to_single_post() -> None:
    rows: list[dict[str, object]] = []
    assert publish_claim_limit(rows) == 1


def test_publish_claim_limit_from_control_config() -> None:
    rows = [
        {
            "key": "news.publish.enabled",
            "config": {
                "claim_limit": 3,
            },
        }
    ]
    assert publish_claim_limit(rows) == 3


def test_telegram_ingest_schedule_times_defaults() -> None:
    rows: list[dict[str, object]] = []
    assert telegram_ingest_schedule_times(rows) == ["07:30", "16:30"]


def test_telegram_ingest_schedule_times_from_control_config() -> None:
    rows = [
        {
            "key": "news.telegram_ingest.enabled",
            "config": {
                "morning_time": "07:00",
                "evening_time": "16:00",
            },
        }
    ]
    assert telegram_ingest_schedule_times(rows) == ["07:00", "16:00"]


def test_telegram_ingest_fetch_limit_from_control_config() -> None:
    rows = [
        {
            "key": "news.telegram_ingest.enabled",
            "config": {
                "fetch_limit": 80,
            },
        }
    ]
    assert telegram_ingest_fetch_limit(rows) == 80
