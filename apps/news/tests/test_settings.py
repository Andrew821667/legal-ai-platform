from __future__ import annotations

from news.settings import Settings


def test_deepseek_provider_prefers_deepseek_key() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="deepseek-key",
        openai_api_key="legacy-key",
        openai_base_url="https://api.deepseek.com/v1",
        news_model="deepseek-v4-flash",
    )

    assert settings.resolved_news_api_key == "deepseek-key"


def test_deepseek_provider_supports_legacy_key_name() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="",
        openai_api_key="legacy-key",
        openai_base_url="https://api.deepseek.com/v1",
        news_model="deepseek-v4-flash",
    )

    assert settings.resolved_news_api_key == "legacy-key"


def test_other_provider_uses_openai_key() -> None:
    settings = Settings(
        _env_file=None,
        deepseek_api_key="deepseek-key",
        openai_api_key="openai-key",
        openai_base_url="https://api.openai.com/v1",
        news_model="gpt-test",
    )

    assert settings.resolved_news_api_key == "openai-key"
