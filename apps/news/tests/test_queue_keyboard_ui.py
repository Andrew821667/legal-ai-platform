from __future__ import annotations

from news.queue_keyboard_ui import build_auto_queue_keyboard_rows, build_manual_queue_keyboard_rows


def _inline_button(text: str, callback_data: str | None = None, *, style: str | None = None) -> dict[str, str | None]:
    return {"text": text, "callback_data": callback_data, "style": style}


def _submenu_nav_rows(*, back_callback: str, back_label: str = "🔙 Назад") -> list[list[dict[str, str | None]]]:
    return [
        [_inline_button(back_label, callback_data=back_callback)],
        [_inline_button("🏠 Рабочий стол", callback_data="refresh")],
    ]


def _callbacks(rows: list[list[dict[str, str | None]]]) -> list[str]:
    result: list[str] = []
    for row in rows:
        for button in row:
            value = button.get("callback_data")
            if value:
                result.append(value)
    return result


def test_build_auto_queue_keyboard_rows() -> None:
    rows = build_auto_queue_keyboard_rows(
        total=20,
        rows=[
            {"id": "p1", "title": "Пост 1", "kind": "daily"},
            {"id": "p2", "title": "Пост 2", "kind": "weekly_review"},
        ],
        offset=8,
        queue_filter="all",
        theme_filter="all",
        page_size=8,
        pillar_keys=["regulation", "case"],
        pillar_display=lambda key: {"regulation": "⚖️ Регулирование", "case": "📚 Кейсы"}[key],
        publication_kind_badge=lambda kind: {"daily": "🤖", "weekly_review": "📚"}.get(kind, "•"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        auto_queue_context=lambda queue_filter, theme_filter: f"aq_{queue_filter}_{theme_filter}",
        inline_button=_inline_button,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "aq:all:all:0" in callbacks
    assert "aq:daily:all:0" in callbacks
    assert "aq:all:regulation:0" in callbacks
    assert "pv:p1:aq_all_all:8" in callbacks
    assert "pv:p2:aq_all_all:8" in callbacks
    assert "aq:all:all:0" in callbacks
    assert "aq:all:all:16" in callbacks
    assert "cal:summary" in callbacks
    assert "sch:menu" in callbacks
    assert "int:menu" in callbacks
    assert "refresh" in callbacks


def test_build_manual_queue_keyboard_rows_due_and_all() -> None:
    due_rows = build_manual_queue_keyboard_rows(
        total=20,
        rows=[
            {"id": "p1", "title": "Пост 1", "kind": "daily"},
            {"id": "p2", "title": "Пост 2", "kind": "longread"},
        ],
        offset=8,
        queue_filter="due",
        theme_filter="all",
        page_size=8,
        pillar_keys=["regulation", "case"],
        pillar_display=lambda key: {"regulation": "⚖️ Регулирование", "case": "📚 Кейсы"}[key],
        queue_context=lambda queue_filter, theme_filter: f"mq_{queue_filter}_{theme_filter}",
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}.get(kind, "•"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        inline_button=_inline_button,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    due_callbacks = _callbacks(due_rows)
    assert "mq:due:all:0" in due_callbacks
    assert "mq:all:all:0" in due_callbacks
    assert "pv:p1:mq_due_all:8" in due_callbacks
    assert "mbp:due:8:page" in due_callbacks
    assert "mbp:due:8:top3" in due_callbacks
    assert "mbp:due:8:top5" in due_callbacks
    assert "mq:due:all:0" in due_callbacks
    assert "mq:due:all:16" in due_callbacks
    assert "sec:worklists" in due_callbacks

    all_rows = build_manual_queue_keyboard_rows(
        total=20,
        rows=[{"id": "p1", "title": "Пост 1", "kind": "daily"}],
        offset=0,
        queue_filter="all",
        theme_filter="all",
        page_size=8,
        pillar_keys=["regulation"],
        pillar_display=lambda key: {"regulation": "⚖️ Регулирование"}[key],
        queue_context=lambda queue_filter, theme_filter: f"mq_{queue_filter}_{theme_filter}",
        publication_kind_badge=lambda kind: {"daily": "🤖"}.get(kind, "•"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        inline_button=_inline_button,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    all_callbacks = _callbacks(all_rows)
    assert "mbp:all:0:page" in all_callbacks
    assert "mbp:all:0:top3" not in all_callbacks
