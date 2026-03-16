from __future__ import annotations

from datetime import datetime, timezone

from news.queue_ui import build_auto_queue_text, build_manual_queue_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def _publish_at_utc(row: dict[str, object]) -> datetime | None:
    raw = str(row.get("publish_at") or "").strip()
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_build_auto_queue_text_non_empty_and_empty() -> None:
    non_empty = build_auto_queue_text(
        total=2,
        rows=[
            {
                "title": "Пост 1",
                "publish_at": "2026-03-09T08:00:00+00:00",
                "kind": "daily",
                "pillar": "implementation",
                "format_label": "Ежедневный",
            },
            {
                "title": "Пост 2",
                "publish_at": "2026-03-09T19:00:00+00:00",
                "kind": "weekly_review",
                "pillar": "regulation",
                "format_label": "Обзор недели",
            },
        ],
        offset=0,
        overdue=1,
        queue_filter="all",
        theme_filter="all",
        tz_name="Europe/Moscow",
        generate_morning="07:30",
        generate_evening="16:30",
        publish_interval_label="каждые 30 мин",
        schedule_daily_morning_label="10:00",
        schedule_daily_evening_label="18:00",
        schedule_weekly_review_label="18:00",
        schedule_humor_label="12:00",
        schedule_longread_label="14:00",
        publication_kind_label=lambda kind: {"daily": "Ежедневный", "weekly_review": "Обзор"}[kind],
        publication_kind_badge=lambda kind: {"daily": "🤖", "weekly_review": "📚"}[kind],
        pillar_display=lambda value: value,
        pillar_label=lambda value: {"implementation": "Implementation", "regulation": "Regulation"}[value],
        post_format_label=lambda row: str(row.get("format_label") or "n/a"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        row_pillar=lambda row: str(row.get("pillar") or "implementation"),
        publish_at_utc=_publish_at_utc,
        screen_guide=_screen_guide_stub,
    )
    assert "Автоочередь публикации" in non_empty
    assert "Фильтр: Все публикации" in non_empty
    assert "Просрочено: 1" in non_empty
    assert "2026-03-09" in non_empty
    assert "1. 11:00 🤖 Ежедневный — Пост 1" in non_empty

    empty = build_auto_queue_text(
        total=0,
        rows=[],
        offset=0,
        overdue=0,
        queue_filter="daily",
        theme_filter="all",
        tz_name="Europe/Moscow",
        generate_morning="07:30",
        generate_evening="16:30",
        publish_interval_label="каждые 30 мин",
        schedule_daily_morning_label="10:00",
        schedule_daily_evening_label="18:00",
        schedule_weekly_review_label="18:00",
        schedule_humor_label="12:00",
        schedule_longread_label="14:00",
        publication_kind_label=lambda kind: {"daily": "Ежедневный"}[kind],
        publication_kind_badge=lambda kind: {"daily": "🤖"}[kind],
        pillar_display=lambda value: value,
        pillar_label=lambda value: value,
        post_format_label=lambda row: str(row),
        row_publication_kind=lambda row: str(row),
        row_pillar=lambda row: str(row),
        publish_at_utc=lambda row: None,
        screen_guide=_screen_guide_stub,
    )
    assert "В очереди публикации сейчас нет постов." in empty


def test_build_manual_queue_text_non_empty_and_empty() -> None:
    now_value = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    non_empty = build_manual_queue_text(
        total=2,
        rows=[
            {
                "title": "Пост 1",
                "publish_at": "2026-03-09T11:00:00+00:00",
                "kind": "daily",
                "pillar": "implementation",
                "format_label": "Ежедневный",
            },
            {
                "title": "Пост 2",
                "publish_at": "2026-03-09T14:00:00+00:00",
                "kind": "longread",
                "pillar": "case",
                "format_label": "Лонгрид",
            },
        ],
        offset=0,
        queue_filter="due",
        due_total=1,
        scheduled_total=2,
        theme_filter="all",
        now_utc=now_value,
        publication_kind_label=lambda kind: {"daily": "Ежедневный", "longread": "Лонгрид"}[kind],
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}[kind],
        pillar_display=lambda value: value,
        pillar_label=lambda value: {"implementation": "Implementation", "case": "Case"}[value],
        post_format_label=lambda row: str(row.get("format_label") or "n/a"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        row_pillar=lambda row: str(row.get("pillar") or "implementation"),
        publish_at_utc=_publish_at_utc,
        screen_guide=_screen_guide_stub,
    )
    assert "Ручная очередь публикации (расширенный режим)" in non_empty
    assert "К публикации сейчас: 1 из 2" in non_empty
    assert "1. ⚡ 🤖 Пост 1" in non_empty
    assert "2. 🕒 📚 Пост 2" in non_empty

    empty = build_manual_queue_text(
        total=0,
        rows=[],
        offset=0,
        queue_filter="all",
        due_total=0,
        scheduled_total=0,
        theme_filter="all",
        publication_kind_label=lambda kind: kind,
        publication_kind_badge=lambda kind: kind,
        pillar_display=lambda value: value,
        pillar_label=lambda value: value,
        post_format_label=lambda row: str(row),
        row_publication_kind=lambda row: str(row),
        row_pillar=lambda row: str(row),
        publish_at_utc=lambda row: None,
        screen_guide=_screen_guide_stub,
    )
    assert "Сейчас записей нет." in empty
