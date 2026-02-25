from __future__ import annotations

import argparse
import logging
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from news.core_client import CoreClient
from news.llm_writer import LLMNewsWriter
from news.logging_config import setup_logging
from news.pipeline import (
    build_source_hash,
    canonicalize_url,
    choose_top_articles,
    lexical_similarity,
    parse_schedule_slots,
)
from news.rag import PostedContentRAG
from news.rss_fetcher import fetch_rss_articles
from news.settings import settings

setup_logging()
logger = logging.getLogger(__name__)


def _parse_sources() -> list[str]:
    return [url.strip() for url in settings.news_source_urls.split(",") if url.strip()]


def _parse_priority_domains() -> set[str]:
    domains: set[str] = set()
    for raw in settings.news_priority_domains.split(","):
        item = raw.strip().lower()
        if not item:
            continue
        if "://" in item:
            parsed = urlparse(item)
            host = parsed.netloc.lower()
        else:
            host = item
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return domains


def _collect_history(client: CoreClient) -> tuple[list[str], set[str]]:
    texts: list[str] = []
    source_urls: set[str] = set()
    for status in ("posted", "scheduled", "publishing"):
        try:
            response = client.list_posts(
                limit=settings.news_history_scan_limit,
                status=status,
                newest_first=True,
            )
            response.raise_for_status()
            rows = response.json()
            for row in rows:
                text = (row.get("text") or "").strip()
                if text:
                    texts.append(text)
                url = canonicalize_url(row.get("source_url") or "")
                if url:
                    source_urls.add(url)
        except Exception as exc:
            logger.warning("history_scan_failed", extra={"status": status, "error": str(exc)})
    return texts, source_urls


def _build_schedule(now_local: datetime, count: int, slots: list[tuple[int, int]]) -> list[datetime]:
    sorted_slots = sorted(slots)
    plan: list[datetime] = []

    for day_offset in range(0, 14):
        day = (now_local + timedelta(days=day_offset)).date()
        for hour, minute in sorted_slots:
            candidate = datetime.combine(day, time(hour=hour, minute=minute), tzinfo=now_local.tzinfo)
            if candidate <= now_local:
                continue
            plan.append(candidate)
            if len(plan) >= count:
                return plan

    raise RuntimeError("Unable to build publish schedule for generated posts")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scheduled channel posts from RSS + LLM")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=settings.news_top_k)
    args = parser.parse_args()

    if not settings.api_key_news:
        logger.error("API_KEY_NEWS is required")
        return 1
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is required for content generation")
        return 1

    source_urls = _parse_sources()
    if not source_urls:
        logger.error("NEWS_SOURCE_URLS is empty; generator cannot run")
        return 1

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo(settings.tz_name))

    articles = fetch_rss_articles(source_urls)
    if not articles:
        logger.info("No articles fetched from sources")
        return 0

    priority_domains = _parse_priority_domains()
    top_limit = max(1, min(args.limit, 20))
    selected_articles = choose_top_articles(
        articles,
        limit=top_limit,
        now_utc=now_utc,
        priority_domains=priority_domains,
        max_per_source=settings.news_max_per_source,
    )
    if not selected_articles:
        logger.info("No relevant articles selected")
        return 0

    slots = parse_schedule_slots(settings.news_schedule_slots)
    schedule = _build_schedule(now_local, len(selected_articles), slots)

    core_client = CoreClient(settings.core_api_url, settings.api_key_news)
    rag = PostedContentRAG(core_client)
    writer = LLMNewsWriter()
    history_texts, existing_source_urls = _collect_history(core_client)

    created = 0
    previewed = 0
    duplicates = 0
    failed = 0

    slot_idx = 0
    for article in selected_articles:
        try:
            article_canonical_url = canonicalize_url(article.article_url)
            if article_canonical_url and article_canonical_url in existing_source_urls:
                duplicates += 1
                logger.info("source_url_duplicate_skipped", extra={"source_url": article.article_url})
                continue

            query_text = f"{article.title}\n{article.summary}"
            rag_context = rag.find_context(query_text, history_limit=50, top_k=3)
            generated = writer.generate_post(article, rag_context)

            max_similarity = 0.0
            if history_texts:
                max_similarity = max(lexical_similarity(generated["text"], prev_text) for prev_text in history_texts)
            if max_similarity >= settings.news_similarity_threshold:
                duplicates += 1
                logger.info(
                    "semantic_duplicate_skipped",
                    extra={
                        "source_url": article.article_url,
                        "similarity": round(max_similarity, 4),
                        "threshold": settings.news_similarity_threshold,
                    },
                )
                continue

            source_hash = build_source_hash(article.article_url, article.title, article.published_at)
            if slot_idx >= len(schedule):
                logger.warning("schedule_slots_exhausted")
                break
            publish_at_utc = schedule[slot_idx].astimezone(timezone.utc)

            payload = {
                "title": generated["title"],
                "text": generated["text"],
                "rubric": generated["rubric"],
                "source_url": article.article_url,
                "source_hash": source_hash,
                "channel_id": settings.telegram_channel_id or None,
                "channel_username": settings.telegram_channel_username or None,
                "publish_at": publish_at_utc.isoformat(),
                "status": "scheduled",
            }

            if args.dry_run:
                previewed += 1
                history_texts.append(generated["text"])
                if article_canonical_url:
                    existing_source_urls.add(article_canonical_url)
                logger.info(
                    "dry_run_preview",
                    extra={
                        "source_url": article.article_url,
                        "title": generated["title"][:120],
                        "publish_at": payload["publish_at"],
                        "text_preview": generated["text"][:700],
                    },
                )
                slot_idx += 1
                continue

            response = core_client.create_scheduled_post(payload)
            if response.status_code in (200, 201):
                created += 1
                slot_idx += 1
                history_texts.append(generated["text"])
                if article_canonical_url:
                    existing_source_urls.add(article_canonical_url)
                logger.info(
                    "scheduled_post_created",
                    extra={
                        "source_url": article.article_url,
                        "publish_at": payload["publish_at"],
                        "dry_run": args.dry_run,
                    },
                )
            elif response.status_code == 409:
                duplicates += 1
                logger.info("duplicate_post_skipped", extra={"source_url": article.article_url})
            else:
                failed += 1
                logger.error(
                    "scheduled_post_create_failed",
                    extra={"status": response.status_code, "body": response.text[:500]},
                )

        except Exception as exc:
            failed += 1
            logger.exception("article_generation_failed", extra={"article_url": article.article_url, "error": str(exc)})

    logger.info(
        "generation_completed",
        extra={
            "fetched": len(articles),
            "selected": len(selected_articles),
            "created": created,
            "previewed": previewed,
            "duplicates": duplicates,
            "failed": failed,
            "dry_run": args.dry_run,
        },
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
