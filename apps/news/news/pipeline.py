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
    "генератив": 2.2,
    "llm": 2.2,
    "gpt": 2.0,
    "openai": 2.0,
    "deepseek": 2.0,
    "legaltech": 2.8,
    "legal tech": 2.8,
    "юрид": 2.0,
    "юрист": 1.8,
    "lawyer": 1.8,
    "legal": 1.5,
    "law ": 1.2,
    "комплаенс": 1.8,
    "compliance": 1.8,
    "privacy": 1.5,
    "персональн": 1.5,
    "договор": 1.7,
    "contract": 1.7,
    "court": 1.4,
    "суд": 1.4,
    "legal ops": 2.0,
    "юротдел": 1.8,
    "документооборот": 1.8,
    "автоматиз": 1.4,
    "workflow": 1.2,
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
_TOKEN_MARKER_PATTERNS = {
    "ai": re.compile(r"(?<![a-z])ai(?![a-z])"),
    "llm": re.compile(r"(?<![a-z])llm(?![a-z])"),
    "gpt": re.compile(r"(?<![a-z])gpt(?![a-z])"),
}
PILLARS = ("regulation", "case", "implementation", "tools", "market")
_DEFAULT_PILLAR_TARGETS: dict[str, float] = {
    "regulation": 0.3,
    "case": 0.2,
    "implementation": 0.3,
    "tools": 0.15,
    "market": 0.05,
}
_PILLAR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "regulation": (
        "ai act",
        "закон об ии",
        "регулирован",
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
        "юрфир",
        "юротдел",
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
        "legal ops",
        "договор",
        "документооборот",
        "согласован",
        "юротдел",
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
        "legaltech",
        "legal tech",
        "юртех",
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
_AI_MARKERS = (
    "ии",
    "ai",
    "искусственный интеллект",
    "генератив",
    "llm",
    "gpt",
    "openai",
    "deepseek",
    "anthropic",
    "copilot",
    "agent",
    "нейросет",
)
_LEGAL_MARKERS = (
    "юрид",
    "юрист",
    "lawyer",
    "legal",
    "law ",
    "договор",
    "contract",
    "комплаенс",
    "compliance",
    "privacy",
    "персональн",
    "регулирован",
    "регулятор",
    "court",
    "суд",
    "claims",
)
_OPS_MARKERS = (
    "автоматиз",
    "workflow",
    "legal ops",
    "юротдел",
    "документооборот",
    "согласован",
    "redline",
    "intake",
    "triage",
    "knowledge base",
    "поиск по документ",
    "контракт",
)
_GENERATION_OPS_MARKERS = (
    "автоматиз",
    "workflow",
    "legal ops",
    "юротдел",
    "документооборот",
    "redline",
    "intake",
    "triage",
    "поиск по документ",
    "контракт",
)
_MARKET_MARKERS = (
    "legaltech",
    "legal tech",
    "юртех",
    "law firm",
    "юрфир",
    "inhouse",
    "инхаус",
)
_HARD_LEGAL_MARKERS = (
    "юрид",
    "юрист",
    "legal",
    "lawyer",
    "law firm",
    "юротдел",
    "договор",
    "contract",
    "комплаенс",
    "compliance",
    "privacy",
    "персональн",
    "court",
    "суд",
    "legal ops",
    "документооборот",
)
_HARD_MARKET_MARKERS = (
    "legaltech",
    "legal tech",
    "юртех",
    "инхаус",
    "юрфир",
)
_OFFTOPIC_MARKERS = (
    "археолог",
    "древн",
    "римск",
    "настольн",
    "игр",
    "музык",
    "кино",
    "погода",
    "спорт",
    "ресторан",
    "астроном",
)
_LEGAL_DOMAINS = {"pravo.ru", "garant.ru", "consultant.ru"}
_AI_TECH_DOMAINS = {"habr.com", "vc.ru"}


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


def _marker_present(text: str, marker: str) -> bool:
    pattern = _TOKEN_MARKER_PATTERNS.get(marker)
    if pattern is not None:
        return bool(pattern.search(text))
    return marker in text


def keyword_score(text: str) -> float:
    normalized = _normalize_text(text)
    score = 0.0
    for keyword, weight in _KEYWORDS_WEIGHTED.items():
        if _marker_present(normalized, keyword):
            score += weight
    return score


def specialized_relevance_score(article: ArticleCandidate) -> float:
    text = _normalize_text(f"{article.title}\n{article.summary}")
    domain = extract_domain(article.article_url or article.source_url)

    ai_hits = sum(1 for marker in _AI_MARKERS if _marker_present(text, marker))
    legal_hits = sum(1 for marker in _LEGAL_MARKERS if _marker_present(text, marker))
    ops_hits = sum(1 for marker in _OPS_MARKERS if _marker_present(text, marker))
    market_hits = sum(1 for marker in _MARKET_MARKERS if _marker_present(text, marker))
    offtopic_hits = sum(1 for marker in _OFFTOPIC_MARKERS if _marker_present(text, marker))

    score = 0.0
    if ai_hits:
        score += 2.0 + min(ai_hits, 3) * 0.4
    if legal_hits:
        score += 1.5 + min(legal_hits, 3) * 0.5
    if ops_hits:
        score += 1.2 + min(ops_hits, 3) * 0.4
    if market_hits:
        score += min(market_hits, 2) * 0.5

    if domain in _LEGAL_DOMAINS and (ai_hits or ops_hits):
        score += 1.3
    if domain in _AI_TECH_DOMAINS and (legal_hits or ops_hits or market_hits):
        score += 0.8

    if ai_hits and (legal_hits or ops_hits or market_hits):
        score += 1.6
    elif legal_hits and ops_hits:
        score += 1.0

    if domain in _AI_TECH_DOMAINS and legal_hits == 0 and market_hits == 0:
        score -= 6.0
    if domain not in _LEGAL_DOMAINS and legal_hits == 0 and market_hits == 0:
        score -= 3.5

    if offtopic_hits and legal_hits == 0 and ops_hits == 0:
        score -= 4.5
    if ai_hits and legal_hits == 0 and ops_hits == 0 and market_hits == 0:
        score -= 2.8

    return score


def passes_editorial_scope(article: ArticleCandidate) -> bool:
    text = _normalize_text(f"{article.title}\n{article.summary}")
    domain = extract_domain(article.article_url or article.source_url)
    has_ai = any(_marker_present(text, marker) for marker in _AI_MARKERS)
    has_hard_legal = any(_marker_present(text, marker) for marker in _HARD_LEGAL_MARKERS)
    has_hard_market = any(_marker_present(text, marker) for marker in _HARD_MARKET_MARKERS)
    has_ops = any(_marker_present(text, marker) for marker in _OPS_MARKERS)

    if domain in _LEGAL_DOMAINS:
        return has_ai or has_ops
    return has_ai and (has_hard_legal or has_hard_market)


def passes_generation_scope(article: ArticleCandidate) -> bool:
    text = _normalize_text(f"{article.title}\n{article.summary}")
    domain = extract_domain(article.article_url or article.source_url)
    has_ai = any(_marker_present(text, marker) for marker in _AI_MARKERS)
    has_hard_legal = any(_marker_present(text, marker) for marker in _HARD_LEGAL_MARKERS)
    has_hard_market = any(_marker_present(text, marker) for marker in _HARD_MARKET_MARKERS)
    has_generation_ops = any(_marker_present(text, marker) for marker in _GENERATION_OPS_MARKERS)

    if domain in _LEGAL_DOMAINS:
        return has_ai or (has_generation_ops and has_hard_legal)
    return has_ai and (has_hard_legal or has_hard_market)


def is_specialized_candidate(article: ArticleCandidate, *, threshold: float = 3.2) -> bool:
    return passes_generation_scope(article) and specialized_relevance_score(article) >= threshold


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
    specialization = specialized_relevance_score(article)
    if specialization < 3.2:
        return -1000.0 + specialization

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
    return base + specialization + freshness_bonus + summary_bonus + summary_penalty + domain_bonus


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
        if not is_specialized_candidate(candidate):
            continue
        base = keyword_score(f"{candidate.title}\n{candidate.summary}") + specialized_relevance_score(candidate)
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
