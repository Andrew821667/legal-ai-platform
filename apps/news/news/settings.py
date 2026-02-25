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


settings = Settings()
