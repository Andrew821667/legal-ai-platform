from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
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
GENERATION_THEME_DEFS: dict[str, dict[str, Any]] = {
    "legal_function_ai": {
        "label": "AI в работе юротдела",
        "note": "Скорость, SLA, маршрутизация, загрузка команды, качество юридического сервиса.",
        "keywords": ("юротдел", "legal ops", "legal department", "in-house legal", "gc office", "sla", "triage"),
    },
    "contracts_ai": {
        "label": "AI в договорной работе",
        "note": "Review, redline, playbook, lifecycle, переговоры и контроль рисков по договорам.",
        "keywords": ("договор", "contract", "redline", "redlining", "playbook", "contract lifecycle", "clm"),
    },
    "leads_ai": {
        "label": "AI в обработке заявок",
        "note": "Intake, квалификация, клиентский путь, ответы и маршрутизация обращений.",
        "keywords": ("intake", "lead", "triage", "заявк", "квалификац", "маршрутизац", "client intake"),
    },
    "documents_ai": {
        "label": "AI в документообороте",
        "note": "Шаблоны, сбор данных, генерация документов и контроль качества.",
        "keywords": ("документооборот", "document", "template", "шаблон", "генерац документов", "knowledge base"),
    },
    "disputes_ai": {
        "label": "AI в спорах и претензионной работе",
        "note": "Судебная аналитика, eDiscovery, legal hold, стратегия спора.",
        "keywords": ("litigation", "e-discovery", "ediscovery", "legal hold", "суд", "претензи", "dispute"),
    },
    "privacy_compliance_ai": {
        "label": "AI в privacy, комплаенсе и governance",
        "note": "ПДн, трансграничка, governance, контроль рисков и регуляторный контур.",
        "keywords": ("privacy", "персональн", "gdpr", "compliance", "governance", "локализац", "трансгранич"),
    },
    "legal_ops_automation": {
        "label": "Legal Ops и автоматизация процессов",
        "note": "Workflow, playbook, операционная модель и автоматизация юридической функции.",
        "keywords": ("workflow", "legal ops", "автоматиз", "playbook", "процесс", "workflow automation"),
    },
    "tools_products_ai": {
        "label": "AI-инструменты и продукты для юристов",
        "note": "Платформы, copilot, vendor evaluation, прикладные AI-инструменты.",
        "keywords": ("tool", "platform", "copilot", "vendor", "assistant", "продукт", "инструмент"),
    },
    "ai_regulation": {
        "label": "Регулирование AI",
        "note": "AI Act, AI law, ответственность, sanctions, privacy law, export controls.",
        "keywords": ("ai act", "регулирован", "ai law", "закон", "санкц", "export", "liability"),
    },
    "legal_ai_market": {
        "label": "Рынок Legal AI и legal tech",
        "note": "Сделки, рост вендоров, кейсы рынка, консолидация и новые сегменты.",
        "keywords": ("рынок", "market", "funding", "acquisition", "legal tech", "legaltech", "vendor"),
    },
    "general_ai": {
        "label": "Общий AI и продуктовые сигналы",
        "note": "Широкие AI-посты как источник идей для внедрения, но в небольшом объеме.",
        "keywords": ("ai assistant", "ai product", "copilot", "enterprise ai", "business ai", "workflow ai", "product launch"),
    },
    "frontier_ai": {
        "label": "Модели, агенты и frontier AI",
        "note": "Frontier models, reasoning, агенты и крупные технологические сдвиги.",
        "keywords": ("frontier", "reasoning", "multimodal", "foundation model", "agentic", "ai agent", "model release"),
    },
    "enterprise_ai": {
        "label": "Enterprise AI и корпоративные внедрения",
        "note": "Корпоративные AI-платформы, copilot-контуры, интеграция в бизнес-процессы.",
        "keywords": ("enterprise ai", "corporate ai", "copilot", "workflow ai", "business ai", "platform rollout"),
    },
    "model_risk_and_safety": {
        "label": "Риски моделей и AI-безопасность",
        "note": "Model risk, safety, red teaming, guardrails, устойчивость и контроль поведения моделей.",
        "keywords": ("model risk", "ai safety", "red team", "guardrail", "hallucination", "alignment", "safety eval"),
    },
}
_PILLAR_TO_GENERATION_THEMES: dict[str, tuple[str, ...]] = {
    "regulation": ("ai_regulation", "privacy_compliance_ai", "disputes_ai"),
    "case": ("legal_ops_automation", "contracts_ai", "disputes_ai"),
    "implementation": ("legal_function_ai", "legal_ops_automation", "contracts_ai", "documents_ai", "leads_ai"),
    "tools": ("tools_products_ai", "general_ai", "frontier_ai", "enterprise_ai"),
    "market": ("legal_ai_market", "tools_products_ai", "general_ai", "enterprise_ai", "model_risk_and_safety"),
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
    "litigation",
    "discovery",
    "e-discovery",
    "document review",
    "legal hold",
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
    "document review",
    "redlining",
    "legal hold",
    "e-discovery",
    "ediscovery",
    "agentic",
    "ai agent",
    "agent",
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
    "document review",
    "redlining",
    "legal hold",
    "e-discovery",
    "ediscovery",
    "agentic",
    "ai agent",
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
_SPECIFICITY_MARKERS = (
    "ai act",
    "gdpr",
    "openai",
    "deepseek",
    "anthropic",
    "google ai",
    "персональн",
    "трансгранич",
    "локализац",
    "конфиденциаль",
    "коммерческ",
    "договор",
    "sla",
    "indemn",
    "ответствен",
    "лиценз",
    "интеллектуальн",
    "privacy",
    "compliance",
    "governance",
    "аудит",
    "логирован",
    "human-in-the-loop",
    "document review",
    "e-discovery",
    "legal hold",
    "agentic",
    "ai agent",
    "gc office",
    "in-house legal",
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


def canonicalize_source_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    parsed = urlparse(raw)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    normalized = parsed._replace(scheme=scheme, netloc=netloc, params="", fragment="")
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


def generation_theme_keys() -> tuple[str, ...]:
    return tuple(GENERATION_THEME_DEFS)


def generation_theme_label(theme_key: str) -> str:
    row = GENERATION_THEME_DEFS.get(theme_key)
    if row is None:
        return theme_key
    return str(row.get("label") or theme_key)


def generation_theme_note(theme_key: str) -> str:
    row = GENERATION_THEME_DEFS.get(theme_key)
    if row is None:
        return ""
    return str(row.get("note") or "")


def generation_themes_for_text(text: str) -> set[str]:
    normalized = _normalize_text(text)
    matched: set[str] = set()
    for theme_key, row in GENERATION_THEME_DEFS.items():
        keywords = tuple(str(item).strip().lower() for item in row.get("keywords", ()) if str(item).strip())
        if any(keyword in normalized for keyword in keywords):
            matched.add(theme_key)

    if matched:
        return matched

    pillar = infer_pillar(text)
    matched.update(_PILLAR_TO_GENERATION_THEMES.get(pillar, ()))
    if matched:
        return matched

    return {"general_ai"}


def article_matches_enabled_generation_themes(article: ArticleCandidate, enabled_theme_keys: set[str] | None) -> bool:
    if not enabled_theme_keys:
        return True
    article_themes = generation_themes_for_text(f"{article.title}\n{article.summary}")
    return bool(article_themes & enabled_theme_keys)


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
    source_priority_weights: dict[str, float] | None = None,
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

    source_priority_bonus = 0.0
    if source_priority_weights:
        source_url_key = canonicalize_source_url(article.source_url)
        article_domain = extract_domain(article.article_url)
        source_domain = extract_domain(article.source_url)
        source_weight = source_priority_weights.get(source_url_key)
        if source_weight is None and source_domain:
            source_weight = source_priority_weights.get(source_domain)
        if source_weight is None and article_domain:
            source_weight = source_priority_weights.get(article_domain)
        if source_weight is not None:
            source_priority_bonus = max(-1.5, min(2.0, source_weight - 1.0))

    # Минимальный порог, чтобы не выбирать нерелевантные статьи.
    return base + specialization + freshness_bonus + summary_bonus + summary_penalty + domain_bonus + source_priority_bonus


def choose_top_articles(
    candidates: list[ArticleCandidate],
    limit: int,
    now_utc: datetime,
    priority_domains: set[str] | None = None,
    source_priority_weights: dict[str, float] | None = None,
    source_bucket_weights: dict[str, str] | None = None,
    max_bucket_counts: dict[str, int] | None = None,
    max_per_source: int = 2,
    recent_pillar_counts: dict[str, int] | None = None,
    target_pillar_shares: dict[str, float] | None = None,
) -> list[ArticleCandidate]:
    scored: list[tuple[ArticleCandidate, float, float, str]] = []
    for candidate in candidates:
        if not is_specialized_candidate(candidate):
            continue
        base = keyword_score(f"{candidate.title}\n{candidate.summary}") + specialized_relevance_score(candidate)
        total = article_score(
            candidate,
            now_utc,
            priority_domains=priority_domains,
            source_priority_weights=source_priority_weights,
        )
        pillar = pillar_for_article(candidate)
        scored.append((candidate, total, base, pillar))
    scored.sort(key=lambda x: x[1], reverse=True)

    recent_counts = dict(recent_pillar_counts or {})
    target_shares = dict(target_pillar_shares or _DEFAULT_PILLAR_TARGETS)
    selected: list[ArticleCandidate] = []
    source_count: dict[str, int] = {}
    selected_pillar_counts: dict[str, int] = {}
    bucket_count: dict[str, int] = {}

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
            bucket_key = "core"
            if source_bucket_weights:
                source_url_key = canonicalize_source_url(candidate.source_url)
                article_domain = extract_domain(candidate.article_url)
                source_domain = extract_domain(candidate.source_url)
                bucket_key = (
                    source_bucket_weights.get(source_url_key)
                    or source_bucket_weights.get(source_domain)
                    or source_bucket_weights.get(article_domain)
                    or "core"
                )
            if max_bucket_counts is not None:
                bucket_limit = max_bucket_counts.get(bucket_key)
                if bucket_limit is not None and bucket_count.get(bucket_key, 0) >= bucket_limit:
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
        if source_bucket_weights:
            source_url_key = canonicalize_source_url(candidate.source_url)
            article_domain = extract_domain(candidate.article_url)
            source_domain = extract_domain(candidate.source_url)
            bucket_key = (
                source_bucket_weights.get(source_url_key)
                or source_bucket_weights.get(source_domain)
                or source_bucket_weights.get(article_domain)
                or "core"
            )
            bucket_count[bucket_key] = bucket_count.get(bucket_key, 0) + 1

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
    normalized = (text or "").strip()
    if not normalized:
        return ""
    if len(normalized) <= 4000:
        return normalized

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if not blocks:
        return _trim_html_safely(normalized, 4000)

    parts: list[str] = []
    for block in blocks:
        candidate = "\n\n".join(parts + [block]).strip()
        if len(candidate) <= 4000:
            parts.append(block)
            continue

        remaining = 4000 - len("\n\n".join(parts).strip()) - (2 if parts else 0)
        if remaining > 180:
            trimmed = _trim_html_safely(block, remaining)
            if trimmed:
                parts.append(trimmed)
        break

    result = "\n\n".join(parts).strip()
    if not result:
        return _trim_html_safely(normalized, 4000)
    return result


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def _extract_text(html_text: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html_text)
    parser.close()
    return parser.get_text()


def _safe_tail_boundary(text: str) -> int:
    stripped = text.rstrip()
    if not stripped:
        return 0
    sentence_boundaries = [stripped.rfind(mark) for mark in (".", "!", "?", "…")]
    boundary = max(sentence_boundaries)
    if boundary >= max(0, len(stripped) - 220):
        return boundary + 1

    newline_boundary = stripped.rfind("\n")
    if newline_boundary >= max(0, len(stripped) - 260):
        return newline_boundary

    space_boundary = stripped.rfind(" ")
    if space_boundary > 0:
        return space_boundary
    return len(stripped)


def _trim_html_safely(html_text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(html_text) <= limit:
        return html_text.strip()

    truncated = html_text[:limit]
    boundary = _safe_tail_boundary(_extract_text(truncated))
    if boundary <= 0:
        truncated = truncated.rstrip()
    else:
        plain = _extract_text(truncated)
        boundary_text = plain[:boundary].rstrip()
        cut = truncated.find(boundary_text)
        if cut != -1:
            truncated = truncated[: cut + len(boundary_text)]
        else:
            truncated = truncated[:limit].rstrip()

    # Drop dangling start of tag/entity if we cut inside HTML markup.
    last_lt = truncated.rfind("<")
    last_gt = truncated.rfind(">")
    if last_lt > last_gt:
        truncated = truncated[:last_lt]
    last_amp = truncated.rfind("&")
    last_semicolon = truncated.rfind(";")
    if last_amp > last_semicolon:
        truncated = truncated[:last_amp]

    open_b = truncated.count("<b>") - truncated.count("</b>")
    if open_b > 0:
        truncated += "</b>" * open_b
    open_a = truncated.count("<a ") - truncated.count("</a>")
    if open_a > 0:
        truncated += "</a>" * open_a
    return truncated.strip()
