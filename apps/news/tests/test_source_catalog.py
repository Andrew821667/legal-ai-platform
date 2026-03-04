from __future__ import annotations

from news.pipeline import canonicalize_source_url
from news.settings import Settings
from news.source_catalog import (
    active_source_specs,
    resolve_source_urls,
    source_bucket_map,
    source_catalog,
    source_priority_map,
    telegram_channel_bucket_map,
    telegram_channel_priority_map,
)


def test_source_catalog_marks_telegram_unconfigured_by_default() -> None:
    settings = Settings(
        news_source_keys='google_news_ru,telegram_channels,pravo_ru',
        news_source_urls='',
        telegram_api_id=0,
        telegram_api_hash='',
        telegram_channels='',
        telegram_fetch_enabled=False,
    )
    catalog = source_catalog(settings)
    assert catalog['telegram_channels'].integrated is False
    active = active_source_specs(settings)
    assert [item.key for item in active] == ['google_news_ru', 'telegram_channels', 'pravo_ru']
    resolved = resolve_source_urls(settings)
    assert any('news.google.com/rss/search' in item for item in resolved)
    assert 'https://www.pravo.ru/rss/' in resolved
    assert all('t.me' not in item for item in resolved)


def test_source_catalog_marks_telegram_configured_when_env_complete() -> None:
    settings = Settings(
        news_source_keys='telegram_channels',
        news_source_urls='',
        telegram_api_id=123456,
        telegram_api_hash='hash',
        telegram_channels='@legal_ai,@legaltech_news',
        telegram_fetch_enabled=True,
    )
    catalog = source_catalog(settings)
    assert catalog['telegram_channels'].integrated is True


def test_source_catalog_includes_extended_google_news_buckets() -> None:
    settings = Settings(news_source_keys="", news_source_urls="")
    catalog = source_catalog(settings)
    assert "google_news_ops_ru" in catalog
    assert "google_news_ops_en" in catalog
    assert "google_news_regulation_ru" in catalog
    assert "google_news_regulation_en" in catalog
    assert "google_news_market_en" in catalog
    assert "google_news_privacy_ru" in catalog
    assert "google_news_privacy_en" in catalog
    assert "google_news_contracts_ru" in catalog
    assert "google_news_contracts_en" in catalog
    assert "google_news_legal_depts_en" in catalog
    assert "google_news_ediscovery_en" in catalog
    assert "google_news_agents_en" in catalog
    assert "google_news_vendors_en" in catalog
    assert "google_news_frontier_en" in catalog
    assert "google_news_enterprise_ai_en" in catalog
    assert "google_news_ai_products_en" in catalog
    assert "google_news_ai_research_en" in catalog
    assert "google_news_ai_policy_global_en" in catalog
    assert "ai_news_global" in catalog
    assert "unite_ai" in catalog
    assert "marktechpost" in catalog
    assert "vedomosti_technology" in catalog
    assert "vedomosti_regulations" in catalog
    assert "vedomosti_security_law" in catalog


def test_source_catalog_marks_garant_unintegrated() -> None:
    settings = Settings(news_source_keys="garant", news_source_urls="")
    catalog = source_catalog(settings)
    assert catalog["garant"].integrated is False


def test_source_priority_map_prefers_legal_sources() -> None:
    settings = Settings(news_source_keys="pravo_ru,garant,lenta", news_source_urls="")
    priorities = source_priority_map(settings)
    assert priorities["pravo.ru"] > priorities["lenta.ru"]
    assert priorities["garant.ru"] > priorities["lenta.ru"]


def test_telegram_channel_priority_map_prefers_legal_channels() -> None:
    settings = Settings()
    priorities = telegram_channel_priority_map(settings, ["@allthingslegal", "@ai_newz"])
    assert priorities["https://t.me/allthingslegal"] > priorities["https://t.me/ai_newz"]


def test_source_bucket_map_marks_broad_ai_sources() -> None:
    settings = Settings(news_source_keys="google_news_contracts_en,google_news_frontier_en", news_source_urls="")
    buckets = source_bucket_map(settings)
    assert buckets["news.google.com"] in {"core", "broad_ai"}
    assert buckets[canonicalize_source_url(source_catalog(settings)["google_news_contracts_en"].url)] == "core"
    assert buckets[canonicalize_source_url(source_catalog(settings)["google_news_frontier_en"].url)] == "broad_ai"


def test_telegram_channel_bucket_map_marks_broad_ai_channels() -> None:
    buckets = telegram_channel_bucket_map(["@allthingslegal", "@ai_newz"])
    assert buckets["https://t.me/allthingslegal"] == "core"
    assert buckets["https://t.me/ai_newz"] == "broad_ai"
