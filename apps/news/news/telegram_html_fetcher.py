"""Fetch Telegram channel posts via the public web preview (no MTProto, no user session).

Telegram exposes a public, browser-friendly mirror of each public channel at
https://t.me/s/<channel> — the same HTML the messenger uses to render link
previews. It requires no API key and no signed-in user session, so it can't
get a user account banned the way Telethon can in 2026.

On infra where t.me is reachable directly this Just Works. On the Mac Mini
(behind RKN filtering) the worker container is expected to point requests at
the host's Happ Plus HTTP proxy (http://host.docker.internal:10808 by
default) — see settings.telegram_html_proxy_url.

The parser is regex-based and tuned for the actual structure Telegram emits.
It deliberately avoids html.parser because the message-text container nests
an identically-classed inner div, which trips state-machine parsers.
"""
from __future__ import annotations

import html
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

PREVIEW_URL_TEMPLATE = "https://t.me/s/{channel}"
DEFAULT_TIMEOUT_SECONDS = 20
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
)


@dataclass(slots=True)
class TelegramHtmlPost:
    channel: str
    message_id: int
    text: str
    permalink: str
    published_at: datetime | None


# Matches the outer "tgme_widget_message" div that carries `data-post`.
# We capture the data-post value and then take everything up to the next
# message_wrap boundary as the message body.
_MESSAGE_RE = re.compile(
    r'<div\s+class="tgme_widget_message[^"]*"[^>]*?'
    r'data-post="(?P<post>[^"]+)"[^>]*>',
    re.DOTALL,
)
_DATETIME_RE = re.compile(r'datetime="([^"]+)"')
_TEXT_RE = re.compile(
    r'<div\s+class="tgme_widget_message_text\s+js-message_text"[^>]*>'
    r'(?P<body>.*?)'
    r'</div>\s*<div\s+class="tgme_widget_message_footer',
    re.DOTALL,
)
# A second, looser pattern for posts that don't have a footer block close
# enough — fall back to "closing div after our body".
_TEXT_FALLBACK_RE = re.compile(
    r'<div\s+class="tgme_widget_message_text\s+js-message_text"[^>]*>(.*?)</div>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RUN_RE = re.compile(r"[ \t]+")


def _strip_html_to_text(body_html: str) -> str:
    """Convert a Telegram message body HTML fragment into readable plain text."""
    # Translate <br> family into newlines so paragraph structure survives.
    text = re.sub(r"<br\s*/?>", "\n", body_html, flags=re.IGNORECASE)
    # Replace common block-ish tags with newlines too so lists/quotes don't merge.
    text = re.sub(r"</(p|div|li|blockquote)>", "\n", text, flags=re.IGNORECASE)
    # Drop the remaining tags
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    # Tidy whitespace
    text = _WHITESPACE_RUN_RE.sub(" ", text)
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text.strip()


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _split_data_post(value: str) -> tuple[str, int | None]:
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2:
        return value, None
    channel, raw_id = parts
    try:
        return channel, int(raw_id)
    except ValueError:
        return channel, None


def parse_channel_html(channel: str, html_body: str) -> list[TelegramHtmlPost]:
    """Pure parser, kept stateless for easy unit testing."""
    posts: list[TelegramHtmlPost] = []

    # Find every message header (data-post anchor); each message body is
    # the slice between this header and the next header (or end of HTML).
    headers = list(_MESSAGE_RE.finditer(html_body))
    for index, match in enumerate(headers):
        body_start = match.end()
        body_end = headers[index + 1].start() if index + 1 < len(headers) else len(html_body)
        block = html_body[body_start:body_end]

        post_channel, message_id = _split_data_post(match.group("post"))
        if message_id is None:
            continue
        canonical_channel = (post_channel or channel).lstrip("@")

        text_match = _TEXT_RE.search(block) or _TEXT_FALLBACK_RE.search(block)
        text = _strip_html_to_text(text_match.group(1) if text_match else "")
        if not text:
            continue

        dt_match = _DATETIME_RE.search(block)
        published_at = _parse_datetime(dt_match.group(1) if dt_match else None)

        posts.append(
            TelegramHtmlPost(
                channel=canonical_channel,
                message_id=message_id,
                text=text,
                permalink=f"https://t.me/{canonical_channel}/{message_id}",
                published_at=published_at,
            )
        )
    return posts


def _resolve_proxy(explicit: str | None) -> str | None:
    """Settings → env → None. Empty string disables the proxy explicitly."""
    if explicit is None:
        explicit = os.environ.get("NEWS_TELEGRAM_HTML_PROXY")
    if explicit is None:
        return None
    explicit = explicit.strip()
    if not explicit or explicit.lower() in ("none", "off", "disabled"):
        return None
    return explicit


def fetch_channel_posts(
    channel: str,
    *,
    fetch_limit: int | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
    proxy_url: str | None = None,
) -> list[TelegramHtmlPost]:
    """Fetch and parse one channel's preview page. Network-side errors are
    swallowed: empty list lets the caller fall back (e.g. to Telethon).
    """
    handle = channel.lstrip("@")
    url = PREVIEW_URL_TEMPLATE.format(channel=handle)
    proxy = _resolve_proxy(proxy_url)
    proxies = {"http": proxy, "https": proxy} if proxy else None
    http = session or requests
    try:
        response = http.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
            proxies=proxies,
        )
    except requests.RequestException as exc:
        logger.warning("telegram_html_fetch_failed", extra={"channel": handle, "error": str(exc)})
        return []

    if response.status_code != 200:
        logger.warning(
            "telegram_html_fetch_non_200",
            extra={"channel": handle, "status": response.status_code},
        )
        return []

    posts = parse_channel_html(handle, response.text)
    if fetch_limit is not None and fetch_limit > 0:
        # Newest first in the rendered HTML — slicing keeps the most recent N
        posts = posts[-fetch_limit:]
    return posts


def fetch_channels(
    channels: Iterable[str],
    *,
    fetch_limit: int | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
    proxy_url: str | None = None,
) -> dict[str, list[TelegramHtmlPost]]:
    out: dict[str, list[TelegramHtmlPost]] = {}
    for channel in channels:
        handle = channel.lstrip("@")
        if not handle:
            continue
        out[handle] = fetch_channel_posts(
            handle,
            fetch_limit=fetch_limit,
            timeout_seconds=timeout_seconds,
            session=session,
            proxy_url=proxy_url,
        )
    return out


__all__ = [
    "TelegramHtmlPost",
    "fetch_channel_posts",
    "fetch_channels",
    "parse_channel_html",
]
