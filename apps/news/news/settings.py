from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    core_api_url: str = "http://core-api:8000"
    api_key_news: str = ""
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_channel_username: str = ""
    news_source_urls: str = ""
    tz_name: str = "Europe/Moscow"
    openai_api_key: str = ""
    openai_base_url: str = ""
    news_model: str = "deepseek-chat"
    news_top_k: int = 5
    news_schedule_slots: str = "10:00,13:00,17:00"
    news_retry_failed_after_minutes: int = 15
    news_max_per_source: int = 2
    news_similarity_threshold: float = 0.48
    news_priority_domains: str = ""
    news_history_scan_limit: int = 120


settings = Settings()
