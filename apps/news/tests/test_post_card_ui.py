from __future__ import annotations

from news.post_card_ui import build_post_card_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_post_card_text_includes_primary_fields() -> None:
    text = build_post_card_text(
        post={
            "id": "42",
            "title": "Тестовый пост",
            "publish_at": "2026-03-09T18:00:00+03:00",
            "status": "review",
            "text": "<b>Содержимое</b>",
            "format_type": "manual_opinion",
            "cta_type": "soft",
            "rubric": "legal_ops",
            "source_url": "https://example.com/source",
            "telegram_message_id": 123,
            "posted_at": "2026-03-09T19:00:00+03:00",
            "feedback_snapshot": {"comments_total": 5},
        },
        strip_html_markup=lambda value: value.replace("<b>", "").replace("</b>", ""),
        post_format_label=lambda _post: "✍️ Мнение",
        row_publication_kind=lambda _post: "daily",
        publication_kind_badge=lambda value: {"daily": "🤖"}[value],
        publication_kind_label=lambda value: {"daily": "Ежедневный"}[value],
        rubric_to_pillar=lambda _rubric, _text: "implementation",
        pillar_display=lambda value: {"implementation": "⚙️ Implementation"}[value],
        rubric_label=lambda value: {"legal_ops": "Legal Ops"}[value],
        status_badge=lambda value: {"review": "🟡"}[value],
        status_label=lambda value: {"review": "🟡 На проверке"}[value],
        feedback_snapshot_formatter=lambda snapshot: f"feedback={snapshot.get('comments_total')}",
        screen_guide=_screen_guide_stub,
    )

    assert "Карточка поста" in text
    assert "🆔 42 | 🟡 🟡 На проверке" in text
    assert "🔗 Источник: https://example.com/source" in text
    assert "📨 Telegram message_id: 123" in text
    assert "✅ Опубликован: 2026-03-09T19:00:00+03:00" in text
    assert "feedback=5" in text
    assert "Текст (фрагмент):" in text


def test_build_post_card_text_uses_defaults_and_truncates_preview() -> None:
    long_text = "x" * 1900
    text = build_post_card_text(
        post={
            "id": "empty",
            "status": "draft",
            "text": long_text,
        },
        strip_html_markup=lambda value: value,
        post_format_label=lambda _post: "n/a",
        row_publication_kind=lambda _post: "daily",
        publication_kind_badge=lambda value: {"daily": "🤖"}[value],
        publication_kind_label=lambda value: {"daily": "Ежедневный"}[value],
        rubric_to_pillar=lambda _rubric, _text: "implementation",
        pillar_display=lambda value: {"implementation": "⚙️ Implementation"}[value],
        rubric_label=lambda _value: "n/a",
        status_badge=lambda value: {"draft": "📝"}[value],
        status_label=lambda value: {"draft": "📝 Черновик"}[value],
        feedback_snapshot_formatter=lambda snapshot: f"snapshot={bool(snapshot)}",
        screen_guide=_screen_guide_stub,
    )

    assert "📰 Без заголовка" in text
    assert "🗓 План публикации: —" in text
    assert "🧩 n/a | CTA: n/a" in text
    assert "snapshot=False" in text
    assert long_text[:1800] in text
    assert "\n\n…" in text
