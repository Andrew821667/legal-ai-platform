from __future__ import annotations

from news.source_catalog import SourceSpec
from news.sources_keyboard_ui import (
    build_source_detail_keyboard_rows,
    build_source_posts_keyboard_rows,
    build_sources_keyboard_rows,
    build_telegram_channel_detail_keyboard_rows,
)


def _inline_button(text: str, callback_data: str | None = None, *, style: str | None = None) -> dict[str, str | None]:
    return {"text": text, "callback_data": callback_data, "style": style}


def _url_button(text: str, url: str) -> dict[str, str]:
    return {"text": text, "url": url}


def _submenu_nav_rows(*, back_callback: str, back_label: str = "🔙 Назад") -> list[list[dict[str, str | None]]]:
    return [
        [_inline_button(back_label, callback_data=back_callback)],
        [_inline_button("🏠 Рабочий стол", callback_data="refresh")],
    ]


def _callbacks(rows: list[list[dict[str, str | None]]]) -> list[str]:
    result: list[str] = []
    for row in rows:
        for button in row:
            value = button.get("callback_data")
            if value:
                result.append(value)
    return result


def test_build_sources_keyboard_rows_pagination_and_sections() -> None:
    specs = [
        SourceSpec(key="alpha", name="Alpha Feed", kind="rss", note="A"),
        SourceSpec(key="beta", name="Beta Feed", kind="rss", note="B"),
        SourceSpec(key="gamma", name="Gamma Feed", kind="telegram", note="C"),
    ]
    rows = build_sources_keyboard_rows(
        specs=specs,
        page=0,
        page_size=2,
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "srd:telegram_channels" in callbacks
    assert "srcm:0" in callbacks
    assert "srd:alpha" in callbacks
    assert "srd:beta" in callbacks
    assert "srcm:1" in callbacks
    assert "sec:generate" in callbacks
    assert "sec:themes" in callbacks
    assert "refresh" in callbacks


def test_build_sources_keyboard_rows_second_page_has_prev_only() -> None:
    specs = [
        SourceSpec(key="alpha", name="Alpha Feed", kind="rss", note="A"),
        SourceSpec(key="beta", name="Beta Feed", kind="rss", note="B"),
        SourceSpec(key="gamma", name="Gamma Feed", kind="telegram", note="C"),
    ]
    rows = build_sources_keyboard_rows(
        specs=specs,
        page=1,
        page_size=2,
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "srcm:0" in callbacks
    assert "srcm:2" not in callbacks
    assert "srd:gamma" in callbacks


def test_build_source_detail_keyboard_rows_non_integrated_has_no_posts_button() -> None:
    spec = SourceSpec(key="beta", name="Beta Feed", kind="rss", note="B", integrated=False)
    rows = build_source_detail_keyboard_rows(
        source_key="beta",
        spec=spec,
        enabled=True,
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
        button_style_success="success",
    )
    callbacks = _callbacks(rows)
    assert "srt:beta" in callbacks
    assert "src:beta:0" not in callbacks


def test_build_source_detail_keyboard_rows_telegram_channels() -> None:
    spec = SourceSpec(key="telegram_channels", name="Telegram", kind="telegram", note="TG", integrated=True)
    rows = build_source_detail_keyboard_rows(
        source_key="telegram_channels",
        spec=spec,
        enabled=False,
        telegram_channels=["@legal_news", "@ai_digest", "@legal_ops"],
        telegram_channel_enabled_map={"legal_news": True, "ai_digest": False, "legal_ops": True},
        telegram_channel_group=lambda value: "legal" if "legal" in value else "ai",
        telegram_channel_group_label=lambda group: {"legal": "⚖️ Право", "ai": "🤖 AI"}[group],
        telegram_channel_slug=lambda value: value.strip().lower().removeprefix("@"),
        telegram_channel_label=lambda value: value.strip(),
        inline_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
        button_style_success="success",
    )
    callbacks = _callbacks(rows)
    assert "srt:telegram_channels" in callbacks
    assert "src:telegram_channels:0" in callbacks
    assert "stc:legal_news" in callbacks
    assert "stc:ai_digest" in callbacks
    assert rows[0][0]["style"] == "success"


def test_build_telegram_channel_detail_keyboard_rows() -> None:
    rows = build_telegram_channel_detail_keyboard_rows(
        slug="@legal_news",
        enabled=False,
        inline_button=_inline_button,
        url_button=_url_button,
        button_style_success="success",
    )
    assert rows[0][0]["callback_data"] == "scc:legal_news"
    assert rows[0][0]["style"] == "success"
    assert rows[1][0]["url"] == "https://t.me/legal_news"
    assert rows[2][0]["callback_data"] == "srd:telegram_channels"
    assert rows[2][1]["callback_data"] == "refresh"


def test_build_source_posts_keyboard_rows() -> None:
    rows = build_source_posts_keyboard_rows(
        source_key="alpha",
        total=20,
        rows=[
            {"id": "p1", "title": "Первый пост", "status": "review", "kind": "daily"},
            {"id": "p2", "title": "Второй пост", "status": "scheduled", "kind": "longread"},
        ],
        offset=8,
        page_size=8,
        status_badge=lambda status: {"review": "🟡", "scheduled": "✅"}.get(status, "•"),
        publication_kind_badge=lambda kind: {"daily": "🤖", "longread": "📚"}.get(kind, "•"),
        publication_kind_resolver=lambda row: str(row.get("kind") or "daily"),
        callback_button=_inline_button,
        submenu_nav_rows=_submenu_nav_rows,
    )
    callbacks = _callbacks(rows)
    assert "pv:p1:src_alpha:8" in callbacks
    assert "pv:p2:src_alpha:8" in callbacks
    assert "src:alpha:0" in callbacks
    assert "src:alpha:16" in callbacks
    assert "sec:sources" in callbacks
