from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlparse

from news.pipeline import ArticleCandidate, canonicalize_url, passes_generation_scope
from news.settings import settings
from news.telegram_html_fetcher import TelegramHtmlPost, fetch_channels as fetch_html_channels

logger = logging.getLogger(__name__)
_STRICT_CHANNELS = {
    "ai_newz",
    "anthropicai",
    "googleai",
    "openai_ru",
    "ai_machinelearning_big_data",
}


@dataclass(slots=True)
class _FetchResult:
    items: list[ArticleCandidate]
    error: Exception | None = None


def _resolve_runtime_path(raw_value: str, *, fallback: str) -> Path:
    raw = raw_value.strip() or fallback
    path = Path(raw)
    if path.is_absolute():
        return path
    return (Path(__file__).resolve().parents[3] / raw).resolve()


def _session_name() -> str:
    return str(_resolve_runtime_path(settings.telegram_session_name, fallback="apps/news/legacy/telegram_bot"))


def _cache_path() -> Path:
    return _resolve_runtime_path(settings.news_telegram_cache_path, fallback="data/news_telegram_cache.json")


def _is_configured(channels: list[str] | None = None) -> bool:
    channel_list = channels if channels is not None else settings.telegram_channels_list
    if not (settings.telegram_fetch_enabled and channel_list):
        return False
    mode = (settings.news_telegram_fetch_mode or "telethon").strip().lower()
    if mode == "html":
        # HTML mode doesn't need MTProto credentials.
        return True
    # telethon or html_then_telethon both need MTProto creds to be useful.
    return bool(settings.telegram_api_id and settings.telegram_api_hash)


def _html_post_to_candidate(post: TelegramHtmlPost) -> ArticleCandidate | None:
    if not post.text:
        return None
    lines = [line.strip() for line in post.text.splitlines() if line.strip()]
    title = (lines[0] if lines else post.text)[:200]
    channel_url = f"https://t.me/{post.channel}"
    candidate = ArticleCandidate(
        source_url=channel_url,
        article_url=post.permalink,
        title=title,
        summary=post.text[:5000],
        published_at=post.published_at,
    )
    if post.channel.lower() in _STRICT_CHANNELS and not passes_generation_scope(candidate):
        return None
    return candidate


def _fetch_via_html(channels: list[str], fetch_limit: int | None) -> list[ArticleCandidate]:
    """Pull posts via the public t.me/s/<channel> preview. Returns [] on any
    network failure — caller decides whether to fall back to Telethon.
    """
    results: list[ArticleCandidate] = []
    proxy_url = (settings.news_telegram_html_proxy_url or "").strip() or None
    by_channel = fetch_html_channels(channels, fetch_limit=fetch_limit, proxy_url=proxy_url)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, settings.news_max_source_age_days))
    for channel, posts in by_channel.items():
        for post in posts:
            if post.published_at is not None and post.published_at < cutoff:
                continue
            candidate = _html_post_to_candidate(post)
            if candidate is not None:
                results.append(candidate)
    return results


def fetch_telegram_articles(
    channels: list[str] | None = None,
    *,
    fetch_limit: int | None = None,
) -> list[ArticleCandidate]:
    active_channels = channels if channels is not None else settings.telegram_channels_list
    if not _is_configured(active_channels):
        return []

    mode = (settings.news_telegram_fetch_mode or "telethon").strip().lower()

    if mode in ("html", "html_then_telethon"):
        html_items = _fetch_via_html(active_channels, fetch_limit)
        if html_items or mode == "html":
            logger.info(
                "telegram_html_fetch_done",
                extra={"count": len(html_items), "channels": len(active_channels), "mode": mode},
            )
            return html_items
        # html_then_telethon and HTML returned nothing — try Telethon next.
        logger.info(
            "telegram_html_empty_falling_back_to_telethon",
            extra={"channels": len(active_channels)},
        )

    result = _FetchResult(items=[])

    def _runner() -> None:
        try:
            result.items = asyncio.run(_fetch_telegram_articles_async(active_channels, fetch_limit=fetch_limit))
        except Exception as exc:  # pragma: no cover
            result.error = exc

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if result.error:
        logger.warning("telegram_fetch_failed", extra={"error": str(result.error)})
        return []
    return result.items


def _article_to_dict(item: ArticleCandidate) -> dict[str, Any]:
    published_at = item.published_at
    if published_at is not None:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        else:
            published_at = published_at.astimezone(timezone.utc)
    return {
        "source_url": item.source_url,
        "article_url": item.article_url,
        "title": item.title,
        "summary": item.summary,
        "published_at": published_at.isoformat() if published_at else None,
    }


def _article_from_dict(payload: dict[str, Any]) -> ArticleCandidate | None:
    source_url = str(payload.get("source_url") or "").strip()
    article_url = str(payload.get("article_url") or "").strip()
    title = str(payload.get("title") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if not source_url or not article_url or not title:
        return None
    published_raw = str(payload.get("published_at") or "").strip()
    published_at: datetime | None = None
    if published_raw:
        try:
            parsed = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            published_at = parsed
        except ValueError:
            published_at = None
    return ArticleCandidate(
        source_url=source_url,
        article_url=article_url,
        title=title,
        summary=summary,
        published_at=published_at,
    )


def _channel_slug(raw_channel: str) -> str:
    return raw_channel.strip().lstrip("@").lower()


def _channel_slug_from_source_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    path = parsed.path.strip("/")
    if path:
        return path.split("/")[0].lower()
    host = (parsed.netloc or "").lower()
    if host.startswith("t.me/"):
        return host.split("/", maxsplit=1)[1]
    return ""


def save_telegram_articles_cache(
    articles: list[ArticleCandidate],
    *,
    channels: list[str] | None = None,
    fetched_at: datetime | None = None,
) -> Path:
    cache_path = _cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = fetched_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    payload = {
        "fetched_at": timestamp.astimezone(timezone.utc).isoformat(),
        "channels": [item for item in (channels or settings.telegram_channels_list)],
        "items": [_article_to_dict(item) for item in articles],
    }
    temp_path = cache_path.with_name(f"{cache_path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(cache_path)
    return cache_path


def load_telegram_articles_cache(
    *,
    channels: list[str] | None = None,
    max_age_minutes: int | None = None,
) -> list[ArticleCandidate]:
    cache_path = _cache_path()
    if not cache_path.exists():
        return []

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("telegram_cache_read_failed", extra={"path": str(cache_path), "error": str(exc)})
        return []

    fetched_raw = str(payload.get("fetched_at") or "").strip()
    if max_age_minutes is None:
        max_age_minutes = settings.news_telegram_cache_max_age_minutes
    if fetched_raw and max_age_minutes and max_age_minutes > 0:
        try:
            fetched_at = datetime.fromisoformat(fetched_raw.replace("Z", "+00:00"))
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            else:
                fetched_at = fetched_at.astimezone(timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
            if age_seconds > max_age_minutes * 60:
                logger.info(
                    "telegram_cache_expired",
                    extra={"path": str(cache_path), "age_minutes": round(age_seconds / 60, 1), "max_age": max_age_minutes},
                )
                return []
        except ValueError:
            logger.warning("telegram_cache_invalid_fetched_at", extra={"path": str(cache_path), "value": fetched_raw})
            return []

    requested_channels = {_channel_slug(item) for item in (channels or []) if _channel_slug(item)}
    deduped: dict[str, ArticleCandidate] = {}
    for raw_item in payload.get("items") or []:
        if not isinstance(raw_item, dict):
            continue
        item = _article_from_dict(raw_item)
        if item is None:
            continue
        if requested_channels:
            slug = _channel_slug_from_source_url(item.source_url)
            if not slug or slug not in requested_channels:
                continue
        deduped[canonicalize_url(item.article_url)] = item

    logger.info(
        "telegram_cache_loaded",
        extra={"path": str(cache_path), "count": len(deduped), "channels_filter": len(requested_channels)},
    )
    return list(deduped.values())


async def _fetch_telegram_articles_async(channels: list[str], *, fetch_limit: int | None = None) -> list[ArticleCandidate]:
    try:
        from telethon import TelegramClient
        from telethon.errors import ChannelInvalidError, ChannelPrivateError, FloodWaitError, UsernameInvalidError
        from telethon.tl.types import Message
    except Exception as exc:  # pragma: no cover
        logger.warning("telethon_not_available", extra={"error": str(exc)})
        return []

    session_name = _session_name()
    session_path = Path(f"{session_name}.session")
    if not session_path.exists():
        logger.warning("telegram_session_missing", extra={"session_name": session_name})
        return []

    requested_limit = fetch_limit if isinstance(fetch_limit, int) and fetch_limit > 0 else settings.telegram_fetch_limit
    # Cap the per-channel batch so a single iteration never looks like a scrape.
    # The default cap is intentionally small (5) — large bursts are exactly
    # what Telegram's 2026 detection looks for on user-session accounts.
    per_channel_cap = max(1, settings.telegram_telethon_per_channel_cap)
    limit = min(requested_limit, per_channel_cap)
    pause_min = max(0.0, float(settings.telegram_telethon_inter_channel_pause_min_seconds))
    pause_max = max(pause_min, float(settings.telegram_telethon_inter_channel_pause_max_seconds))
    flood_cap = max(1, int(settings.telegram_telethon_flood_max_wait_seconds))
    client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
    accepted: list[ArticleCandidate] = []
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("telegram_session_not_authorized", extra={"session_name": session_name})
            return []

        for channel_index, raw_channel in enumerate(channels):
            channel = raw_channel.lstrip("@")
            try:
                entity = await client.get_entity(channel)
            except (ChannelPrivateError, ChannelInvalidError, UsernameInvalidError) as exc:
                logger.warning("telegram_channel_unavailable", extra={"channel": channel, "error": str(exc)})
                continue

            try:
                messages = await client.get_messages(entity, limit=limit)
            except FloodWaitError as exc:
                wait_seconds = min(exc.seconds, flood_cap)
                logger.warning(
                    "telegram_flood_wait",
                    extra={
                        "channel": channel,
                        "wait_seconds": exc.seconds,
                        "sleeping_seconds": wait_seconds,
                    },
                )
                if exc.seconds >= flood_cap:
                    # Telegram is throttling us hard — abort this run rather
                    # than power through and risk a 24h soft-ban.
                    logger.warning(
                        "telegram_flood_wait_exceeds_cap_aborting",
                        extra={"channel": channel, "wait_seconds": exc.seconds, "cap": flood_cap},
                    )
                    break
                await asyncio.sleep(wait_seconds)
                continue

            for message in messages:
                if not isinstance(message, Message):
                    continue
                text = (getattr(message, "message", None) or getattr(message, "text", None) or "").strip()
                if not text:
                    continue
                published_at = getattr(message, "date", None)
                if published_at is None:
                    continue
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
                else:
                    published_at = published_at.astimezone(timezone.utc)
                if published_at < datetime.now(timezone.utc) - timedelta(
                    days=max(1, settings.news_max_source_age_days)
                ):
                    continue

                lines = [line.strip() for line in text.splitlines() if line.strip()]
                title = (lines[0] if lines else text)[:200]
                message_url = f"https://t.me/{channel}/{message.id}"
                channel_url = f"https://t.me/{channel}"
                candidate = ArticleCandidate(
                    source_url=channel_url,
                    article_url=message_url,
                    title=title,
                    summary=text[:5000],
                    published_at=published_at,
                )
                if channel.lower() in _STRICT_CHANNELS and not passes_generation_scope(candidate):
                    continue
                accepted.append(candidate)
            # Randomised pause between channels — uniform timing is a red flag
            # to behavioural detection. Skip the pause after the last channel.
            if channel_index + 1 < len(channels):
                jitter = random.uniform(pause_min, pause_max) if pause_max > 0 else 0.0
                if jitter > 0:
                    await asyncio.sleep(jitter)
    finally:
        await client.disconnect()

    deduped: dict[str, ArticleCandidate] = {}
    for item in accepted:
        deduped[canonicalize_url(item.article_url)] = item
    logger.info("telegram_articles_fetched", extra={"count": len(deduped), "channels": len(channels), "limit": limit})
    return list(deduped.values())
