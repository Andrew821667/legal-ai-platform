from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
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
    extract_domain,
    lexical_similarity,
    normalize_rubric_to_pillar,
    passes_generation_scope,
    pillar_for_article,
)
from news.rag import PostedContentRAG
from news.rss_fetcher import fetch_rss_articles
from news.settings import settings
from news.source_catalog import active_source_specs, resolve_source_urls, source_catalog
from news.strategy import build_publish_plan
from news.telegram_ingest import fetch_telegram_articles

setup_logging()
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GenerationRunResult:
    previews: list[dict[str, str]]
    fetched: int
    pool_selected: int
    slots_planned: int
    duplicates: int
    feedback_skipped: int
    skipped_slots: int


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
    if domains:
        return domains
    for spec in active_source_specs(settings):
        if spec.domain and spec.integrated:
            domains.add(spec.domain)
    return domains


def _load_controls(client: CoreClient) -> list[dict[str, Any]]:
    try:
        response = client.list_automation_controls(scope="news")
        response.raise_for_status()
        return list(response.json())
    except Exception as exc:
        logger.warning("automation_controls_fetch_failed", extra={"error": str(exc)})
        return []


def _controls_enabled_map(control_rows: list[dict[str, Any]]) -> dict[str, bool]:
    controls: dict[str, bool] = {}
    for row in control_rows:
        key = str(row.get("key") or "").strip()
        if key:
            controls[key] = bool(row.get("enabled", True))
    return controls


def _is_enabled(controls: dict[str, bool], key: str, default: bool = True) -> bool:
    return controls.get(key, default)


def _source_enabled_map(controls: dict[str, bool]) -> dict[str, bool]:
    catalog = source_catalog(settings)
    return {
        key: controls.get(f"news.source.{key}.enabled", True)
        for key in catalog
    }


def _enabled_telegram_channels(controls: dict[str, bool]) -> list[str]:
    result: list[str] = []
    for channel in settings.telegram_channels_list:
        slug = channel.strip().lstrip("@").lower()
        if not slug:
            continue
        if controls.get(f"news.telegram_channel.{slug}.enabled", True):
            result.append(channel)
    return result


def _collect_history(
    client: CoreClient,
) -> tuple[list[str], set[str], dict[str, int], list[dict[str, str]], list[dict[str, str]]]:
    texts: list[str] = []
    source_urls: set[str] = set()
    recent_pillar_counts: dict[str, int] = {}
    posted_items: list[dict[str, str]] = []

    for status in ("posted", "review", "scheduled", "publishing", "failed"):
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

            if status == "failed":
                last_error = str(row.get("last_error") or "").strip().lower()
                if not last_error.startswith("deleted_irrelevant"):
                    continue
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
                continue

            if status in {"review", "scheduled", "publishing"}:
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
                continue

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


def _normalize_snippet(text: str, limit: int = 260) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rsplit(" ", maxsplit=1)[0] + "..."


def _build_weekly_review_candidate(now_utc: datetime, posted_items: list[dict[str, Any]]) -> ArticleCandidate | None:
    if not posted_items:
        return None

    start_of_week = (now_utc - timedelta(days=now_utc.weekday())).date()
    per_day: dict[str, list[dict[str, Any]]] = {}
    for item in posted_items:
        publish_raw = str(item.get("publish_at") or "").strip()
        if not publish_raw:
            continue
        try:
            publish_at = datetime.fromisoformat(publish_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if publish_at.date() < start_of_week:
            continue
        bucket = per_day.setdefault(publish_at.date().isoformat(), [])
        if len(bucket) < 2:
            bucket.append(item)

    highlights = [entry for day_key in sorted(per_day) for entry in per_day[day_key]][:10]
    if len(highlights) < 5:
        return None

    lines: list[str] = []
    for index, item in enumerate(highlights, start=1):
        title = _normalize_snippet(str(item.get("title") or f"Пункт {index}"), 110)
        text = _normalize_snippet(str(item.get("text") or ""), 220)
        lines.append(f"{index}. {title} — {text}")

    year, week, _ = now_utc.isocalendar()
    return ArticleCandidate(
        source_url="internal://weekly-review",
        article_url=f"internal://weekly-review/{year}-W{week}",
        title=f"Обзор недели по Legal AI и автоматизации юрфункции (W{week})",
        summary=(
            "Собери обзор недели на 8-10 пунктов. Обязательное требование: итоговый пост должен быть цельным и не обрезаться.\n"
            "Используй только материалы этой недели:\n"
            + "\n".join(lines)
        ),
        published_at=now_utc,
    )


def _build_longread_candidate(
    now_utc: datetime,
    longread_topic: str | None,
    selected_articles: list[ArticleCandidate],
) -> ArticleCandidate | None:
    topic = (longread_topic or "").strip()
    if not topic:
        return None
    materials = selected_articles[:5]
    if not materials:
        return None
    lines: list[str] = []
    for index, article in enumerate(materials, start=1):
        lines.append(
            f"{index}. {article.title} — {_normalize_snippet(article.summary, 220)}"
        )
    return ArticleCandidate(
        source_url="internal://longread",
        article_url=f"internal://longread/{now_utc.date().isoformat()}",
        title=f"Лонгрид: {topic}",
        summary=(
            f"Тема лонгрида: {topic}.\n"
            "Собери плотный воскресный longread по теме, опираясь на эти сигналы недели:\n"
            + "\n".join(lines)
        ),
        published_at=now_utc,
    )


def _build_humor_candidate(now_utc: datetime, selected_articles: list[ArticleCandidate]) -> ArticleCandidate | None:
    materials = selected_articles[:4]
    if not materials:
        return None
    lines: list[str] = []
    for index, article in enumerate(materials, start=1):
        lines.append(f"{index}. {article.title} — {_normalize_snippet(article.summary, 180)}")
    return ArticleCandidate(
        source_url="internal://humor",
        article_url=f"internal://humor/{now_utc.date().isoformat()}",
        title="Субботний юмористический пост о Legal AI",
        summary=(
            "Сделай легкий субботний пост с профессиональным юмором про Legal AI, юридическую автоматизацию и типичные боли юрфункции. "
            "Опирайся на реальные сигналы недели, но без клоунады и без потери профессионального тона.\n"
            + "\n".join(lines)
        ),
        published_at=now_utc,
    )


def collect_generation_previews(limit: int) -> GenerationRunResult:
    if not settings.api_key_news:
        raise RuntimeError("API_KEY_NEWS is required")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for content generation")

    top_limit = max(1, min(limit, 20))
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(ZoneInfo(settings.tz_name))

    core_client = CoreClient(settings.core_api_url, settings.api_key_news)
    control_rows = _load_controls(core_client)
    controls = _controls_enabled_map(control_rows)
    if not _is_enabled(controls, "news.generate.enabled", True):
        return GenerationRunResult(
            previews=[],
            fetched=0,
            pool_selected=0,
            slots_planned=0,
            duplicates=0,
            feedback_skipped=0,
            skipped_slots=0,
        )

    source_urls = resolve_source_urls(settings, enabled_overrides=_source_enabled_map(controls))
    if not source_urls:
        raise RuntimeError("NEWS_SOURCE_URLS is empty; generator cannot run")

    history_texts, existing_source_urls, recent_pillar_counts, posted_items, negative_feedback_examples = _collect_history(
        core_client
    )
    feedback_guard_enabled = _is_enabled(controls, "news.feedback.guard.enabled", True)
    negative_feedback_context = (
        render_negative_feedback_context(negative_feedback_examples) if feedback_guard_enabled else ""
    )

    articles = fetch_rss_articles(source_urls)
    telegram_articles = fetch_telegram_articles(_enabled_telegram_channels(controls))
    if telegram_articles:
        articles.extend(telegram_articles)
        logger.info("telegram_articles_appended", extra={"count": len(telegram_articles)})
    priority_domains = _parse_priority_domains()
    selection_limit = min(200, max(80, top_limit * 16))
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
        return GenerationRunResult(
            previews=[],
            fetched=len(articles),
            pool_selected=0,
            slots_planned=0,
            duplicates=0,
            feedback_skipped=0,
            skipped_slots=0,
        )

    publish_plan = build_publish_plan(now_local, top_limit, control_rows=control_rows)
    if not publish_plan:
        return GenerationRunResult(
            previews=[],
            fetched=len(articles),
            pool_selected=len(selected_articles),
            slots_planned=0,
            duplicates=0,
            feedback_skipped=0,
            skipped_slots=0,
        )

    rag = PostedContentRAG(core_client)
    writer = LLMNewsWriter()

    article_queue = list(selected_articles)
    previews: list[dict[str, str]] = []
    duplicates = 0
    feedback_skipped = 0
    skipped_slots = 0

    for slot in publish_plan:
        slot_done = False
        publication_kind = slot.publication_kind
        format_type = slot.format_type
        cta_type = slot.cta_type

        for _ in range(0, 80):
            synthetic_slot = False
            if publication_kind == "weekly_review":
                article = _build_weekly_review_candidate(now_utc, posted_items)
                synthetic_slot = True
                if article is None:
                    break
            elif publication_kind == "longread":
                article = _build_longread_candidate(now_utc, slot.longread_topic, selected_articles)
                synthetic_slot = True
                if article is None:
                    break
            elif publication_kind == "humor":
                article = _build_humor_candidate(now_utc, selected_articles)
                synthetic_slot = True
                if article is None:
                    break
            else:
                if not article_queue:
                    break
                article = article_queue.pop(0)

            if not synthetic_slot and not passes_generation_scope(article):
                logger.info("candidate_failed_generation_scope", extra={"source_url": article.article_url})
                continue

            article_canonical_url = canonicalize_url(article.article_url)
            if not synthetic_slot and article_canonical_url and article_canonical_url in existing_source_urls:
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
            if generated is None:
                logger.info("candidate_rejected_after_llm_review", extra={"source_url": article.article_url})
                continue

            max_similarity = 0.0
            if history_texts:
                max_similarity = max(lexical_similarity(generated["text"], prev_text) for prev_text in history_texts)
            similarity_threshold = settings.news_similarity_threshold + (0.15 if synthetic_slot else 0.0)
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
                if synthetic_slot:
                    break
                continue

            source_hash = build_source_hash(article.article_url, article.title, article.published_at)
            publish_at_utc = slot.publish_at_local.astimezone(timezone.utc)
            preview = {
                "title": generated["title"],
                "text": generated["text"],
                "rubric": generated["rubric"],
                "publication_kind": publication_kind,
                "format_type": format_type,
                "cta_type": cta_type,
                "source_url": article.article_url,
                "source_feed_url": article.source_url,
                "source_title": article.title,
                "source_summary": article.summary,
                "source_domain": extract_domain(article.article_url),
                "source_hash": source_hash,
                "pillar": pillar,
                "channel_id": settings.telegram_channel_id or "",
                "channel_username": settings.telegram_channel_username or "",
                "publish_at": publish_at_utc.isoformat(),
                "status": "review",
                "article_published_at": article.published_at.isoformat() if article.published_at else "",
                "longread_topic": slot.longread_topic or "",
            }
            previews.append(preview)
            history_texts.append(generated["text"])
            if article_canonical_url:
                existing_source_urls.add(article_canonical_url)
            slot_done = True
            break

        if not slot_done:
            skipped_slots += 1

    return GenerationRunResult(
        previews=previews,
        fetched=len(articles),
        pool_selected=len(selected_articles),
        slots_planned=len(publish_plan),
        duplicates=duplicates,
        feedback_skipped=feedback_skipped,
        skipped_slots=skipped_slots,
    )


def run_generation(limit: int, *, dry_run: bool = False) -> int:
    try:
        result = collect_generation_previews(limit)
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    if not result.previews:
        logger.info(
            "generation_completed",
            extra={
                "fetched": result.fetched,
                "pool_selected": result.pool_selected,
                "slots_planned": result.slots_planned,
                "created_posts": 0,
                "previewed": 0,
                "duplicates": result.duplicates,
                "feedback_skipped": result.feedback_skipped,
                "failed": 0,
                "skipped_slots": result.skipped_slots,
                "dry_run": dry_run,
            },
        )
        return 0

    core_client = CoreClient(settings.core_api_url, settings.api_key_news)
    created = 0
    failed = 0
    if dry_run:
        for preview in result.previews:
            logger.info(
                "dry_run_preview",
                extra={
                    "source_url": preview["source_url"],
                    "title": preview["title"][:120],
                    "publication_kind": preview.get("publication_kind") or "",
                    "format_type": preview["format_type"],
                    "cta_type": preview["cta_type"],
                    "publish_at": preview["publish_at"],
                    "text_preview": preview["text"][:700],
                },
            )
    else:
        for preview in result.previews:
            payload = {
                "title": preview["title"],
                "text": preview["text"],
                "rubric": preview["rubric"],
                "format_type": preview["format_type"],
                "cta_type": preview["cta_type"],
                "source_url": preview["source_url"],
                "source_hash": preview["source_hash"],
                "channel_id": preview["channel_id"] or None,
                "channel_username": preview["channel_username"] or None,
                "publish_at": preview["publish_at"],
                "status": preview["status"],
            }
            response = core_client.create_scheduled_post(payload)
            if response.status_code in (200, 201):
                created += 1
                logger.info(
                    "scheduled_post_created",
                    extra={
                        "source_url": preview["source_url"],
                        "publication_kind": preview.get("publication_kind") or "",
                        "format_type": preview["format_type"],
                        "cta_type": preview["cta_type"],
                        "publish_at": preview["publish_at"],
                    },
                )
                continue
            if response.status_code == 409:
                logger.info("duplicate_post_skipped", extra={"source_url": preview["source_url"]})
                continue
            failed += 1
            logger.error(
                "scheduled_post_create_failed",
                extra={"status": response.status_code, "body": response.text[:500]},
            )

    logger.info(
        "generation_completed",
        extra={
            "fetched": result.fetched,
            "pool_selected": result.pool_selected,
            "slots_planned": result.slots_planned,
            "created_posts": created,
            "previewed": len(result.previews) if dry_run else 0,
            "duplicates": result.duplicates,
            "feedback_skipped": result.feedback_skipped,
            "failed": failed,
            "skipped_slots": result.skipped_slots,
            "dry_run": dry_run,
        },
    )
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate scheduled channel posts from RSS + LLM")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=settings.news_top_k)
    args = parser.parse_args()
    return run_generation(args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
