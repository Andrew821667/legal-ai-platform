"""
Reader Bot Entry Point.

Main bot for readers - personalization, search, digests.
"""

import asyncio
import sys
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.bot.reader_handlers import router
from app.models.database import AsyncSessionLocal, init_db

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Database middleware
async def db_middleware(handler, event, data):
    """Provide database session for handlers."""
    async with AsyncSessionLocal() as session:
        data['db'] = session
        try:
            return await handler(event, data)
        finally:
            await session.close()


async def main():
    """Main entry point for reader bot."""
    logger.info(f"Reader bot starting with token: {settings.reader_bot_token[:10]}...")

    # Initialize database
    await init_db()
    logger.info("Reader bot database initialized")

    # Create bot and dispatcher
    bot = Bot(token=settings.reader_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Set bot commands menu
    commands = [
        BotCommand(command="start", description="🚀 Начать работу с ботом"),
        BotCommand(command="lead_magnet", description="🎯 Лид-магнит: дайджест за контакты"),
        BotCommand(command="ask_question", description="🤖 Задать вопрос по LegalTech"),
        BotCommand(command="today", description="📰 Персональные новости за сегодня"),
        BotCommand(command="search", description="🔍 Поиск по архиву"),
        BotCommand(command="saved", description="🔖 Сохранённые статьи"),
        BotCommand(command="settings", description="⚙️ Настройки профиля"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot commands menu set")

    # Register handlers
    dp.include_router(router)

    # Add database middleware
    dp.update.middleware(db_middleware)

    logger.info("Reader bot starting polling...")

    # Start polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Reader bot stopped by user")
    except Exception as e:
        logger.error(f"Reader bot error: {str(e)}")
        raise
    finally:
        await bot.session.close()
        logger.info("Reader bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Reader bot interrupted")
        sys.exit(0)
