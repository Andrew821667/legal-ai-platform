from __future__ import annotations

from news.posts_keyboard_ui import build_posts_keyboard_rows, build_review_posts_keyboard_rows


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


def test_build_posts_keyboard_rows() -> None:
    rows = build_posts_keyboard_rows(
        total=20,
        rows=[
            {"id": "p1", "title": "Пост 1", "status": "draft", "kind": "daily"},
            {"id": "p2", "title": "Пост 2", "status": "draft", "kind": "longread"},
        ],
        offset=8,
        status="draft",
        page_size=8,
        status_badge=lambda status: {"draft": "📝"}[status],
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}[kind],
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "pv:p1:draft:8" in callbacks
    assert "pv:p2:draft:8" in callbacks
    assert "ba:review:draft:8" in callbacks
    assert "pl:draft:0" in callbacks
    assert "pl:draft:16" in callbacks
    assert "pl:draft:8" in callbacks
    assert "sec:worklists" in callbacks


def test_build_review_posts_keyboard_rows() -> None:
    rows = build_review_posts_keyboard_rows(
        total=20,
        rows=[
            {"id": "p1", "title": "Пост 1", "format_type": "operator_ai_daily", "kind": "daily"},
            {"id": "p2", "title": "Пост 2", "format_type": "manual_longread", "kind": "longread"},
        ],
        offset=8,
        review_filter="all",
        kind_filter="all",
        theme_filter="all",
        page_size=8,
        pillar_keys=["regulation", "case"],
        pillar_display=lambda pillar: {"regulation": "⚖️ Regulation", "case": "📚 Case"}[pillar],
        review_origin_badge=lambda value: "🤖" if "operator_ai" in value else "✍️",
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}[kind],
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        inline_button=_inline_button,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "rv:all:all:all:0" in callbacks
    assert "rv:ai:all:all:0" in callbacks
    assert "rv:manual:all:all:0" in callbacks
    assert "rv:all:daily:all:0" in callbacks
    assert "rv:all:all:regulation:0" in callbacks
    assert "pv:p1:review:8" in callbacks
    assert "pv:p2:review:8" in callbacks
    assert "ba:ready:review:8" in callbacks
    assert "rv:all:all:all:16" in callbacks
    assert "rv:all:all:all:8" in callbacks
    assert "sec:worklists" in callbacks
