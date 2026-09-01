from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from news.active_queue import parse_post_datetime, row_publication_kind
from news.strategy import build_schedule_window

MONITOR_WORKER_ID = "news-publication-monitor"
_ACTIVE_STATUSES = ("review", "ready", "scheduled", "publishing")


@dataclass(frozen=True)
class PublicationAlert:
    keys: tuple[str, ...]
    text: str


def _slot_key(value: datetime) -> str:
    return value.replace(second=0, microsecond=0).isoformat()


def _publish_enabled(control_rows: list[dict[str, Any]]) -> bool:
    row = next(
        (item for item in control_rows if str(item.get("key") or "") == "news.publish.enabled"),
        None,
    )
    return row is None or bool(row.get("enabled", True))


def _schedule_slots(
    now_utc: datetime,
    *,
    control_rows: list[dict[str, Any]],
    tz_name: str,
    lookback_hours: int,
    warning_minutes: int,
) -> list[Any]:
    tz = ZoneInfo(tz_name)
    now_local = now_utc.astimezone(tz)
    start_local = now_local - timedelta(hours=max(lookback_hours, 1))
    end_local = now_local + timedelta(minutes=max(warning_minutes, 1))
    day_count = max(2, (end_local.date() - start_local.date()).days + 1)
    return [
        slot
        for slot in build_schedule_window(
            start_local,
            days=day_count,
            control_rows=control_rows,
            future_only=False,
        )
        if start_local <= slot.publish_at_local <= end_local
    ]


def _posted_slot_keys(rows: list[dict[str, Any]], tz_name: str) -> set[str]:
    tz = ZoneInfo(tz_name)
    keys: set[str] = set()
    for row in rows:
        if publish_at := parse_post_datetime(row.get("publish_at")):
            keys.add(_slot_key(publish_at.astimezone(tz)))
    return keys


def _worker_state(workers: list[dict[str, Any]], worker_id: str) -> str:
    row = next((item for item in workers if str(item.get("worker_id") or "") == worker_id), None)
    if row is None:
        return "heartbeat не найден"
    return "работает" if bool(row.get("active")) else "heartbeat устарел"


def _queue_counts(posts_by_status: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {status: len(posts_by_status.get(status) or []) for status in _ACTIVE_STATUSES}


def _queue_line(counts: dict[str, int]) -> str:
    return (
        "Очередь: на проверке "
        f"{counts['review']}, готовых {counts['ready']}, "
        f"запланированных {counts['scheduled']}, в публикации {counts['publishing']}."
    )


def _format_slot(value: datetime) -> str:
    return value.strftime("%d.%m в %H:%M")


def acknowledged_alert_keys(workers: list[dict[str, Any]]) -> set[str]:
    row = next(
        (item for item in workers if str(item.get("worker_id") or "") == MONITOR_WORKER_ID),
        None,
    )
    info = (row or {}).get("info") or {}
    raw = info.get("alerted_keys") if isinstance(info, dict) else []
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw if str(item).strip()}


def build_publication_alerts(
    *,
    now_utc: datetime,
    control_rows: list[dict[str, Any]],
    posts_by_status: dict[str, list[dict[str, Any]]],
    workers: list[dict[str, Any]],
    acknowledged_keys: set[str],
    tz_name: str,
    grace_minutes: int,
    warning_minutes: int,
    lookback_hours: int,
) -> list[PublicationAlert]:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    if not _publish_enabled(control_rows):
        return []

    tz = ZoneInfo(tz_name)
    now_local = now_utc.astimezone(tz)
    slots = _schedule_slots(
        now_utc,
        control_rows=control_rows,
        tz_name=tz_name,
        lookback_hours=lookback_hours,
        warning_minutes=warning_minutes,
    )
    posted = _posted_slot_keys(posts_by_status.get("posted") or [], tz_name)
    counts = _queue_counts(posts_by_status)
    alerts: list[PublicationAlert] = []

    missed: list[tuple[str, datetime]] = []
    cutoff = now_local - timedelta(minutes=max(grace_minutes, 1))
    for slot in slots:
        key = f"missed:{_slot_key(slot.publish_at_local)}"
        if slot.publish_at_local <= cutoff and _slot_key(slot.publish_at_local) not in posted:
            if key not in acknowledged_keys:
                missed.append((key, slot.publish_at_local))

    if missed:
        slot_lines = "\n".join(f"• {_format_slot(value)}" for _, value in missed[-4:])
        text = (
            "Канал пропустил плановую публикацию.\n\n"
            f"Пропущенные слоты:\n{slot_lines}\n\n"
            f"{_queue_line(counts)}\n"
            f"Генератор: {_worker_state(workers, 'news-generate')}. "
            f"Публикатор: {_worker_state(workers, 'news-publish')}.\n\n"
            "Проверка выполнена автоматически. Откройте очередь в боте-модераторе."
        )
        alerts.append(PublicationAlert(tuple(key for key, _ in missed), text))

    upcoming = next((slot for slot in slots if slot.publish_at_local > now_local), None)
    if upcoming is not None:
        key = f"reserve:{_slot_key(upcoming.publish_at_local)}"
        remaining = upcoming.publish_at_local - now_local
        active_for_kind = [
            row
            for status in _ACTIVE_STATUSES
            for row in posts_by_status.get(status) or []
            if row_publication_kind(row) == upcoming.publication_kind
        ]
        if (
            remaining <= timedelta(minutes=max(warning_minutes, 1))
            and not active_for_kind
            and key not in acknowledged_keys
        ):
            minutes = max(1, int(remaining.total_seconds() // 60))
            text = (
                f"До публикации {_format_slot(upcoming.publish_at_local)} осталось {minutes} мин., "
                "но подходящего материала в резерве нет.\n\n"
                f"{_queue_line(counts)}\n"
                f"Генератор: {_worker_state(workers, 'news-generate')}. "
                f"Публикатор: {_worker_state(workers, 'news-publish')}.\n\n"
                "Проверка выполнена автоматически."
            )
            alerts.append(PublicationAlert((key,), text))

    return alerts
