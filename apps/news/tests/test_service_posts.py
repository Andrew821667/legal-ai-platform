from __future__ import annotations

from datetime import date, timedelta

from news.llm_writer import LLMNewsWriter
from news.service_posts import service_post_count, service_post_for


def test_service_posts_form_a_long_rotation_and_pass_manual_quality_gate() -> None:
    start = date(2026, 1, 1)
    posts = [service_post_for(start + timedelta(weeks=week)) for week in range(service_post_count())]

    assert len({post.slug for post in posts}) == service_post_count()
    assert service_post_count() >= 10
    for post in posts:
        assert post.title.startswith("Практика AI Verdict:")
        assert "<b>Следующий шаг</b>" in post.text
        assert "ai-verdict.ru" in post.text
        assert "купить" not in post.text.lower()
        assert LLMNewsWriter._quality_gate_failure_reason(
            post.text,
            "promo_offer",
            manual_editorial=True,
        ) is None
