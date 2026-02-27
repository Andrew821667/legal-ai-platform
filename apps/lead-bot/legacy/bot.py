#!/usr/bin/env python3
"""
Точка входа legacy-бота.

Запускает:
- пользовательский и business flow;
- callback-обработчики меню/магнитов/админ-панели;
- фоновую задачу отправки отложенных уведомлений по лидам.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

import database
from config import Config
from handlers.admin import (
    blacklist_command,
    edit_pdn_command,
    export_command,
    leads_command,
    pdn_user_command,
    revoke_user_consent_command,
    security_stats_command,
    show_admin_panel,
    stats_command,
    unblacklist_command,
    view_conversation_command,
)
from handlers.business import handle_business_connection, handle_business_message
from handlers.callbacks import (
    handle_admin_panel_callback,
    handle_business_menu_callback,
    handle_cleanup_callback,
    handle_consent_callback,
    handle_documents_callback,
    handle_lead_magnet_callback,
)
from handlers.common import error_handler
from handlers.helpers import notify_admin_new_lead
from handlers.user import (
    ai_policy_command,
    consent_status_command,
    correct_data_command,
    delete_data_command,
    documents_command,
    export_data_command,
    handle_message,
    help_command,
    marketing_consent_command,
    menu_command,
    profile_command,
    privacy_command,
    reset_command,
    revoke_consent_command,
    start_command,
    transborder_consent_command,
    user_agreement_command,
)

config = Config()

log_dir = os.path.dirname(config.LOG_FILE)
if log_dir:
    os.makedirs(log_dir, exist_ok=True)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _is_business_update(update: Update) -> bool:
    return getattr(update, "business_message", None) is not None


def _extract_incoming_message(update: Update) -> Any:
    if _is_business_update(update):
        return update.business_message
    return update.message


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Общий роутер входящих сообщений.
    """
    message = _extract_incoming_message(update)
    if not message:
        return

    from_user = getattr(message, "from_user", None)
    if from_user and from_user.id == context.bot.id:
        logger.info("Skip self message")
        return

    # В business-режиме игнорируем сообщения владельца аккаунта,
    # чтобы не ловить ответные циклы.
    if _is_business_update(update) and from_user and str(from_user.id) == str(config.ADMIN_TELEGRAM_ID):
        logger.info("Skip business owner message")
        return

    if _is_business_update(update):
        await handle_business_message(update, context)
    else:
        await handle_message(update, context)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Роутер callback_data.
    """
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    if data.startswith("menu_"):
        await handle_business_menu_callback(update, context)
    elif data.startswith("consent_"):
        await handle_consent_callback(update, context)
    elif data.startswith("doc_"):
        await handle_documents_callback(update, context)
    elif data.startswith("magnet_"):
        await handle_lead_magnet_callback(update, context)
    elif data.startswith("cleanup_"):
        await handle_cleanup_callback(update, context)
    elif data.startswith("admin_"):
        await handle_admin_panel_callback(update, context)
    else:
        await query.answer("Неизвестное действие")


async def business_connection_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if getattr(update, "business_connection", None) is None:
        return
    await handle_business_connection(update, context)


async def business_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if getattr(update, "business_message", None) is None:
        return
    await message_router(update, context)


async def check_pending_leads_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Проверка лидов, где диалог затих, и отправка уведомлений админу.
    """
    try:
        ready_leads = database.db.get_leads_ready_for_notification(idle_minutes=5)
        if not ready_leads:
            return

        logger.info("Pending leads ready for notification: %s", len(ready_leads))
        for lead in ready_leads:
            lead_id = lead.get("id")
            user_id = lead.get("user_id")
            if not lead_id or not user_id:
                continue

            user_data = database.db.get_user_by_id(user_id) or {"id": user_id, "telegram_id": None}
            await notify_admin_new_lead(
                context=context,
                lead_id=lead_id,
                lead_data=lead,
                user_data=user_data,
                is_update=False,
            )

    except Exception as error:
        logger.error("Error in pending leads job: %s", error, exc_info=True)


def build_application() -> Application:
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Пользовательские команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("documents", documents_command))
    application.add_handler(CommandHandler("privacy", privacy_command))
    application.add_handler(CommandHandler("transborder_consent", transborder_consent_command))
    application.add_handler(CommandHandler("user_agreement", user_agreement_command))
    application.add_handler(CommandHandler("ai_policy", ai_policy_command))
    application.add_handler(CommandHandler("marketing_consent", marketing_consent_command))
    application.add_handler(CommandHandler("consent_status", consent_status_command))
    application.add_handler(CommandHandler("export_data", export_data_command))
    application.add_handler(CommandHandler("revoke_consent", revoke_consent_command))
    application.add_handler(CommandHandler("delete_data", delete_data_command))
    application.add_handler(CommandHandler("correct_data", correct_data_command))

    # Админские команды
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("leads", leads_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("view_conversation", view_conversation_command))
    application.add_handler(CommandHandler("security_stats", security_stats_command))
    application.add_handler(CommandHandler("blacklist", blacklist_command))
    application.add_handler(CommandHandler("unblacklist", unblacklist_command))
    application.add_handler(CommandHandler("pdn_user", pdn_user_command))
    application.add_handler(CommandHandler("edit_pdn", edit_pdn_command))
    application.add_handler(CommandHandler("revoke_user_consent", revoke_user_consent_command))
    application.add_handler(CommandHandler("admin", show_admin_panel))

    # Сообщения и callbacks
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    application.add_handler(CallbackQueryHandler(callback_router))

    # Business message/update может не попадать под стандартные filters.TEXT.
    application.add_handler(TypeHandler(Update, business_message_router))

    # Business connection update приходит отдельным типом update.
    application.add_handler(TypeHandler(Update, business_connection_router))

    application.add_error_handler(error_handler)

    if application.job_queue is not None:
        application.job_queue.run_repeating(
            check_pending_leads_job,
            interval=60,
            first=30,
            name="pending_leads_notifier",
        )
    else:
        logger.warning("JobQueue is not available, pending lead notifications disabled")

    return application


def main() -> None:
    try:
        app = build_application()
        logger.info("Legacy bot started")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Legacy bot stopped by user")
    except Exception as error:
        logger.error("Critical startup error: %s", error, exc_info=True)
        raise


if __name__ == "__main__":
    main()
