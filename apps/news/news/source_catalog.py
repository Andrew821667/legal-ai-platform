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
    return {
        "google_news_ru": SourceSpec(
            key="google_news_ru",
            name="Google News RU",
            kind="search_rss",
            note="Поисковый RSS по русскоязычным темам AI в праве и автоматизации юрфункции",
            url=google_ru,
            domain="news.google.com",
        ),
        "google_news_en": SourceSpec(
            key="google_news_en",
            name="Google News EN",
            kind="search_rss",
            note="Поисковый RSS по англоязычным темам legal AI и legal ops",
            url=google_en,
            domain="news.google.com",
        ),
        "google_news_ops_ru": SourceSpec(
            key="google_news_ops_ru",
            name="Google News Legal Ops RU",
            kind="search_rss",
            note="Поисковый RSS по русскоязычным сценариям AI в юротделе, договорной работе и документообороте",
            url=google_ops_ru,
            domain="news.google.com",
        ),
        "google_news_ops_en": SourceSpec(
            key="google_news_ops_en",
            name="Google News Legal Ops EN",
            kind="search_rss",
            note="Поисковый RSS по legal operations, contract automation и AI для юрфункции",
            url=google_ops_en,
            domain="news.google.com",
        ),
        "google_news_regulation_ru": SourceSpec(
            key="google_news_regulation_ru",
            name="Google News AI Regulation RU",
            kind="search_rss",
            note="Поисковый RSS по регулированию ИИ, ответственности и данным на русском языке",
            url=google_regulation_ru,
            domain="news.google.com",
        ),
        "google_news_regulation_en": SourceSpec(
            key="google_news_regulation_en",
            name="Google News AI Regulation EN",
            kind="search_rss",
            note="Поисковый RSS по AI regulation, AI Act, governance, privacy law",
            url=google_regulation_en,
            domain="news.google.com",
        ),
        "google_news_market_en": SourceSpec(
            key="google_news_market_en",
            name="Google News Legal AI Market EN",
            kind="search_rss",
            note="Поисковый RSS по рынку legal AI, legaltech и продуктовым AI-решениям для юристов",
            url=google_market_en,
            domain="news.google.com",
        ),
        "pravo_ru": SourceSpec(
            key="pravo_ru",
            name="Право.ru",
            kind="rss",
            note="Юррынок, практика, судебка, legal ops",
            url="https://www.pravo.ru/rss/",
            domain="pravo.ru",
        ),
        "garant": SourceSpec(
            key="garant",
            name="Гарант",
            kind="rss",
            note="Регуляторика, изменения законодательства, правовые обзоры",
            url="https://www.garant.ru/rss/news/",
            domain="garant.ru",
        ),
        "habr_news": SourceSpec(
            key="habr_news",
            name="Habr Новости",
            kind="rss",
            note="AI и автоматизация, только через жесткий topical filter",
            url="https://habr.com/ru/rss/news/?fl=ru",
            domain="habr.com",
        ),
        "habr_hubs": SourceSpec(
            key="habr_hubs",
            name="Habr Хабы",
            kind="rss",
            note="Технические и продуктовые материалы, только через жесткий topical filter",
            url="https://habr.com/ru/rss/hubs/",
            domain="habr.com",
        ),
        "vc": SourceSpec(
            key="vc",
            name="vc.ru",
            kind="rss",
            note="Enterprise AI, продукты и legal tech, только через topical filter",
            url="https://vc.ru/rss/all",
            domain="vc.ru",
        ),
        "tass": SourceSpec(
            key="tass",
            name="ТАСС",
            kind="rss",
            note="Общий новостной поток, допускается только через topical/legal filter",
            url="https://tass.ru/rss/v2.xml",
            domain="tass.ru",
        ),
        "lenta": SourceSpec(
            key="lenta",
            name="Lenta.ru",
            kind="rss",
            note="Общий новостной поток, используется только через topical/legal filter",
            url="https://lenta.ru/rss/news",
            domain="lenta.ru",
        ),
        "interfax": SourceSpec(
            key="interfax",
            name="Интерфакс",
            kind="rss",
            note="Технологии и наука, только через topical/legal filter",
            url="https://www.interfax.ru/rss.asp",
            domain="interfax.ru",
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
        "pravo_ru",
        "garant",
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
                )
            )
            continue
        specs.append(spec)
    return specs
