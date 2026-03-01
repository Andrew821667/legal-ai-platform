from __future__ import annotations

from typing import Any

from telegram import ReactionCount, ReactionTypeCustomEmoji, ReactionTypeEmoji

POSITIVE_REACTIONS = {"👍", "❤", "❤️", "🔥", "👏", "⚡", "💯", "🤝", "🎉"}
NEGATIVE_REACTIONS = {"👎", "🤮", "💩", "🤡", "😡", "🙈"}

POSITIVE_COMMENT_MARKERS = (
    "спасибо",
    "полезно",
    "сильно",
    "отлично",
    "класс",
    "интересно",
    "забрал",
    "беру",
    "в точку",
)
NEGATIVE_COMMENT_MARKERS = (
    "вода",
    "слишком общо",
    "слишком общий",
    "банально",
    "ерунда",
    "не согласен",
    "непонятно",
    "слабо",
    "мимо",
    "реклама",
    "продажа",
)


def reaction_type_key(value: Any) -> str:
    if isinstance(value, ReactionTypeEmoji):
        return value.emoji
    if isinstance(value, ReactionTypeCustomEmoji):
        return "custom_emoji"
    emoji = getattr(value, "emoji", None)
    if emoji:
        return str(emoji)
    return str(getattr(value, "type", "unknown"))


def summarize_reaction_counts(reactions: list[ReactionCount] | tuple[ReactionCount, ...]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    positive = 0
    negative = 0
    total = 0

    for row in reactions:
        key = reaction_type_key(row.type)
        count = int(getattr(row, "total_count", 0) or 0)
        counts[key] = count
        total += count
        if key in POSITIVE_REACTIONS:
            positive += count
        elif key in NEGATIVE_REACTIONS:
            negative += count

    top_reactions = [
        {"reaction": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    return {
        "total_count": total,
        "positive_count": positive,
        "negative_count": negative,
        "top_reactions": top_reactions,
        "counts": counts,
    }


def classify_comment_signal(text: str) -> tuple[int, str]:
    normalized = " ".join((text or "").lower().split())
    if not normalized:
        return 0, "neutral"

    positive_hits = sum(1 for marker in POSITIVE_COMMENT_MARKERS if marker in normalized)
    negative_hits = sum(1 for marker in NEGATIVE_COMMENT_MARKERS if marker in normalized)

    if negative_hits > positive_hits:
        return -1, "negative"
    if positive_hits > negative_hits:
        return 1, "positive"
    return 0, "neutral"


def feedback_score(snapshot: dict[str, Any] | None) -> int:
    data = snapshot or {}
    return (
        int(data.get("reaction_positive", 0))
        + int(data.get("comments_positive", 0)) * 2
        - int(data.get("reaction_negative", 0)) * 2
        - int(data.get("comments_negative", 0)) * 3
    )


def select_negative_feedback_examples(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        snapshot = row.get("feedback_snapshot") or {}
        negative_total = int(snapshot.get("reaction_negative", 0)) + int(snapshot.get("comments_negative", 0))
        if negative_total <= 0:
            continue
        score = int(snapshot.get("score", feedback_score(snapshot)))
        positive_total = int(snapshot.get("reaction_positive", 0)) + int(snapshot.get("comments_positive", 0))
        if score > -2 and positive_total > negative_total:
            continue

        selected.append(
            {
                "post_id": row.get("id"),
                "title": row.get("title") or "",
                "text": row.get("text") or "",
                "score": score,
                "negative_total": negative_total,
                "recent_negative_comments": list(snapshot.get("recent_negative_comments") or [])[:3],
            }
        )

    selected.sort(key=lambda item: (item["score"], -item["negative_total"]))
    return selected[:limit]


def render_negative_feedback_context(examples: list[dict[str, Any]], limit: int = 4) -> str:
    if not examples:
        return ""

    lines = ["Сигналы слабой реакции аудитории на похожие прошлые посты:"]
    for idx, example in enumerate(examples[:limit], start=1):
        title = " ".join(str(example.get("title") or "").split())[:120] or f"Пост {idx}"
        comments = example.get("recent_negative_comments") or []
        lines.append(
            f"{idx}. {title} | score={example.get('score')} | negative={example.get('negative_total')}"
        )
        for comment in comments[:2]:
            lines.append(f"   - {comment[:180]}")
    return "\n".join(lines)
