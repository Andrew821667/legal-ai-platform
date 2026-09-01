from __future__ import annotations

from types import SimpleNamespace

from news.rss_fetcher import fetch_rss_articles, probe_rss_sources
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
    captured = SimpleNamespace(timeout=None, headers=None, proxies=None)

    def fake_get(url: str, *, timeout: int, headers: dict[str, str], proxies: dict[str, str] | None):
        assert url == "https://example.com/feed.xml"
        captured.timeout = timeout
        captured.headers = headers
        captured.proxies = proxies
        return _Response()

    monkeypatch.setattr(settings, "news_rss_fetch_timeout_seconds", 9)
    monkeypatch.setattr(settings, "news_rss_proxy_url", "")
    monkeypatch.setattr("news.rss_fetcher.requests.get", fake_get)

    articles = fetch_rss_articles(["https://example.com/feed.xml"])

    assert len(articles) == 1
    assert articles[0].article_url == "https://example.com/item"
    assert captured.timeout == 9
    assert captured.headers == {"User-Agent": "AI-Verdict-News/1.0"}
    assert captured.proxies is None


def test_fetch_rss_articles_uses_dedicated_proxy(monkeypatch) -> None:
    captured = SimpleNamespace(proxies=None)

    def fake_get(url: str, *, timeout: int, headers: dict[str, str], proxies: dict[str, str] | None):
        captured.proxies = proxies
        return _Response()

    monkeypatch.setattr(settings, "news_rss_proxy_url", "http://host.docker.internal:14809")
    monkeypatch.setattr("news.rss_fetcher.requests.get", fake_get)

    articles = fetch_rss_articles(["https://example.com/feed.xml"])

    assert len(articles) == 1
    assert captured.proxies == {
        "http": "http://host.docker.internal:14809",
        "https": "http://host.docker.internal:14809",
    }


def test_fetch_rss_articles_keeps_other_sources_when_one_fails(monkeypatch) -> None:
    def fake_get(url: str, *, timeout: int, headers: dict[str, str], proxies: dict[str, str] | None):
        _ = timeout, headers, proxies
        if url.endswith("broken.xml"):
            raise TimeoutError("source timed out")
        return _Response()

    monkeypatch.setattr(settings, "news_rss_fetch_workers", 2)
    monkeypatch.setattr(settings, "news_rss_proxy_url", "")
    monkeypatch.setattr("news.rss_fetcher.requests.get", fake_get)

    articles = fetch_rss_articles(
        ["https://example.com/broken.xml", "https://example.com/working.xml"]
    )

    assert len(articles) == 1
    assert articles[0].article_url == "https://example.com/item"


def test_probe_rss_sources_reports_each_source(monkeypatch) -> None:
    def fake_get(url: str, *, timeout: int, headers: dict[str, str], proxies: dict[str, str] | None):
        _ = timeout, headers, proxies
        if url.endswith("broken.xml"):
            raise TimeoutError("source timed out")
        return _Response()

    monkeypatch.setattr(settings, "news_rss_fetch_workers", 2)
    monkeypatch.setattr(settings, "news_rss_proxy_url", "")
    monkeypatch.setattr("news.rss_fetcher.requests.get", fake_get)

    rows = probe_rss_sources(
        ["https://example.com/working.xml", "https://example.com/broken.xml"]
    )

    assert [(row.available, row.entry_count) for row in rows] == [(True, 1), (False, 0)]
    assert rows[1].error.startswith("TimeoutError:")
