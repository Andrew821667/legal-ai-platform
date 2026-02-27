"""
Handlers: common
"""
import logging
import time
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Conflict, NetworkError, RetryAfter, TimedOut
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


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    error = context.error
    logger.error(
        "Update %s caused error %s",
        update,
        error,
        exc_info=(type(error), error, error.__traceback__) if error else None,
    )

    if isinstance(error, Conflict):
        logger.error("Detected polling conflict: likely multiple bot instances are running")
        return

    if update and update.callback_query:
        try:
            await utils.safe_answer_callback(
                update.callback_query,
                action="error_handler_callback_answer",
            )
        except Exception as callback_error:
            logger.warning("Failed to answer callback in error handler: %s", callback_error)

    if not update or not update.effective_message:
        return

    if isinstance(error, TimedOut):
        user_text = "Сетевая задержка на стороне Telegram. Попробуйте повторить действие через 2-3 секунды."
    elif isinstance(error, RetryAfter):
        retry_after = int(getattr(error, "retry_after", 2))
        user_text = f"Сервис временно ограничил частоту запросов. Повторите через {retry_after} сек."
    elif isinstance(error, NetworkError):
        user_text = "Временная проблема связи с Telegram API. Попробуйте еще раз."
    elif isinstance(error, BadRequest) and "message is too long" in str(error).lower():
        user_text = "Ответ оказался слишком длинным. Разделите запрос на части и повторите."
    else:
        user_text = "Произошла непредвиденная ошибка. Попробуйте еще раз или свяжитесь с поддержкой."

    try:
        await utils.safe_reply_text(
            update.effective_message,
            user_text,
            action="error_handler_notify_user",
        )
    except Exception as notify_error:
        logger.warning("Failed to notify user from error handler: %s", notify_error)


