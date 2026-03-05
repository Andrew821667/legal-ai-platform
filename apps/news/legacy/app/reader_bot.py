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
from app.models.database import AsyncSessionLocal, engine
from app.models import reader_models as _reader_models  # noqa: F401
from app.models import reader_publications as _reader_publications  # noqa: F401
from app.models.reader_models import UserProfile, LeadProfile, UserFeedback, UserInteraction, SavedArticle

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


async def init_reader_tables():
    """Create only reader-related tables, without legacy admin schema."""
    tables = [
        UserProfile.__table__,
        LeadProfile.__table__,
        UserFeedback.__table__,
        UserInteraction.__table__,
        SavedArticle.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: _reader_models.Base.metadata.create_all(sync_conn, tables=tables))


async def main():
    """Main entry point for reader bot."""
    token = (settings.reader_bot_token or "").strip()
    if not token or ":" not in token:
        raise RuntimeError(
            "READER_BOT_TOKEN не задан или некорректен. "
            "Добавьте его в apps/news/legacy/.env"
        )

    logger.info(f"Reader bot starting with token: {token[:10]}...")

    # Initialize reader-specific tables
    await init_reader_tables()
    logger.info("Reader bot tables initialized")

    # Create bot and dispatcher
    bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    try:
        # Set bot commands menu
        commands = [
            BotCommand(command="start", description="🚀 Начать работу с ботом"),
            BotCommand(command="lead_magnet", description="🎯 Лид-магнит: дайджест за контакты"),
            BotCommand(command="ask_question", description="🤖 Задать вопрос по LegalTech"),
            BotCommand(command="today", description="📰 Персональные новости за сегодня"),
            BotCommand(command="weekly", description="📆 Недельный дайджест"),
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
