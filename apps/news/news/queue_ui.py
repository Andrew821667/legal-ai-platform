from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo


ScreenGuide = Callable[[str, list[str]], str]


def build_auto_queue_text(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    overdue: int,
    queue_filter: str,
    theme_filter: str = "all",
    tz_name: str,
    generate_morning: str,
    generate_evening: str,
    publish_interval_label: str,
    schedule_daily_morning_label: str,
    schedule_daily_evening_label: str,
    schedule_weekly_review_label: str,
    schedule_humor_label: str,
    schedule_longread_label: str,
    publication_kind_label: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    pillar_display: Callable[[str], str],
    pillar_label: Callable[[str], str],
    post_format_label: Callable[[dict[str, Any]], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    row_pillar: Callable[[dict[str, Any]], str],
    publish_at_utc: Callable[[dict[str, Any]], datetime | None],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    tz = ZoneInfo(tz_name)
    filter_label = "Все публикации" if queue_filter == "all" else publication_kind_label(queue_filter)
    theme_label = "Все темы" if theme_filter == "all" else pillar_display(theme_filter)
    lines = [
        "Автоочередь публикации",
        "",
        guide(
            "Автоматическая очередь постов на публикацию с фильтрами по виду и теме.",
            [
                "Используйте фильтры, чтобы быстро отобрать нужный тип публикаций.",
                "Открывайте карточку поста для ручных правок или немедленной публикации.",
                "Переходите в «Календарь/Время слотов/Ритм» для корректировки расписания.",
            ],
        ),
        "",
        f"Фильтр: {filter_label}",
        f"Тема: {theme_label}",
        f"Автогенерация: {generate_morning} и {generate_evening}",
        f"Автопубликация: {publish_interval_label}",
        f"Всего на публикацию: {total}",
        f"Просрочено: {overdue}",
        "",
        "Текущая сетка:",
        f"• Пн-Пт: {schedule_daily_morning_label} и {schedule_daily_evening_label}",
        f"• Пятница: обзор недели в {schedule_weekly_review_label}",
        f"• Суббота: практика недели в {schedule_humor_label}",
        f"• Воскресенье: лонгрид в {schedule_longread_label}",
        "",
    ]
    if not rows:
        lines.append("В очереди публикации сейчас нет постов.")
        return "\n".join(lines)

    current_day = ""
    for idx, row in enumerate(rows, start=offset + 1):
        publish_at = publish_at_utc(row)
        if publish_at is None:
            continue
        local_dt = publish_at.astimezone(tz)
        day_label = local_dt.strftime("%Y-%m-%d")
        if day_label != current_day:
            current_day = day_label
            lines.extend(["", day_label])
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        kind = row_publication_kind(row)
        pillar = row_pillar(row)
        format_label = post_format_label(row)
        lines.append(
            f"{idx}. {local_dt.strftime('%H:%M')} {publication_kind_badge(kind)} {publication_kind_label(kind)} — {title[:68]}"
        )
        lines.append(f"   🧭 {pillar_label(pillar)} | {format_label}")
    return "\n".join(lines)


def build_manual_queue_text(
    *,
    total: int,
    rows: list[dict[str, Any]],
    offset: int,
    queue_filter: str,
    due_total: int,
    scheduled_total: int,
    theme_filter: str = "all",
    now_utc: datetime | None = None,
    publication_kind_label: Callable[[str], str],
    publication_kind_badge: Callable[[str], str],
    pillar_display: Callable[[str], str],
    pillar_label: Callable[[str], str],
    post_format_label: Callable[[dict[str, Any]], str],
    row_publication_kind: Callable[[dict[str, Any]], str],
    row_pillar: Callable[[dict[str, Any]], str],
    publish_at_utc: Callable[[dict[str, Any]], datetime | None],
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    current_utc = now_utc or datetime.now(timezone.utc)
    filter_label = "к публикации сейчас" if queue_filter == "due" else "все на публикацию"
    theme_label = "Все темы" if theme_filter == "all" else pillar_display(theme_filter)

    if not rows:
        return (
            "Ручная очередь публикации (расширенный режим)\n\n"
            + guide(
                "Ручной контур публикации готовых постов.",
                [
                    "Режим «К публикации сейчас» показывает due-посты для немедленного выхода.",
                    "Доступны пакетные режимы: страница / топ-3 / топ-5.",
                ],
            )
            + "\n\n"
            f"Фильтр: {filter_label}\n"
            f"Тема: {theme_label}\n"
            f"К публикации сейчас: {due_total} из {scheduled_total}\n\n"
            "Сейчас записей нет."
        )

    lines = [
        "Ручная очередь публикации (расширенный режим)",
        "",
        guide(
            "Ручной контур публикации готовых постов.",
            [
                "Режим «К публикации сейчас» показывает due-посты для немедленного выхода.",
                "Доступны пакетные режимы: страница / топ-3 / топ-5.",
            ],
        ),
        "",
        f"Фильтр: {filter_label}",
        f"Тема: {theme_label}",
        f"К публикации сейчас: {due_total} из {scheduled_total}",
        "Режимы топ-3/топ-5 доступны только в фильтре «К публикации сейчас».",
        "",
    ]
    for idx, row in enumerate(rows, start=offset + 1):
        title = str(row.get("title") or "Без заголовка").replace("\n", " ")
        publish_at = str(row.get("publish_at") or "")
        publish_at_value = publish_at_utc(row)
        due_mark = "⚡" if publish_at_value and publish_at_value <= current_utc else "🕒"
        publication_kind = row_publication_kind(row)
        pillar = row_pillar(row)
        format_label = post_format_label(row)
        lines.append(f"{idx}. {due_mark} {publication_kind_badge(publication_kind)} {title[:84]}")
        lines.append(
            f"   ⏰ {publish_at} | {publication_kind_label(publication_kind)} | 🧭 {pillar_label(pillar)} | {format_label}"
        )
    return "\n".join(lines)
