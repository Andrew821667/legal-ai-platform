from __future__ import annotations

from news.feedback import (
    classify_comment_signal,
    feedback_score,
    render_negative_feedback_context,
    select_negative_feedback_examples,
)


def test_classify_comment_signal_negative() -> None:
    score, sentiment = classify_comment_signal("Слишком общо и опять вода, практики мало")
    assert score == -1
    assert sentiment == "negative"


def test_classify_comment_signal_positive() -> None:
    score, sentiment = classify_comment_signal("Спасибо, очень полезно и прямо в точку")
    assert score == 1
    assert sentiment == "positive"


def test_select_negative_feedback_examples_uses_snapshot() -> None:
    rows = [
        {
            "id": "a",
            "title": "Слабый пост",
            "text": "Поверхностный обзор legal ai",
            "feedback_snapshot": {
                "reaction_positive": 0,
                "reaction_negative": 2,
                "comments_positive": 0,
                "comments_negative": 1,
                "recent_negative_comments": ["Слишком общо"],
            },
        },
        {
            "id": "b",
            "title": "Сильный пост",
            "text": "Глубокий разбор red flags",
            "feedback_snapshot": {
                "reaction_positive": 12,
                "reaction_negative": 0,
                "comments_positive": 2,
                "comments_negative": 0,
            },
        },
    ]

    examples = select_negative_feedback_examples(rows)
    assert len(examples) == 1
    assert examples[0]["post_id"] == "a"
    assert feedback_score(rows[0]["feedback_snapshot"]) < 0


def test_render_negative_feedback_context_includes_comment_excerpt() -> None:
    text = render_negative_feedback_context(
        [
            {
                "title": "Пост про legal ops",
                "score": -4,
                "negative_total": 3,
                "recent_negative_comments": ["Слишком общо и мало прикладной пользы"],
            }
        ]
    )
    assert "Сигналы слабой реакции аудитории" in text
    assert "Слишком общо" in text
