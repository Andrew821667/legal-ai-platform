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
    miniapp_public_base_url: str = "http://localhost:3000"
    db_pool_size: int = 8
    db_max_overflow: int = 8
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800


@lru_cache
def get_settings() -> Settings:
    return Settings()
