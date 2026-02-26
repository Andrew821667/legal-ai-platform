from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from news.pipeline import parse_schedule_slots
from news.settings import settings

_WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_CTA_SEQUENCE_DEFAULT = "soft,soft,soft,soft,soft,soft,soft,mid,mid,hard"


@dataclass(slots=True)
class PostPlan:
    publish_at_local: datetime
    format_type: str
    cta_type: str


def _slots_by_weekday() -> dict[int, list[tuple[int, int]]]:
    weekdays = parse_schedule_slots(settings.news_weekday_slots)
    saturday = parse_schedule_slots(settings.news_saturday_slots) if settings.news_saturday_slots.strip() else []
    sunday = parse_schedule_slots(settings.news_sunday_slots) if settings.news_sunday_slots.strip() else []
    slots = {
        0: weekdays,
        1: weekdays,
        2: weekdays,
        3: weekdays,
        4: weekdays,
        5: saturday,
        6: sunday,
    }
    return slots


def _parse_deep_days(raw: str) -> set[int]:
    days: set[int] = set()
    for chunk in raw.split(","):
        item = chunk.strip().lower()
        if not item:
            continue
        if item.isdigit():
            day = int(item)
            if 0 <= day <= 6:
                days.add(day)
            continue
        if item in _WEEKDAY_NAMES:
            days.add(_WEEKDAY_NAMES.index(item))
    return days or {1, 3}


def _cta_sequence() -> list[str]:
    raw = settings.news_cta_sequence.strip() or _CTA_SEQUENCE_DEFAULT
    sequence = [item.strip().lower() for item in raw.split(",") if item.strip()]
    allowed = {"soft", "mid", "hard"}
    sequence = [item for item in sequence if item in allowed]
    return sequence or _CTA_SEQUENCE_DEFAULT.split(",")


def _format_for_slot(weekday: int, hour: int, slot_index_in_day: int, global_index: int, deep_days: set[int]) -> str:
    if weekday == settings.news_digest_weekday:
        return "digest"
    if hour >= 18:
        return "signal"
    if weekday in deep_days and slot_index_in_day == 0:
        return "deep"
    if global_index % 5 == 2:
        return "deep"
    return "standard"


def build_publish_plan(now_local: datetime, count: int, allow_alert_slot: bool) -> list[PostPlan]:
    slots_map = _slots_by_weekday()
    deep_days = _parse_deep_days(settings.news_deep_days)
    ctas = _cta_sequence()
    alert_slots = parse_schedule_slots(settings.news_alert_slot) if settings.news_alert_slot.strip() else []

    plan: list[PostPlan] = []
    for day_offset in range(0, 21):
        day = (now_local + timedelta(days=day_offset)).date()
        weekday = day.weekday()

        day_slots = list(slots_map.get(weekday, []))
        if (
            allow_alert_slot
            and settings.news_enable_alert_slot
            and weekday <= 4
            and settings.news_alert_slot.strip()
        ):
            day_slots.extend(alert_slots)
            day_slots = sorted(set(day_slots))

        for slot_index, (hour, minute) in enumerate(day_slots):
            publish_at_local = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=now_local.tzinfo)
            if publish_at_local <= now_local:
                continue
            if len(plan) >= count:
                return plan

            format_type = _format_for_slot(weekday, hour, slot_index, len(plan), deep_days)
            cta_type = ctas[len(plan) % len(ctas)]
            plan.append(PostPlan(publish_at_local=publish_at_local, format_type=format_type, cta_type=cta_type))

    return plan
