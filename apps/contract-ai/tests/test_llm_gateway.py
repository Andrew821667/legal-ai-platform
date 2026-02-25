"""
Тестирование LLM Gateway с поддержкой всех провайдеров
"""
import sys
import os

# Добавляем текущую директорию в path
sys.path.insert(0, os.getcwd())

from src.services.llm_gateway import LLMGateway, llm_call
from config.settings import settings

def test_llm_gateway():
    """Тестирует LLM Gateway"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ LLM GATEWAY")
    print("=" * 60)

    # Тест 1: Проверка доступных провайдеров
    print("\n1. Проверка конфигурации провайдеров...")
    print(f"   - Default provider: {settings.default_llm_provider}")

    providers_config = {
        "claude": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "perplexity": settings.perplexity_api_key,
        "yandex": settings.yandex_api_key,
        
        "deepseek": settings.deepseek_api_key,
        "qwen": settings.qwen_api_key
    }

    available_providers = []
    for provider, api_key in providers_config.items():
        status = "✓ Configured" if api_key else "✗ No API key"
        print(f"   - {provider}: {status}")
        if api_key:
            available_providers.append(provider)

    # Тест 2: Инициализация Gateway
    print("\n2. Инициализация LLM Gateway...")
    try:
        gateway = LLMGateway()  # Использует default provider
        print(f"   ✓ Gateway создан с провайдером: {gateway.provider}")

        # Информация о провайдере
        info = gateway.get_provider_info()
        print(f"   - Provider: {info['provider']}")
        print(f"   - Available: {info['available']}")
        print(f"   - Temperature: {info['temperature']}")
        print(f"   - Max tokens: {info['max_tokens']}")

    except Exception as e:
        print(f"   ✗ Ошибка инициализации: {e}")
        return False

    # Тест 3: Тестовый вызов (если есть настроенный провайдер)
    if available_providers:
        print(f"\n3. Тестовый вызов к провайдеру ({gateway.provider})...")

        test_prompt = "Привет! Ответь одним словом: какой сейчас год?"

        try:
            # Проверяем, есть ли API ключ для default provider
            if providers_config[gateway.provider]:
                print("   ВНИМАНИЕ: Будет выполнен реальный API вызов!")
                print(f"   Промпт: '{test_prompt}'")

                # Раскомментируй следующую строку для реального вызова:
                # response = gateway.call(prompt=test_prompt)
                # print(f"   ✓ Ответ получен: {response}")

                print("   ⚠ Тест пропущен (раскомментируй код для вызова API)")
            else:
                print(f"   ✗ Нет API ключа для {gateway.provider}")

        except Exception as e:
            print(f"   ✗ Ошибка вызова: {e}")
            return False

    # Тест 4: Подсчёт токенов
    print("\n4. Тестирование подсчёта токенов...")
    test_text = "Это тестовая строка для подсчёта токенов. Она содержит несколько слов."
    token_count = gateway.count_tokens(test_text)
    print(f"   Текст: '{test_text}'")
    print(f"   Длина: {len(test_text)} символов")
    print(f"   Токены (примерно): {token_count}")

    # Тест 5: Быстрый вызов через utility функцию
    print("\n5. Тестирование llm_call utility...")
    print("   ✓ Функция llm_call импортирована")

    print("\n" + "=" * 60)
    print("✓ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)
    print("\nДля полного тестирования:")
    print("1. Добавь API ключи в .env файл")
    print("2. Раскомментируй строку с вызовом API в коде теста")
    print("3. Запусти тест снова")

    return True


if __name__ == "__main__":
    success = test_llm_gateway()
    sys.exit(0 if success else 1)
