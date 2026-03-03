from __future__ import annotations

from news.control_plane import generate_limit, generate_schedule_times, review_retention_days


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
