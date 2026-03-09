from __future__ import annotations

from news.themes_keyboard_ui import (
    build_theme_posts_keyboard_rows,
    build_themes_archive_keyboard_rows,
    build_themes_daily_keyboard_rows,
    build_themes_keyboard_rows,
)


def _inline_button(text: str, callback_data: str | None = None, *, style: str | None = None) -> dict[str, str | None]:
    return {"text": text, "callback_data": callback_data, "style": style}


def _submenu_nav_rows(*, back_callback: str, back_label: str = "🔙 Назад") -> list[list[dict[str, str | None]]]:
    return [
        [_inline_button(back_label, callback_data=back_callback)],
        [_inline_button("🏠 Рабочий стол", callback_data="refresh")],
    ]


def _two_column_rows(buttons: list[dict[str, str | None]]) -> list[list[dict[str, str | None]]]:
    rows: list[list[dict[str, str | None]]] = []
    for idx in range(0, len(buttons), 2):
        rows.append(buttons[idx : idx + 2])
    return rows


def _callbacks(rows: list[list[dict[str, str | None]]]) -> list[str]:
    result: list[str] = []
    for row in rows:
        for button in row:
            value = button.get("callback_data")
            if value:
                result.append(value)
    return result


def test_build_themes_keyboard_rows() -> None:
    rows = build_themes_keyboard_rows(
        counts={"regulation": 2, "case": 1, "implementation": 3, "tools": 0, "market": 1},
        generation_themes_total=10,
        enabled_generation_themes_count=6,
        active_longread_topics_count=4,
        longread_topics_total=7,
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "thm:daily" in callbacks
    assert "lt:menu" in callbacks
    assert "thm:archive" in callbacks
    assert "sec:generate" in callbacks
    assert "refresh" in callbacks


def test_build_themes_daily_keyboard_rows() -> None:
    rows = build_themes_daily_keyboard_rows(
        generation_theme_keys=["legal", "market"],
        generation_theme_counts={"legal": 11, "market": 4},
        enabled_generation_themes={"legal"},
        generation_theme_label=lambda key: {"legal": "Юридическая AI-тема", "market": "Рынок"}[key],
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "gt:bulk:on" in callbacks
    assert "gt:bulk:profile" in callbacks
    assert "gt:legal" in callbacks
    assert "gt:market" in callbacks
    assert "lt:menu" in callbacks
    assert "sec:themes" in callbacks


def test_build_themes_archive_keyboard_rows() -> None:
    rows = build_themes_archive_keyboard_rows(
        pillar_keys=["regulation", "case", "implementation"],
        counts={"regulation": 2, "case": 4, "implementation": 3},
        pillar_display=lambda key: {"regulation": "⚖️ Regulation", "case": "📚 Case", "implementation": "⚙️ Impl"}[key],
        inline_button=_inline_button,
        two_column_rows=_two_column_rows,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "th:regulation:0" in callbacks
    assert "th:case:0" in callbacks
    assert "th:implementation:0" in callbacks
    assert "sec:themes" in callbacks


def test_build_theme_posts_keyboard_rows() -> None:
    rows = build_theme_posts_keyboard_rows(
        pillar="case",
        total=20,
        rows=[
            {"id": "p1", "title": "Пост 1", "status": "review", "kind": "daily"},
            {"id": "p2", "title": "Пост 2", "status": "scheduled", "kind": "longread"},
        ],
        offset=8,
        page_size=8,
        status_badge=lambda status: {"review": "🟡", "scheduled": "✅"}.get(status, "•"),
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}.get(kind, "•"),
        publication_kind_resolver=lambda row: str(row.get("kind") or "daily"),
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "pv:p1:th_case:8" in callbacks
    assert "pv:p2:th_case:8" in callbacks
    assert "th:case:0" in callbacks
    assert "th:case:16" in callbacks
    assert "sec:themes" in callbacks
