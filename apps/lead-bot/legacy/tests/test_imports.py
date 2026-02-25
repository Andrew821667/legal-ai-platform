"""
Тесты импортов модулей - проверка что все модули импортируются без ошибок
"""
import pytest


def test_import_config():
    """Тест импорта config модуля"""
    try:
        from config import Config
        config = Config()
        assert config.TELEGRAM_BOT_TOKEN is not None
        assert config.OPENAI_API_KEY is not None
        assert config.ADMIN_TELEGRAM_ID > 0
    except ImportError as e:
        pytest.fail(f"Failed to import config: {e}")


def test_import_database():
    """Тест импорта database модуля"""
    try:
        import database
        assert database.Database is not None
    except ImportError as e:
        pytest.fail(f"Failed to import database: {e}")


def test_import_ai_brain():
    """Тест импорта ai_brain модуля"""
    try:
        import ai_brain
        assert ai_brain.AIBrain is not None
    except ImportError as e:
        pytest.fail(f"Failed to import ai_brain: {e}")


def test_import_handlers():
    """Тест импорта handlers модуля"""
    try:
        import handlers
        assert handlers.start_command is not None
        assert handlers.handle_message is not None
    except ImportError as e:
        pytest.fail(f"Failed to import handlers: {e}")


def test_import_lead_qualifier():
    """Тест импорта lead_qualifier модуля"""
    try:
        import lead_qualifier
        assert lead_qualifier.LeadQualifier is not None
    except ImportError as e:
        pytest.fail(f"Failed to import lead_qualifier: {e}")
