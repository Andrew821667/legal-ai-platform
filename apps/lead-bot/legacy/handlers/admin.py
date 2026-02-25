"""
Handlers: admin
"""
import logging
import time
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database
import ai_brain
import lead_qualifier
import admin_interface
from config import Config
config = Config()
import utils
import email_sender
import security
import prompts
from handlers.constants import *

logger = logging.getLogger(__name__)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - статистика (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        stats_message = admin_interface.admin_interface.format_statistics(30)
        await update.message.reply_text(stats_message)

    except Exception as e:
        logger.error(f"Error in stats_command: {e}")
        await update.message.reply_text("Ошибка при получении статистики")



async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /leads - список лидов (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        # Парсим аргументы (например: /leads hot)
        args = context.args
        temperature = args[0] if args else None

        leads_message = admin_interface.admin_interface.format_leads_list(
            temperature=temperature,
            limit=20
        )
        await update.message.reply_text(leads_message)

    except Exception as e:
        logger.error(f"Error in leads_command: {e}")
        await update.message.reply_text("Ошибка при получении списка лидов")



async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export - экспорт лидов в CSV (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        csv_data = admin_interface.admin_interface.export_leads_to_csv()

        if csv_data:
            await update.message.reply_document(
                document=csv_data.encode('utf-8') if isinstance(csv_data, str) else csv_data,
                filename='leads_export.csv',
                caption="Экспорт лидов"
            )
        else:
            await update.message.reply_text("Ошибка при экспорте данных")

    except Exception as e:
        logger.error(f"Error in export_command: {e}")
        await update.message.reply_text("Ошибка при экспорте данных")



async def view_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /view_conversation <telegram_id> - просмотр истории диалога (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        # Парсим аргументы
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /view_conversation <telegram_id>")
            return

        telegram_id = int(args[0])

        history_text = admin_interface.admin_interface.get_conversation_history_text(telegram_id)

        # Разбиваем на части если слишком длинное
        max_length = 4000
        if len(history_text) > max_length:
            parts = [history_text[i:i+max_length] for i in range(0, len(history_text), max_length)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(history_text)

    except ValueError:
        await update.message.reply_text("Неверный telegram_id")
    except Exception as e:
        logger.error(f"Error in view_conversation_command: {e}")
        await update.message.reply_text("Ошибка при получении истории диалога")



async def security_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /security_stats - статистика безопасности (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        stats = security.security_manager.get_stats()

        stats_message = (
            "🛡️ СТАТИСТИКА БЕЗОПАСНОСТИ\n\n"
            f"📊 Токены:\n"
            f"• Использовано сегодня: {stats['total_tokens_today']:,}\n"
            f"• Дневной бюджет: {stats['daily_budget']:,}\n"
            f"• Осталось: {stats['budget_remaining']:,}\n"
            f"• Использовано: {stats['budget_percentage']:.1f}%\n\n"
            f"🚫 Безопасность:\n"
            f"• Заблокированных пользователей: {stats['blacklisted_users']}\n"
            f"• Подозрительных пользователей: {stats['suspicious_users']}\n\n"
            f"⚙️ Лимиты:\n"
            f"• Сообщений в минуту: {security.security_manager.RATE_LIMITS['messages_per_minute']}\n"
            f"• Сообщений в час: {security.security_manager.RATE_LIMITS['messages_per_hour']}\n"
            f"• Сообщений в день: {security.security_manager.RATE_LIMITS['messages_per_day']}\n"
            f"• Cooldown: {security.security_manager.COOLDOWN_SECONDS} сек\n"
            f"• Макс длина сообщения: {security.security_manager.MAX_MESSAGE_LENGTH} символов"
        )

        await update.message.reply_text(stats_message)

    except Exception as e:
        logger.error(f"Error in security_stats_command: {e}")
        await update.message.reply_text("Ошибка при получении статистики безопасности")



async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /blacklist <telegram_id> - добавить в черный список (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        # Парсим аргументы
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: /blacklist <telegram_id> [причина]\n\n"
                "Пример: /blacklist 123456789 Спам"
            )
            return

        target_user_id = int(args[0])
        reason = " ".join(args[1:]) if len(args) > 1 else "Заблокирован админом"

        # Добавляем в черный список
        security.security_manager.add_to_blacklist(target_user_id, reason)

        await update.message.reply_text(
            f"✅ Пользователь {target_user_id} добавлен в черный список\n"
            f"Причина: {reason}"
        )

        logger.info(f"Admin {user.id} blacklisted user {target_user_id}: {reason}")

    except ValueError:
        await update.message.reply_text("Неверный telegram_id. Должно быть число.")
    except Exception as e:
        logger.error(f"Error in blacklist_command: {e}")
        await update.message.reply_text("Ошибка при добавлении в черный список")



async def unblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /unblacklist <telegram_id> - удалить из черного списка (только для админа)"""
    try:
        user = update.effective_user

        if user.id != config.ADMIN_TELEGRAM_ID:
            await update.message.reply_text("У вас нет доступа к этой команде")
            return

        # Парсим аргументы
        args = context.args
        if not args:
            await update.message.reply_text(
                "Использование: /unblacklist <telegram_id>\n\n"
                "Пример: /unblacklist 123456789"
            )
            return

        target_user_id = int(args[0])

        # Проверяем что пользователь в черном списке
        if target_user_id not in security.security_manager.blacklist:
            await update.message.reply_text(f"Пользователь {target_user_id} не найден в черном списке")
            return

        # Удаляем из черного списка
        security.security_manager.remove_from_blacklist(target_user_id)

        await update.message.reply_text(f"✅ Пользователь {target_user_id} удален из черного списка")

        logger.info(f"Admin {user.id} unblacklisted user {target_user_id}")

    except ValueError:
        await update.message.reply_text("Неверный telegram_id. Должно быть число.")
    except Exception as e:
        logger.error(f"Error in unblacklist_command: {e}")
        await update.message.reply_text("Ошибка при удалении из черного списка")



async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ админ-панели"""
    try:
        admin_panel_message = (
            "⚙️ АДМИН-ПАНЕЛЬ\n\n"
            "Выберите действие:"
        )

        reply_markup = InlineKeyboardMarkup(ADMIN_PANEL_MENU)
        await update.message.reply_text(admin_panel_message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in show_admin_panel: {e}")
        await update.message.reply_text("Ошибка при открытии админ-панели")



