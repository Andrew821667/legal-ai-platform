from __future__ import annotations

from news.posts_ui import build_posts_text, build_review_posts_text


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_posts_text_non_empty_and_empty() -> None:
    non_empty = build_posts_text(
        total=2,
        rows=[
            {"title": "Пост 1", "publish_at": "2026-03-09T10:00:00+03:00", "status": "draft", "kind": "daily"},
            {"title": "Пост 2", "publish_at": "2026-03-09T12:00:00+03:00", "status": "draft", "kind": "longread"},
        ],
        offset=0,
        status="draft",
        page_size=8,
        status_label=lambda status: {"draft": "📝 Черновики"}[status],
        status_badge=lambda status: {"draft": "📝"}[status],
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}[kind],
        publication_kind_label=lambda kind: {"daily": "Ежедневный", "longread": "Лонгрид"}[kind],
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        screen_guide=_screen_guide_stub,
    )
    assert "📝 Черновики: 2" in non_empty
    assert "1. 📝 🤖 Пост 1" in non_empty
    assert "2. 📝 📚 Пост 2" in non_empty

    empty = build_posts_text(
        total=0,
        rows=[],
        offset=0,
        status="posted",
        page_size=8,
        status_label=lambda status: {"posted": "📤 Опубликованные"}[status],
        status_badge=lambda status: status,
        publication_kind_badge=lambda kind: kind,
        publication_kind_label=lambda kind: kind,
        row_publication_kind=lambda row: str(row),
        screen_guide=_screen_guide_stub,
    )
    assert "📤 Опубликованные (status=posted)" in empty
    assert "Сейчас записей нет." in empty


def test_build_review_posts_text_non_empty_and_empty() -> None:
    non_empty = build_review_posts_text(
        total=2,
        rows=[
            {
                "title": "Пост 1",
                "publish_at": "2026-03-09T10:00:00+03:00",
                "format_type": "operator_ai_daily",
                "kind": "daily",
                "pillar": "implementation",
                "format_label": "Ежедневный",
            },
            {
                "title": "Пост 2",
                "publish_at": "2026-03-09T12:00:00+03:00",
                "format_type": "manual_longread",
                "kind": "longread",
                "pillar": "case",
                "format_label": "Лонгрид",
            },
        ],
        offset=0,
        review_filter="all",
        kind_filter="all",
        theme_filter="all",
        page_size=8,
        review_origin_label=lambda value: {"all": "Все источники"}[value],
        review_origin_badge=lambda value: "🤖" if "operator_ai" in value else "✍️",
        publication_kind_label=lambda kind: {"daily": "Ежедневный", "longread": "Лонгрид"}[kind],
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}[kind],
        pillar_display=lambda value: value,
        pillar_label=lambda value: {"implementation": "Implementation", "case": "Case"}[value],
        post_format_label=lambda row: str(row.get("format_label") or "n/a"),
        row_publication_kind=lambda row: str(row.get("kind") or "daily"),
        row_pillar=lambda row: str(row.get("pillar") or "implementation"),
        screen_guide=_screen_guide_stub,
    )
    assert "🟡 На проверке" in non_empty
    assert "Фильтр: Все источники" in non_empty
    assert "1. 🤖 🤖 Пост 1" in non_empty
    assert "2. ✍️ 📚 Пост 2" in non_empty

    empty = build_review_posts_text(
        total=0,
        rows=[],
        offset=0,
        review_filter="ai",
        kind_filter="daily",
        theme_filter="implementation",
        page_size=8,
        review_origin_label=lambda value: {"ai": "Только AI"}[value],
        review_origin_badge=lambda value: value,
        publication_kind_label=lambda kind: {"daily": "Ежедневные"}[kind],
        publication_kind_badge=lambda kind: kind,
        pillar_display=lambda value: {"implementation": "Implementation"}[value],
        pillar_label=lambda value: value,
        post_format_label=lambda row: str(row),
        row_publication_kind=lambda row: str(row),
        row_pillar=lambda row: str(row),
        screen_guide=_screen_guide_stub,
    )
    assert "Фильтр: Только AI" in empty
    assert "Вид: Ежедневные" in empty
    assert "Тема: Implementation" in empty
    assert "Сейчас записей нет." in empty
