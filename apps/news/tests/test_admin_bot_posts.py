from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.admin_bot import (
    _batch_mode_label,
    _batch_mode_limit,
    _compute_quick_publish_at,
    _is_manual_queue_context,
    _normalize_operator_note,
    _parse_batch_publish_callback,
    _parse_manual_queue_callback,
    _parse_post_list_callback,
    _queue_context_from_filter,
    _queue_filter_from_context,
    _slot_label,
    _status_badge,
    _status_label,
)


def test_parse_post_list_callback_legacy_format() -> None:
    status, offset = _parse_post_list_callback("pl:12")
    assert status == "scheduled"
    assert offset == 12


def test_parse_post_list_callback_new_format() -> None:
    status, offset = _parse_post_list_callback("pl:draft:7")
    assert status == "draft"
    assert offset == 7


def test_parse_manual_queue_callback_formats() -> None:
    queue_filter, offset = _parse_manual_queue_callback("mq:4")
    assert queue_filter == "due"
    assert offset == 4
    queue_filter, offset = _parse_manual_queue_callback("mq:all:12")
    assert queue_filter == "all"
    assert offset == 12


def test_manual_queue_context_helpers() -> None:
    assert _queue_context_from_filter("due") == "mq_due"
    assert _queue_context_from_filter("all") == "mq_all"
    assert _queue_filter_from_context("mq_due") == "due"
    assert _queue_filter_from_context("mq_all") == "all"
    assert _is_manual_queue_context("mq_due")
    assert not _is_manual_queue_context("scheduled")


def test_parse_batch_publish_callback_formats() -> None:
    queue_filter, offset, mode = _parse_batch_publish_callback("mbp:due:8")
    assert queue_filter == "due"
    assert offset == 8
    assert mode == "page"
    queue_filter, offset, mode = _parse_batch_publish_callback("mbp:all:16:top5")
    assert queue_filter == "all"
    assert offset == 16
    assert mode == "top5"


def test_batch_mode_helpers() -> None:
    assert _batch_mode_limit("page") is None
    assert _batch_mode_limit("top3") == 3
    assert _batch_mode_limit("top5") == 5
    assert _batch_mode_label("top3") == "топ-3"


def test_status_labels_and_badges() -> None:
    assert _status_label("draft").startswith("🆕")
    assert _status_label("scheduled").startswith("✅")
    assert _status_badge("failed") == "❌"


def test_compute_quick_publish_at_h1_is_future_utc() -> None:
    before = datetime.now(timezone.utc)
    planned = _compute_quick_publish_at("h1")
    assert planned.tzinfo is not None
    assert planned > before + timedelta(minutes=55)


def test_slot_label_mapping() -> None:
    assert _slot_label("h1") == "+1ч"
    assert _slot_label("e19") == "сегодня/след. 19:00"


def test_normalize_operator_note() -> None:
    assert _normalize_operator_note("  срочно   для  клиента ") == "срочно для клиента"
    assert _normalize_operator_note("a" * 700).endswith("…")
    assert len(_normalize_operator_note("a" * 700)) == 500
