from __future__ import annotations

from news.settings import Settings
from news.source_catalog import active_source_specs, resolve_source_urls, source_catalog


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
