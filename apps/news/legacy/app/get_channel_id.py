#!/usr/bin/env python3
"""
Скрипт для получения numeric ID Telegram канала.
Использует Telethon API для конвертации username в numeric ID.
"""

import sys
import os

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, '/app')

import asyncio
from telethon import TelegramClient
from app.config import settings


async def get_channel_numeric_id():
    """Получить numeric ID канала по его username."""

    # Подключаемся к Telegram через Telethon
    client = TelegramClient(
        settings.telegram_session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash
    )

    try:
        await client.start()

        channel_username = settings.telegram_channel_id
        print(f"\n🔍 Получаю информацию о канале: {channel_username}")

        # Получаем entity канала
        entity = await client.get_entity(channel_username)

        print(f"\n✅ Канал найден!")
        print(f"📛 Название: {entity.title}")
        print(f"👤 Username: @{entity.username}")
        print(f"🆔 Numeric ID: {entity.id}")
        print(f"\n💡 Добавьте эту строку в ваш .env файл:")
        print(f"TELEGRAM_CHANNEL_ID_NUMERIC=-100{entity.id}")

        return entity.id

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return None

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(get_channel_numeric_id())
