#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тест подключения к OpenAI API
"""
import os
from config.settings import settings

print("=" * 60)
print("ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К OPENAI")
print("=" * 60)
print()

# Проверяем настройки
print("1. Проверка конфигурации...")
print(f"   - LLM Provider: {settings.default_llm_provider}")
print(f"   - OpenAI API Key: {'*' * 20}{settings.openai_api_key[-10:] if settings.openai_api_key else 'НЕТ'}")
print()

if not settings.openai_api_key:
    print("❌ API ключ OpenAI не найден в .env файле!")
    exit(1)

# Тест подключения
print("2. Тестирование LLM Gateway...")
try:
    from src.services.llm_gateway import LLMGateway

    gateway = LLMGateway(provider="openai")
    print("   ✓ LLMGateway инициализирован")

    # Простой тест
    print()
    print("3. Отправка тестового запроса к OpenAI...")

    response = gateway.call(
        prompt="Скажи 'Привет, система готова к работе!' в одном предложении.",
        temperature=0.0,
        max_tokens=50
    )

    print(f"   ✓ Ответ получен: {response}")
    print()
    print("=" * 60)
    print("✅ OPENAI API РАБОТАЕТ!")
    print("=" * 60)

except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
