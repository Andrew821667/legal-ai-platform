"""
Application configuration module.
Loads settings from environment variables using pydantic-settings.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = Field(default="AI-News Aggregator for LegalTech")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # PostgreSQL
    postgres_db: str = Field(default="legal_ai_news")
    postgres_user: str = Field(default="legal_user")
    postgres_password: str = Field(default="changeme")
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    database_url: Optional[str] = Field(default=None)

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        """Construct database URL if not provided."""
        if v:
            return v
        data = info.data
        return (
            f"postgresql+asyncpg://{data.get('postgres_user')}:"
            f"{data.get('postgres_password')}@{data.get('postgres_host')}:"
            f"{data.get('postgres_port')}/{data.get('postgres_db')}"
        )

    # Redis
    redis_host: str = Field(default="redis")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="changeme")
    redis_db: int = Field(default=0)
    redis_url: Optional[str] = Field(default=None)

    @field_validator("redis_url", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info) -> str:
        """Construct Redis URL if not provided."""
        if v:
            return v
        data = info.data
        password = data.get('redis_password')
        return (
            f"redis://:{password}@{data.get('redis_host')}:"
            f"{data.get('redis_port')}/{data.get('redis_db')}"
        )

    # Celery
    celery_broker_url: Optional[str] = Field(default=None)
    celery_result_backend: Optional[str] = Field(default=None)
    celery_task_serializer: str = Field(default="json")
    celery_result_serializer: str = Field(default="json")
    celery_accept_content: List[str] = Field(default=["json"])
    celery_timezone: str = Field(default="Europe/Moscow")
    celery_enable_utc: bool = Field(default=True)

    @field_validator("celery_broker_url", mode="before")
    @classmethod
    def set_celery_broker(cls, v: Optional[str], info) -> str:
        """Set Celery broker URL from Redis URL."""
        if v:
            return v
        data = info.data
        redis_url = data.get('redis_url')
        if redis_url:
            return redis_url.replace('/0', '/0')
        return "redis://localhost:6379/0"

    @field_validator("celery_result_backend", mode="before")
    @classmethod
    def set_celery_result(cls, v: Optional[str], info) -> str:
        """Set Celery result backend from Redis URL."""
        if v:
            return v
        data = info.data
        redis_url = data.get('redis_url')
        if redis_url:
            return redis_url.replace('/0', '/1')
        return "redis://localhost:6379/1"

    # OpenAI
    openai_api_key: str = Field(default="")
    openai_model_analysis: str = Field(default="gpt-4o-mini")
    openai_model_critical: str = Field(default="gpt-4o")
    openai_tts_model: str = Field(default="tts-1")
    openai_tts_voice: str = Field(default="nova")
    openai_max_tokens: int = Field(default=3500)
    openai_temperature: float = Field(default=0.7)

    # Perplexity AI
    perplexity_api_key: str = Field(default="")
    perplexity_model: str = Field(default="pplx-70b-online")
    perplexity_max_tokens: int = Field(default=3500)
    perplexity_temperature: float = Field(default=0.7)
    perplexity_search_enabled: bool = Field(default=False)  # ОТКЛЮЧЕНО: нет средств на балансе Perplexity

    # DeepSeek AI
    deepseek_api_key: str = Field(default="")
    deepseek_model: str = Field(default="deepseek-chat")  # deepseek-chat or deepseek-reasoner
    deepseek_max_tokens: int = Field(default=3500)
    deepseek_temperature: float = Field(default=0.7)
    deepseek_base_url: str = Field(default="https://api.deepseek.com")

    # LLM Provider Selection
    default_llm_provider: str = Field(default="deepseek")  # openai, perplexity, or deepseek

    # Qdrant Vector Database
    qdrant_host: str = Field(default="qdrant")
    qdrant_port: int = Field(default=6333)
    qdrant_enabled: bool = Field(default=True)  # Включить/выключить векторный поиск

    # Telegram Bot (для модерации и публикации)
    telegram_bot_token: str = Field(default="")
    telegram_admin_id: int = Field(default=0)
    telegram_channel_id: str = Field(default="")
    telegram_channel_id_numeric: int = Field(default=0)

    # Reader Bot (для читателей канала)
    reader_bot_token: str = Field(default="")

    # Telegram Client API (для сбора новостей из каналов)
    telegram_api_id: int = Field(default=0)
    telegram_api_hash: str = Field(default="")
    telegram_session_name: str = Field(default="telegram_bot")
    telegram_channels: str = Field(default="")  # Comma-separated list of channels
    telegram_fetch_limit: int = Field(default=50)  # Messages per channel
    telegram_fetch_enabled: bool = Field(default=True)

    @property
    def telegram_channels_list(self) -> List[str]:
        """Parse Telegram channels from comma-separated string."""
        if not self.telegram_channels:
            return []
        return [ch.strip() for ch in self.telegram_channels.split(",") if ch.strip()]

    # News Fetcher
    fetcher_enabled: bool = Field(default=True)
    fetcher_interval_hours: int = Field(default=24)
    fetcher_max_articles_per_source: int = Field(default=10)  # Сокращено для быстрого тестирования
    fetcher_request_timeout: int = Field(default=30)
    fetcher_max_retries: int = Field(default=3)
    fetcher_retry_delay: int = Field(default=2)

    # Google News RSS
    google_news_rss_url: str = Field(default="https://news.google.com/rss/search")
    # Расширенные запросы: AI в бизнесе + нативные юридические связи для привлечения клиентов
    google_news_query_ru: str = Field(default="искусственный интеллект AND (право OR суд OR юрист OR бизнес OR комплаенс OR договор OR автоматизация OR корпоративный OR риски OR управление)")
    google_news_query_en: str = Field(default="artificial intelligence AND (law OR legal OR court OR lawyer OR business OR compliance OR contract OR automation OR corporate OR risk OR governance OR legaltech)")
    google_news_lang_ru: str = Field(default="ru")
    google_news_lang_en: str = Field(default="en")
    google_news_region: str = Field(default="RU")

    # RSS Sources
    rss_sources: str = Field(default="")

    @property
    def rss_sources_list(self) -> List[str]:
        """Parse RSS sources from comma-separated string."""
        if not self.rss_sources:
            return []
        return [s.strip() for s in self.rss_sources.split(",") if s.strip()]

    # Cleaner/Filter
    cleaner_min_content_length: int = Field(default=300)
    cleaner_similarity_threshold: float = Field(default=0.85)
    cleaner_enabled_languages: str = Field(default="ru,en")

    @property
    def cleaner_languages_list(self) -> List[str]:
        """Parse enabled languages from comma-separated string."""
        return [lang.strip() for lang in self.cleaner_enabled_languages.split(",")]

    # ML Classification
    ml_classifier_model: str = Field(default="facebook/bart-large-mnli")
    ml_confidence_threshold: float = Field(default=0.6)
    ml_labels: str = Field(default="legal AI news,court technology,law automation,irrelevant news")

    @property
    def ml_labels_list(self) -> List[str]:
        """Parse ML labels from comma-separated string."""
        return [label.strip() for label in self.ml_labels.split(",")]

    # AI Core
    ai_ranking_enabled: bool = Field(default=True)
    ai_top_articles_count: int = Field(default=3)
    ai_post_min_length: int = Field(default=150)
    ai_post_max_length: int = Field(default=250)
    ai_legal_context_enabled: bool = Field(default=True)
    ai_legal_context_confidence_min: float = Field(default=0.7)

    # Media Factory
    media_templates_dir: str = Field(default="/app/templates")
    media_output_dir: str = Field(default="/app/media")
    media_template_image_path: str = Field(default="/app/templates/base_template.jpg")
    media_image_width: int = Field(default=1200)
    media_image_height: int = Field(default=630)
    media_font_size_title: int = Field(default=48)
    media_font_size_date: int = Field(default=24)
    media_watermark_enabled: bool = Field(default=True)

    # DALL-E
    dalle_enabled: bool = Field(default=False)
    dalle_model: str = Field(default="dall-e-3")
    dalle_size: str = Field(default="1024x1024")
    dalle_quality: str = Field(default="standard")

    # Publisher
    publisher_auto_publish: bool = Field(default=False)
    publisher_require_approval: bool = Field(default=True)
    publisher_max_posts_per_day: int = Field(default=3)

    # Analytics
    analytics_enabled: bool = Field(default=True)
    analytics_collection_interval_hours: int = Field(default=6)
    analytics_retention_days: int = Field(default=90)

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_second: int = Field(default=1)
    rate_limit_openai_rpm: int = Field(default=60)

    # Security
    secret_key: str = Field(default="change-in-production")
    allowed_hosts: str = Field(default="localhost,127.0.0.1")
    cors_origins: str = Field(default="http://localhost:8000")

    # Monitoring
    healthcheck_enabled: bool = Field(default=True)
    healthcheck_interval: int = Field(default=30)

    # Timezone
    tz: str = Field(default="Europe/Moscow")


# Global settings instance
settings = Settings()
