from __future__ import annotations

from typing import Any


def default_feedback_snapshot() -> dict[str, Any]:
    return {
        "reaction_total": 0,
        "reaction_positive": 0,
        "reaction_negative": 0,
        "comments_total": 0,
        "comments_positive": 0,
        "comments_negative": 0,
        "last_signal_at": None,
        "top_reactions": [],
        "recent_negative_comments": [],
    }


def feedback_score(snapshot: dict[str, Any] | None) -> int:
    state = default_feedback_snapshot()
    if snapshot:
        state.update(snapshot)
    return (
        int(state.get("reaction_positive", 0))
        + int(state.get("comments_positive", 0)) * 2
        - int(state.get("reaction_negative", 0)) * 2
        - int(state.get("comments_negative", 0)) * 3
    )


def apply_feedback_signal(
    snapshot: dict[str, Any] | None,
    *,
    source: str,
    signal_value: int,
    text: str | None,
    payload: dict[str, Any] | None,
    created_at_iso: str | None,
) -> dict[str, Any]:
    state = default_feedback_snapshot()
    if snapshot:
        state.update(snapshot)

    meta = payload or {}

    if source == "reaction_count":
        state["reaction_total"] = int(meta.get("total_count", 0))
        state["reaction_positive"] = int(meta.get("positive_count", 0))
        state["reaction_negative"] = int(meta.get("negative_count", 0))
        top_reactions = meta.get("top_reactions") or []
        if isinstance(top_reactions, list):
            state["top_reactions"] = top_reactions[:5]
    elif source == "comment":
        state["comments_total"] = int(state.get("comments_total", 0)) + 1
        if signal_value > 0:
            state["comments_positive"] = int(state.get("comments_positive", 0)) + 1
        elif signal_value < 0:
            state["comments_negative"] = int(state.get("comments_negative", 0)) + 1
            excerpt = " ".join((text or "").split())[:240]
            if excerpt:
                recent = list(state.get("recent_negative_comments") or [])
                recent.insert(0, excerpt)
                state["recent_negative_comments"] = recent[:5]

    if created_at_iso:
        state["last_signal_at"] = created_at_iso

    state["score"] = feedback_score(state)
    return state
