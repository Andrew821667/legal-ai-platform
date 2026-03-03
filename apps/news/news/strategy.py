from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from news.pipeline import parse_schedule_slots
from news.settings import settings

PUBLICATION_KIND_ORDER = ("daily", "weekly_review", "longread", "humor", "other")
PUBLICATION_KIND_LABELS = {
    "daily": "Ежедневный пост",
    "weekly_review": "Обзор недели",
    "longread": "Лонгрид",
    "humor": "Юмор",
    "other": "Прочее",
}
PUBLICATION_KIND_BADGES = {
    "daily": "🗞",
    "weekly_review": "🧭",
    "longread": "📚",
    "humor": "😄",
    "other": "📌",
}

_SCHEDULE_CONTROL_KEYS = {
    "daily_morning": "news.schedule.daily_morning",
    "daily_evening": "news.schedule.daily_evening",
    "weekly_review": "news.schedule.weekly_review",
    "longread": "news.schedule.longread",
    "humor": "news.schedule.humor",
}
_FORMAT_TYPE_BY_KIND = {
    "daily": "daily",
    "weekly_review": "weekly_review",
    "longread": "longread",
    "humor": "humor",
}
_CTA_TYPE_BY_KIND = {
    "daily": "soft",
    "weekly_review": "soft",
    "longread": "mid",
    "humor": "soft",
}
_LONGREAD_TOPIC_FALLBACK = (
    "AI для intake и первичной квалификации обращений",
    "Автоматизация договорной работы и redline-процессов",
    "AI-поиск по базе знаний и внутренним документам",
    "AI-комплаенс, privacy и governance для юрфункции",
)


@dataclass(slots=True)
class ScheduleConfig:
    daily_morning_enabled: bool
    daily_evening_enabled: bool
    weekly_review_enabled: bool
    longread_enabled: bool
    humor_enabled: bool
    daily_morning_slot: tuple[int, int]
    daily_evening_slot: tuple[int, int]
    weekly_review_slot: tuple[int, int]
    longread_slot: tuple[int, int]
    humor_slot: tuple[int, int]
    daily_morning_options: list[str]
    daily_evening_options: list[str]
    weekly_review_options: list[str]
    longread_options: list[str]
    humor_options: list[str]
    longread_topics: list[str]


@dataclass(slots=True)
class ScheduleSlot:
    day: date
    publish_at_local: datetime
    publication_kind: str
    longread_topic: str | None = None


@dataclass(slots=True)
class PostPlan:
    publish_at_local: datetime
    publication_kind: str
    format_type: str
    cta_type: str
    longread_topic: str | None = None


def publication_kind_label(kind: str) -> str:
    return PUBLICATION_KIND_LABELS.get(kind, PUBLICATION_KIND_LABELS["other"])


def publication_kind_badge(kind: str) -> str:
    return PUBLICATION_KIND_BADGES.get(kind, PUBLICATION_KIND_BADGES["other"])


def publication_kind_sort_key(kind: str) -> int:
    try:
        return PUBLICATION_KIND_ORDER.index(kind)
    except ValueError:
        return len(PUBLICATION_KIND_ORDER)


def publication_kind_from_format_type(format_type: str | None) -> str:
    normalized = str(format_type or "").strip().lower()
    if normalized in {"daily", "signal", "standard"}:
        return "daily"
    if normalized in {"weekly_review", "digest"}:
        return "weekly_review"
    if normalized in {"longread", "deep"}:
        return "longread"
    if normalized == "humor":
        return "humor"
    return "other"


def schedule_control_key(alias: str) -> str:
    return _SCHEDULE_CONTROL_KEYS[alias]


def schedule_control_keys() -> tuple[str, ...]:
    return tuple(_SCHEDULE_CONTROL_KEYS.values())


def schedule_aliases() -> tuple[str, ...]:
    return tuple(_SCHEDULE_CONTROL_KEYS)


def schedule_alias_meta(alias: str) -> dict[str, str]:
    mapping = {
        "daily_morning": {
            "label": "Будни: утренний слот",
            "kind": "daily",
            "window": "Пн-Пт, утро",
        },
        "daily_evening": {
            "label": "Будни: вечерний слот",
            "kind": "daily",
            "window": "Пн-Пт, вечер",
        },
        "weekly_review": {
            "label": "Пятничный обзор недели",
            "kind": "weekly_review",
            "window": "Пятница, 14:00-16:00",
        },
        "longread": {
            "label": "Воскресный лонгрид",
            "kind": "longread",
            "window": "Воскресенье, 12:00-14:00",
        },
        "humor": {
            "label": "Субботний юмористический пост",
            "kind": "humor",
            "window": "Суббота, 10:00-12:00",
        },
    }
    return mapping[alias]


def schedule_defaults() -> ScheduleConfig:
    return ScheduleConfig(
        daily_morning_enabled=True,
        daily_evening_enabled=True,
        weekly_review_enabled=True,
        longread_enabled=True,
        humor_enabled=True,
        daily_morning_slot=_parse_single_slot(settings.news_daily_morning_slot),
        daily_evening_slot=_parse_single_slot(settings.news_daily_evening_slot),
        weekly_review_slot=_parse_single_slot(settings.news_weekly_review_slot),
        longread_slot=_parse_single_slot(settings.news_longread_slot),
        humor_slot=_parse_single_slot(settings.news_humor_slot),
        daily_morning_options=list(settings.news_daily_morning_options_list),
        daily_evening_options=list(settings.news_daily_evening_options_list),
        weekly_review_options=list(settings.news_weekly_review_options_list),
        longread_options=list(settings.news_longread_options_list),
        humor_options=list(settings.news_humor_options_list),
        longread_topics=list(settings.news_longread_topics_list) or list(_LONGREAD_TOPIC_FALLBACK),
    )


def resolve_schedule_config(control_rows: list[dict[str, Any]] | None = None) -> ScheduleConfig:
    config = schedule_defaults()
    if not control_rows:
        return config

    row_map = {str(row.get("key") or ""): row for row in control_rows}
    _apply_schedule_row(config, row_map.get(schedule_control_key("daily_morning")), "daily_morning")
    _apply_schedule_row(config, row_map.get(schedule_control_key("daily_evening")), "daily_evening")
    _apply_schedule_row(config, row_map.get(schedule_control_key("weekly_review")), "weekly_review")
    _apply_schedule_row(config, row_map.get(schedule_control_key("longread")), "longread")
    _apply_schedule_row(config, row_map.get(schedule_control_key("humor")), "humor")
    return config


def build_schedule_window(
    now_local: datetime,
    *,
    days: int,
    control_rows: list[dict[str, Any]] | None = None,
    future_only: bool = True,
) -> list[ScheduleSlot]:
    config = resolve_schedule_config(control_rows)
    slots: list[ScheduleSlot] = []
    start_day = now_local.date()
    for day_offset in range(0, max(days, 1)):
        current_day = start_day + timedelta(days=day_offset)
        for publication_kind, slot_value, enabled in _day_slots(current_day, config):
            publish_at_local = datetime.combine(
                current_day,
                time(hour=slot_value[0], minute=slot_value[1]),
                tzinfo=now_local.tzinfo,
            )
            if future_only and publish_at_local <= now_local:
                continue
            if not enabled:
                continue
            slots.append(
                ScheduleSlot(
                    day=current_day,
                    publish_at_local=publish_at_local,
                    publication_kind=publication_kind,
                    longread_topic=_longread_topic_for_day(config.longread_topics, current_day)
                    if publication_kind == "longread"
                    else None,
                )
            )
    slots.sort(key=lambda item: item.publish_at_local)
    return slots


def build_publish_plan(
    now_local: datetime,
    count: int,
    control_rows: list[dict[str, Any]] | None = None,
) -> list[PostPlan]:
    plan: list[PostPlan] = []
    for slot in build_schedule_window(now_local, days=21, control_rows=control_rows, future_only=True):
        plan.append(
            PostPlan(
                publish_at_local=slot.publish_at_local,
                publication_kind=slot.publication_kind,
                format_type=_FORMAT_TYPE_BY_KIND[slot.publication_kind],
                cta_type=_CTA_TYPE_BY_KIND[slot.publication_kind],
                longread_topic=slot.longread_topic,
            )
        )
        if len(plan) >= count:
            break
    return plan


def schedule_slot_label(slot_value: tuple[int, int]) -> str:
    return f"{slot_value[0]:02d}:{slot_value[1]:02d}"


def _parse_single_slot(raw_value: str) -> tuple[int, int]:
    slots = parse_schedule_slots(raw_value)
    return slots[0]


def _parse_options(raw_options: list[str], fallback: tuple[int, int]) -> list[str]:
    normalized: list[str] = []
    for item in raw_options:
        try:
            normalized.append(schedule_slot_label(_parse_single_slot(item)))
        except Exception:
            continue
    fallback_label = schedule_slot_label(fallback)
    if fallback_label not in normalized:
        normalized.append(fallback_label)
    normalized.sort()
    return normalized


def _apply_schedule_row(config: ScheduleConfig, row: dict[str, Any] | None, alias: str) -> None:
    if row is None:
        return
    setattr(config, f"{alias}_enabled", bool(row.get("enabled", True)))
    payload = row.get("config") or {}
    if not isinstance(payload, dict):
        payload = {}

    selected_attr = f"{alias}_slot"
    options_attr = f"{alias}_options"
    current_slot = getattr(config, selected_attr)
    current_options = list(getattr(config, options_attr))

    selected_raw = str(payload.get("selected_time") or "").strip()
    selected_label = schedule_slot_label(current_slot)
    if selected_raw:
        try:
            selected_tuple = _parse_single_slot(selected_raw)
            selected_label = schedule_slot_label(selected_tuple)
            current_slot = selected_tuple
        except Exception:
            pass

    options_raw = payload.get("options")
    if isinstance(options_raw, list):
        current_options = _parse_options([str(item) for item in options_raw], current_slot)
    else:
        current_options = _parse_options(current_options, current_slot)

    if selected_label not in current_options:
        current_options.append(selected_label)
        current_options.sort()

    setattr(config, selected_attr, current_slot)
    setattr(config, options_attr, current_options)

    if alias == "longread":
        topics_raw = payload.get("topics")
        if isinstance(topics_raw, list):
            topics = [str(item).strip() for item in topics_raw if str(item).strip()]
            if topics:
                config.longread_topics = topics


def _day_slots(current_day: date, config: ScheduleConfig) -> list[tuple[str, tuple[int, int], bool]]:
    weekday = current_day.weekday()
    if weekday <= 4:
        slots = [
            ("daily", config.daily_morning_slot, config.daily_morning_enabled),
            ("daily", config.daily_evening_slot, config.daily_evening_enabled),
        ]
        if weekday == 4:
            slots.append(("weekly_review", config.weekly_review_slot, config.weekly_review_enabled))
        return slots
    if weekday == 5:
        return [("humor", config.humor_slot, config.humor_enabled)]
    return [("longread", config.longread_slot, config.longread_enabled)]


def _longread_topic_for_day(topics: list[str], current_day: date) -> str | None:
    pool = [item.strip() for item in topics if item.strip()]
    if not pool:
        pool = list(_LONGREAD_TOPIC_FALLBACK)
    if not pool:
        return None
    return pool[(current_day.toordinal() // 7) % len(pool)]
