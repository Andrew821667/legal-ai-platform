from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from news.settings import settings
from news.strategy import build_publish_plan


def test_build_publish_plan_weekday_default_slots() -> None:
    original = {
        "news_weekday_slots": settings.news_weekday_slots,
        "news_saturday_slots": settings.news_saturday_slots,
        "news_sunday_slots": settings.news_sunday_slots,
        "news_alert_slot": settings.news_alert_slot,
        "news_enable_alert_slot": settings.news_enable_alert_slot,
        "news_digest_weekday": settings.news_digest_weekday,
        "news_deep_days": settings.news_deep_days,
        "news_cta_sequence": settings.news_cta_sequence,
    }
    try:
        settings.news_weekday_slots = "10:00,16:30"
        settings.news_saturday_slots = "11:00"
        settings.news_sunday_slots = ""
        settings.news_alert_slot = "19:00"
        settings.news_enable_alert_slot = True
        settings.news_digest_weekday = 5
        settings.news_deep_days = "tue,thu"
        settings.news_cta_sequence = "soft,mid,hard"

        now = datetime(2026, 2, 23, 9, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Monday
        plan = build_publish_plan(now_local=now, count=3, allow_alert_slot=False)

        assert len(plan) == 3
        assert plan[0].publish_at_local.hour == 10
        assert plan[1].publish_at_local.hour == 16
        assert plan[2].publish_at_local.date() > now.date()
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


def test_build_publish_plan_alert_slot_included() -> None:
    original = {
        "news_weekday_slots": settings.news_weekday_slots,
        "news_alert_slot": settings.news_alert_slot,
        "news_enable_alert_slot": settings.news_enable_alert_slot,
        "news_saturday_slots": settings.news_saturday_slots,
        "news_sunday_slots": settings.news_sunday_slots,
        "news_cta_sequence": settings.news_cta_sequence,
    }
    try:
        settings.news_weekday_slots = "10:00,16:30"
        settings.news_alert_slot = "19:00"
        settings.news_enable_alert_slot = True
        settings.news_saturday_slots = ""
        settings.news_sunday_slots = ""
        settings.news_cta_sequence = "soft,soft,hard"

        now = datetime(2026, 2, 23, 8, 0, tzinfo=ZoneInfo("Europe/Moscow"))  # Monday
        plan = build_publish_plan(now_local=now, count=3, allow_alert_slot=True)

        assert len(plan) == 3
        assert [item.publish_at_local.hour for item in plan] == [10, 16, 19]
        assert [item.cta_type for item in plan] == ["soft", "soft", "hard"]
    finally:
        for key, value in original.items():
            setattr(settings, key, value)
