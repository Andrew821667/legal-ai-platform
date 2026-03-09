from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


def compose_create_post_text(
    *,
    draft: dict[str, Any],
    ensure_create_draft_footer: Callable[[dict[str, Any]], dict[str, Any]],
    compose_manual_post_html: Callable[..., str],
) -> str:
    ensure_create_draft_footer(draft)
    return compose_manual_post_html(
        str(draft.get("title") or ""),
        str(draft.get("text") or ""),
        str(draft.get("kind") or ""),
        footer_text=str(draft.get("footer_text") or ""),
    )


def build_create_post_payload(
    *,
    draft: dict[str, Any],
    status: str,
    publish_at: datetime,
    channel_id: str | int | None,
    channel_username: str | None,
    compose_create_post_text_fn: Callable[[dict[str, Any]], str],
    manual_theme_rubric: Callable[[str], str],
    manual_post_kind_rubric: Callable[[str], str],
) -> dict[str, Any]:
    title = str(draft.get("title") or "").strip()
    mode = str(draft.get("mode") or "manual")
    kind = str(draft.get("kind") or "")
    theme = str(draft.get("theme") or "")
    source_url = str(draft.get("source_url") or "").strip()
    resolved_source_url = source_url or f"manual://{theme or 'manual'}/{kind or 'post'}"
    resolved_kind = kind or "generic"
    rubric = manual_theme_rubric(theme) or manual_post_kind_rubric(kind)
    return {
        "channel_id": channel_id or None,
        "channel_username": channel_username or None,
        "title": title or None,
        "text": compose_create_post_text_fn(draft),
        "media_urls": list(draft.get("media_urls") or []) or None,
        "source_url": resolved_source_url,
        "publish_at": publish_at.isoformat(),
        "status": status,
        "format_type": f"{'manual' if mode == 'manual' else 'operator_ai'}_{resolved_kind}",
        "cta_type": kind or "manual",
        "rubric": rubric,
    }


def build_generation_preview_payload(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": preview["title"],
        "text": preview["text"],
        "rubric": preview["rubric"],
        "format_type": preview["format_type"],
        "cta_type": preview["cta_type"],
        "source_url": preview["source_url"],
        "source_hash": preview["source_hash"],
        "channel_id": preview["channel_id"] or None,
        "channel_username": preview["channel_username"] or None,
        "publish_at": preview["publish_at"],
        "status": "review",
    }
