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
    database_url: str = "postgresql+psycopg://legalai_app:change_me_local_only@localhost:5432/legalai_platform"
    cors_origins: str = "http://localhost:3000"
    alert_bot_token: str | None = None
    alert_chat_id: str | None = None
    lead_notify_bot_token: str | None = None
    lead_notify_chat_id: str | None = None
    lead_notify_web_base_url: str = "https://ai-verdict.ru"
    api_key_cache_ttl_seconds: int = 60
    health_worker_active_minutes: int = 10
    news_retry_failed_after_minutes: int = 15
    miniapp_public_base_url: str = "https://ai-verdict.ru"
    db_pool_size: int = 8
    db_max_overflow: int = 8
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    contract_ai_bridge_enabled_default: bool = False
    contract_ai_bridge_deployment: str = "docker_local_macbook"
    contract_ai_bridge_mode: str = "offline"
    contract_ai_bridge_secret: str = ""
    contract_ai_bridge_status_url: str = ""
    contract_ai_bridge_analysis_url: str = ""
    contract_ai_bridge_progress_url: str = ""
    contract_ai_bridge_result_url: str = ""
    contract_ai_bridge_sso_url: str = ""
    contract_ai_bridge_demo_link_url: str = ""

    # Разбор юридических обращений моделью.
    # Отдельные переменные, а не OPENAI_*: те исторически указывают на другого
    # провайдера (OPENAI_BASE_URL ведёт на api.deepseek.com), и переиспользовать
    # их значило бы сломать генерацию новостей.
    intake_analysis_enabled: bool = True
    intake_analysis_api_key: str = ""
    intake_analysis_base_url: str = "https://api.openai.com/v1"
    intake_analysis_model: str = "gpt-5.6-sol"
    # Прямой доступ к вендору с production-хоста закрыт по региону.
    intake_analysis_proxy_url: str = ""
    intake_analysis_timeout_seconds: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
