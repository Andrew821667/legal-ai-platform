#!/usr/bin/env python3
"""
Скрипт для первоначальной авторизации Telegram Client API.

Запустите ОДИН РАЗ для создания файла сессии telegram_bot.session.
После этого авторизация больше не потребуется.

Usage:
    python setup_telegram_session.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к app для импорта config
sys.path.insert(0, str(Path(__file__).parent))

try:
    from telethon import TelegramClient
    from telethon.errors import ApiIdInvalidError, PhoneNumberInvalidError
except ImportError:
    print("❌ Telethon не установлен. Установите:")
    print("   pip install telethon==1.34.0")
    sys.exit(1)


def load_env_file():
    """Загрузить переменные из .env файла."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return {}

    env_vars = {}
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


async def main():
    """Запустить процесс авторизации."""
    print("=" * 60)
    print("🔐 Telegram Client API - Первоначальная авторизация")
    print("=" * 60)
    print()

    # Загружаем credentials
    env = load_env_file()
    api_id = env.get('TELEGRAM_API_ID', '34617695')
    api_hash = env.get('TELEGRAM_API_HASH', 'e95e6e190f5efcff98001a490acea1c1')
    session_name = env.get('TELEGRAM_SESSION_NAME', 'telegram_bot')

    # Проверяем credentials
    if not api_id or not api_hash:
        print("❌ Ошибка: TELEGRAM_API_ID или TELEGRAM_API_HASH не найдены в .env")
        print()
        print("Добавьте в .env файл:")
        print("TELEGRAM_API_ID=34617695")
        print("TELEGRAM_API_HASH=e95e6e190f5efcff98001a490acea1c1")
        return

    print(f"📋 API ID: {api_id}")
    print(f"📋 Session name: {session_name}")
    print()

    # Проверяем существующую сессию
    session_file = Path(f"{session_name}.session")
    if session_file.exists():
        print(f"⚠️  Файл сессии уже существует: {session_file}")
        response = input("   Пересоздать сессию? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Отменено.")
            return
        print()

    # Выбор метода авторизации
    print("Выберите метод авторизации:")
    print("  1. Через Bot Token (рекомендуется)")
    print("  2. Через номер телефона")
    print()
    choice = input("Выбор (1 или 2): ").strip()

    try:
        client = TelegramClient(session_name, int(api_id), api_hash)

        if choice == '1':
            # Авторизация через bot token
            print()
            bot_token = env.get('TELEGRAM_BOT_TOKEN', '')
            if not bot_token:
                print("Введите Bot Token (из @BotFather):")
                bot_token = input("Bot Token: ").strip()

            print()
            print("🔄 Подключаемся...")
            await client.start(bot_token=bot_token)

        elif choice == '2':
            # Авторизация через номер телефона
            print()
            print("⚠️  Вам потребуется:")
            print("   1. Номер телефона (формат: +79991234567)")
            print("   2. Код подтверждения из Telegram")
            print()

            await client.start()

        else:
            print("❌ Неверный выбор.")
            return

        # Проверяем авторизацию
        me = await client.get_me()

        print()
        print("=" * 60)
        print("✅ Авторизация успешна!")
        print("=" * 60)
        print()

        if me:
            if hasattr(me, 'username') and me.username:
                print(f"👤 Авторизован как: @{me.username}")
            elif hasattr(me, 'first_name'):
                print(f"👤 Авторизован как: {me.first_name}")
            else:
                print(f"👤 Авторизован как бот")

        print()
        print(f"📁 Файл сессии создан: {session_file.absolute()}")
        print()
        print("🎯 Следующие шаги:")
        print("   1. НЕ коммитьте файл *.session в git (уже в .gitignore)")
        print("   2. Настройте TELEGRAM_CHANNELS в .env")
        print("   3. Перезапустите Docker контейнеры:")
        print("      docker compose restart celery_worker bot")
        print("   4. Запустите сбор через /fetch в боте")
        print()

        await client.disconnect()

    except ApiIdInvalidError:
        print("❌ Ошибка: Неверный API ID или API Hash")
        print("   Проверьте credentials в .env файле")

    except PhoneNumberInvalidError:
        print("❌ Ошибка: Неверный формат номера телефона")
        print("   Используйте формат: +79991234567")

    except KeyboardInterrupt:
        print()
        print("❌ Отменено пользователем")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print()
        print("Возможные причины:")
        print("  - Неверный Bot Token")
        print("  - Неверный код подтверждения")
        print("  - Проблемы с сетью")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Отменено")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
