from __future__ import annotations

from news.reader_ui import build_reader_funnel_text, build_reader_miniapp_text, build_reader_summary_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_reader_summary_text_contains_metrics_and_tops() -> None:
    payload = {
        "stats": {
            "signals_total": 12,
            "weekly_opened": 7,
            "idea_requested": 3,
            "consultation_intent": 2,
            "useful_feedback": 5,
            "not_useful_feedback": 1,
        },
        "top_negative_reasons": [{"reason": "too_complex", "count": 2}],
        "top_posts": [
            {
                "title": "AI и юрпроцессы",
                "consultation_intent": 2,
                "idea_requested": 1,
                "useful_feedback": 3,
            }
        ],
    }
    text = build_reader_summary_text(payload=payload, days=7, screen_guide=_screen_guide_stub)
    assert "Reader-метрики за 7 дн." in text
    assert "Сигналов всего: 12" in text
    assert "• слишком сложно: 2" in text
    assert "Топ публикаций по интересу reader → консультация:" in text


def test_build_reader_funnel_text_contains_conversion() -> None:
    payload = {
        "feedback": {"weekly_opened": 10, "weekly_users": 8, "idea_requested": 4, "idea_users": 3, "consultation_intent": 2, "consultation_users": 2},
        "leads": {
            "reader_referral_created": 3,
            "reader_referral_with_contact": 2,
            "reader_referral_qualified_plus": 1,
            "reader_referral_booked_plus": 1,
            "reader_referral_won": 0,
        },
        "conversion": {
            "reader_lead_contact_rate_pct": 66,
            "reader_lead_qualified_rate_pct": 33,
            "consultation_users_total": 2,
            "consultation_users_to_reader_lead": 1,
            "consultation_to_reader_lead_rate_pct": 50,
        },
        "recent_referrals": [{"status": "qualified", "name": "Иван Иванов", "with_contact": True}],
    }
    text = build_reader_funnel_text(payload=payload, days=14, screen_guide=_screen_guide_stub)
    assert "Reader → Lead воронка за 14 дн." in text
    assert "• CR consultation → lead: 50%" in text
    assert "Последние reader-referral лиды:" in text


def test_build_reader_miniapp_text_contains_top_sections() -> None:
    payload = {
        "total_events": 13,
        "unique_users": 2,
        "top_sources": [{"label": "reader", "count": 9}],
        "top_event_types": [{"label": "open", "count": 7}],
        "top_screens": [{"label": "/miniapp", "count": 5}],
        "top_actions": [{"label": "cta_click", "count": 4}],
        "top_users": [{"telegram_user_id": 1001, "count": 8}],
        "recent_events": [
            {
                "created_at": "2026-03-09T17:49:00+03:00",
                "telegram_user_id": 1001,
                "source": "reader",
                "screen": "/miniapp",
                "action": "open",
            }
        ],
    }
    text = build_reader_miniapp_text(payload=payload, hours=24, screen_guide=_screen_guide_stub)
    assert "Mini-App мониторинг за 24ч" in text
    assert "Всего событий: 13" in text
    assert "Топ источников:" in text
    assert "Последние события:" in text
