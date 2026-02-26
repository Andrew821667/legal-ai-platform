from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.admin_bot import (
    _compute_quick_publish_at,
    _normalize_operator_note,
    _parse_post_list_callback,
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
