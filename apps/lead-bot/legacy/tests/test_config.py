"""
Тесты для config.py - проверка корректности конфигурации
"""
import pytest
from config import Config

# Создаем экземпляр конфигурации для тестов
config = Config()


def test_required_variables():
    """Проверка что все обязательные переменные установлены"""
    assert config.TELEGRAM_BOT_TOKEN, "TELEGRAM_BOT_TOKEN не установлен"
    assert config.OPENAI_API_KEY, "OPENAI_API_KEY не установлен"
    assert config.ADMIN_TELEGRAM_ID > 0, "ADMIN_TELEGRAM_ID должен быть положительным числом"


def test_openai_settings():
    """Проверка настроек OpenAI"""
    assert config.OPENAI_MODEL in ['gpt-4o-mini', 'gpt-4', 'gpt-3.5-turbo'], "Неверная модель OpenAI"
    assert config.MAX_TOKENS > 0, "MAX_TOKENS должен быть положительным"
    assert config.MAX_COMPLETION_TOKENS > 0, "MAX_COMPLETION_TOKENS должен быть положительным"
    assert 0 <= config.TEMPERATURE <= 2, "TEMPERATURE должна быть между 0 и 2"


def test_paths():
    """Проверка путей к файлам"""
    assert config.DATABASE_PATH, "DATABASE_PATH не установлен"
    assert config.LOG_FILE, "LOG_FILE не установлен"


def test_bot_behavior():
    """Проверка настроек поведения бота"""
    assert config.MAX_HISTORY_MESSAGES > 0, "MAX_HISTORY_MESSAGES должен быть положительным"
    assert config.RESPONSE_DELAY >= 0, "RESPONSE_DELAY не может быть отрицательным"


def test_log_level():
    """Проверка уровня логирования"""
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    assert config.LOG_LEVEL in valid_log_levels, f"LOG_LEVEL должен быть одним из {valid_log_levels}"
