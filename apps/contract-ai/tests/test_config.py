"""
Скрипт для тестирования базовой конфигурации
"""
import sys
from pathlib import Path

def test_configuration():
    """Тестирует базовую конфигурацию"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ БАЗОВОЙ КОНФИГУРАЦИИ")
    print("=" * 60)

    # Проверка структуры проекта
    print("\n1. Проверка структуры проекта...")
    required_dirs = [
        "config",
        "src/orchestrator",
        "src/agents",
        "src/services",
        "src/models",
        "src/utils",
        "data/uploads",
        "data/normalized",
        "data/reports",
        "data/templates",
        "data/exports",
        "database",
        "tests"
    ]

    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"   ✓ {dir_path}")
        else:
            print(f"   ✗ {dir_path} - ОТСУТСТВУЕТ!")
            return False

    # Проверка конфигурационных файлов
    print("\n2. Проверка конфигурационных файлов...")
    required_files = [
        "requirements.txt",
        ".env.example",
        ".gitignore",
        "config/settings.py"
    ]

    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✓ {file_path}")
        else:
            print(f"   ✗ {file_path} - ОТСУТСТВУЕТ!")
            return False

    # Попытка импорта settings
    print("\n3. Попытка импорта конфигурации...")
    try:
        from config.settings import settings
        print(f"   ✓ Конфигурация загружена")
        print(f"   - DEFAULT_LLM_PROVIDER: {settings.default_llm_provider}")
        print(f"   - LOG_LEVEL: {settings.log_level}")
        print(f"   - APP_ENV: {settings.app_env}")
    except Exception as e:
        print(f"   ✗ Ошибка импорта: {e}")
        return False

    # Проверка создания директорий
    print("\n4. Проверка автоматического создания директорий...")
    if Path(settings.upload_dir).exists():
        print(f"   ✓ {settings.upload_dir}")
    else:
        print(f"   ✗ {settings.upload_dir} не создалась!")
        return False

    print("\n" + "=" * 60)
    print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_configuration()
    sys.exit(0 if success else 1)
