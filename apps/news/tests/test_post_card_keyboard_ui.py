from __future__ import annotations

from news.post_card_keyboard_ui import (
    build_batch_publish_confirm_keyboard_rows,
    build_batch_publish_reason_keyboard_rows,
    build_delete_confirm_keyboard_rows,
    build_delete_reason_keyboard_rows,
    build_post_card_keyboard_rows,
    build_publish_confirm_keyboard_rows,
    build_publish_reason_keyboard_rows,
)


def _inline_button(text: str, callback_data: str | None = None, *, style: str | None = None) -> dict[str, str | None]:
    return {"text": text, "callback_data": callback_data, "style": style}


def _two_column_rows(buttons: list[dict[str, str | None]]) -> list[list[dict[str, str | None]]]:
    return [buttons[index : index + 2] for index in range(0, len(buttons), 2)]


def _callbacks(rows: list[list[dict[str, str | None]]]) -> list[str]:
    values: list[str] = []
    for row in rows:
        for button in row:
            callback_data = button.get("callback_data")
            if callback_data:
                values.append(callback_data)
    return values


def _auto_filters(context: str) -> tuple[str, str]:
    parts = context.removeprefix("aq_").split("_", 1)
    if len(parts) == 1:
        return parts[0], "all"
    return parts[0], parts[1]


def _manual_filters(context: str) -> tuple[str, str]:
    parts = context.removeprefix("mq_").split("_", 1)
    if len(parts) == 1:
        return parts[0], "all"
    return parts[0], parts[1]


def _calendar_date(context: str) -> str:
    raw = context.removeprefix("cal_")
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def test_build_post_card_keyboard_rows_for_review() -> None:
    rows = build_post_card_keyboard_rows(
        post_id="p1",
        status="review",
        offset=0,
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        is_auto_queue_context=lambda value: value.startswith("aq_"),
        auto_queue_filters_from_context=_auto_filters,
        is_calendar_context=lambda value: value.startswith("cal_"),
        calendar_date_from_context=_calendar_date,
        is_theme_context=lambda value: value.startswith("th_"),
        theme_from_context=lambda value: value.removeprefix("th_"),
        is_source_context=lambda value: value.startswith("src_"),
        source_from_context=lambda value: value.removeprefix("src_"),
        is_manual_queue_context=lambda value: value.startswith("mq_"),
        queue_filters_from_context=_manual_filters,
        button_style_danger="danger",
    )
    callbacks = _callbacks(rows)
    assert "pt:p1:review:0:h1" in callbacks
    assert "ppc:p1:review:0" in callbacks
    assert "pm:p1:review:0" in callbacks
    assert "pa:p1:review:0" in callbacks
    assert "pf:p1:review:0" in callbacks
    assert "pdd:p1:review:0" in callbacks
    assert "pr:p1:review:0" in callbacks
    assert "rv:all:all:all:0" in callbacks
    assert "refresh" in callbacks
    delete_rows = [row for row in rows if row and row[0].get("callback_data") == "pdd:p1:review:0"]
    assert delete_rows
    assert delete_rows[0][0].get("style") == "danger"


def test_build_post_card_keyboard_rows_resolves_back_targets() -> None:
    cases = [
        ("aq_daily_regulation", "aq:daily:regulation:4"),
        ("cal_20260301", "cal:day:2026-03-01"),
        ("th_implementation", "th:implementation:4"),
        ("src_telegram", "src:telegram:4"),
        ("mq_due_regulation", "mq:due:regulation:4"),
        ("ready", "pl:ready:4"),
        ("scheduled", "pl:scheduled:4"),
    ]
    for status, expected_callback in cases:
        rows = build_post_card_keyboard_rows(
            post_id="p1",
            status=status,
            offset=4,
            two_column_rows=_two_column_rows,
            callback_button=_inline_button,
            is_auto_queue_context=lambda value: value.startswith("aq_"),
            auto_queue_filters_from_context=_auto_filters,
            is_calendar_context=lambda value: value.startswith("cal_"),
            calendar_date_from_context=_calendar_date,
            is_theme_context=lambda value: value.startswith("th_"),
            theme_from_context=lambda value: value.removeprefix("th_"),
            is_source_context=lambda value: value.startswith("src_"),
            source_from_context=lambda value: value.removeprefix("src_"),
            is_manual_queue_context=lambda value: value.startswith("mq_"),
            queue_filters_from_context=_manual_filters,
            button_style_danger="danger",
        )
        assert expected_callback in _callbacks(rows)


def test_build_post_card_keyboard_rows_for_ready_and_scheduled() -> None:
    ready_rows = build_post_card_keyboard_rows(
        post_id="p1",
        status="ready",
        offset=1,
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        is_auto_queue_context=lambda value: value.startswith("aq_"),
        auto_queue_filters_from_context=_auto_filters,
        is_calendar_context=lambda value: value.startswith("cal_"),
        calendar_date_from_context=_calendar_date,
        is_theme_context=lambda value: value.startswith("th_"),
        theme_from_context=lambda value: value.removeprefix("th_"),
        is_source_context=lambda value: value.startswith("src_"),
        source_from_context=lambda value: value.removeprefix("src_"),
        is_manual_queue_context=lambda value: value.startswith("mq_"),
        queue_filters_from_context=_manual_filters,
        button_style_danger="danger",
    )
    assert "pg:p1:ready:1" in _callbacks(ready_rows)
    assert "rr:p1:ready:1" in _callbacks(ready_rows)

    scheduled_rows = build_post_card_keyboard_rows(
        post_id="p1",
        status="scheduled",
        offset=1,
        two_column_rows=_two_column_rows,
        callback_button=_inline_button,
        is_auto_queue_context=lambda value: value.startswith("aq_"),
        auto_queue_filters_from_context=_auto_filters,
        is_calendar_context=lambda value: value.startswith("cal_"),
        calendar_date_from_context=_calendar_date,
        is_theme_context=lambda value: value.startswith("th_"),
        theme_from_context=lambda value: value.removeprefix("th_"),
        is_source_context=lambda value: value.startswith("src_"),
        source_from_context=lambda value: value.removeprefix("src_"),
        is_manual_queue_context=lambda value: value.startswith("mq_"),
        queue_filters_from_context=_manual_filters,
        button_style_danger="danger",
    )
    assert "gr:p1:scheduled:1" in _callbacks(scheduled_rows)


def test_build_post_card_action_keyboards() -> None:
    publish_confirm = build_publish_confirm_keyboard_rows(
        post_id="p1",
        status="review",
        offset=2,
        callback_button=_inline_button,
    )
    assert _callbacks(publish_confirm) == ["ppy:p1:review:2", "ppn:p1:review:2", "refresh"]

    publish_reason = build_publish_reason_keyboard_rows(
        post_id="p1",
        status="review",
        offset=2,
        callback_button=_inline_button,
    )
    assert _callbacks(publish_reason) == ["ppn:p1:review:2", "refresh"]

    delete_reason = build_delete_reason_keyboard_rows(
        post_id="p1",
        status="review",
        offset=2,
        callback_button=_inline_button,
    )
    assert _callbacks(delete_reason) == ["pdn:p1:review:2", "refresh"]

    delete_confirm = build_delete_confirm_keyboard_rows(
        post_id="p1",
        status="review",
        offset=2,
        callback_button=_inline_button,
    )
    assert _callbacks(delete_confirm) == ["pdy:p1:review:2", "pdn:p1:review:2", "refresh"]

    batch_reason = build_batch_publish_reason_keyboard_rows(
        queue_filter="due",
        offset=8,
        mode="page",
        callback_button=_inline_button,
    )
    assert _callbacks(batch_reason) == ["mbn:due:8:page", "refresh"]

    batch_confirm = build_batch_publish_confirm_keyboard_rows(
        queue_filter="due",
        offset=8,
        mode="page",
        callback_button=_inline_button,
    )
    assert _callbacks(batch_confirm) == ["mbc:due:8:page", "mbn:due:8:page", "refresh"]
