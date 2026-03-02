#!/usr/bin/env python3
"""
Точка входа legacy-бота.

Запускает:
- пользовательский и business flow;
- callback-обработчики меню/магнитов/админ-панели;
- фоновую задачу отправки отложенных уведомлений по лидам.
"""

from __future__ import annotations

import atexit
import fcntl
import logging
import os
import sys
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.request import HTTPXRequest
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
import content
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
from handlers.business import build_business_menu_markup, handle_business_connection, handle_business_message
from handlers.callbacks import (
    handle_admin_panel_callback,
    handle_business_menu_callback,
    handle_cleanup_callback,
    handle_consent_callback,
    handle_documents_callback,
    handle_lead_magnet_callback,
    handle_profile_callback,
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
_LOCK_FILE_HANDLE = None


def _release_single_instance_lock() -> None:
    global _LOCK_FILE_HANDLE
    if _LOCK_FILE_HANDLE is None:
        return
    try:
        fcntl.flock(_LOCK_FILE_HANDLE.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        _LOCK_FILE_HANDLE.close()
    except Exception:
        pass
    _LOCK_FILE_HANDLE = None


def _acquire_single_instance_lock(lock_path: str = "data/lead-bot.lock") -> None:
    """
    Защита от случайного запуска двух polling-процессов на одном хосте.
    """
    global _LOCK_FILE_HANDLE
    lock_file = Path(lock_path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_file.open("w", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        handle.close()
        raise RuntimeError("Обнаружен второй экземпляр бота: остановите дублирующий процесс.") from error

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    _LOCK_FILE_HANDLE = handle
    atexit.register(_release_single_instance_lock)


def _is_business_update(update: Update) -> bool:
    return getattr(update, "business_message", None) is not None


def _extract_incoming_message(update: Update) -> Any:
    if _is_business_update(update):
        return update.business_message
    return update.message


def _business_skip_reason(message: Any, bot_id: int) -> str | None:
    from_user = getattr(message, "from_user", None)
    if from_user is None:
        return "missing_from_user"
    if getattr(from_user, "is_bot", False):
        return "from_user_is_bot"
    if from_user.id == bot_id:
        return "self_message"
    if str(from_user.id) == str(config.ADMIN_TELEGRAM_ID):
        return "owner_message"
    if getattr(message, "sender_business_bot", None) is not None:
        return "sender_business_bot"
    if getattr(message, "via_bot", None) is not None:
        return "via_bot_message"
    if getattr(message, "is_from_offline", False):
        return "offline_message"

    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    chat_type = str(getattr(chat, "type", "")).lower()
    # В private business-чатах входящее от клиента должно иметь from_user.id == chat.id.
    if chat_id is not None and chat_type == "private":
        try:
            if int(chat_id) != int(from_user.id):
                return "outgoing_private_message"
        except (TypeError, ValueError):
            return "invalid_sender_chat_ids"
    return None


def _is_legacy_owner_intro_text(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    signals = [
        "я андрей попов",
        "автоматизировать работу юротдела",
        "обучение команды работе с ai",
        "какая задача стоит перед вашей компанией",
        "разработка специализированного решения",
        "аудит существующих процессов",
    ]
    hits = sum(1 for token in signals if token in normalized)
    if normalized.startswith("здравствуйте!") and hits >= 2:
        return True
    return hits >= 3 and len(normalized) >= 180


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Общий роутер входящих сообщений.
    """
    message = _extract_incoming_message(update)
    if not message:
        return

    if _is_business_update(update):
        reason = _business_skip_reason(message, context.bot.id)
        if reason:
            if reason == "owner_message":
                text = getattr(message, "text", "") or ""
                if _is_legacy_owner_intro_text(text):
                    connection_id = getattr(message, "business_connection_id", None)
                    chat = getattr(message, "chat", None)
                    chat_id = getattr(chat, "id", None)
                    client_name = getattr(chat, "first_name", "") or "клиент"
                    message_id = getattr(message, "message_id", None)

                    if connection_id and message_id:
                        try:
                            await context.bot.delete_business_messages(
                                business_connection_id=str(connection_id),
                                message_ids=[int(message_id)],
                            )
                            logger.info(
                                "Deleted legacy owner intro message %s on connection %s",
                                message_id,
                                connection_id,
                            )
                        except Exception as delete_error:
                            logger.warning(
                                "Failed to delete legacy owner intro message %s: %s",
                                message_id,
                                delete_error,
                            )

                    if connection_id and chat_id is not None:
                        try:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=content.build_welcome_message(client_name),
                                reply_markup=build_business_menu_markup(),
                                business_connection_id=str(connection_id),
                            )
                            logger.info(
                                "Sent replacement welcome after owner intro for chat %s (connection %s)",
                                chat_id,
                                connection_id,
                            )
                        except Exception as send_error:
                            logger.warning(
                                "Failed to send replacement welcome for chat %s: %s",
                                chat_id,
                                send_error,
                            )
            logger.info("Skip business update %s: reason=%s", update.update_id, reason)
            return

        connection_id = getattr(message, "business_connection_id", None)
        if not database.db.is_business_connection_enabled(connection_id):
            logger.info(
                "Skip business update %s: connection disabled (%s)",
                update.update_id,
                connection_id,
            )
            return

        chat_id = getattr(getattr(message, "chat", None), "id", None)
        if chat_id is not None and not database.db.is_chat_enabled(int(chat_id)):
            logger.info("Skip business update %s: chat %s disabled", update.update_id, chat_id)
            return

        await handle_business_message(update, context)
    else:
        from_user = getattr(message, "from_user", None)
        if from_user and from_user.id == context.bot.id:
            logger.info("Skip self message")
            return
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
    elif data.startswith("profile_"):
        await handle_profile_callback(update, context)
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
    request = HTTPXRequest(
        connect_timeout=8.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=3.0,
    )
    get_updates_request = HTTPXRequest(
        connect_timeout=8.0,
        read_timeout=45.0,
        write_timeout=20.0,
        pool_timeout=3.0,
    )

    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )

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
    # Важно: контакт/документы/фото приходят не как TEXT, но должны обрабатываться
    # в едином user-flow (например, кнопка "Отправить телефон").
    application.add_handler(MessageHandler((filters.CONTACT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, message_router))
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
        _acquire_single_instance_lock()
        app = build_application()
        logger.info("Legacy bot started")
        app.run_polling(
            timeout=30,
            bootstrap_retries=5,
            allowed_updates=Update.ALL_TYPES,
        )
    except RuntimeError as lock_error:
        logger.error("%s", lock_error)
    except KeyboardInterrupt:
        logger.info("Legacy bot stopped by user")
    except Exception as error:
        logger.error("Critical startup error: %s", error, exc_info=True)
        raise


if __name__ == "__main__":
    main()
