from __future__ import annotations

from datetime import datetime, timezone

from news.create_payloads import (
    build_create_post_payload,
    build_generation_preview_payload,
    compose_create_post_text,
)


def test_compose_create_post_text_calls_footer_enricher() -> None:
    draft = {"title": "Заголовок", "text": "Текст", "kind": "opinion"}
    called: list[bool] = []

    def _ensure_footer(state: dict[str, object]) -> dict[str, object]:
        called.append(True)
        state["footer_text"] = "Футер"
        return state

    def _compose_html(title: str, text: str, kind: str, *, footer_text: str) -> str:
        return f"{title}|{text}|{kind}|{footer_text}"

    result = compose_create_post_text(
        draft=draft,
        ensure_create_draft_footer=_ensure_footer,
        compose_manual_post_html=_compose_html,
    )

    assert called == [True]
    assert result == "Заголовок|Текст|opinion|Футер"
    assert draft["footer_text"] == "Футер"


def test_build_create_post_payload_manual_and_fallbacks() -> None:
    publish_at = datetime(2026, 3, 9, 18, 0, tzinfo=timezone.utc)
    payload = build_create_post_payload(
        draft={
            "title": "  Новый пост  ",
            "mode": "manual",
            "kind": "opinion",
            "theme": "regulation",
            "source_url": "",
            "media_urls": [],
        },
        status="review",
        publish_at=publish_at,
        channel_id=-100123,
        channel_username="@channel",
        compose_create_post_text_fn=lambda _draft: "<b>html</b>",
        manual_theme_rubric=lambda theme: "ai_law" if theme == "regulation" else "",
        manual_post_kind_rubric=lambda kind: "manual" if kind else "",
    )
    assert payload["channel_id"] == -100123
    assert payload["channel_username"] == "@channel"
    assert payload["title"] == "Новый пост"
    assert payload["text"] == "<b>html</b>"
    assert payload["media_urls"] is None
    assert payload["source_url"] == "manual://regulation/opinion"
    assert payload["publish_at"] == publish_at.isoformat()
    assert payload["status"] == "review"
    assert payload["format_type"] == "manual_opinion"
    assert payload["cta_type"] == "opinion"
    assert payload["rubric"] == "ai_law"


def test_build_create_post_payload_ai_empty_kind() -> None:
    publish_at = datetime(2026, 3, 9, 18, 0, tzinfo=timezone.utc)
    payload = build_create_post_payload(
        draft={
            "mode": "ai",
            "kind": "",
            "theme": "",
            "source_url": "",
        },
        status="draft",
        publish_at=publish_at,
        channel_id=None,
        channel_username=None,
        compose_create_post_text_fn=lambda _draft: "text",
        manual_theme_rubric=lambda _theme: "",
        manual_post_kind_rubric=lambda _kind: "manual",
    )
    assert payload["channel_id"] is None
    assert payload["channel_username"] is None
    assert payload["title"] is None
    assert payload["source_url"] == "manual://manual/post"
    assert payload["format_type"] == "operator_ai_generic"
    assert payload["cta_type"] == "manual"
    assert payload["rubric"] == "manual"


def test_build_generation_preview_payload() -> None:
    payload = build_generation_preview_payload(
        {
            "title": "T",
            "text": "Body",
            "rubric": "legal_ops",
            "format_type": "daily",
            "cta_type": "soft",
            "source_url": "https://example.com",
            "source_hash": "abc",
            "channel_id": "",
            "channel_username": "",
            "publish_at": "2026-03-09T18:00:00+03:00",
        }
    )
    assert payload["title"] == "T"
    assert payload["text"] == "Body"
    assert payload["channel_id"] is None
    assert payload["channel_username"] is None
    assert payload["status"] == "review"
