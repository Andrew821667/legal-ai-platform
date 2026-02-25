"""
Конфигурация приложения Contract AI System
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Database
    # По умолчанию SQLite, можно переключить на PostgreSQL в .env
    database_url: str = "sqlite:///./contract_ai.db"

    # LLM API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    deepseek_api_key: str = ""
    qwen_api_key: str = ""

    # Default LLM Provider
    default_llm_provider: Literal["claude", "openai", "perplexity", "yandex", "deepseek", "qwen"] = "openai"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"

    # File Storage
    upload_dir: str = "./data/uploads"
    normalized_dir: str = "./data/normalized"
    reports_dir: str = "./data/reports"
    templates_dir: str = "./data/templates"
    exports_dir: str = "./data/exports"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    debug: bool = True

    # Streamlit
    streamlit_server_port: int = 8501
    streamlit_server_address: str = "localhost"

    # Redis (optional)
    redis_url: str = "redis://localhost:6379/0"

    # LLM Settings
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4000
    llm_timeout: int = 120

    # Test Mode - экономия токенов
    llm_test_mode: bool = True  # Переключатель: True = тестовый режим, False = продакшн

    # Two-level analysis system
    llm_quick_model: str = "gpt-4o-mini"  # Быстрый анализ (Уровень 1)
    llm_deep_model: str = "gpt-5.1"       # Глубокий анализ (Уровень 2) - лучшая модель OpenAI

    # Batch analysis settings (оптимизировано для производительности)
    llm_batch_size: int = 15  # Сколько пунктов анализировать в одном запросе (оптимально для gpt-4o-mini)

    # Token limits for test mode
    llm_test_max_tokens: int = 800       # Для тестового режима
    llm_test_max_clauses: int = 20       # Макс. пунктов для анализа в тесте (увеличено для эффективности)

    # Model pricing (per 1M tokens) для расчёта стоимости
    llm_pricing: dict = {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-5": {"input": 5.00, "output": 15.00},
        "gpt-5.1": {"input": 6.00, "output": 18.00},
        "o1-preview": {"input": 15.00, "output": 60.00},
        "o1-mini": {"input": 3.00, "output": 12.00},
    }

    # RAG Settings
    rag_top_k: int = 5
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # Security
    secret_key: str = ""  # REQUIRED in production! Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"

    # Email / SMTP Settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Contract AI System"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Security validation: require SECRET_KEY in production
        if self.app_env == "production" and not self.secret_key:
            raise ValueError(
                "❌ SECRET_KEY must be set in production environment!\n"
                "Generate a secure key with:\n"
                "  python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n"
                "Then add to .env file:\n"
                "  SECRET_KEY=<generated-key>"
            )

        # Warn if using default/weak key in any environment
        if self.secret_key in ["", "your-secret-key-here", "changeme", "secret"]:
            import warnings
            warnings.warn(
                "⚠️  Using empty or default SECRET_KEY! This is INSECURE!\n"
                f"Current environment: {self.app_env}",
                UserWarning,
                stacklevel=2
            )

        # Создаём необходимые директории
        self._create_directories()

    def _create_directories(self):
        """Создаёт необходимые директории для хранения файлов"""
        directories = [
            self.upload_dir,
            self.normalized_dir,
            self.reports_dir,
            self.templates_dir,
            self.exports_dir,
            self.chroma_persist_directory
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()


# Экспорт для удобного импорта
__all__ = ["settings", "Settings"]
