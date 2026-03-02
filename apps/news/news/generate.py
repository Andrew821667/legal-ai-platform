from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from news.core_client import CoreClient
from news.feedback import render_negative_feedback_context, select_negative_feedback_examples
from news.llm_writer import LLMNewsWriter
from news.logging_config import setup_logging
from news.pipeline import (
    ArticleCandidate,
    build_source_hash,
    canonicalize_url,
    choose_top_articles,
    default_pillar_targets,
    lexical_similarity,
    normalize_rubric_to_pillar,
    pillar_for_article,
    urgency_score,
)
from news.rag import PostedContentRAG
from news.rss_fetcher import fetch_rss_articles
from news.settings import settings
from news.strategy import build_publish_plan

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


def _load_controls(client: CoreClient) -> dict[str, bool]:
    try:
        response = client.list_automation_controls(scope="news")
        response.raise_for_status()
        rows = response.json()
    except Exception as exc:
        logger.warning("automation_controls_fetch_failed", extra={"error": str(exc)})
        return {}

    controls: dict[str, bool] = {}
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        controls[key] = bool(row.get("enabled", True))
    return controls


def _is_enabled(controls: dict[str, bool], key: str, default: bool = True) -> bool:
    return controls.get(key, default)


def _collect_history(
    client: CoreClient,
) -> tuple[list[str], set[str], dict[str, int], list[dict[str, str]], list[dict[str, str]]]:
    texts: list[str] = []
    source_urls: set[str] = set()
    recent_pillar_counts: dict[str, int] = {}
    posted_items: list[dict[str, str]] = []

    for status in ("posted", "review", "scheduled", "publishing"):
        try:
            response = client.list_posts(
                limit=settings.news_history_scan_limit,
                status=status,
                newest_first=True,
            )
            response.raise_for_status()
            rows = response.json()
        except Exception as exc:
            logger.warning("history_scan_failed", extra={"status": status, "error": str(exc)})
            continue

        for row in rows:
            title = (row.get("title") or "").strip()
            text = (row.get("text") or "").strip()
            if text:
                texts.append(text)

            url = canonicalize_url(row.get("source_url") or "")
            if url:
                source_urls.add(url)

            if status != "posted":
                continue
            pillar = normalize_rubric_to_pillar(row.get("rubric"), f"{title}\n{text}")
            recent_pillar_counts[pillar] = recent_pillar_counts.get(pillar, 0) + 1
            posted_items.append(
                {
                    "title": title,
                    "text": text,
                    "source_url": row.get("source_url") or "",
                    "publish_at": row.get("publish_at") or "",
                    "feedback_snapshot": row.get("feedback_snapshot") or {},
                    "id": str(row.get("id") or ""),
                }
            )

    return texts, source_urls, recent_pillar_counts, posted_items, select_negative_feedback_examples(posted_items)


def _build_digest_candidate(now_utc: datetime, posted_items: list[dict[str, str]]) -> ArticleCandidate | None:
    if not posted_items:
        return None

    highlights = posted_items[:7]
    lines: list[str] = []
    for idx, item in enumerate(highlights, start=1):
        title = re.sub(r"\s+", " ", (item.get("title") or "").strip())
        text = re.sub(r"\s+", " ", (item.get("text") or "").strip())
        if len(text) > 190:
            text = text[:190].rsplit(" ", maxsplit=1)[0] + "..."
        title = title or f"Пункт {idx}"
        lines.append(f"{idx}. {title}: {text}")

    year, week, _ = now_utc.isocalendar()
    return ArticleCandidate(
        source_url="internal://weekly-digest",
        article_url=f"internal://weekly-digest/{year}-W{week}",
        title=f"Недельный дайджест Legal AI (W{week})",
        summary="Ключевые публикации недели:\n" + "\n".join(lines),
        published_at=now_utc,
    )


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

    top_limit = max(1, min(args.limit, 20))
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo(settings.tz_name))

    core_client = CoreClient(settings.core_api_url, settings.api_key_news)
    controls = _load_controls(core_client)
    if not _is_enabled(controls, "news.generate.enabled", True):
        logger.info("generation_disabled_by_control_plane")
        return 0

    source_urls = _parse_sources()
    if not source_urls:
        logger.error("NEWS_SOURCE_URLS is empty; generator cannot run")
        return 1

    history_texts, existing_source_urls, recent_pillar_counts, posted_items, negative_feedback_examples = _collect_history(
        core_client
    )
    digest_enabled = _is_enabled(controls, "news.digest.enabled", True)
    feedback_guard_enabled = _is_enabled(controls, "news.feedback.guard.enabled", True)
    digest_candidate = _build_digest_candidate(now_utc, posted_items) if digest_enabled else None
    negative_feedback_context = (
        render_negative_feedback_context(negative_feedback_examples) if feedback_guard_enabled else ""
    )

    articles = fetch_rss_articles(source_urls)
    priority_domains = _parse_priority_domains()
    selection_limit = min(60, top_limit * 6)
    selected_articles = choose_top_articles(
        articles,
        limit=selection_limit,
        now_utc=now_utc,
        priority_domains=priority_domains,
        max_per_source=settings.news_max_per_source,
        recent_pillar_counts=recent_pillar_counts,
        target_pillar_shares=default_pillar_targets(),
    )

    if not selected_articles and digest_candidate is None:
        logger.info("no_candidates_for_generation")
        return 0

    allow_alert_slot = (
        _is_enabled(controls, "news.alert_slot.enabled", settings.news_enable_alert_slot)
        and any(urgency_score(article, now_utc) >= 2.0 for article in selected_articles[:20])
    )
    publish_plan = build_publish_plan(now_local, top_limit, allow_alert_slot=allow_alert_slot)
    if not publish_plan:
        logger.info("no_available_publish_slots")
        return 0

    rag = PostedContentRAG(core_client)
    writer = LLMNewsWriter()

    article_queue = list(selected_articles)
    digest_used = False
    created = 0
    previewed = 0
    duplicates = 0
    feedback_skipped = 0
    failed = 0
    skipped_slots = 0

    for slot in publish_plan:
        slot_done = False
        format_type = slot.format_type
        cta_type = slot.cta_type

        if format_type == "digest" and not digest_enabled:
            format_type = "standard"

        for _ in range(0, 80):
            digest_for_slot = False
            if format_type == "digest":
                if digest_used or digest_candidate is None:
                    format_type = "standard"
                    continue
                article = digest_candidate
                digest_for_slot = True
            else:
                if not article_queue:
                    break
                article = article_queue.pop(0)

            article_canonical_url = canonicalize_url(article.article_url)
            if not digest_for_slot and article_canonical_url and article_canonical_url in existing_source_urls:
                duplicates += 1
                logger.info("source_url_duplicate_skipped", extra={"source_url": article.article_url})
                continue

            if feedback_guard_enabled and negative_feedback_examples:
                candidate_text = f"{article.title}\n{article.summary}"
                blocked_example: dict[str, str] | None = None
                blocked_similarity = 0.0
                for example in negative_feedback_examples:
                    similarity = lexical_similarity(candidate_text, str(example.get("text") or ""))
                    if similarity >= 0.76:
                        blocked_example = example
                        blocked_similarity = similarity
                        break
                if blocked_example is not None:
                    feedback_skipped += 1
                    logger.info(
                        "feedback_guard_skipped_candidate",
                        extra={
                            "article_url": article.article_url,
                            "matched_post_id": blocked_example.get("post_id"),
                            "similarity": round(blocked_similarity, 4),
                        },
                    )
                    continue

            query_text = f"{article.title}\n{article.summary}"
            rag_context = rag.find_context(query_text, history_limit=50, top_k=3)
            pillar = pillar_for_article(article)
            generated = writer.generate_post(
                article,
                rag_context,
                format_type=format_type,
                cta_type=cta_type,
                pillar=pillar,
                negative_feedback_context=negative_feedback_context,
            )

            max_similarity = 0.0
            if history_texts:
                max_similarity = max(lexical_similarity(generated["text"], prev_text) for prev_text in history_texts)
            similarity_threshold = settings.news_similarity_threshold + (0.15 if digest_for_slot else 0.0)
            if max_similarity >= similarity_threshold:
                duplicates += 1
                logger.info(
                    "semantic_duplicate_skipped",
                    extra={
                        "source_url": article.article_url,
                        "format_type": format_type,
                        "similarity": round(max_similarity, 4),
                        "threshold": similarity_threshold,
                    },
                )
                if digest_for_slot:
                    break
                continue

            source_hash = build_source_hash(article.article_url, article.title, article.published_at)
            publish_at_utc = slot.publish_at_local.astimezone(timezone.utc)
            payload = {
                "title": generated["title"],
                "text": generated["text"],
                "rubric": generated["rubric"],
                "format_type": format_type,
                "cta_type": cta_type,
                "source_url": article.article_url,
                "source_hash": source_hash,
                "channel_id": settings.telegram_channel_id or None,
                "channel_username": settings.telegram_channel_username or None,
                "publish_at": publish_at_utc.isoformat(),
                "status": "review",
            }

            if args.dry_run:
                previewed += 1
                slot_done = True
                history_texts.append(generated["text"])
                if article_canonical_url:
                    existing_source_urls.add(article_canonical_url)
                if digest_for_slot:
                    digest_used = True
                logger.info(
                    "dry_run_preview",
                    extra={
                        "source_url": article.article_url,
                        "title": generated["title"][:120],
                        "format_type": format_type,
                        "cta_type": cta_type,
                        "publish_at": payload["publish_at"],
                        "text_preview": generated["text"][:700],
                    },
                )
                break

            response = core_client.create_scheduled_post(payload)
            if response.status_code in (200, 201):
                created += 1
                slot_done = True
                history_texts.append(generated["text"])
                if article_canonical_url:
                    existing_source_urls.add(article_canonical_url)
                if digest_for_slot:
                    digest_used = True
                logger.info(
                    "scheduled_post_created",
                    extra={
                        "source_url": article.article_url,
                        "format_type": format_type,
                        "cta_type": cta_type,
                        "publish_at": payload["publish_at"],
                    },
                )
                break

            if response.status_code == 409:
                duplicates += 1
                logger.info("duplicate_post_skipped", extra={"source_url": article.article_url})
                if digest_for_slot:
                    break
                continue

            failed += 1
            slot_done = True
            logger.error(
                "scheduled_post_create_failed",
                extra={"status": response.status_code, "body": response.text[:500]},
            )
            break

        if not slot_done:
            skipped_slots += 1

    logger.info(
        "generation_completed",
        extra={
            "fetched": len(articles),
            "pool_selected": len(selected_articles),
            "slots_planned": len(publish_plan),
            "created_posts": created,
            "previewed": previewed,
            "duplicates": duplicates,
            "feedback_skipped": feedback_skipped,
            "failed": failed,
            "skipped_slots": skipped_slots,
            "dry_run": args.dry_run,
        },
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
