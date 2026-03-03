from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "legal-ai-core-api"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://legalai:legalai@localhost:5432/legalai"
    cors_origins: str = "http://localhost:3000"
    alert_bot_token: str | None = None
    alert_chat_id: str | None = None
    api_key_cache_ttl_seconds: int = 60
    health_worker_active_minutes: int = 10
    news_retry_failed_after_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
