from __future__ import annotations

from collections.abc import Callable
from typing import Any


ScreenGuide = Callable[[str, list[str]], str]


def build_reader_summary_text(
    *,
    payload: dict[str, Any],
    days: int = 7,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    stats = payload.get("stats") or {}
    top_reasons = payload.get("top_negative_reasons") or []
    top_posts = payload.get("top_posts") or []

    reason_label_map = {
        "too_complex": "слишком сложно",
        "not_relevant": "не по теме",
        "outdated": "устарело",
        "shallow": "поверхностно",
        "other": "прочее",
    }

    lines = [
        f"Reader-метрики за {days} дн.",
        "",
        guide(
            "Сводка пользовательских сигналов из reader-бота.",
            [
                "Переключайте период 7/14/30 дней кнопками.",
                "Используйте негативные причины и топ-посты для корректировки контент-стратегии.",
            ],
        ),
        "",
        f"Сигналов всего: {stats.get('signals_total', 0)}",
        f"Открыт weekly digest: {stats.get('weekly_opened', 0)}",
        f"Запрошено «Идея внедрения»: {stats.get('idea_requested', 0)}",
        f"Намерение на консультацию: {stats.get('consultation_intent', 0)}",
        f"Полезно (👍): {stats.get('useful_feedback', 0)}",
        f"Не полезно (👎): {stats.get('not_useful_feedback', 0)}",
        "",
        "Негативные причины:",
    ]
    if top_reasons:
        for row in top_reasons[:5]:
            reason = reason_label_map.get(str(row.get("reason") or ""), str(row.get("reason") or "other"))
            lines.append(f"• {reason}: {int(row.get('count') or 0)}")
    else:
        lines.append("• пока нет")

    lines.append("")
    lines.append("Топ публикаций по интересу reader → консультация:")
    if top_posts:
        for idx, row in enumerate(top_posts[:5], start=1):
            title = str(row.get("title") or "Без заголовка")
            lines.append(
                f"{idx}. {title[:70]} — "
                f"consult={int(row.get('consultation_intent') or 0)}, "
                f"idea={int(row.get('idea_requested') or 0)}, "
                f"useful={int(row.get('useful_feedback') or 0)}"
            )
    else:
        lines.append("• пока нет данных")

    return "\n".join(lines)


def build_reader_funnel_text(
    *,
    payload: dict[str, Any],
    days: int = 7,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    feedback = payload.get("feedback") or {}
    leads = payload.get("leads") or {}
    conversion = payload.get("conversion") or {}
    recent_referrals = payload.get("recent_referrals") or []

    lines = [
        f"Reader → Lead воронка за {days} дн.",
        "",
        guide(
            "Конверсия читателей reader-бота в лиды.",
            [
                "Следите за переходами между этапами воронки.",
                "Если CR падает, корректируйте темы, структуру постов и CTA.",
            ],
        ),
        "",
        "Reader-сигналы",
        f"• Weekly opened: {feedback.get('weekly_opened', 0)} (users: {feedback.get('weekly_users', 0)})",
        f"• Идея внедрения: {feedback.get('idea_requested', 0)} (users: {feedback.get('idea_users', 0)})",
        f"• Интент консультации: {feedback.get('consultation_intent', 0)} (users: {feedback.get('consultation_users', 0)})",
        "",
        "Reader-referral лиды",
        f"• Создано лидов: {leads.get('reader_referral_created', 0)}",
        f"• С контактом: {leads.get('reader_referral_with_contact', 0)} ({conversion.get('reader_lead_contact_rate_pct', 0)}%)",
        f"• Qualified+: {leads.get('reader_referral_qualified_plus', 0)} ({conversion.get('reader_lead_qualified_rate_pct', 0)}%)",
        f"• Booked+: {leads.get('reader_referral_booked_plus', 0)}",
        f"• Won: {leads.get('reader_referral_won', 0)}",
        "",
        "Конверсия",
        f"• Consultation users: {conversion.get('consultation_users_total', 0)}",
        f"• Перешли в reader-referral lead: {conversion.get('consultation_users_to_reader_lead', 0)}",
        f"• CR consultation → lead: {conversion.get('consultation_to_reader_lead_rate_pct', 0)}%",
    ]

    lines.append("")
    lines.append("Последние reader-referral лиды:")
    if recent_referrals:
        for idx, row in enumerate(recent_referrals[:5], start=1):
            status = str(row.get("status") or "new")
            name = str(row.get("name") or "Без имени").strip() or "Без имени"
            contact_mark = "контакт ✅" if row.get("with_contact") else "контакт ☐"
            lines.append(f"{idx}. {name[:36]} — {status}, {contact_mark}")
    else:
        lines.append("• пока нет")

    return "\n".join(lines)


def build_reader_miniapp_text(
    *,
    payload: dict[str, Any],
    hours: int = 24,
    screen_guide: ScreenGuide | None = None,
) -> str:
    guide = screen_guide or (lambda _what, _actions: "")
    total_events = int(payload.get("total_events") or 0)
    unique_users = int(payload.get("unique_users") or 0)
    top_sources = payload.get("top_sources") or []
    top_event_types = payload.get("top_event_types") or []
    top_screens = payload.get("top_screens") or []
    top_actions = payload.get("top_actions") or []
    top_users = payload.get("top_users") or []
    recent_events = payload.get("recent_events") or []

    def _top_lines(rows: list[dict[str, Any]], *, fallback: str = "• пока нет") -> list[str]:
        result: list[str] = []
        for row in rows[:5]:
            label = str(row.get("label") or "").strip()
            count = int(row.get("count") or 0)
            if not label:
                continue
            result.append(f"• {label[:42]}: {count}")
        return result or [fallback]

    def _recent_lines(rows: list[dict[str, Any]]) -> list[str]:
        result: list[str] = []
        for row in rows[:5]:
            ts = str(row.get("created_at") or "")[:16].replace("T", " ")
            user_id = int(row.get("telegram_user_id") or 0)
            source = str(row.get("source") or "miniapp")
            screen = str(row.get("screen") or "n/a")
            action = str(row.get("action") or "n/a")
            result.append(f"• {ts} | u{user_id} | {source} | {screen[:28]} | {action[:28]}")
        return result or ["• пока нет"]

    lines = [
        f"Mini-App мониторинг за {hours}ч",
        "",
        guide(
            "Сводка использования mini-app и переходов из reader-бота.",
            [
                "Следите за динамикой событий и количеством уникальных пользователей.",
                "Проверяйте, какие экраны и действия самые частые.",
                "Используйте данные для корректировки маршрута reader -> mini-app -> лид.",
            ],
        ),
        "",
        f"Всего событий: {total_events}",
        f"Уникальных пользователей: {unique_users}",
        "",
        "Топ источников:",
        *_top_lines(top_sources),
        "",
        "Топ типов событий:",
        *_top_lines(top_event_types),
        "",
        "Топ экранов:",
        *_top_lines(top_screens),
        "",
        "Топ действий:",
        *_top_lines(top_actions),
        "",
        "Топ пользователей:",
    ]

    if top_users:
        for row in top_users[:5]:
            lines.append(f"• u{int(row.get('telegram_user_id') or 0)}: {int(row.get('count') or 0)}")
    else:
        lines.append("• пока нет")

    lines.append("")
    lines.append("Последние события:")
    lines.extend(_recent_lines(recent_events))
    return "\n".join(lines)
