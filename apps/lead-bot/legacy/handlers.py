#!/usr/bin/env python3
"""
Обработчики Telegram бота
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import Config
from database import Database
from ai_brain import AIBrain
from lead_qualifier import LeadQualifier
from admin_interface import AdminInterface

logger = logging.getLogger(__name__)

class Handlers:
    """Класс для обработки команд и сообщений"""

    def __init__(self, database: Database, config: Config):
        self.database = database
        self.config = config
        self.ai_brain = AIBrain(config)
        self.lead_qualifier = LeadQualifier(database, config)
        self.admin_interface = AdminInterface(database, config)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id

            # Сохраняем пользователя в базу данных
            self.database.save_user(user.id, user.username, user.first_name, user.last_name)

            # Создаем новую сессию диалога
            self.database.create_conversation(user.id, chat_id)

            welcome_message = (
                f"👋 Привет, {user.first_name}!\n\n"
                "Я AI-ассистент по юридическим вопросам. "
                "Я могу помочь вам разобраться с:\n\n"
                "• Консультациями по AI и правовым аспектам\n"
                "• Анализом юридических документов\n"
                "• Рекомендациями по compliance\n\n"
                "Расскажите, чем я могу вам помочь?"
            )

            await update.message.reply_text(welcome_message)
            logger.info(f"Пользователь {user.id} начал диалог")

        except Exception as e:
            logger.error(f"Ошибка в start_command: {e}")
            await update.message.reply_text("Извините, произошла ошибка. Попробуйте позже.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        try:
            help_text = (
                "🤖 Доступные команды:\n\n"
                "/start - Начать работу с ботом\n"
                "/help - Показать эту справку\n"
                "/reset - Начать диалог заново\n\n"
                "Просто напишите мне свой вопрос, и я постараюсь помочь! 💼"
            )

            await update.message.reply_text(help_text)

        except Exception as e:
            logger.error(f"Ошибка в help_command: {e}")

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /reset"""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id

            # Создаем новую сессию диалога
            self.database.create_conversation(user_id, chat_id)

            await update.message.reply_text(
                "🔄 Диалог сброшен. Начнем заново!\n\n"
                "Расскажите, чем я могу вам помочь?"
            )

            logger.info(f"Пользователь {user_id} сбросил диалог")

        except Exception as e:
            logger.error(f"Ошибка в reset_command: {e}")
            await update.message.reply_text("Извините, произошла ошибка.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        try:
            user = update.effective_user
            message = update.message
            chat_id = update.effective_chat.id

            # Проверяем, что это не сообщение от бота (дополнительная проверка)
            if user.id == context.bot.id:
                logger.info(f"Пропускаем сообщение от бота в handle_message: {message.text[:50]}...")
                return

            # Сохраняем пользователя
            self.database.save_user(user.id, user.username, user.first_name, user.last_name)

            # Сохраняем сообщение пользователя
            self.database.save_message(user.id, chat_id, message.text, 'user')

            # Получаем историю диалога для контекста
            conversation_history = self.database.get_conversation_history(user.id, chat_id, limit=10)

            # Генерируем ответ через AI
            ai_response = await self.ai_brain.generate_response(message.text, conversation_history)

            # Сохраняем ответ AI
            self.database.save_message(user.id, chat_id, ai_response, 'assistant')

            # Отправляем ответ пользователю
            await message.reply_text(ai_response)

            # Квалифицируем лида в фоне
            await self.lead_qualifier.qualify_lead_async(user.id, chat_id, message.text, ai_response)

            logger.info(f"Обработано сообщение от пользователя {user.id}")

        except Exception as e:
            logger.error(f"Ошибка в handle_message: {e}")
            await update.message.reply_text(
                "Извините, произошла техническая ошибка. "
                "Попробуйте переформулировать вопрос."
            )

    async def handle_business_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик бизнес-сообщений (Telegram Business Messages)"""
        try:
            user = update.business_message.from_user
            message = update.business_message
            chat_id = update.business_message.chat.id
            business_connection_id = update.business_connection.id if update.business_connection else None

            logger.info(f"Обработка business-сообщения от пользователя {user.id} в чате {chat_id}")

            # Сохраняем пользователя
            self.database.save_user(user.id, user.username, user.first_name, user.last_name)

            # Сохраняем сообщение пользователя
            self.database.save_message(user.id, chat_id, message.text, 'user')

            # Получаем историю диалога для контекста
            conversation_history = self.database.get_conversation_history(user.id, chat_id, limit=10)

            # Генерируем ответ через AI
            ai_response = await self.ai_brain.generate_response(message.text, conversation_history)

            # Сохраняем ответ AI
            self.database.save_message(user.id, chat_id, ai_response, 'assistant')

            # Отправляем ответ через бизнес-соединение
            await context.bot.send_message(
                chat_id=chat_id,
                text=ai_response,
                business_connection_id=business_connection_id
            )

            # Квалифицируем лида в фоне
            await self.lead_qualifier.qualify_lead_async(user.id, chat_id, message.text, ai_response)

            logger.info(f"Обработано business-сообщение от пользователя {user.id}")

        except Exception as e:
            logger.error(f"Ошибка в handle_business_message: {e}")
            # В бизнес-чатах нужно отправлять ответ через business_connection_id
            try:
                business_connection_id = update.business_connection.id if update.business_connection else None
                await context.bot.send_message(
                    chat_id=update.business_message.chat.id,
                    text="Извините, произошла техническая ошибка. Попробуйте переформулировать вопрос.",
                    business_connection_id=business_connection_id
                )
            except Exception as send_error:
                logger.error(f"Ошибка отправки сообщения об ошибке: {send_error}")

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /stats"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        await self.admin_interface.send_stats(update, context)

    async def admin_leads(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /leads"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        # Получаем аргументы команды
        args = context.args if context.args else []

        if args and args[0] in ['hot', 'warm', 'cold']:
            lead_type = args[0]
        else:
            lead_type = None

        await self.admin_interface.send_leads(update, context, lead_type)

    async def admin_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /export"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        await self.admin_interface.export_leads(update, context)

    async def admin_view_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админская команда /view_conversation"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        if not context.args:
            await update.message.reply_text("Использование: /view_conversation <telegram_id>")
            return

        try:
            target_user_id = int(context.args[0])
            await self.admin_interface.view_conversation(update, context, target_user_id)
        except ValueError:
            await update.message.reply_text("Неверный формат ID пользователя")

    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        return str(user_id) == str(self.config.ADMIN_TELEGRAM_ID)
    def _is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат"""
        return self.database.is_chat_enabled(chat_id)

    async def enable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /enable_chat <chat_id>"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        if not context.args:
            await update.message.reply_text("Использование: /enable_chat <chat_id>")
            return

        try:
            chat_id = int(context.args[0])
            self.database.set_chat_enabled(chat_id, True)
            await update.message.reply_text(f"✅ Чат {chat_id} включен")
            logger.info(f"Admin {update.effective_user.id} enabled chat {chat_id}")
        except ValueError:
            await update.message.reply_text("Неверный формат ID чата")

    async def disable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /disable_chat <chat_id>"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        if not context.args:
            await update.message.reply_text("Использование: /disable_chat <chat_id>")
            return

        try:
            chat_id = int(context.args[0])
            self.database.set_chat_enabled(chat_id, False)
            await update.message.reply_text(f"🚫 Чат {chat_id} отключен")
            logger.info(f"Admin {update.effective_user.id} disabled chat {chat_id}")
        except ValueError:
            await update.message.reply_text("Неверный формат ID чата")

    async def list_disabled_chats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /disabled_chats"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        disabled_chats = self.database.get_disabled_chats()
        if disabled_chats:
            chat_list = "\n".join([f"• {chat_id}" for chat_id in disabled_chats])
            await update.message.reply_text(f"🚫 Отключенные чаты:\n{chat_list}")
        else:
            await update.message.reply_text("✅ Все чаты включены")

    def _is_chat_enabled(self, chat_id: int) -> bool:
        """Проверка, включен ли чат"""
        return self.database.is_chat_enabled(chat_id)

    async def enable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /enable_chat <chat_id>"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        if not context.args:
            await update.message.reply_text("Использование: /enable_chat <chat_id>")
            return

        try:
            chat_id = int(context.args[0])
            self.database.set_chat_enabled(chat_id, True)
            await update.message.reply_text(f"✅ Чат {chat_id} включен")
            logger.info(f"Admin {update.effective_user.id} enabled chat {chat_id}")
        except ValueError:
            await update.message.reply_text("Неверный формат ID чата")

    async def disable_chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /disable_chat <chat_id>"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        if not context.args:
            await update.message.reply_text("Использование: /disable_chat <chat_id>")
            return

        try:
            chat_id = int(context.args[0])
            self.database.set_chat_enabled(chat_id, False)
            await update.message.reply_text(f"🚫 Чат {chat_id} отключен")
            logger.info(f"Admin {update.effective_user.id} disabled chat {chat_id}")
        except ValueError:
            await update.message.reply_text("Неверный формат ID чата")

    async def list_disabled_chats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /disabled_chats"""
        if not self._is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Доступ запрещен")
            return

        disabled_chats = self.database.get_disabled_chats()
        if disabled_chats:
            chat_list = "\n".join([f"• {chat_id}" for chat_id in disabled_chats])
            await update.message.reply_text(f"🚫 Отключенные чаты:\n{chat_list}")
        else:
            await update.message.reply_text("✅ Все чаты включены")

    async def handle_business_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик бизнес-сообщений (Telegram Business Messages)"""
        try:
            user = update.business_message.from_user
            message = update.business_message
            chat_id = update.business_message.chat.id
            business_connection_id = update.business_connection.id if update.business_connection else None

            logger.info(f"Обработка business-сообщения от пользователя {user.id} в чате {chat_id}")

            # Проверяем, включен ли чат
            if not self._is_chat_enabled(chat_id):
                logger.info(f"Пропускаем business-сообщение из отключенного чата: {chat_id}")
                return

            # Сохраняем пользователя
            self.database.save_user(user.id, user.username, user.first_name, user.last_name)

            # Сохраняем сообщение пользователя
            self.database.save_message(user.id, chat_id, message.text, 'user')

            # Получаем историю диалога для контекста
            conversation_history = self.database.get_conversation_history(user.id, chat_id, limit=10)

            # Генерируем ответ через AI
            ai_response = await self.ai_brain.generate_response(message.text, conversation_history)

            # Сохраняем ответ AI
            self.database.save_message(user.id, chat_id, ai_response, 'assistant')

            # Отправляем ответ через бизнес-соединение
            await context.bot.send_message(
                chat_id=chat_id,
                text=ai_response,
                business_connection_id=business_connection_id
            )

            # Квалифицируем лида в фоне
            await self.lead_qualifier.qualify_lead_async(user.id, chat_id, message.text, ai_response)

            logger.info(f"Обработано business-сообщение от пользователя {user.id}")

        except Exception as e:
            logger.error(f"Ошибка в handle_business_message: {e}")
            # В бизнес-чатах нужно отправлять ответ через business_connection_id
            try:
                business_connection_id = update.business_connection.id if update.business_connection else None
                await context.bot.send_message(
                    chat_id=update.business_message.chat.id,
                    text="Извините, произошла техническая ошибка. Попробуйте переформулировать вопрос.",
                    business_connection_id=business_connection_id
                )
            except Exception as send_error:
                logger.error(f"Ошибка отправки сообщения об ошибке: {send_error}")
