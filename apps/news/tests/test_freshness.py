from __future__ import annotations

from datetime import UTC, datetime, timedelta

from news.generate import _drop_stale_source_articles
from news.pipeline import ArticleCandidate
from news.publish import _post_exceeds_freshness_limit
from news.settings import settings


def _article(url: str, published_at: datetime | None) -> ArticleCandidate:
    return ArticleCandidate(
        source_url="https://example.com/feed.xml",
        article_url=url,
        title="Новость",
        summary="Описание новости",
        published_at=published_at,
    )


def test_drop_stale_source_articles_keeps_only_dated_fresh_items(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_max_source_age_days", 3)
    now_utc = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    fresh = _article("https://example.com/fresh", now_utc - timedelta(days=2, hours=23))
    stale = _article("https://example.com/stale", now_utc - timedelta(days=3, seconds=1))
    undated = _article("https://example.com/undated", None)

    filtered, stale_count, undated_count = _drop_stale_source_articles(
        [fresh, stale, undated],
        now_utc,
    )

    assert filtered == [fresh]
    assert stale_count == 1
    assert undated_count == 1


def test_drop_stale_source_articles_keeps_internal_editorial_candidates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_max_source_age_days", 3)
    now_utc = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    internal = _article("internal://weekly-review/2026-W29", None)

    filtered, stale_count, undated_count = _drop_stale_source_articles([internal], now_utc)

    assert filtered == [internal]
    assert stale_count == 0
    assert undated_count == 0


def test_post_freshness_rejects_old_or_overdelayed_queue_items(monkeypatch) -> None:
    monkeypatch.setattr(settings, "news_max_source_age_days", 3)
    now_utc = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)

    assert _post_exceeds_freshness_limit(
        {
            "created_at": (now_utc - timedelta(days=4)).isoformat(),
            "publish_at": now_utc.isoformat(),
        },
        now_utc=now_utc,
    )
    assert _post_exceeds_freshness_limit(
        {
            "created_at": now_utc.isoformat(),
            "publish_at": (now_utc + timedelta(days=4)).isoformat(),
        },
        now_utc=now_utc,
    )
    assert not _post_exceeds_freshness_limit(
        {
            "created_at": (now_utc - timedelta(days=1)).isoformat(),
            "publish_at": (now_utc + timedelta(hours=2)).isoformat(),
        },
        now_utc=now_utc,
    )
