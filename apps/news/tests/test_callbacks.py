from __future__ import annotations

from news.callbacks import (
    auto_queue_context,
    auto_queue_filters_from_context,
    calendar_context,
    calendar_date_from_context,
    callback_payload_text,
    callback_prefix_matcher,
    is_auto_queue_context,
    is_calendar_callback,
    is_calendar_context,
    is_controls_callback,
    is_create_callback,
    is_manual_queue_context,
    is_posts_callback,
    parse_auto_queue_callback,
    parse_batch_publish_callback,
    parse_manual_queue_callback,
    parse_post_list_callback,
    parse_review_filter_callback,
    queue_context_from_filter,
    queue_filters_from_context,
    slot_from_token,
    slot_token,
)


def test_parse_post_list_callback_formats() -> None:
    assert parse_post_list_callback("pl:12") == ("scheduled", 12)
    assert parse_post_list_callback("pl:draft:7") == ("draft", 7)
    assert parse_post_list_callback("pl:review:3") == ("review", 3)


def test_parse_manual_auto_review_callbacks() -> None:
    assert parse_manual_queue_callback("mq:4") == ("due", "all", 4)
    assert parse_manual_queue_callback("mq:all:12") == ("all", "all", 12)
    assert parse_manual_queue_callback("mq:due:implementation:7") == ("due", "implementation", 7)
    assert parse_auto_queue_callback("aq:daily:8") == ("daily", "all", 8)
    assert parse_auto_queue_callback("aq:daily:regulation:5") == ("daily", "regulation", 5)
    assert parse_review_filter_callback("rv:manual:weekly_review:market:4") == ("manual", "weekly_review", "market", 4)


def test_parse_batch_publish_callback_formats() -> None:
    assert parse_batch_publish_callback("mbp:due:8") == ("due", 8, "page")
    assert parse_batch_publish_callback("mbp:all:16:top5") == ("all", 16, "top5")


def test_callback_route_helpers() -> None:
    assert callback_payload_text("cal:summary") == "cal:summary"
    assert callback_payload_text(123) == ""
    assert callback_prefix_matcher("refresh", exact=frozenset({"refresh"}))
    assert callback_prefix_matcher("gen:pick:5", prefixes=("gen:",))
    assert not callback_prefix_matcher("rv:all:0", prefixes=("gen:",))
    assert is_calendar_callback("cal:summary")
    assert is_create_callback("cn:start")
    assert is_controls_callback("refresh")
    assert is_controls_callback("sec:sources")
    assert is_controls_callback("wrk:token:refresh")
    assert is_posts_callback("pv:123:review:0")
    assert not is_posts_callback("sec:sources")


def test_context_helpers() -> None:
    assert queue_context_from_filter("due") == "mq_due_all"
    assert queue_context_from_filter("all", "regulation") == "mq_all_regulation"
    assert queue_filters_from_context("mq_due_implementation") == ("due", "implementation")
    assert is_manual_queue_context("mq_due_all")
    assert auto_queue_context("daily", "market") == "aq_daily_market"
    assert auto_queue_filters_from_context("aq_humor_market") == ("practice", "market")
    assert is_auto_queue_context("aq_all_all")
    cal_context = calendar_context("2026-03-01")
    assert cal_context == "cal_20260301"
    assert is_calendar_context(cal_context)
    assert calendar_date_from_context(cal_context) == "2026-03-01"
    token = slot_token(10, 30)
    assert token == "1030"
    assert slot_from_token(token) == (10, 30)
