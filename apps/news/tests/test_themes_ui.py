from __future__ import annotations

from news.themes_ui import (
    build_theme_posts_text,
    build_themes_archive_text,
    build_themes_daily_text,
    build_themes_text,
)


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_themes_text_contains_core_counters() -> None:
    text = build_themes_text(
        counts={"regulation": 2, "case": 1, "implementation": 3, "tools": 0, "market": 1},
        generation_counts={"a": 5, "b": 2, "c": 1},
        enabled_generation_themes_count=2,
        active_longread_topics_count=4,
        longread_topics_total=7,
        screen_guide=_screen_guide_stub,
    )
    assert "Тематики контента" in text
    assert "Активно ежедневных тем: 2/3" in text
    assert "Активно тем лонгридов: 4/7" in text
    assert "Постов в архивных корзинах: 7" in text


def test_build_themes_daily_text_marks_enabled_items() -> None:
    text = build_themes_daily_text(
        generation_theme_keys=["legal", "market"],
        generation_theme_counts={"legal": 10, "market": 2},
        enabled_generation_themes={"legal"},
        generation_theme_label=lambda key: {"legal": "Юридическая AI-тема", "market": "Рынок"}[key],
        generation_theme_note=lambda key: {"legal": "Фокус права", "market": "Фокус рынка"}[key],
        screen_guide=_screen_guide_stub,
    )
    assert "• ✅ Юридическая AI-тема — 10" in text
    assert "• ☐ Рынок — 2" in text
    assert "Фокус права" in text
    assert "Фокус рынка" in text


def test_build_themes_archive_text_renders_pillars() -> None:
    text = build_themes_archive_text(
        counts={"regulation": 3, "case": 1},
        pillar_labels={"regulation": "Регулирование", "case": "Кейсы"},
        pillar_badge=lambda pillar: {"regulation": "⚖️", "case": "📚"}[pillar],
        pillar_rubrics={"regulation": ("compliance",), "case": ("case_story",)},
        rubric_label=lambda key: {"compliance": "Комплаенс", "case_story": "Кейс-стади"}[key],
        screen_guide=_screen_guide_stub,
    )
    assert "• ⚖️ Регулирование: 3 пост(ов)" in text
    assert "• 📚 Кейсы: 1 пост(ов)" in text
    assert "Рубрики: Комплаенс" in text
    assert "Рубрики: Кейс-стади" in text


def test_build_theme_posts_text_rows_and_empty_state() -> None:
    non_empty = build_theme_posts_text(
        pillar_label="Кейсы",
        total=2,
        rows=[
            {"title": "Кейс 1", "rubric": "case_story", "status": "review", "kind": "daily"},
            {"title": "Кейс 2", "rubric": "case_story", "status": "scheduled", "kind": "longread"},
        ],
        offset=0,
        page_size=8,
        rubric_label=lambda value: {"case_story": "Кейс-стади"}.get(value, value),
        status_badge=lambda value: {"review": "🟡", "scheduled": "✅"}.get(value, "•"),
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}.get(kind, "•"),
        publication_kind_label=lambda kind: {"daily": "ежедневный", "longread": "лонгрид"}.get(kind, kind),
        publication_kind_resolver=lambda row: str(row.get("kind") or "daily"),
        screen_guide=_screen_guide_stub,
    )
    assert "Тематика: Кейсы" in non_empty
    assert "1. 🟡 🤖 Кейс 1" in non_empty
    assert "2. ✅ 📚 Кейс 2" in non_empty
    assert "Рубрика: Кейс-стади" in non_empty

    empty = build_theme_posts_text(
        pillar_label="Кейсы",
        total=0,
        rows=[],
        offset=0,
        page_size=8,
        rubric_label=lambda value: value,
        status_badge=lambda value: value,
        publication_kind_badge=lambda kind: kind,
        publication_kind_label=lambda kind: kind,
        publication_kind_resolver=lambda _row: "daily",
        screen_guide=_screen_guide_stub,
    )
    assert "Постов пока нет." in empty
