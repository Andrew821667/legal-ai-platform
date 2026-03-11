from __future__ import annotations

import logging
import os
import shutil
import sqlite3
from datetime import datetime

from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import database
import security
import utils
from config import get_config
from handlers.constants import ADMIN_CLEANUP_MENU

config = get_config()
logger = logging.getLogger(__name__)


def _backup_and_truncate_log(log_file: str) -> str | None:
    """
    Создает backup лог-файла и очищает текущий файл без rename.
    Так FileHandler продолжает писать в тот же inode.
    """
    if not os.path.exists(log_file):
        return None

    backup_file = f"{log_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(log_file, backup_file)
    with open(log_file, "w", encoding="utf-8"):
        pass
    return backup_file


async def handle_cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик cleanup-операций."""
    _ = context
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="cleanup_answer")
    except TelegramError as answer_error:
        logger.warning("Failed to answer cleanup callback: %s", answer_error)

    user = query.from_user

    if user.id != config.ADMIN_TELEGRAM_ID:
        await utils.safe_reply_text(query.message, "У вас нет доступа к этой функции", action="cleanup_access_denied")
        return

    action = query.data

    try:
        if action == "cleanup_conversations":
            conn = database.db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM conversations")
                conn.commit()
                count = cursor.rowcount

                await utils.safe_edit_text(
                    query.message,
                    f"✅ Удалено {count} сообщений из диалогов",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_conversations",
                )
                logger.info("Admin %s cleared %s conversations", user.id, count)
            finally:
                conn.close()

        elif action == "cleanup_leads":
            conn = database.db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM leads")
                conn.commit()
                count = cursor.rowcount

                await utils.safe_edit_text(
                    query.message,
                    f"✅ Удалено {count} лидов",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_leads",
                )
                logger.info("Admin %s cleared %s leads", user.id, count)
            finally:
                conn.close()

        elif action == "cleanup_logs":
            backup_file = _backup_and_truncate_log(config.LOG_FILE)
            if backup_file:
                await utils.safe_edit_text(
                    query.message,
                    f"✅ Логи очищены\nBackup: {backup_file}",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_logs",
                )
                logger.info("Admin %s cleared logs, backup: %s", user.id, backup_file)
            else:
                await utils.safe_edit_text(
                    query.message,
                    "Файл логов не найден",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_logs_not_found",
                )

        elif action == "cleanup_security":
            security.security_manager.reset_runtime_state(clear_blacklist=True)

            new_time = security.security_manager.stats_start_time.strftime("%d.%m.%Y %H:%M")
            await utils.safe_edit_text(
                query.message,
                f"✅ Счетчики безопасности сброшены\n📅 Статистика теперь с: {new_time}",
                reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                action="cleanup_security",
            )
            logger.info("Admin %s reset security counters", user.id)

        elif action == "cleanup_all":
            conn = database.db.get_connection()
            cursor = conn.cursor()

            try:
                cursor.execute("DELETE FROM conversations")
                conv_count = cursor.rowcount

                cursor.execute("DELETE FROM leads")
                leads_count = cursor.rowcount

                cursor.execute("DELETE FROM admin_notifications")
                notif_count = cursor.rowcount

                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
            finally:
                conn.close()

            backup_file = _backup_and_truncate_log(config.LOG_FILE)
            security.security_manager.reset_runtime_state(clear_blacklist=True)

            result_message = (
                "✅ ВСЕ ДАННЫЕ ОЧИЩЕНЫ\n\n"
                f"🗑️ Диалоги: {conv_count}\n"
                f"🗑️ Лиды: {leads_count}\n"
                f"🗑️ Уведомления: {notif_count}\n"
                f"🗑️ Логи: {'очищены (backup создан)' if backup_file else 'файл не найден'}\n"
                f"🗑️ Счетчики безопасности: сброшены"
            )

            await utils.safe_edit_text(
                query.message,
                result_message,
                reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                action="cleanup_all",
            )
            logger.warning("Admin %s cleared ALL data", user.id)

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, IOError) as error:
        logger.error("Error in handle_cleanup_callback: %s", error)
        await utils.safe_reply_text(query.message, f"Ошибка: {str(error)}", action="cleanup_error")
