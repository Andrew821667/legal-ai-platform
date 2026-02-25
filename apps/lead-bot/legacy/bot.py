#!/usr/bin/env python3
"""
Legal AI Telegram Bot - основной файл запуска
AI-powered Telegram бот для консультирования клиентов по юридическим AI-решениям
"""

import asyncio
import logging
import sys
from typing import Dict, Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import Config
from handlers import Handlers
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class LegalAIBot:
    """Основной класс бота"""

    def __init__(self):
        self.config = Config()
        self.database = Database()
        self.handlers = Handlers(self.database, self.config)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await self.handlers.start_command(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await self.handlers.help_command(update, context)

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /reset"""
        await self.handlers.reset_command(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений (включая бизнес-сообщения)"""
        # Детальное логирование для отладки
        logger.info(f"Получен update: type={type(update).__name__}")

        # Определяем, является ли это бизнес-сообщением
        is_business = hasattr(update, 'business_message') and update.business_message is not None
        message = update.business_message if is_business else update.message

        if message:
            logger.info(f"Message from user {message.from_user.id} (bot id: {context.bot.id}): {message.text[:100]}...")
            logger.info(f"Chat type: {message.chat.type}, Chat id: {message.chat.id}")
            logger.info(f"Is business message: {is_business}")
            if is_business and hasattr(update, 'business_connection'):
                logger.info(f"Business connection ID: {update.business_connection.id if update.business_connection else 'None'}")

            # Проверяем, включен ли чат
            if not self.handlers._is_chat_enabled(update.effective_chat.id):
                logger.info(f"Пропускаем сообщение из отключенного чата: {update.effective_chat.id}")
                return

            # Проверяем, включен ли чат
            if not self.handlers._is_chat_enabled(update.effective_chat.id):
                logger.info(f"Пропускаем сообщение из отключенного чата: {update.effective_chat.id}")
                return

            # Проверяем, что сообщение не от самого бота
            if message.from_user.id == context.bot.id:
                logger.info(f"Пропускаем сообщение от самого бота: {message.text[:50]}...")
                return

            # В бизнес-чатах также пропускаем сообщения от бизнес-владельца (чтобы избежать зацикливания)
            if is_business and str(message.from_user.id) == str(self.config.ADMIN_TELEGRAM_ID):
                logger.info(f"Пропускаем business-сообщение от бизнес-владельца: {message.text[:50]}...")
                return

        # Вызываем соответствующий обработчик
        if is_business:
            await self.handlers.handle_business_message(update, context)
        else:
            await self.handlers.handle_message(update, context)

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /stats"""
        await self.handlers.admin_stats(update, context)

    async def admin_leads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /leads"""
        await self.handlers.admin_leads(update, context)

    async def admin_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /export"""
        await self.handlers.admin_export(update, context)

    async def admin_view_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /view_conversation"""
        await self.handlers.admin_view_conversation(update, context)

    def setup_handlers(self, application: Application):
        """Настройка обработчиков команд"""

        # Команды для всех пользователей
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("reset", self.reset_command))

        # Админские команды
        application.add_handler(CommandHandler("stats", self.admin_stats))
        application.add_handler(CommandHandler("leads", self.admin_leads))
        application.add_handler(CommandHandler("export", self.admin_export))
        application.add_handler(CommandHandler("view_conversation", self.admin_view_conversation))
        # Chat management commands
        application.add_handler(CommandHandler("enable_chat", self.enable_chat_command))
        application.add_handler(CommandHandler("disable_chat", self.disable_chat_command))
        application.add_handler(CommandHandler("disabled_chats", self.list_disabled_chats_command))

        # Обработчик текстовых сообщений (включая бизнес-сообщения)
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))

        logger.info("Обработчики настроены")

    async def run(self):
        """Запуск бота"""
        try:
            # Создаем приложение
            application = Application.builder().token(self.config.TELEGRAM_BOT_TOKEN).build()

            # Настраиваем обработчики
            self.setup_handlers(application)

            # Запускаем бота
            logger.info("Бот запущен и готов к работе")
            await application.run_polling(allowed_updates=Update.ALL_TYPES)

        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

def main():
    """Главная функция"""
    try:
        # Инициализируем и запускаем бота
        bot = LegalAIBot()
        asyncio.run(bot.run())

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
    async def enable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /enable_chat"""
        await self.handlers.enable_chat_command(update, context)

    async def disable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /disable_chat"""
        await self.handlers.disable_chat_command(update, context)

    async def list_disabled_chats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /disabled_chats"""
        await self.handlers.list_disabled_chats_command(update, context)

    async def enable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /enable_chat"""
        await self.handlers.enable_chat_command(update, context)

    async def disable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /disable_chat"""
        await self.handlers.disable_chat_command(update, context)

    async def list_disabled_chats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /disabled_chats"""
        await self.handlers.list_disabled_chats_command(update, context)

    async def list_disabled_chats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /disabled_chats"""
        await self.handlers.list_disabled_chats_command(update, context)

def main():
    """Главная функция"""
    try:
        # Инициализируем и запускаем бота
        bot = LegalAIBot()
        asyncio.run(bot.run())

    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
