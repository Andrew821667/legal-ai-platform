from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.admin_bot import (
    _auto_queue_context,
    _auto_queue_filter_from_context,
    _button_icon_map,
    _main_menu_markup,
    _batch_mode_label,
    _batch_mode_limit,
    _calendar_context,
    _calendar_date_from_context,
    _compute_quick_publish_at,
    _format_workers_status,
    _is_hidden_deleted_post,
    _is_auto_queue_context,
    _is_batch_mode_allowed,
    _is_calendar_context,
    _is_manual_queue_context,
    _manual_post_kind_label,
    _manual_post_kind_prompt_block,
    _manual_post_kind_style_hint,
    _parse_review_filter_callback,
    _review_origin,
    _review_origin_badge,
    _manual_post_kind_structure,
    NewsAdminBot,
    _normalize_operator_note,
    _parse_auto_queue_callback,
    _parse_batch_publish_callback,
    _parse_manual_queue_callback,
    _parse_post_list_callback,
    _queue_context_from_filter,
    _queue_filter_from_context,
    _slot_from_token,
    _slot_token,
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
    status, offset = _parse_post_list_callback("pl:review:3")
    assert status == "review"
    assert offset == 3


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
    assert _auto_queue_context("daily") == "aq_daily"
    assert _auto_queue_filter_from_context("aq_humor") == "humor"
    assert _is_auto_queue_context("aq_all")


def test_parse_auto_queue_callback_formats() -> None:
    queue_filter, offset = _parse_auto_queue_callback("aq:daily:8")
    assert queue_filter == "daily"
    assert offset == 8
    queue_filter, offset = _parse_auto_queue_callback("aq:other:0")
    assert queue_filter == "other"
    assert offset == 0


def test_parse_review_filter_callback_formats() -> None:
    review_filter, offset = _parse_review_filter_callback("rv:ai:8")
    assert review_filter == "ai"
    assert offset == 8
    review_filter, offset = _parse_review_filter_callback("rv:manual:0")
    assert review_filter == "manual"
    assert offset == 0


def test_calendar_context_helpers() -> None:
    context = _calendar_context("2026-03-01")
    assert context == "cal_20260301"
    assert _is_calendar_context(context)
    assert _calendar_date_from_context(context) == "2026-03-01"


def test_slot_token_helpers() -> None:
    token = _slot_token(10, 30)
    assert token == "1030"
    assert _slot_from_token(token) == (10, 30)


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
    assert _is_batch_mode_allowed("due", "top3")
    assert not _is_batch_mode_allowed("all", "top3")
    assert _is_batch_mode_allowed("all", "page")


def test_status_labels_and_badges() -> None:
    assert _status_label("draft").startswith("📝")
    assert _status_label("review").startswith("🟡")
    assert _status_label("scheduled").startswith("✅")
    assert _status_label("posted").startswith("📤")
    assert _status_label("cal_20260301").startswith("🗓")
    assert _status_badge("failed") == "❌"


def test_compute_quick_publish_at_h1_is_future_utc() -> None:
    before = datetime.now(timezone.utc)
    planned = _compute_quick_publish_at("h1")
    assert planned.tzinfo is not None
    assert planned > before + timedelta(minutes=55)


def test_move_to_next_day_same_time_preserves_hour_and_minute() -> None:
    source = datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)
    moved = NewsAdminBot._move_to_next_day_same_time(source)
    assert moved.tzinfo is not None
    assert moved > source


def test_slot_label_mapping() -> None:
    assert _slot_label("h1") == "+1ч"
    assert _slot_label("e19") == "сегодня/след. 19:00"


def test_normalize_operator_note() -> None:
    assert _normalize_operator_note("  срочно   для  клиента ") == "срочно для клиента"
    assert _normalize_operator_note("a" * 700).endswith("…")
    assert len(_normalize_operator_note("a" * 700)) == 500


def test_format_workers_status_payload() -> None:
    text = _format_workers_status(
        {
            "any_active": True,
            "workers": [
                {
                    "worker_id": "news-publish",
                    "active": True,
                    "last_seen_at": "2026-02-27T09:00:00+00:00",
                }
            ],
        }
    )
    assert "Активные воркеры: да" in text
    assert "news-publish" in text


def test_main_menu_markup_removes_reply_keyboard(monkeypatch) -> None:
    monkeypatch.delenv("NEWS_ADMIN_BUTTON_ICON_MAP", raising=False)
    _button_icon_map.cache_clear()
    try:
        markup = _main_menu_markup()
        payload = markup.to_dict()
        assert payload.get("remove_keyboard") is True
    finally:
        _button_icon_map.cache_clear()


def test_main_menu_remove_keyboard_has_no_buttons() -> None:
    markup = _main_menu_markup()
    assert "keyboard" not in markup.to_dict()


def test_hidden_deleted_post_helper() -> None:
    assert _is_hidden_deleted_post({"last_error": "deleted_irrelevant"})
    assert _is_hidden_deleted_post({"last_error": "deleted_irrelevant: ai-noise"})
    assert not _is_hidden_deleted_post({"last_error": "timeout"})


def test_manual_post_kind_label_exists() -> None:
    assert _manual_post_kind_label("promo_offer") == "Рекламный"


def test_manual_post_kind_structure_exists() -> None:
    assert "боль клиента" in _manual_post_kind_structure("promo_offer")
    assert "тезис" in _manual_post_kind_structure("opinion")


def test_manual_post_kind_style_hints_exist() -> None:
    assert "агрессивного продавливания" in _manual_post_kind_style_hint("promo_offer")
    assert "авторский" in _manual_post_kind_style_hint("opinion")
    assert "действием или критерием" in _manual_post_kind_style_hint("checklist")


def test_manual_post_kind_prompt_blocks_exist() -> None:
    assert "узкого места клиента" in _manual_post_kind_prompt_block("promo_offer")
    assert "Первая фраза должна содержать четкий тезис" in _manual_post_kind_prompt_block("opinion")
    assert "исходную проблему" in _manual_post_kind_prompt_block("case_story")


def test_review_origin_helpers() -> None:
    assert _review_origin("manual_checklist") == "manual"
    assert _review_origin("operator_ai_digest") == "ai"
    assert _review_origin_badge("manual_checklist") == "✍️"
    assert _review_origin_badge("daily") == "🤖"
