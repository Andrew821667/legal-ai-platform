from __future__ import annotations

from types import SimpleNamespace

from news.rss_fetcher import fetch_rss_articles
from news.settings import settings


class _Response:
    content = b"""
        <rss version="2.0"><channel><title>Test</title>
        <item><title>Fresh legal AI news</title><link>https://example.com/item</link>
        <description>Useful details</description><pubDate>Mon, 13 Jul 2026 08:00:00 GMT</pubDate></item>
        </channel></rss>
    """

    def raise_for_status(self) -> None:
        return None


def test_fetch_rss_articles_uses_explicit_http_timeout(monkeypatch) -> None:
    captured = SimpleNamespace(timeout=None, headers=None)

    def fake_get(url: str, *, timeout: int, headers: dict[str, str]):
        assert url == "https://example.com/feed.xml"
        captured.timeout = timeout
        captured.headers = headers
        return _Response()

    monkeypatch.setattr(settings, "news_rss_fetch_timeout_seconds", 9)
    monkeypatch.setattr("news.rss_fetcher.requests.get", fake_get)

    articles = fetch_rss_articles(["https://example.com/feed.xml"])

    assert len(articles) == 1
    assert articles[0].article_url == "https://example.com/item"
    assert captured.timeout == 9
    assert captured.headers == {"User-Agent": "AI-Verdict-News/1.0"}
