from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from news.strategy import (
    build_publish_plan,
    build_schedule_window,
    publication_kind_from_format_type,
    resolve_schedule_config,
    schedule_slot_label,
)


def test_build_publish_plan_uses_new_publication_grid() -> None:
    now = datetime(2026, 3, 2, 7, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Monday
    plan = build_publish_plan(now_local=now, count=6)

    assert len(plan) == 6
    assert [item.publication_kind for item in plan[:4]] == ["daily", "daily", "daily", "daily"]
    assert plan[0].publish_at_local.strftime("%H:%M") == "09:00"
    assert plan[1].publish_at_local.strftime("%H:%M") == "18:00"
    assert all(item.format_type in {"daily", "weekly_review", "longread", "humor"} for item in plan)


def test_build_publish_plan_skips_occupied_slots() -> None:
    now = datetime(2026, 3, 2, 7, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Monday
    occupied = {
        datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")).isoformat(),
        datetime(2026, 3, 2, 18, 0, tzinfo=ZoneInfo("Europe/Moscow")).isoformat(),
    }
    plan = build_publish_plan(now_local=now, count=3, occupied_slot_keys=occupied)

    assert len(plan) == 3
    assert plan[0].publish_at_local.strftime("%Y-%m-%d %H:%M") == "2026-03-03 09:00"
    assert plan[1].publish_at_local.strftime("%Y-%m-%d %H:%M") == "2026-03-03 18:00"
    assert plan[2].publish_at_local.strftime("%Y-%m-%d %H:%M") == "2026-03-04 09:00"


def test_build_schedule_window_includes_friday_review_saturday_humor_and_sunday_longread() -> None:
    now = datetime(2026, 3, 6, 8, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Friday
    slots = build_schedule_window(now, days=3, future_only=True)

    assert [item.publication_kind for item in slots] == ["daily", "weekly_review", "daily", "humor", "longread"]
    assert slots[1].publish_at_local.strftime("%H:%M") == "15:00"
    assert slots[2].publish_at_local.strftime("%H:%M") == "18:00"
    assert slots[3].publish_at_local.strftime("%H:%M") == "11:00"
    assert slots[4].publish_at_local.strftime("%H:%M") == "13:00"
    assert slots[4].longread_topic


def test_resolve_schedule_config_prefers_control_config() -> None:
    config = resolve_schedule_config(
        [
            {
                "key": "news.schedule.daily_morning",
                "enabled": True,
                "config": {"selected_time": "08:30", "options": ["08:00", "08:30", "09:00"]},
            },
            {
                "key": "news.schedule.longread",
                "enabled": True,
                "config": {"selected_time": "12:30", "topics": ["Тема A", "Тема B"]},
            },
        ]
    )

    assert schedule_slot_label(config.daily_morning_slot) == "08:30"
    assert config.daily_morning_options == ["08:00", "08:30", "09:00"]
    assert schedule_slot_label(config.longread_slot) == "12:30"
    assert config.longread_topics == ["Тема A", "Тема B"]


def test_publication_kind_from_format_type_maps_new_and_legacy_values() -> None:
    assert publication_kind_from_format_type("daily") == "daily"
    assert publication_kind_from_format_type("weekly_review") == "weekly_review"
    assert publication_kind_from_format_type("digest") == "weekly_review"
    assert publication_kind_from_format_type("deep") == "longread"
    assert publication_kind_from_format_type("humor") == "humor"
    assert publication_kind_from_format_type("manual_promo_offer") == "other"
