from __future__ import annotations

from news.source_catalog import SourceSpec
from news.sources_ui import (
    build_source_detail_text,
    build_source_posts_text,
    build_sources_text,
    build_telegram_channel_detail_text,
)


def _screen_guide_stub(what: str, actions: list[str]) -> str:
    _ = actions
    return f"ℹ️ Что это: {what}"


def test_build_sources_text_lists_catalog_items() -> None:
    specs = [
        SourceSpec(key="alpha", name="Alpha Feed", kind="rss", note="RSS feed", integrated=True),
        SourceSpec(key="beta", name="Beta TG", kind="telegram", note="Telegram feed", integrated=False),
    ]
    text = build_sources_text(
        specs=specs,
        counts_by_key={
            "alpha": {"review": 1, "scheduled": 2, "posted": 0, "failed": 1},
            "beta": {"review": 0, "scheduled": 0, "posted": 1, "failed": 0},
        },
        enabled_map={"alpha": True, "beta": False},
        page=0,
        page_size=12,
        screen_guide=_screen_guide_stub,
    )
    assert "Активных интегрированных источников: 1" in text
    assert "RSS/Search: 1 | Telegram: 1" in text
    assert "1. ✅ Alpha Feed [rss]" in text
    assert "2. 🟡 Beta TG [telegram]" in text
    assert "ожидает настройки" in text


def test_build_source_detail_text_handles_missing_spec() -> None:
    text = build_source_detail_text(
        source_key="missing",
        spec=None,
        enabled_map={},
        counts={},
        screen_guide=_screen_guide_stub,
    )
    assert text == "Источник не найден."


def test_build_source_detail_text_for_telegram_channels() -> None:
    spec = SourceSpec(
        key="telegram_channels",
        name="Telegram Channels",
        kind="telegram",
        note="Telegram pool",
        integrated=True,
    )
    text = build_source_detail_text(
        source_key="telegram_channels",
        spec=spec,
        enabled_map={"telegram_channels": True},
        counts={"review": 2, "scheduled": 3, "posted": 4, "failed": 1},
        telegram_channels=["@legal_news", "@ai_digest"],
        telegram_channel_enabled_map={"legal_news": True, "ai_digest": False},
        telegram_channel_group=lambda value: "legal" if "legal" in value else "ai",
        telegram_channel_group_label=lambda group: {"legal": "⚖️ Право", "ai": "🤖 AI"}[group],
        telegram_channel_label=lambda value: value.strip(),
        screen_guide=_screen_guide_stub,
    )
    assert "Источник: Telegram Channels" in text
    assert "Подключенные каналы: 2" in text
    assert "• ⚖️ Право:" in text
    assert "• 🤖 AI:" in text
    assert "✅ @legal_news" in text
    assert "☐ @ai_digest" in text
    assert "• На проверке: 2" in text


def test_build_telegram_channel_detail_text_contains_core_fields() -> None:
    text = build_telegram_channel_detail_text(
        slug="legal_news",
        enabled=False,
        counts={"review": 1, "scheduled": 2, "posted": 3, "failed": 0},
        group_label="⚖️ Право",
        note="Юридический канал",
        screen_guide=_screen_guide_stub,
    )
    assert "Telegram-канал: @legal_news" in text
    assert "Статус: ☐ Выключен" in text
    assert "Группа: ⚖️ Право" in text
    assert "Ссылка: https://t.me/legal_news" in text


def test_build_source_posts_text_renders_rows_and_empty_state() -> None:
    non_empty = build_source_posts_text(
        source_label="Alpha Feed",
        total=2,
        rows=[
            {"title": "Пост 1", "status": "review", "publish_at": "2026-03-09T10:00:00+03:00", "kind": "daily"},
            {"title": "Пост 2", "status": "scheduled", "publish_at": "2026-03-09T12:00:00+03:00", "kind": "longread"},
        ],
        offset=0,
        page_size=8,
        status_badge=lambda status: {"review": "🟡", "scheduled": "✅"}.get(status, "•"),
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}.get(kind, "•"),
        publication_kind_label=lambda kind: {"daily": "ежедневный", "longread": "лонгрид"}.get(kind, kind),
        publication_kind_resolver=lambda row: str(row.get("kind") or "daily"),
        screen_guide=_screen_guide_stub,
    )
    assert "Источник: Alpha Feed" in non_empty
    assert "Всего постов: 2" in non_empty
    assert "1. 🟡 🤖 Пост 1" in non_empty
    assert "2. ✅ 📚 Пост 2" in non_empty

    empty = build_source_posts_text(
        source_label="Alpha Feed",
        total=0,
        rows=[],
        offset=0,
        page_size=8,
        status_badge=lambda _status: "•",
        publication_kind_badge=lambda _kind: "•",
        publication_kind_label=lambda kind: kind,
        publication_kind_resolver=lambda _row: "daily",
        screen_guide=_screen_guide_stub,
    )
    assert "Постов по этому источнику пока нет." in empty
