from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from typing import Any

from news.pipeline import ArticleCandidate, canonicalize_url, passes_generation_scope
from news.settings import settings

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


def _session_name() -> str:
    raw = settings.telegram_session_name.strip()
    if not raw:
        raw = "apps/news/legacy/telegram_bot"
    path = Path(raw)
    if path.is_absolute():
        return str(path)
    return str((Path(__file__).resolve().parents[3] / raw).resolve())


def _is_configured(channels: list[str] | None = None) -> bool:
    channel_list = channels if channels is not None else settings.telegram_channels_list
    return bool(
        settings.telegram_fetch_enabled
        and settings.telegram_api_id
        and settings.telegram_api_hash
        and channel_list
    )


def fetch_telegram_articles(channels: list[str] | None = None) -> list[ArticleCandidate]:
    active_channels = channels if channels is not None else settings.telegram_channels_list
    if not _is_configured(active_channels):
        return []

    result = _FetchResult(items=[])

    def _runner() -> None:
        try:
            result.items = asyncio.run(_fetch_telegram_articles_async(active_channels))
        except Exception as exc:  # pragma: no cover
            result.error = exc

    thread = Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if result.error:
        logger.warning("telegram_fetch_failed", extra={"error": str(result.error)})
        return []
    return result.items


async def _fetch_telegram_articles_async(channels: list[str]) -> list[ArticleCandidate]:
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

    client = TelegramClient(session_name, settings.telegram_api_id, settings.telegram_api_hash)
    accepted: list[ArticleCandidate] = []
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("telegram_session_not_authorized", extra={"session_name": session_name})
            return []

        for raw_channel in channels:
            channel = raw_channel.lstrip("@")
            try:
                entity = await client.get_entity(channel)
            except (ChannelPrivateError, ChannelInvalidError, UsernameInvalidError) as exc:
                logger.warning("telegram_channel_unavailable", extra={"channel": channel, "error": str(exc)})
                continue

            try:
                messages = await client.get_messages(entity, limit=settings.telegram_fetch_limit)
            except FloodWaitError as exc:
                logger.warning("telegram_flood_wait", extra={"channel": channel, "wait_seconds": exc.seconds})
                await asyncio.sleep(exc.seconds)
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
                if published_at < datetime.now(timezone.utc) - timedelta(days=7):
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
            await asyncio.sleep(0.5)
    finally:
        await client.disconnect()

    deduped: dict[str, ArticleCandidate] = {}
    for item in accepted:
        deduped[canonicalize_url(item.article_url)] = item
    logger.info("telegram_articles_fetched", extra={"count": len(deduped), "channels": len(channels)})
    return list(deduped.values())
