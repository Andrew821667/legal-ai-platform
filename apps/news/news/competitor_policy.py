from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlparse

DEFAULT_COMPETITOR_CHANNELS = ("law_gpt", "zakongpt", "zakon_gpt")
DEFAULT_COMPETITOR_DOMAINS = ("lawgpt.ru", "rfgpt.ru", "legalai-service.ru")
DEFAULT_COMPETITOR_BRANDS = (
    "LawGPT",
    "Law GPT",
    "ЗаконГПТ",
    "Закон GPT",
    "ZakonGPT",
    "Zakon GPT",
    "Моментальный Юрист",
    "Neurolegal",
)
COMPETITOR_REPLACEMENT = "сторонний российский Legal AI-сервис"


def normalize_channel_slug(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith(("t.me/", "telegram.me/")):
        raw = raw.split("/", maxsplit=1)[1]
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.netloc.lower().removeprefix("www.") not in {"t.me", "telegram.me"}:
            return ""
        raw = parsed.path.strip("/").split("/", maxsplit=1)[0]
    return raw.lstrip("@").strip("/").split("/", maxsplit=1)[0].strip().lower()


def normalized_values(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        result.append(normalized)
    return tuple(result)


def is_competitor_channel(value: str, blocked_channels: Iterable[str] = DEFAULT_COMPETITOR_CHANNELS) -> bool:
    slug = normalize_channel_slug(value)
    blocked = {normalize_channel_slug(item) for item in blocked_channels}
    return bool(slug and slug in blocked)


def is_competitor_source_url(
    value: str,
    *,
    blocked_channels: Iterable[str] = DEFAULT_COMPETITOR_CHANNELS,
    blocked_domains: Iterable[str] = DEFAULT_COMPETITOR_DOMAINS,
) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if is_competitor_channel(raw, blocked_channels):
        return True
    parsed = urlparse(raw)
    host = parsed.netloc.lower().split(":", maxsplit=1)[0].removeprefix("www.")
    if host in {"t.me", "telegram.me"}:
        return is_competitor_channel(raw, blocked_channels)
    for domain in blocked_domains:
        normalized = str(domain or "").strip().lower().removeprefix("www.")
        if normalized and (host == normalized or host.endswith(f".{normalized}")):
            return True
    return False


def _brand_pattern(brands: Iterable[str]) -> re.Pattern[str] | None:
    variants = normalized_values(brands)
    if not variants:
        return None
    parts = []
    for item in variants:
        tokens = [token for token in re.split(r"[\s_-]+", item) if token]
        if tokens:
            parts.append(r"[\s_-]*".join(re.escape(token) for token in tokens))
    parts.sort(key=len, reverse=True)
    return re.compile(rf"(?<![\w])(?:{'|'.join(parts)})(?![\w])", re.IGNORECASE)


def competitor_mentions(text: str, brands: Iterable[str] = DEFAULT_COMPETITOR_BRANDS) -> tuple[str, ...]:
    pattern = _brand_pattern(brands)
    if pattern is None:
        return ()
    return normalized_values(match.group(0) for match in pattern.finditer(str(text or "")))


def anonymize_competitor_mentions(
    text: str,
    brands: Iterable[str] = DEFAULT_COMPETITOR_BRANDS,
    *,
    replacement: str = COMPETITOR_REPLACEMENT,
) -> str:
    pattern = _brand_pattern(brands)
    if pattern is None:
        return str(text or "")
    return pattern.sub(replacement, str(text or ""))


def competitor_policy_failure_reason(
    *,
    text: str,
    title: str = "",
    source_url: str = "",
    article_url: str = "",
    blocked_channels: Iterable[str] = DEFAULT_COMPETITOR_CHANNELS,
    blocked_domains: Iterable[str] = DEFAULT_COMPETITOR_DOMAINS,
    brands: Iterable[str] = DEFAULT_COMPETITOR_BRANDS,
) -> str | None:
    for value in (source_url, article_url):
        if is_competitor_source_url(
            value,
            blocked_channels=blocked_channels,
            blocked_domains=blocked_domains,
        ):
            return "competitor_source"
    if competitor_mentions(f"{title}\n{text}", brands):
        return "competitor_brand_mention"
    return None
