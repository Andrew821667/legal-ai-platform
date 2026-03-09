from __future__ import annotations

from news.create_keyboard_ui import (
    build_create_draft_keyboard_rows,
    build_create_kind_keyboard_rows,
    build_create_link_keyboard_rows,
    build_create_media_keyboard_rows,
    build_create_start_keyboard_rows,
    build_create_theme_keyboard_rows,
)


def _inline_button(text: str, callback_data: str | None = None, *, style: str | None = None) -> dict[str, str | None]:
    return {"text": text, "callback_data": callback_data, "style": style}


def _two_column_rows(buttons: list[dict[str, str | None]]) -> list[list[dict[str, str | None]]]:
    return [buttons[index : index + 2] for index in range(0, len(buttons), 2)]


def _submenu_nav_rows(*, back_callback: str, back_label: str = "🔙 Назад") -> list[list[dict[str, str | None]]]:
    return [
        [_inline_button(back_label, callback_data=back_callback)],
        [_inline_button("🏠 Рабочий стол", callback_data="refresh")],
    ]


def _callbacks(rows: list[list[dict[str, str | None]]]) -> list[str]:
    values: list[str] = []
    for row in rows:
        for button in row:
            callback_data = button.get("callback_data")
            if callback_data:
                values.append(callback_data)
    return values


def test_build_create_start_kind_and_theme_keyboards() -> None:
    start_rows = build_create_start_keyboard_rows(
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    start_callbacks = _callbacks(start_rows)
    assert "cn:manual" in start_callbacks
    assert "cn:ai" in start_callbacks
    assert "cn:transcript" in start_callbacks
    assert "cn:cancel" in start_callbacks
    assert "refresh" in start_callbacks

    kind_rows = build_create_kind_keyboard_rows(
        post_kind_order=["daily", "longread"],
        post_kind_label=lambda value: {"daily": "Ежедневный", "longread": "Лонгрид"}[value],
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    kind_callbacks = _callbacks(kind_rows)
    assert "ck:daily" in kind_callbacks
    assert "ck:longread" in kind_callbacks
    assert "cn:cancel" in kind_callbacks

    theme_rows = build_create_theme_keyboard_rows(
        theme_order=["regulation", "case"],
        theme_label=lambda value: {"regulation": "Регулирование", "case": "Кейсы"}[value],
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    theme_callbacks = _callbacks(theme_rows)
    assert "ct:regulation" in theme_callbacks
    assert "ct:case" in theme_callbacks
    assert "cn:cancel" in theme_callbacks


def test_build_create_media_and_link_keyboards() -> None:
    media_default = build_create_media_keyboard_rows(
        can_clear=False,
        media_count=0,
        editing=False,
        callback_button=_inline_button,
    )
    assert _callbacks(media_default) == ["cm:skip", "cn:cancel", "refresh"]

    media_editing = build_create_media_keyboard_rows(
        can_clear=True,
        media_count=2,
        editing=True,
        callback_button=_inline_button,
    )
    assert _callbacks(media_editing) == ["cm:clear", "cm:done", "cn:cancel", "refresh"]

    link_rows = build_create_link_keyboard_rows(
        can_clear=True,
        cancel_callback="cn:start",
        callback_button=_inline_button,
    )
    assert _callbacks(link_rows) == ["cl:clear", "cl:skip", "cn:start", "refresh"]


def test_build_create_draft_keyboard_rows() -> None:
    rows = build_create_draft_keyboard_rows(
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "ce:kind" in callbacks
    assert "ce:theme" in callbacks
    assert "ce:media" in callbacks
    assert "ce:link" in callbacks
    assert "ce:source" in callbacks
    assert "ce:title" in callbacks
    assert "ce:text" in callbacks
    assert "ce:ai" in callbacks
    assert "cs:draft" in callbacks
    assert "cs:review" in callbacks
    assert "cs:scheduled:h1" in callbacks
    assert "cs:scheduled:e19" in callbacks
    assert "cs:scheduled:t10" in callbacks
    assert "cr:lastfirst" in callbacks
    assert "cr:reverse" in callbacks
    assert "cn:start" in callbacks
    assert "refresh" in callbacks
