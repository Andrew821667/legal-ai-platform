from __future__ import annotations

from news.competitor_policy import (
    COMPETITOR_REPLACEMENT,
    anonymize_competitor_mentions,
    competitor_mentions,
    competitor_policy_failure_reason,
    is_competitor_channel,
    is_competitor_source_url,
)


def test_competitor_channel_matches_username_and_telegram_url() -> None:
    assert is_competitor_channel("@Law_GPT")
    assert is_competitor_source_url("https://t.me/Law_GPT/144")
    assert is_competitor_source_url("t.me/Law_GPT/144")
    assert is_competitor_source_url("@Law_GPT")
    assert not is_competitor_source_url("https://t.me/allthingslegal/10")


def test_competitor_domain_matches_subdomains_only() -> None:
    assert is_competitor_source_url("https://app.lawgpt.ru/workspace")
    assert not is_competitor_source_url("https://example.com/article-about-lawgpt")


def test_competitor_mentions_cover_brand_variants() -> None:
    text = "Law_GPT и ЗаконГПТ представили обновление"
    assert set(item.lower() for item in competitor_mentions(text)) == {"law_gpt", "законгпт"}


def test_anonymize_competitor_mentions_keeps_industry_fact_without_brand() -> None:
    text = "Платформа LawGPT добавила экспорт истории работы."
    result = anonymize_competitor_mentions(text)
    assert result == f"Платформа {COMPETITOR_REPLACEMENT} добавила экспорт истории работы."
    assert not competitor_mentions(result)


def test_competitor_policy_rejects_source_and_public_brand_leak() -> None:
    assert (
        competitor_policy_failure_reason(
            text="Нейтральный редакционный материал",
            source_url="https://t.me/Law_GPT/144",
        )
        == "competitor_source"
    )
    assert (
        competitor_policy_failure_reason(
            text="LawGPT выпустил новую функцию",
            source_url="https://example.com/news",
        )
        == "competitor_brand_mention"
    )
