from datetime import UTC, datetime

from news.publication_monitor import (
    MONITOR_WORKER_ID,
    acknowledged_alert_keys,
    build_publication_alerts,
)


def _post(publish_at: str, *, format_type: str = "daily") -> dict[str, str]:
    return {"publish_at": publish_at, "format_type": format_type}


def _workers() -> list[dict[str, object]]:
    return [
        {"worker_id": "news-generate", "active": True, "info": {}},
        {"worker_id": "news-publish", "active": True, "info": {}},
    ]


def test_monitor_reports_only_unpublished_slots() -> None:
    alerts = build_publication_alerts(
        now_utc=datetime(2026, 9, 1, 7, 0, tzinfo=UTC),
        control_rows=[],
        posts_by_status={
            "posted": [_post("2026-08-31T09:00:00+03:00")],
            "review": [],
            "ready": [],
            "scheduled": [],
            "publishing": [],
        },
        workers=_workers(),
        acknowledged_keys=set(),
        tz_name="Europe/Moscow",
        grace_minutes=45,
        warning_minutes=30,
        lookback_hours=36,
    )

    assert len(alerts) == 1
    assert "31.08 в 18:00" in alerts[0].text
    assert "01.09 в 09:00" in alerts[0].text
    assert "31.08 в 09:00" not in alerts[0].text
    assert len(alerts[0].keys) == 2


def test_monitor_warns_when_upcoming_slot_has_no_reserve() -> None:
    alerts = build_publication_alerts(
        now_utc=datetime(2026, 9, 1, 14, 35, tzinfo=UTC),
        control_rows=[],
        posts_by_status={status: [] for status in ("posted", "review", "ready", "scheduled", "publishing")},
        workers=_workers(),
        acknowledged_keys={
            "missed:2026-08-31T09:00:00+03:00",
            "missed:2026-08-31T18:00:00+03:00",
            "missed:2026-09-01T09:00:00+03:00",
        },
        tz_name="Europe/Moscow",
        grace_minutes=45,
        warning_minutes=30,
        lookback_hours=36,
    )

    assert len(alerts) == 1
    assert alerts[0].keys == ("reserve:2026-09-01T18:00:00+03:00",)
    assert "материала в резерве нет" in alerts[0].text


def test_monitor_accepts_matching_review_reserve() -> None:
    alerts = build_publication_alerts(
        now_utc=datetime(2026, 9, 1, 14, 35, tzinfo=UTC),
        control_rows=[],
        posts_by_status={
            "posted": [],
            "review": [_post("2026-09-01T18:00:00+03:00")],
            "ready": [],
            "scheduled": [],
            "publishing": [],
        },
        workers=_workers(),
        acknowledged_keys={
            "missed:2026-08-31T09:00:00+03:00",
            "missed:2026-08-31T18:00:00+03:00",
            "missed:2026-09-01T09:00:00+03:00",
        },
        tz_name="Europe/Moscow",
        grace_minutes=45,
        warning_minutes=30,
        lookback_hours=36,
    )

    assert alerts == []


def test_monitor_respects_publish_switch_and_persisted_keys() -> None:
    workers = _workers() + [
        {
            "worker_id": MONITOR_WORKER_ID,
            "active": True,
            "info": {"alerted_keys": ["missed:2026-09-01T09:00:00+03:00"]},
        }
    ]
    assert acknowledged_alert_keys(workers) == {"missed:2026-09-01T09:00:00+03:00"}

    alerts = build_publication_alerts(
        now_utc=datetime(2026, 9, 1, 7, 0, tzinfo=UTC),
        control_rows=[{"key": "news.publish.enabled", "enabled": False}],
        posts_by_status={status: [] for status in ("posted", "review", "ready", "scheduled", "publishing")},
        workers=workers,
        acknowledged_keys=set(),
        tz_name="Europe/Moscow",
        grace_minutes=45,
        warning_minutes=30,
        lookback_hours=36,
    )

    assert alerts == []
