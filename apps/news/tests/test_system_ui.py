from __future__ import annotations

from news.system_ui import build_ops_health_mark, build_ops_summary_text, build_system_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_system_text_contains_core_sections() -> None:
    text = build_system_text(
        {"draft": 1, "review": 2, "scheduled": 3, "posted": 4, "failed": 5, "publishing": 6},
        "2026-03-09T18:00:00+03:00",
        screen_guide=_screen_guide_stub,
    )
    assert "Система и сервисные функции" in text
    assert "📝 Черновики: 1" in text
    assert "⏳ В публикации: 6" in text
    assert "Следующая публикация: 2026-03-09T18:00:00+03:00" in text


def test_build_ops_health_mark_rules() -> None:
    assert build_ops_health_mark(issues=[], overdue=0, stale_publishing=0) == "🟢"
    assert build_ops_health_mark(issues=["miniapp_summary_unavailable"], overdue=0, stale_publishing=0) == "🟠"
    assert build_ops_health_mark(issues=["worker_inactive:news-publish"], overdue=0, stale_publishing=0) == "🔴"
    assert build_ops_health_mark(issues=[], overdue=1, stale_publishing=0) == "🔴"


def test_build_ops_summary_text_with_issues() -> None:
    text = build_ops_summary_text(
        next_publish="2026-03-09T18:00:00+03:00",
        snapshot_at="2026-03-09T17:49:00+03:00",
        heartbeat_max_age_minutes=2,
        overdue=0,
        stale_publishing=0,
        failed_posts=2,
        review_count=11,
        miniapp_line="• Mini-app события 24ч: 13 (users: 1)",
        worker_lines=["⚠️ 🧠 Генератор драфтов: не удалось прочитать события 24ч"],
        issues=["worker_activity_unavailable:news-generate"],
        screen_guide=_screen_guide_stub,
    )
    assert "Состояние контура: 🟠" in text
    assert "• Ошибки в ленте (посл.100): 2" in text
    assert "Снимок сформирован: 2026-03-09T17:49:00+03:00" in text
    assert "Макс. давность heartbeat: 2 мин" in text
    assert "Найдены риски: 1" in text
    assert "Рекомендуется: проверить воркеры -> сбросить stale -> повторно открыть экран." in text


def test_build_ops_summary_text_without_issues() -> None:
    text = build_ops_summary_text(
        next_publish="2026-03-09T18:00:00+03:00",
        snapshot_at="2026-03-09T17:49:00+03:00",
        heartbeat_max_age_minutes=None,
        overdue=0,
        stale_publishing=0,
        failed_posts=0,
        review_count=8,
        miniapp_line="• Mini-app события 24ч: 13 (users: 1)",
        worker_lines=["🟢 📡 Telegram-парсер: активен (last_seen: now)"],
        issues=[],
        screen_guide=_screen_guide_stub,
    )
    assert "Состояние контура: 🟢" in text
    assert "Макс. давность heartbeat: n/a" in text
    assert "Критичных рисков не обнаружено." in text
