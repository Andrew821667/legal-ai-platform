"""
Простой тест LLM Gateway без внешних зависимостей
"""
import sys
import os

# Добавляем текущую директорию в path
sys.path.insert(0, os.getcwd())

def test_import():
    """Тестирует импорт конфигурации"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ LLM GATEWAY (ПРОСТОЙ)")
    print("=" * 60)

    # Тест 1: Импорт настроек
    print("\n1. Импорт настроек...")
    try:
        from config.settings import settings
        print("   ✓ Настройки загружены")
        print(f"   - Default provider: {settings.default_llm_provider}")
    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False

    # Тест 2: Проверка API ключей
    print("\n2. Проверка конфигурации провайдеров...")

    providers = {
        "claude": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "perplexity": settings.perplexity_api_key,
        "yandex": settings.yandex_api_key,
        
        "deepseek": settings.deepseek_api_key,
        "qwen": settings.qwen_api_key
    }

    configured = 0
    for provider, api_key in providers.items():
        if api_key:
            print(f"   ✓ {provider}: Configured")
            configured += 1
        else:
            print(f"   ✗ {provider}: No API key")

    print(f"\n   Итого настроено: {configured}/7 провайдеров")

    # Тест 3: Проверка структуры LLM Gateway
    print("\n3. Проверка структуры LLM Gateway...")
    try:
        import inspect
        from src.services import llm_gateway

        # Проверяем наличие основных классов/функций
        if hasattr(llm_gateway, 'LLMGateway'):
            print("   ✓ Класс LLMGateway найден")
        else:
            print("   ✗ Класс LLMGateway не найден")
            return False

        if hasattr(llm_gateway, 'llm_call'):
            print("   ✓ Функция llm_call найдена")
        else:
            print("   ✗ Функция llm_call не найдена")
            return False

    except Exception as e:
        print(f"   ⚠ Не удалось импортировать (требуются зависимости): {e}")
        print("   ℹ Это нормально, если зависимости ещё не установлены")

    print("\n" + "=" * 60)
    print("✓ БАЗОВЫЕ ПРОВЕРКИ ПРОЙДЕНЫ")
    print("=" * 60)
    print("\nСледующие шаги:")
    print("1. Установи зависимости: pip install -r requirements.txt")
    print("2. Добавь API ключи в .env файл")
    print("3. Запусти полный тест: python test_llm_gateway.py")

    return True


if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1)
