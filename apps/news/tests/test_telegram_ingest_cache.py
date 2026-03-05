from __future__ import annotations

from datetime import datetime, timedelta, timezone

from news.pipeline import ArticleCandidate
from news.settings import settings
from news.telegram_ingest import load_telegram_articles_cache, save_telegram_articles_cache


def test_telegram_cache_roundtrip_and_channel_filter(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "telegram_cache.json"
    monkeypatch.setattr(settings, "news_telegram_cache_path", str(cache_path))

    items = [
        ArticleCandidate(
            source_url="https://t.me/legal_ai",
            article_url="https://t.me/legal_ai/10",
            title="legal",
            summary="legal summary",
            published_at=datetime.now(timezone.utc),
        ),
        ArticleCandidate(
            source_url="https://t.me/ai_newz",
            article_url="https://t.me/ai_newz/11",
            title="ai",
            summary="ai summary",
            published_at=datetime.now(timezone.utc),
        ),
    ]
    save_telegram_articles_cache(items, channels=["@legal_ai", "@ai_newz"])

    filtered = load_telegram_articles_cache(channels=["@legal_ai"], max_age_minutes=120)
    assert len(filtered) == 1
    assert filtered[0].source_url == "https://t.me/legal_ai"


def test_telegram_cache_respects_ttl(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "telegram_cache.json"
    monkeypatch.setattr(settings, "news_telegram_cache_path", str(cache_path))

    item = ArticleCandidate(
        source_url="https://t.me/legal_ai",
        article_url="https://t.me/legal_ai/12",
        title="legal",
        summary="legal summary",
        published_at=datetime.now(timezone.utc),
    )
    save_telegram_articles_cache(
        [item],
        channels=["@legal_ai"],
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )

    assert load_telegram_articles_cache(max_age_minutes=60) == []
