from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus


@dataclass(frozen=True, slots=True)
class SourceSpec:
    key: str
    name: str
    kind: str
    note: str
    url: str | None = None
    domain: str | None = None
    integrated: bool = True
    priority: float = 1.0


_TELEGRAM_CHANNEL_PRIORITIES: dict[str, float] = {
    "allthingslegal": 1.9,
    "legal_tech": 1.8,
    "law_gpt": 1.7,
    "openai_ru": 1.1,
    "ai_newz": 0.8,
    "anthropicai": 0.7,
    "googleai": 0.7,
    "ai_machinelearning_big_data": 0.7,
}


def build_google_news_rss_url(query: str, lang: str, region: str) -> str:
    encoded_query = quote_plus(query.strip())
    return f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={region}&ceid={region}:{lang}"


def source_catalog(settings: Any) -> dict[str, SourceSpec]:
    telegram_channels = list(getattr(settings, "telegram_channels_list", []))
    telegram_ready = bool(
        getattr(settings, "telegram_fetch_enabled", False)
        and getattr(settings, "telegram_api_id", 0)
        and getattr(settings, "telegram_api_hash", "")
        and telegram_channels
    )
    google_ru = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_ru",
            '("искусственный интеллект" OR "юридический ИИ" OR legaltech OR "автоматизация юротдела" OR "автоматизация юридической функции")',
        ),
        getattr(settings, "google_news_lang_ru", "ru"),
        getattr(settings, "google_news_region_ru", "RU"),
    )
    google_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_en",
            '("legal AI" OR legaltech OR "AI for lawyers" OR "contract automation" OR "legal operations automation")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_ops_ru = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_ops_ru",
            '("автоматизация договорной работы" OR "автоматизация юротдела" OR legaltech OR "документооборот юристов" OR "AI для юристов")',
        ),
        getattr(settings, "google_news_lang_ru", "ru"),
        getattr(settings, "google_news_region_ru", "RU"),
    )
    google_ops_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_ops_en",
            '("legal operations" OR "contract automation" OR "AI for legal departments" OR "AI for lawyers" OR legaltech)',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_regulation_ru = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_regulation_ru",
            '("регулирование ИИ" OR "закон об ИИ" OR "ответственность за ИИ" OR "персональные данные ИИ" OR "AI compliance")',
        ),
        getattr(settings, "google_news_lang_ru", "ru"),
        getattr(settings, "google_news_region_ru", "RU"),
    )
    google_regulation_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_regulation_en",
            '("AI regulation" OR "AI Act" OR "AI compliance" OR "AI governance" OR "AI privacy law")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_market_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_market_en",
            '("legal tech" OR legaltech OR "legal AI" OR "AI contract review" OR "AI compliance platform")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_privacy_ru = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_privacy_ru",
            '("ИИ и персональные данные" OR "AI и персональные данные" OR "трансграничная передача ИИ" OR "privacy AI" OR "AI governance privacy")',
        ),
        getattr(settings, "google_news_lang_ru", "ru"),
        getattr(settings, "google_news_region_ru", "RU"),
    )
    google_privacy_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_privacy_en",
            '("AI privacy" OR "AI data protection" OR "AI governance privacy" OR "generative AI privacy" OR "AI cross-border data")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_contracts_ru = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_contracts_ru",
            '("AI договоры" OR "автоматизация договорной работы" OR "contract review AI" OR "AI redlining" OR "договорный ИИ")',
        ),
        getattr(settings, "google_news_lang_ru", "ru"),
        getattr(settings, "google_news_region_ru", "RU"),
    )
    google_contracts_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_contracts_en",
            '("AI contract review" OR "contract automation AI" OR "legal AI contracts" OR "redlining AI" OR "contract lifecycle AI")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_legal_depts_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_legal_depts_en",
            '("AI legal department" OR "GC AI" OR "in-house legal AI" OR "legal operations AI" OR "corporate legal automation")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_ediscovery_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_ediscovery_en",
            '("e-discovery AI" OR "document review AI" OR "AI for eDiscovery" OR "litigation AI" OR "legal hold AI")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_agents_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_agents_en",
            '("agentic legal AI" OR "legal AI agent" OR "AI agent for lawyers" OR "agentic AI contract review" OR "AI workflow legal")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_vendors_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_vendors_en",
            '("legal AI platform" OR "AI legal assistant" OR "contract review platform" OR "AI compliance platform" OR "legal tech product")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_frontier_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_frontier_en",
            '("frontier AI model" OR "foundation model" OR "reasoning model" OR "multimodal AI" OR "frontier model")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_enterprise_ai_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_enterprise_ai_en",
            '("enterprise AI" OR "AI copilots business" OR "AI workflow automation" OR "AI agents enterprise" OR "business AI platform")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    google_ai_products_en = build_google_news_rss_url(
        getattr(
            settings,
            "google_news_query_ai_products_en",
            '("AI product launch" OR "AI platform launch" OR "generative AI product" OR "AI assistant release" OR "AI tool launch")',
        ),
        getattr(settings, "google_news_lang_en", "en"),
        getattr(settings, "google_news_region_en", "US"),
    )
    return {
        "google_news_ru": SourceSpec(
            key="google_news_ru",
            name="Google News RU",
            kind="search_rss",
            note="Поисковый RSS по русскоязычным темам AI в праве и автоматизации юрфункции",
            url=google_ru,
            domain="news.google.com",
            priority=1.35,
        ),
        "google_news_en": SourceSpec(
            key="google_news_en",
            name="Google News EN",
            kind="search_rss",
            note="Поисковый RSS по англоязычным темам legal AI и legal ops",
            url=google_en,
            domain="news.google.com",
            priority=1.35,
        ),
        "google_news_ops_ru": SourceSpec(
            key="google_news_ops_ru",
            name="Google News Legal Ops RU",
            kind="search_rss",
            note="Поисковый RSS по русскоязычным сценариям AI в юротделе, договорной работе и документообороте",
            url=google_ops_ru,
            domain="news.google.com",
            priority=1.55,
        ),
        "google_news_ops_en": SourceSpec(
            key="google_news_ops_en",
            name="Google News Legal Ops EN",
            kind="search_rss",
            note="Поисковый RSS по legal operations, contract automation и AI для юрфункции",
            url=google_ops_en,
            domain="news.google.com",
            priority=1.55,
        ),
        "google_news_regulation_ru": SourceSpec(
            key="google_news_regulation_ru",
            name="Google News AI Regulation RU",
            kind="search_rss",
            note="Поисковый RSS по регулированию ИИ, ответственности и данным на русском языке",
            url=google_regulation_ru,
            domain="news.google.com",
            priority=1.6,
        ),
        "google_news_regulation_en": SourceSpec(
            key="google_news_regulation_en",
            name="Google News AI Regulation EN",
            kind="search_rss",
            note="Поисковый RSS по AI regulation, AI Act, governance, privacy law",
            url=google_regulation_en,
            domain="news.google.com",
            priority=1.6,
        ),
        "google_news_market_en": SourceSpec(
            key="google_news_market_en",
            name="Google News Legal AI Market EN",
            kind="search_rss",
            note="Поисковый RSS по рынку legal AI, legaltech и продуктовым AI-решениям для юристов",
            url=google_market_en,
            domain="news.google.com",
            priority=1.3,
        ),
        "google_news_privacy_ru": SourceSpec(
            key="google_news_privacy_ru",
            name="Google News AI Privacy RU",
            kind="search_rss",
            note="Поисковый RSS по AI, персональным данным, трансграничной передаче и privacy на русском языке",
            url=google_privacy_ru,
            domain="news.google.com",
            priority=1.65,
        ),
        "google_news_privacy_en": SourceSpec(
            key="google_news_privacy_en",
            name="Google News AI Privacy EN",
            kind="search_rss",
            note="Поисковый RSS по AI privacy, data protection, governance и cross-border data",
            url=google_privacy_en,
            domain="news.google.com",
            priority=1.65,
        ),
        "google_news_contracts_ru": SourceSpec(
            key="google_news_contracts_ru",
            name="Google News AI Contracts RU",
            kind="search_rss",
            note="Поисковый RSS по AI в договорной работе, review, redline и контрактным процессам",
            url=google_contracts_ru,
            domain="news.google.com",
            priority=1.7,
        ),
        "google_news_contracts_en": SourceSpec(
            key="google_news_contracts_en",
            name="Google News AI Contracts EN",
            kind="search_rss",
            note="Поисковый RSS по contract automation, contract review и contract lifecycle AI",
            url=google_contracts_en,
            domain="news.google.com",
            priority=1.7,
        ),
        "google_news_legal_depts_en": SourceSpec(
            key="google_news_legal_depts_en",
            name="Google News In-House Legal AI EN",
            kind="search_rss",
            note="Поисковый RSS по AI для инхаус-команд, GC office и автоматизации корпоративной юрфункции",
            url=google_legal_depts_en,
            domain="news.google.com",
            priority=1.75,
        ),
        "google_news_ediscovery_en": SourceSpec(
            key="google_news_ediscovery_en",
            name="Google News eDiscovery AI EN",
            kind="search_rss",
            note="Поисковый RSS по eDiscovery, document review, litigation AI и legal hold automation",
            url=google_ediscovery_en,
            domain="news.google.com",
            priority=1.6,
        ),
        "google_news_agents_en": SourceSpec(
            key="google_news_agents_en",
            name="Google News Agentic Legal AI EN",
            kind="search_rss",
            note="Поисковый RSS по agentic legal AI, AI agents для юристов и AI workflow для юрфункции",
            url=google_agents_en,
            domain="news.google.com",
            priority=1.5,
        ),
        "google_news_vendors_en": SourceSpec(
            key="google_news_vendors_en",
            name="Google News Legal AI Vendors EN",
            kind="search_rss",
            note="Поисковый RSS по продуктам, платформам и вендорам в сегменте legal AI и legaltech",
            url=google_vendors_en,
            domain="news.google.com",
            priority=1.35,
        ),
        "google_news_frontier_en": SourceSpec(
            key="google_news_frontier_en",
            name="Google News Frontier AI EN",
            kind="search_rss",
            note="Зарубежный поисковый RSS по frontier models, reasoning, multimodal AI и крупным сдвигам в моделях",
            url=google_frontier_en,
            domain="news.google.com",
            priority=0.95,
        ),
        "google_news_enterprise_ai_en": SourceSpec(
            key="google_news_enterprise_ai_en",
            name="Google News Enterprise AI EN",
            kind="search_rss",
            note="Зарубежный поисковый RSS по enterprise AI, AI workflow automation и корпоративным AI-платформам",
            url=google_enterprise_ai_en,
            domain="news.google.com",
            priority=1.0,
        ),
        "google_news_ai_products_en": SourceSpec(
            key="google_news_ai_products_en",
            name="Google News AI Products EN",
            kind="search_rss",
            note="Зарубежный поисковый RSS по запускам AI-продуктов, AI assistants и новым AI-инструментам",
            url=google_ai_products_en,
            domain="news.google.com",
            priority=0.95,
        ),
        "pravo_ru": SourceSpec(
            key="pravo_ru",
            name="Право.ru",
            kind="rss",
            note="Юррынок, практика, судебка, legal ops",
            url="https://www.pravo.ru/rss/",
            domain="pravo.ru",
            priority=1.8,
        ),
        "garant": SourceSpec(
            key="garant",
            name="Гарант",
            kind="rss",
            note="Официальный источник, но прямой RSS сейчас закрыт DDoS-Guard и нестабилен для автоматического сбора",
            url="https://www.garant.ru/rss/news/",
            domain="garant.ru",
            priority=1.8,
            integrated=False,
        ),
        "vedomosti_technology": SourceSpec(
            key="vedomosti_technology",
            name="Ведомости.Технологии",
            kind="rss",
            note="Резервный источник: официальный RSS Ведомостей, но в текущей среде нестабилен по DNS и не включен в активный сбор",
            url="https://www.vedomosti.ru/rss/rubric/technology",
            domain="vedomosti.ru",
            priority=1.15,
            integrated=False,
        ),
        "vedomosti_regulations": SourceSpec(
            key="vedomosti_regulations",
            name="Ведомости.Правила",
            kind="rss",
            note="Резервный источник: официальный RSS Ведомостей по регулированию, но в текущей среде нестабилен по DNS и не включен в активный сбор",
            url="https://www.vedomosti.ru/rss/rubric/economics/regulations",
            domain="vedomosti.ru",
            priority=1.25,
            integrated=False,
        ),
        "vedomosti_security_law": SourceSpec(
            key="vedomosti_security_law",
            name="Ведомости.Безопасность и право",
            kind="rss",
            note="Резервный источник: официальный RSS Ведомостей по праву и безопасности, но в текущей среде нестабилен по DNS и не включен в активный сбор",
            url="https://www.vedomosti.ru/rss/rubric/politics/security_law",
            domain="vedomosti.ru",
            priority=1.3,
            integrated=False,
        ),
        "habr_news": SourceSpec(
            key="habr_news",
            name="Habr Новости",
            kind="rss",
            note="AI и автоматизация, только через жесткий topical filter",
            url="https://habr.com/ru/rss/news/?fl=ru",
            domain="habr.com",
            priority=1.0,
        ),
        "habr_hubs": SourceSpec(
            key="habr_hubs",
            name="Habr Хабы",
            kind="rss",
            note="Технические и продуктовые материалы, только через жесткий topical filter",
            url="https://habr.com/ru/rss/hubs/",
            domain="habr.com",
            priority=0.95,
        ),
        "vc": SourceSpec(
            key="vc",
            name="vc.ru",
            kind="rss",
            note="Enterprise AI, продукты и legal tech, только через topical filter",
            url="https://vc.ru/rss/all",
            domain="vc.ru",
            priority=1.0,
        ),
        "tass": SourceSpec(
            key="tass",
            name="ТАСС",
            kind="rss",
            note="Общий новостной поток, допускается только через topical/legal filter",
            url="https://tass.ru/rss/v2.xml",
            domain="tass.ru",
            priority=0.85,
        ),
        "lenta": SourceSpec(
            key="lenta",
            name="Lenta.ru",
            kind="rss",
            note="Общий новостной поток, используется только через topical/legal filter",
            url="https://lenta.ru/rss/news",
            domain="lenta.ru",
            priority=0.7,
        ),
        "interfax": SourceSpec(
            key="interfax",
            name="Интерфакс",
            kind="rss",
            note="Технологии и наука, только через topical/legal filter",
            url="https://www.interfax.ru/rss.asp",
            domain="interfax.ru",
            priority=0.95,
        ),
        "telegram_channels": SourceSpec(
            key="telegram_channels",
            name="Telegram Channels",
            kind="telegram",
            note=(
                f"Публичные Telegram-каналы через MTProto/Telethon: {', '.join(telegram_channels)}"
                if telegram_ready
                else "Источник поддержан кодом, но требует TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_CHANNELS / session"
            ),
            integrated=telegram_ready,
            priority=1.3,
        ),
        "perplexity_ru": SourceSpec(
            key="perplexity_ru",
            name="Perplexity Search RU",
            kind="search_api",
            note="Было в legacy-контуре как web-search источник, в новом pipeline пока не возвращено",
            integrated=False,
        ),
        "perplexity_en": SourceSpec(
            key="perplexity_en",
            name="Perplexity Search EN",
            kind="search_api",
            note="Было в legacy-контуре как web-search источник, в новом pipeline пока не возвращено",
            integrated=False,
        ),
    }


def parse_active_source_keys(settings: Any) -> list[str]:
    raw_keys = getattr(settings, "news_source_keys", "")
    if raw_keys:
        return [item.strip() for item in raw_keys.split(",") if item.strip()]

    raw_urls = getattr(settings, "news_source_urls", "")
    if raw_urls:
        return [item.strip() for item in raw_urls.split(",") if item.strip()]

    return [
        "google_news_ru",
        "google_news_en",
        "google_news_ops_ru",
        "google_news_ops_en",
        "google_news_regulation_ru",
        "google_news_regulation_en",
        "google_news_market_en",
        "google_news_privacy_ru",
        "google_news_privacy_en",
        "google_news_contracts_ru",
        "google_news_contracts_en",
        "google_news_legal_depts_en",
        "google_news_ediscovery_en",
        "google_news_agents_en",
        "google_news_vendors_en",
        "google_news_frontier_en",
        "google_news_enterprise_ai_en",
        "google_news_ai_products_en",
        "pravo_ru",
        "habr_news",
        "habr_hubs",
        "vc",
        "tass",
        "lenta",
        "interfax",
    ]


def resolve_source_urls(settings: Any, enabled_overrides: dict[str, bool] | None = None) -> list[str]:
    catalog = source_catalog(settings)
    result: list[str] = []
    seen: set[str] = set()
    for item in parse_active_source_keys(settings):
        if enabled_overrides is not None and not enabled_overrides.get(item, True):
            continue
        spec = catalog.get(item)
        url = spec.url if spec else item
        if not url:
            continue
        normalized = url.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def active_source_specs(settings: Any, enabled_overrides: dict[str, bool] | None = None) -> list[SourceSpec]:
    catalog = source_catalog(settings)
    specs: list[SourceSpec] = []
    for item in parse_active_source_keys(settings):
        if enabled_overrides is not None and not enabled_overrides.get(item, True):
            continue
        spec = catalog.get(item)
        if spec is None:
            specs.append(
                SourceSpec(
                    key=item,
                    name=item,
                    kind="rss",
                    note="Источник задан URL напрямую",
                    url=item,
                    domain=None,
                    priority=1.0,
                )
            )
            continue
        specs.append(spec)
    return specs


def source_priority_map(settings: Any, enabled_overrides: dict[str, bool] | None = None) -> dict[str, float]:
    result: dict[str, float] = {}
    for spec in active_source_specs(settings, enabled_overrides=enabled_overrides):
        if spec.url:
            result[spec.url.strip()] = float(spec.priority)
        if spec.domain:
            result[spec.domain.strip().lower()] = float(spec.priority)
    return result


def telegram_channel_priority_map(settings: Any, channels: list[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for raw_channel in channels:
        slug = raw_channel.strip().lstrip("@").lower()
        if not slug:
            continue
        result[f"https://t.me/{slug}"] = _TELEGRAM_CHANNEL_PRIORITIES.get(slug, 1.0)
    return result
