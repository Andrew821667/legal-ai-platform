from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from news.rss_fetcher import RSSSourceResult


@dataclass(frozen=True, slots=True)
class SourceHealth:
    total: int
    working: int
    empty: int
    failed: int
    problem_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DailyReportSnapshot:
    now_local: datetime
    source_health: SourceHealth
    telegram_channels: int
    telegram_items: int | None
    telegram_checked_at: datetime | None
    telegram_stale: bool
    worker_active: int
    worker_total: int
    inactive_workers: tuple[str, ...]
    published_24h: int
    failed_24h: int
    review_count: int
    ready_count: int
    scheduled_count: int
    publishing_count: int
    next_publish: str
    generation_state: str


def daily_report_due(
    now_utc: datetime,
    *,
    last_report_date: str,
    tz_name: str,
    hour: int,
    minute: int,
) -> bool:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    now_local = now_utc.astimezone(ZoneInfo(tz_name))
    if last_report_date == now_local.date().isoformat():
        return False
    scheduled = now_local.replace(
        hour=max(0, min(hour, 23)),
        minute=max(0, min(minute, 59)),
        second=0,
        microsecond=0,
    )
    return now_local >= scheduled


def persisted_report_date(
    workers: Sequence[Mapping[str, Any]],
    *,
    worker_id: str,
) -> str:
    row = next(
        (item for item in workers if str(item.get("worker_id") or "") == worker_id),
        None,
    )
    info = (row or {}).get("info") or {}
    if not isinstance(info, Mapping):
        return ""
    return str(info.get("last_daily_report_date") or "").strip()


def summarize_sources(
    rows: Sequence[RSSSourceResult],
    *,
    names_by_url: Mapping[str, str],
) -> SourceHealth:
    working = [row for row in rows if row.available and row.entry_count > 0]
    empty = [row for row in rows if row.available and row.entry_count == 0]
    failed = [row for row in rows if not row.available]
    problems = [
        names_by_url.get(row.source_url, row.source_url)
        for row in (*failed, *empty)
    ]
    return SourceHealth(
        total=len(rows),
        working=len(working),
        empty=len(empty),
        failed=len(failed),
        problem_names=tuple(problems),
    )


def count_recent_posts(
    rows: Sequence[Mapping[str, Any]],
    *,
    now_utc: datetime,
    hours: int = 24,
) -> int:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    cutoff = now_utc - timedelta(hours=max(1, hours))
    return sum(
        1
        for row in rows
        if (stamp := _post_datetime(row)) is not None and stamp >= cutoff
    )


def latest_worker_event(
    payload: Mapping[str, Any],
    *,
    actions: set[str],
) -> Mapping[str, Any] | None:
    rows = payload.get("entries") or []
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping) and str(row.get("action") or "") in actions
    ]
    return max(matches, key=lambda row: _event_datetime(row) or datetime.min.replace(tzinfo=UTC), default=None)


def event_datetime(row: Mapping[str, Any] | None) -> datetime | None:
    return _event_datetime(row or {})


def build_daily_report_text(snapshot: DailyReportSnapshot) -> str:
    source = snapshot.source_health
    reserve = snapshot.ready_count + snapshot.scheduled_count
    problems: list[str] = []
    if source.working == 0:
        problems.append("нет работающих RSS-источников")
    elif source.failed or source.empty:
        problems.append("часть RSS-источников требует проверки")
    if snapshot.telegram_stale:
        problems.append("Telegram-сбор не дал свежего результата")
    if snapshot.inactive_workers:
        problems.append("не все критические воркеры активны")
    if reserve == 0:
        problems.append("очередь публикаций пуста")
    if snapshot.failed_24h:
        problems.append("есть ошибки публикации за 24 часа")

    critical = source.working == 0 or reserve == 0 or bool(snapshot.inactive_workers) or snapshot.failed_24h > 0
    if critical:
        status = "ТРЕБУЕТСЯ ВМЕШАТЕЛЬСТВО"
    elif problems:
        status = "НУЖЕН КОНТРОЛЬ"
    else:
        status = "СИСТЕМА РАБОТАЕТ ШТАТНО"

    checked = _format_local(snapshot.telegram_checked_at, snapshot.now_local.tzinfo)
    if snapshot.telegram_items is None:
        telegram_line = f"• Telegram: {snapshot.telegram_channels} каналов настроено; свежего цикла за 24ч нет"
    else:
        telegram_line = (
            f"• Telegram: {snapshot.telegram_channels} каналов; "
            f"последний сбор {snapshot.telegram_items} материалов ({checked})"
        )

    problem_lines = ""
    if source.problem_names:
        names = ", ".join(source.problem_names[:6])
        suffix = f" и еще {len(source.problem_names) - 6}" if len(source.problem_names) > 6 else ""
        problem_lines = f"\n• Проблемные RSS: {names}{suffix}"

    inactive_line = ""
    if snapshot.inactive_workers:
        inactive_line = f"\n• Неактивны: {', '.join(snapshot.inactive_workers)}"

    action_lines = ""
    if problems:
        action_lines = "\n\nЧто проверить:\n" + "\n".join(f"• {item}" for item in problems)

    return (
        "Ежедневный отчет AI Verdict\n"
        f"{snapshot.now_local.strftime('%d.%m.%Y %H:%M')} МСК\n\n"
        f"Состояние: {status}\n\n"
        "Источники\n"
        f"• RSS: {source.working}/{source.total} работают; "
        f"пустых {source.empty}; ошибок {source.failed}\n"
        f"{telegram_line}"
        f"{problem_lines}\n\n"
        "Контент за 24 часа\n"
        f"• Опубликовано: {snapshot.published_24h}\n"
        f"• Ошибок публикации: {snapshot.failed_24h}\n"
        f"• Последняя генерация: {snapshot.generation_state}\n\n"
        "Очередь\n"
        f"• Запас: {reserve} (готовых {snapshot.ready_count}, запланированных {snapshot.scheduled_count})\n"
        f"• На проверке: {snapshot.review_count}\n"
        f"• В публикации: {snapshot.publishing_count}\n"
        f"• Следующая публикация: {snapshot.next_publish}\n\n"
        "Сервисы\n"
        f"• Критические воркеры: {snapshot.worker_active}/{snapshot.worker_total} активны"
        f"{inactive_line}"
        f"{action_lines}"
    )


def _post_datetime(row: Mapping[str, Any]) -> datetime | None:
    for key in ("posted_at", "published_at", "updated_at", "publish_at", "created_at"):
        if parsed := _parse_datetime(row.get(key)):
            return parsed
    return None


def _event_datetime(row: Mapping[str, Any]) -> datetime | None:
    return _parse_datetime(row.get("occurred_at"))


def _parse_datetime(raw: object) -> datetime | None:
    if isinstance(raw, datetime):
        parsed = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_local(value: datetime | None, tzinfo: object) -> str:
    if value is None:
        return "время неизвестно"
    return value.astimezone(tzinfo).strftime("%d.%m %H:%M")
