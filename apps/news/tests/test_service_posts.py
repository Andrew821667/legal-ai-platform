from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from news import generate
from news.llm_writer import LLMNewsWriter
from news.service_posts import service_post_count, service_post_for
from news.settings import settings


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


def test_service_slot_does_not_need_fresh_news_or_llm_calls(monkeypatch) -> None:
    monkeypatch.setattr(settings, "api_key_news", "test-key")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(generate, "_load_controls", lambda client: [])
    monkeypatch.setattr(generate, "_collect_history", lambda *args: ([], set(), {}, [], [], set()))
    monkeypatch.setattr(generate, "fetch_rss_articles", lambda urls: [])
    monkeypatch.setattr(generate, "enabled_telegram_channels", lambda rows: [])
    slot = SimpleNamespace(
        publication_kind="services", format_type="manual_promo_offer", cta_type="soft",
        publish_at_local=datetime(2026, 10, 15, 15, tzinfo=UTC),
    )
    monkeypatch.setattr(generate, "build_publish_plan", lambda *args, **kwargs: [slot])

    def no_llm(*args, **kwargs):
        raise AssertionError("Service posts must not call the LLM or embeddings")

    monkeypatch.setattr(generate, "LLMNewsWriter", no_llm)
    monkeypatch.setattr(generate, "PostedContentRAG", no_llm)
    result = generate.collect_generation_previews(1)

    assert len(result.previews) == 1
    assert result.previews[0]["publication_kind"] == "services"
