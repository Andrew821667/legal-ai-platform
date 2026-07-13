from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests

from news.pipeline import ArticleCandidate, canonicalize_url
from news.settings import settings

logger = logging.getLogger(__name__)
_HTML_RE = re.compile(r"<[^>]+>")


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


def fetch_rss_articles(source_urls: list[str], per_source_limit: int = 30) -> list[ArticleCandidate]:
    items: list[ArticleCandidate] = []

    for source_url in source_urls:
        try:
            response = requests.get(
                source_url,
                timeout=max(3, settings.news_rss_fetch_timeout_seconds),
                headers={"User-Agent": "AI-Verdict-News/1.0"},
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.get("bozo"):
                logger.warning(
                    "rss_source_parse_warning",
                    extra={"source_url": source_url, "error": str(feed.get("bozo_exception", "unknown"))},
                )

            entries = feed.entries[:per_source_limit]
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
        except Exception as exc:
            logger.exception("rss_source_fetch_failed", extra={"source_url": source_url, "error": str(exc)})

    # URL-level dedup.
    deduped: dict[str, ArticleCandidate] = {}
    for item in items:
        deduped[canonicalize_url(item.article_url)] = item
    return list(deduped.values())
