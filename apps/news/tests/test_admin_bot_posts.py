from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.admin_bot import (
    _auto_queue_context,
    _auto_queue_filters_from_context,
    _auto_queue_filter_from_context,
    _button_icon_map,
    _callback_payload_text,
    _callback_prefix_matcher,
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
    _manual_post_kind_from_format_type,
    _manual_post_kind_prompt_block,
    _manual_post_kind_screen_template,
    _manual_post_kind_style_hint,
    _post_format_display_label,
    _parse_review_filter_callback,
    _review_origin,
    _review_origin_badge,
    _manual_post_kind_structure,
    _is_calendar_callback,
    _is_controls_callback,
    _is_create_callback,
    _is_posts_callback,
    NewsAdminBot,
    _normalize_operator_note,
    _parse_auto_queue_callback,
    _parse_batch_publish_callback,
    _parse_manual_queue_callback,
    _parse_post_list_callback,
    _queue_context_from_filter,
    _queue_filters_from_context,
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
    queue_filter, theme_filter, offset = _parse_manual_queue_callback("mq:4")
    assert queue_filter == "due"
    assert theme_filter == "all"
    assert offset == 4
    queue_filter, theme_filter, offset = _parse_manual_queue_callback("mq:all:12")
    assert queue_filter == "all"
    assert theme_filter == "all"
    assert offset == 12
    queue_filter, theme_filter, offset = _parse_manual_queue_callback("mq:due:implementation:7")
    assert queue_filter == "due"
    assert theme_filter == "implementation"
    assert offset == 7


def test_callback_payload_text_and_prefix_matcher() -> None:
    assert _callback_payload_text("cal:summary") == "cal:summary"
    assert _callback_payload_text(123) == ""
    assert _callback_prefix_matcher("refresh", exact=frozenset({"refresh"}))
    assert _callback_prefix_matcher("gen:pick:5", prefixes=("gen:",))
    assert not _callback_prefix_matcher("rv:all:0", prefixes=("gen:",))


def test_callback_route_matchers() -> None:
    assert _is_calendar_callback("cal:summary")
    assert _is_create_callback("cn:start")
    assert _is_controls_callback("refresh")
    assert _is_controls_callback("sec:sources")
    assert _is_controls_callback("rdg:menu")
    assert _is_posts_callback("pv:123:review:0")
    assert not _is_posts_callback("sec:sources")
    assert not _is_controls_callback("rv:all:0")


def test_manual_queue_context_helpers() -> None:
    assert _queue_context_from_filter("due") == "mq_due_all"
    assert _queue_context_from_filter("all") == "mq_all_all"
    assert _queue_context_from_filter("due", "implementation") == "mq_due_implementation"
    assert _queue_filter_from_context("mq_due") == "due"
    assert _queue_filter_from_context("mq_all") == "all"
    assert _queue_filters_from_context("mq_due_implementation") == ("due", "implementation")
    assert _is_manual_queue_context("mq_due")
    assert not _is_manual_queue_context("scheduled")
    assert _auto_queue_context("daily") == "aq_daily_all"
    assert _auto_queue_context("daily", "regulation") == "aq_daily_regulation"
    assert _auto_queue_filter_from_context("aq_humor") == "humor"
    assert _auto_queue_filters_from_context("aq_humor_market") == ("humor", "market")
    assert _is_auto_queue_context("aq_all")


def test_parse_auto_queue_callback_formats() -> None:
    queue_filter, theme_filter, offset = _parse_auto_queue_callback("aq:daily:8")
    assert queue_filter == "daily"
    assert theme_filter == "all"
    assert offset == 8
    queue_filter, theme_filter, offset = _parse_auto_queue_callback("aq:other:0")
    assert queue_filter == "other"
    assert theme_filter == "all"
    assert offset == 0
    queue_filter, theme_filter, offset = _parse_auto_queue_callback("aq:daily:regulation:5")
    assert queue_filter == "daily"
    assert theme_filter == "regulation"
    assert offset == 5


def test_parse_review_filter_callback_formats() -> None:
    review_filter, kind_filter, theme_filter, offset = _parse_review_filter_callback("rv:ai:8")
    assert review_filter == "ai"
    assert kind_filter == "all"
    assert theme_filter == "all"
    assert offset == 8
    review_filter, kind_filter, theme_filter, offset = _parse_review_filter_callback("rv:manual:0")
    assert review_filter == "manual"
    assert kind_filter == "all"
    assert theme_filter == "all"
    assert offset == 0
    review_filter, kind_filter, theme_filter, offset = _parse_review_filter_callback(
        "rv:manual:weekly_review:market:4"
    )
    assert review_filter == "manual"
    assert kind_filter == "weekly_review"
    assert theme_filter == "market"
    assert offset == 4


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
    assert "самостоятельно" in _manual_post_kind_prompt_block("digest")
    assert "проверкой, действием или критерием" in _manual_post_kind_prompt_block("checklist")
    assert "реально задает клиент" in _manual_post_kind_prompt_block("faq")


def test_manual_post_kind_screen_templates_exist() -> None:
    assert "Где у клиента рвется процесс" in _manual_post_kind_screen_template("promo_offer")
    assert "Жесткий тезис" in _manual_post_kind_screen_template("opinion")
    assert "процесс до изменений" in _manual_post_kind_screen_template("case_story")
    assert "4-6 самостоятельных пунктов" in _manual_post_kind_screen_template("digest")
    assert "5-7 действий или критериев" in _manual_post_kind_screen_template("checklist")
    assert "4-6 реальных вопросов" in _manual_post_kind_screen_template("faq")


def test_manual_post_kind_from_format_type_and_display_label() -> None:
    assert _manual_post_kind_from_format_type("manual_promo_offer") == "promo_offer"
    assert _manual_post_kind_from_format_type("operator_ai_case_story") == "case_story"
    assert _post_format_display_label({"format_type": "manual_opinion"}) == "✍️ Мнение"
    assert _post_format_display_label({"format_type": "operator_ai_case_story"}) == "🤖 Кейс внедрения"


def test_review_origin_helpers() -> None:
    assert _review_origin("manual_checklist") == "manual"
    assert _review_origin("operator_ai_digest") == "ai"
    assert _review_origin_badge("manual_checklist") == "✍️"


def test_workspace_keyboard_contains_system_section() -> None:
    bot = NewsAdminBot()
    markup = bot._workspace_keyboard({})
    payload = markup.to_dict()
    rows = payload.get("inline_keyboard") or []
    callbacks = [btn.get("callback_data") for row in rows for btn in row if btn.get("callback_data")]
    assert "sec:system" in callbacks
    assert "automation" not in callbacks


def test_system_keyboard_exposes_service_actions() -> None:
    bot = NewsAdminBot()
    markup = bot._system_keyboard()
    payload = markup.to_dict()
    rows = payload.get("inline_keyboard") or []
    callbacks = {btn.get("callback_data") for row in rows for btn in row if btn.get("callback_data")}
    assert {"status", "workers", "rdg:menu", "reader:funnel:7", "automation", "resetstale", "sec:help", "refresh"} <= callbacks


def test_help_text_has_reduced_fallback_commands() -> None:
    bot = NewsAdminBot()
    text = bot._help_text()
    assert "/start, /admin, /newpost, /generate_now, /calendar, /help" in text
    assert _review_origin_badge("daily") == "🤖"


def test_apply_footer_to_post_text_inserts_before_source() -> None:
    original = (
        "<b>Заголовок</b>\n\n"
        "<b>Что произошло</b>\nТекст.\n\n"
        "<b>Источник</b>: <a href=\"https://example.com\">оригинал статьи</a>\n"
        "#LegalAI"
    )
    updated = NewsAdminBot._apply_footer_to_post_text(
        original,
        "Если хотите примерить такой сценарий к вашей юрфункции, напишите в @legal_ai_helper_new_bot.",
    )
    assert "<b>Следующий шаг</b>" in updated
    assert updated.index("<b>Следующий шаг</b>") < updated.index("<b>Источник</b>")
    assert "<a href=\"https://t.me/legal_ai_helper_new_bot\">Ассистент Legal AI Pro</a>" in updated


def test_apply_footer_to_post_text_appends_helper_contact_when_missing() -> None:
    original = "<b>Заголовок</b>\n\n<b>Источник</b>: ссылка\n#LegalAI"
    updated = NewsAdminBot._apply_footer_to_post_text(
        original,
        "Можем помочь внедрить такой сценарий в юридическую функцию.",
    )
    assert "<b>Следующий шаг</b>" in updated
    assert "Ассистент Legal AI Pro" in updated
    assert "https://t.me/legal_ai_helper_new_bot" in updated


def test_post_card_keyboard_has_add_footer_button() -> None:
    bot = NewsAdminBot()
    markup = bot._post_card_keyboard("123", "review", 0)
    payload = markup.to_dict()
    labels = [button["text"] for row in payload["inline_keyboard"] for button in row]
    assert "🧩 Добавить футер" in labels


def test_fallback_footer_text_is_varied_for_different_posts() -> None:
    bot = NewsAdminBot()
    first = bot._fallback_footer_text(
        {
            "id": "post-1",
            "title": "Первый кейс",
            "rubric": "legal_ops",
            "format_type": "daily",
            "text": "<b>Текст</b>",
        }
    )
    second = bot._fallback_footer_text(
        {
            "id": "post-2",
            "title": "Второй кейс",
            "rubric": "legal_ops",
            "format_type": "daily",
            "text": "<b>Текст</b>",
        }
    )
    assert "Ассистент Legal AI Pro" in first
    assert "Ассистент Legal AI Pro" in second
    assert first != second
