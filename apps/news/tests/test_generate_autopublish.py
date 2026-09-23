from __future__ import annotations

from news import generate
from news.settings import settings


def test_generated_posts_go_straight_to_schedule_by_default(monkeypatch) -> None:
    """Плановый генератор больше не ждёт ручного одобрения: пост сразу в
    расписании и уйдёт в канал сам."""
    monkeypatch.setattr(settings, "news_autopublish_generated", True)
    assert generate.generated_post_status() == "scheduled"


def test_generated_posts_can_be_returned_to_manual_review(monkeypatch) -> None:
    """NEWS_AUTOPUBLISH_GENERATED=0 возвращает прежний режим одной строкой."""
    monkeypatch.setattr(settings, "news_autopublish_generated", False)
    assert generate.generated_post_status() == "review"
