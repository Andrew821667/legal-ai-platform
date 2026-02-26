from __future__ import annotations

from news.admin_bot import _parse_post_list_callback, _status_badge, _status_label


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
