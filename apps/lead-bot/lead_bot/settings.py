from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    core_api_url: str = "http://core-api:8000"
    api_key_bot: str = ""
    telegram_bot_token: str = ""
    buffer_db_path: str = "/tmp/lead_bot_buffer.sqlite3"
    flush_interval_seconds: int = 60


settings = Settings()
