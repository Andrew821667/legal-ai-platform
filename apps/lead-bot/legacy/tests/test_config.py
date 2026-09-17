"""
Тесты для config.py - проверка корректности конфигурации
"""
from config import Config, default_ai_model_for_base_url, get_config

# Создаем экземпляр конфигурации для тестов
config = get_config()


def test_required_variables():
    """Проверка что все обязательные переменные установлены"""
    assert config.TELEGRAM_BOT_TOKEN, "TELEGRAM_BOT_TOKEN не установлен"
    assert config.OPENAI_API_KEY, "OPENAI_API_KEY не установлен"
    assert config.ADMIN_TELEGRAM_ID > 0, "ADMIN_TELEGRAM_ID должен быть положительным числом"


def test_openai_settings():
    """Проверка настроек OpenAI"""
    assert config.OPENAI_MODEL, "OPENAI_MODEL не должен быть пустым"
    assert config.MAX_TOKENS > 0, "MAX_TOKENS должен быть положительным"


def test_max_tokens_default_is_enough_for_reasoning_model_with_rag(monkeypatch):
    """Регрессия на 17.09: 1000 (старый дефолт) не хватало deepseek-v4-pro с
    непустым RAG-контекстом — ответы обрывались (finish_reason=length) или
    уходили пустыми. 800 в .env.example давал ту же проблему ещё быстрее."""
    monkeypatch.delenv("MAX_TOKENS", raising=False)
    monkeypatch.delenv("MAX_COMPLETION_TOKENS", raising=False)
    fresh = Config()
    assert fresh.MAX_TOKENS >= 4000
    assert fresh.MAX_COMPLETION_TOKENS >= 4000
    assert config.MAX_COMPLETION_TOKENS > 0, "MAX_COMPLETION_TOKENS должен быть положительным"
    assert 0 <= config.TEMPERATURE <= 2, "TEMPERATURE должна быть между 0 и 2"


def test_deepseek_default_model_is_provider_compatible():
    assert default_ai_model_for_base_url("https://api.deepseek.com/v1") == "deepseek-v4-pro"


def test_paths():
    """Проверка путей к файлам"""
    assert config.DATABASE_PATH, "DATABASE_PATH не установлен"
    assert config.LOG_FILE, "LOG_FILE не установлен"


def test_bot_behavior():
    """Проверка настроек поведения бота"""
    assert config.MAX_HISTORY_MESSAGES > 0, "MAX_HISTORY_MESSAGES должен быть положительным"
    assert config.RESPONSE_DELAY >= 0, "RESPONSE_DELAY не может быть отрицательным"
    assert config.PENDING_LEADS_CHECK_INTERVAL_SECONDS >= 15, "Интервал pending leads должен быть >= 15 сек"
    assert config.PENDING_LEADS_IDLE_MINUTES >= 1, "Idle timeout pending leads должен быть >= 1 мин"
    assert config.PENDING_LEADS_JOB_MAX_BATCH >= 1, "Batch pending leads должен быть >= 1"
    assert config.PENDING_LEADS_NOTIFY_TIMEOUT_SECONDS >= 2.0, "Timeout notify pending leads должен быть >= 2 сек"


def test_telegram_proxy_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_PROXY_URL", "http://192.168.64.1:10811")

    assert Config().TELEGRAM_API_PROXY_URL == "http://192.168.64.1:10811"


def test_log_level():
    """Проверка уровня логирования"""
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    assert config.LOG_LEVEL in valid_log_levels, f"LOG_LEVEL должен быть одним из {valid_log_levels}"


def test_embedding_settings_point_to_openai_not_deepseek():
    """Эмбеддинги (RAG) — только у OpenAI; общий OPENAI_BASE_URL может
    указывать на DeepSeek (чат бота), но это не должно ломать эмбеддинги."""
    assert config.EMBEDDING_BASE_URL == "https://api.openai.com/v1"
    assert config.EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_base_url_is_independent_from_openai_base_url(monkeypatch):
    """Даже когда OPENAI_BASE_URL указывает на DeepSeek, EMBEDDING_BASE_URL
    остаётся отдельной, дефолтной на OpenAI переменной (регрессия на 404)."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    fresh = Config()
    assert fresh.OPENAI_BASE_URL == "https://api.deepseek.com/v1"
    assert fresh.EMBEDDING_BASE_URL == "https://api.openai.com/v1"


def test_embedding_settings_are_overridable(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "custom-embedding")
    fresh = Config()
    assert fresh.EMBEDDING_BASE_URL == "https://example.test/v1"
    assert fresh.EMBEDDING_MODEL == "custom-embedding"


def test_embedding_proxy_url_defaults_to_empty(monkeypatch):
    monkeypatch.delenv("LEGAL_AI_HTTPS_PROXY", raising=False)
    monkeypatch.delenv("LEGAL_AI_HTTP_PROXY", raising=False)
    assert Config().EMBEDDING_PROXY_URL == ""


def test_embedding_proxy_url_prefers_https_over_http(monkeypatch):
    monkeypatch.setenv("LEGAL_AI_HTTPS_PROXY", "http://host.docker.internal:11808")
    monkeypatch.setenv("LEGAL_AI_HTTP_PROXY", "http://host.docker.internal:14809")
    assert Config().EMBEDDING_PROXY_URL == "http://host.docker.internal:11808"


def test_embedding_proxy_url_falls_back_to_http(monkeypatch):
    monkeypatch.delenv("LEGAL_AI_HTTPS_PROXY", raising=False)
    monkeypatch.setenv("LEGAL_AI_HTTP_PROXY", "http://host.docker.internal:11808")
    assert Config().EMBEDDING_PROXY_URL == "http://host.docker.internal:11808"


def test_chat_api_key_falls_back_to_openai_key_when_unset(monkeypatch):
    """Дев/CI: один ключ на всё, как было до разделения — не должно ломаться."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shared-test-key")
    assert Config().CHAT_API_KEY == "sk-shared-test-key"


def test_chat_api_key_prefers_dedicated_deepseek_key(monkeypatch):
    """Регрессия на 17.09: ротация OPENAI_API_KEY (для эмбеддингов) не должна
    молча подменять ключ чата — у DeepSeek теперь свой слот."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-embeddings-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-chat-key")
    fresh = Config()
    assert fresh.CHAT_API_KEY == "sk-deepseek-chat-key"
    assert fresh.OPENAI_API_KEY == "sk-openai-embeddings-key"
