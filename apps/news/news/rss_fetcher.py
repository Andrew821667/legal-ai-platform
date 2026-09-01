from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from itertools import repeat

import feedparser
import requests

from news.pipeline import ArticleCandidate, canonicalize_url
from news.settings import settings

logger = logging.getLogger(__name__)
_HTML_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class RSSSourceResult:
    source_url: str
    articles: list[ArticleCandidate]
    available: bool
    entry_count: int
    error: str = ""


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _HTML_RE.sub(" ", text or "")).strip()


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    published_raw = entry.get("published") or entry.get("updated")
    if published_raw:
        try:
            dt = parsedate_to_datetime(published_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except Exception:
            pass

    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=UTC)
        except Exception:
            return None
    return None


def _fetch_source(
    source_url: str,
    per_source_limit: int,
    proxies: dict[str, str] | None,
) -> RSSSourceResult:
    try:
        response = requests.get(
            source_url,
            timeout=max(3, settings.news_rss_fetch_timeout_seconds),
            headers={"User-Agent": "AI-Verdict-News/1.0"},
            proxies=proxies,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.get("bozo"):
            logger.warning(
                "rss_source_parse_warning",
                extra={"source_url": source_url, "error": str(feed.get("bozo_exception", "unknown"))},
            )

        entries = feed.entries[:per_source_limit]
        items: list[ArticleCandidate] = []
        for entry in entries:
            article_url = (entry.get("link") or source_url).strip()
            title = (entry.get("title") or "").strip()
            content_value = ""
            content_items = entry.get("content")
            if isinstance(content_items, list) and content_items:
                content_value = content_items[0].get("value") or ""
            summary = _strip_html(entry.get("summary") or entry.get("description") or content_value)
            if not article_url or not title:
                continue
            items.append(
                ArticleCandidate(
                    source_url=source_url,
                    article_url=article_url,
                    title=title,
                    summary=summary,
                    published_at=_parse_published(entry),
                )
            )

        logger.info("rss_source_fetched", extra={"source_url": source_url, "count": len(entries)})
        return RSSSourceResult(
            source_url=source_url,
            articles=items,
            available=True,
            entry_count=len(entries),
        )
    except Exception as exc:
        logger.exception("rss_source_fetch_failed", extra={"source_url": source_url, "error": str(exc)})
        return RSSSourceResult(
            source_url=source_url,
            articles=[],
            available=False,
            entry_count=0,
            error=f"{type(exc).__name__}: {exc}"[:240],
        )


def _fetch_sources(source_urls: list[str], per_source_limit: int) -> list[RSSSourceResult]:
    if not source_urls:
        return []

    proxy_url = settings.news_rss_proxy_url.strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    worker_count = min(len(source_urls), max(1, settings.news_rss_fetch_workers))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="rss") as pool:
        return list(
            pool.map(
                _fetch_source,
                source_urls,
                repeat(per_source_limit),
                repeat(proxies),
            )
        )


def probe_rss_sources(source_urls: list[str]) -> list[RSSSourceResult]:
    """Check source reachability without downloading the full article pool."""
    return _fetch_sources(source_urls, per_source_limit=1)


def fetch_rss_articles(source_urls: list[str], per_source_limit: int = 30) -> list[ArticleCandidate]:
    items: list[ArticleCandidate] = []
    for result in _fetch_sources(source_urls, per_source_limit):
        items.extend(result.articles)

    # URL-level dedup.
    deduped: dict[str, ArticleCandidate] = {}
    for item in items:
        deduped[canonicalize_url(item.article_url)] = item
    return list(deduped.values())
