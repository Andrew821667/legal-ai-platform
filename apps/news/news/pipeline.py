from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import urlparse, urlunparse


_KEYWORDS_WEIGHTED: dict[str, float] = {
    "ии": 2.0,
    "ai": 2.0,
    "искусственный интеллект": 3.0,
    "legaltech": 2.5,
    "юрид": 1.5,
    "комплаенс": 1.5,
    "регуля": 1.2,
    "суд": 1.0,
    "договор": 1.0,
    "прав": 1.0,
    "санкц": 1.2,
    "персональн": 1.2,
    "данн": 1.0,
    "automated": 0.8,
    "automation": 0.8,
}

_STOP_WORDS = {
    "это",
    "как",
    "для",
    "или",
    "что",
    "когда",
    "через",
    "после",
    "будет",
    "новый",
    "год",
    "день",
    "the",
    "and",
    "with",
    "from",
    "that",
    "this",
}

_WORD_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}")


@dataclass(slots=True)
class ArticleCandidate:
    source_url: str
    article_url: str
    title: str
    summary: str
    published_at: datetime | None = None


@dataclass(slots=True)
class RAGExample:
    title: str
    text: str
    rubric: str | None = None


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    normalized = parsed._replace(scheme=scheme, netloc=netloc, params="", query="", fragment="")
    return urlunparse(normalized).rstrip("/")


def extract_domain(url: str) -> str:
    parsed = urlparse(url or "")
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def parse_schedule_slots(raw_slots: str) -> list[tuple[int, int]]:
    slots: list[tuple[int, int]] = []
    for chunk in raw_slots.split(","):
        part = chunk.strip()
        if not part:
            continue
        hour_text, minute_text = part.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid slot value: {part}")
        slots.append((hour, minute))

    if not slots:
        raise ValueError("At least one schedule slot is required")

    return slots


def slot_times(now_local: datetime, slots: list[tuple[int, int]]) -> list[datetime]:
    results: list[datetime] = []
    for hour, minute in slots:
        candidate = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now_local:
            candidate += timedelta(days=1)
        results.append(candidate)
    return results


def build_source_hash(article_url: str, title: str, published_at: datetime | None) -> str:
    _ = published_at
    canonical_url = canonicalize_url(article_url)
    raw = f"{canonical_url}|{_normalize_text(title)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def keyword_score(text: str) -> float:
    normalized = _normalize_text(text)
    score = 0.0
    for keyword, weight in _KEYWORDS_WEIGHTED.items():
        if keyword in normalized:
            score += weight
    return score


def article_score(
    article: ArticleCandidate,
    now_utc: datetime,
    priority_domains: set[str] | None = None,
) -> float:
    base = keyword_score(f"{article.title}\n{article.summary}")

    freshness_bonus = 0.0
    if article.published_at:
        age = max(0.0, (now_utc - article.published_at.astimezone(timezone.utc)).total_seconds())
        age_hours = age / 3600
        if age_hours <= 24:
            freshness_bonus = 1.5
        elif age_hours <= 72:
            freshness_bonus = 0.8

    summary_bonus = 0.5 if len((article.summary or "").strip()) >= 300 else 0.0
    summary_penalty = -0.6 if len((article.summary or "").strip()) < 90 else 0.0

    domain_bonus = 0.0
    if priority_domains:
        domain = extract_domain(article.article_url)
        if domain in priority_domains:
            domain_bonus = 0.8

    # Минимальный порог, чтобы не выбирать нерелевантные статьи.
    return base + freshness_bonus + summary_bonus + summary_penalty + domain_bonus


def choose_top_articles(
    candidates: list[ArticleCandidate],
    limit: int,
    now_utc: datetime,
    priority_domains: set[str] | None = None,
    max_per_source: int = 2,
) -> list[ArticleCandidate]:
    scored: list[tuple[ArticleCandidate, float, float]] = []
    for candidate in candidates:
        base = keyword_score(f"{candidate.title}\n{candidate.summary}")
        total = article_score(candidate, now_utc, priority_domains=priority_domains)
        scored.append((candidate, total, base))
    scored.sort(key=lambda x: x[1], reverse=True)

    selected: list[ArticleCandidate] = []
    source_count: dict[str, int] = {}
    for candidate, score, base in scored:
        if len(selected) >= limit:
            break
        if base < 1.0:
            continue
        source_key = extract_domain(candidate.source_url or candidate.article_url)
        already = source_count.get(source_key, 0)
        if already >= max(1, max_per_source):
            continue
        selected.append(candidate)
        source_count[source_key] = already + 1

    return selected


def tokenize(text: str) -> set[str]:
    terms = {
        token.lower()
        for token in _WORD_RE.findall(text or "")
        if token.lower() not in _STOP_WORDS
    }
    return terms


def lexical_similarity(left_text: str, right_text: str) -> float:
    left = tokenize(left_text)
    right = tokenize(right_text)
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    return intersection / union if union else 0.0


def select_rag_examples(query_text: str, examples: Iterable[RAGExample], top_k: int) -> list[RAGExample]:
    ranked: list[tuple[RAGExample, float]] = []
    for example in examples:
        similarity = lexical_similarity(query_text, f"{example.title}\n{example.text}")
        ranked.append((example, similarity))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [example for example, score in ranked[:top_k] if score > 0]


def normalize_post_text(text: str) -> str:
    # Telegram hard limit for sendMessage is 4096 chars.
    normalized = (text or "").strip()
    return normalized[:4000]
