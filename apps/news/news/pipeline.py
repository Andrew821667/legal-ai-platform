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
PILLARS = ("regulation", "case", "implementation", "tools", "market")
_DEFAULT_PILLAR_TARGETS: dict[str, float] = {
    "regulation": 0.35,
    "case": 0.25,
    "implementation": 0.2,
    "tools": 0.1,
    "market": 0.1,
}
_PILLAR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "regulation": (
        "регуля",
        "закон",
        "норм",
        "суд",
        "штраф",
        "gdpr",
        "комплаенс",
        "compliance",
        "governance",
    ),
    "case": (
        "кейс",
        "внедр",
        "компан",
        "roi",
        "сократ",
        "увелич",
        "автоматиз",
        "case study",
    ),
    "implementation": (
        "процесс",
        "шаг",
        "playbook",
        "чек-лист",
        "workflow",
        "practice",
        "best practice",
        "framework",
    ),
    "tools": (
        "модел",
        "платформ",
        "api",
        "copilot",
        "openai",
        "deepseek",
        "llm",
        "tool",
    ),
    "market": (
        "рынок",
        "инвест",
        "funding",
        "m&a",
        "acquisition",
        "valuation",
        "стратег",
    ),
}
_RUBRIC_TO_PILLAR: dict[str, str] = {
    "regulation": "regulation",
    "ai_law": "regulation",
    "compliance": "regulation",
    "privacy": "regulation",
    "litigation": "regulation",
    "case": "case",
    "cases": "case",
    "market": "market",
    "legal_ops": "implementation",
    "implementation": "implementation",
    "contracts": "implementation",
    "tools": "tools",
}
_URGENT_KEYWORDS = (
    "штраф",
    "запрет",
    "исков",
    "утечк",
    "суд",
    "принял закон",
    "регулятор",
    "lawsuit",
    "ban",
    "penalty",
)


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


def default_pillar_targets() -> dict[str, float]:
    return dict(_DEFAULT_PILLAR_TARGETS)


def infer_pillar(text: str) -> str:
    normalized = _normalize_text(text)
    best_pillar = "implementation"
    best_score = -1.0
    for pillar, keywords in _PILLAR_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            if keyword in normalized:
                score += 1.0
        if score > best_score:
            best_score = score
            best_pillar = pillar
    return best_pillar


def normalize_rubric_to_pillar(rubric: str | None, fallback_text: str = "") -> str:
    normalized_rubric = (rubric or "").strip().lower()
    if normalized_rubric in _RUBRIC_TO_PILLAR:
        return _RUBRIC_TO_PILLAR[normalized_rubric]
    return infer_pillar(fallback_text)


def pillar_for_article(article: ArticleCandidate) -> str:
    return infer_pillar(f"{article.title}\n{article.summary}")


def urgency_score(article: ArticleCandidate, now_utc: datetime) -> float:
    score = 0.0
    normalized = _normalize_text(f"{article.title}\n{article.summary}")
    for keyword in _URGENT_KEYWORDS:
        if keyword in normalized:
            score += 1.0
    if article.published_at:
        age_hours = max(
            0.0,
            (now_utc - article.published_at.astimezone(timezone.utc)).total_seconds() / 3600,
        )
        if age_hours <= 24:
            score += 1.0
        elif age_hours <= 48:
            score += 0.5
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
    recent_pillar_counts: dict[str, int] | None = None,
    target_pillar_shares: dict[str, float] | None = None,
) -> list[ArticleCandidate]:
    scored: list[tuple[ArticleCandidate, float, float, str]] = []
    for candidate in candidates:
        base = keyword_score(f"{candidate.title}\n{candidate.summary}")
        total = article_score(candidate, now_utc, priority_domains=priority_domains)
        pillar = pillar_for_article(candidate)
        scored.append((candidate, total, base, pillar))
    scored.sort(key=lambda x: x[1], reverse=True)

    recent_counts = dict(recent_pillar_counts or {})
    target_shares = dict(target_pillar_shares or _DEFAULT_PILLAR_TARGETS)
    selected: list[ArticleCandidate] = []
    source_count: dict[str, int] = {}
    selected_pillar_counts: dict[str, int] = {}

    remaining = list(scored)
    while remaining and len(selected) < limit:
        best_idx: int | None = None
        best_adjusted = -10_000.0
        for idx, (candidate, total, base, pillar) in enumerate(remaining):
            if base < 1.0:
                continue
            source_key = extract_domain(candidate.source_url or candidate.article_url)
            already = source_count.get(source_key, 0)
            if already >= max(1, max_per_source):
                continue

            observed_total = max(1, sum(recent_counts.values()) + sum(selected_pillar_counts.values()))
            observed_share = (
                (recent_counts.get(pillar, 0) + selected_pillar_counts.get(pillar, 0))
                / observed_total
            )
            target_share = target_shares.get(pillar, 1.0 / len(PILLARS))
            pillar_balance_bonus = (target_share - observed_share) * 2.5
            adjusted = total + pillar_balance_bonus
            if adjusted > best_adjusted:
                best_adjusted = adjusted
                best_idx = idx

        if best_idx is None:
            break

        candidate, total, base, pillar = remaining.pop(best_idx)
        selected.append(candidate)
        source_key = extract_domain(candidate.source_url or candidate.article_url)
        source_count[source_key] = source_count.get(source_key, 0) + 1
        selected_pillar_counts[pillar] = selected_pillar_counts.get(pillar, 0) + 1

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
