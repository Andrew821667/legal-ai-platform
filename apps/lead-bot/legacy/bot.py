#!/usr/bin/env python3
"""
Точка входа legacy-бота.

Запускает:
- пользовательский и business flow;
- callback-обработчики меню/магнитов/админ-панели;
- фоновую задачу отправки отложенных уведомлений по лидам.
"""

from __future__ import annotations

import asyncio
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
import security
import utils
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
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
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


def _classify_message_kind(message: Any) -> str:
    if getattr(message, "text", None):
        return "text"
    if getattr(message, "contact", None) is not None:
        return "contact"
    if getattr(message, "document", None) is not None:
        return "document"
    if getattr(message, "photo", None):
        return "photo"
    if getattr(message, "video", None) is not None:
        return "video"
    if getattr(message, "audio", None) is not None:
        return "audio"
    if getattr(message, "voice", None) is not None:
        return "voice"
    if getattr(message, "sticker", None) is not None:
        return "sticker"
    if getattr(message, "animation", None) is not None:
        return "animation"
    if getattr(message, "location", None) is not None:
        return "location"
    return "unknown"


def _security_alert_text(
    decision: security.SecurityDecision,
    *,
    update_type: str,
    user_id: int | None,
    chat_id: int | None,
) -> str:
    lines = [
        "🛡️ Security alert",
        f"Action: {decision.action}",
        f"Reason: {decision.reason_code or 'unknown'}",
        f"Update: {update_type}",
        f"User ID: {user_id or 'n/a'}",
        f"Chat ID: {chat_id or 'n/a'}",
    ]
    if decision.details:
        details_text = ", ".join(f"{key}={value}" for key, value in sorted(decision.details.items()))
        if details_text:
            lines.append(f"Details: {details_text[:500]}")
    return "\n".join(lines)


async def _send_security_alert(
    context: ContextTypes.DEFAULT_TYPE,
    decision: security.SecurityDecision,
    *,
    update_type: str,
    user_id: int | None,
    chat_id: int | None,
) -> None:
    if not decision.alert_admin:
        return
    try:
        await utils.telegram_call_with_retry(
            lambda: context.bot.send_message(
                chat_id=config.ADMIN_TELEGRAM_ID,
                text=_security_alert_text(
                    decision,
                    update_type=update_type,
                    user_id=user_id,
                    chat_id=chat_id,
                ),
            ),
            action="security_alert",
            max_retries=2,
            base_delay=1.0,
        )
    except Exception as error:
        logger.warning("Failed to send security alert: %s", error)


async def _apply_security_decision(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    decision: security.SecurityDecision,
    *,
    update_type: str,
    user_id: int | None,
    chat_id: int | None,
    notify_user: bool = True,
) -> bool:
    if decision.allowed:
        return True

    await _send_security_alert(
        context,
        decision,
        update_type=update_type,
        user_id=user_id,
        chat_id=chat_id,
    )

    if not notify_user or not decision.user_message:
        return False

    query = update.callback_query
    if query is not None:
        try:
            await utils.safe_answer_callback(
                query,
                text=decision.user_message,
                show_alert=True,
                action="security_callback_block",
            )
        except Exception as error:
            logger.warning("Failed to answer blocked callback: %s", error)
        return False

    message = _extract_incoming_message(update)
    if message is not None:
        try:
            await utils.safe_reply_text(
                message,
                decision.user_message,
                action="security_message_block",
            )
        except Exception as error:
            logger.warning("Failed to notify blocked user: %s", error)
    return False


async def _guard_message_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = _extract_incoming_message(update)
    if message is None:
        return True

    from_user = getattr(message, "from_user", None)
    chat = getattr(message, "chat", None)
    user_id = getattr(from_user, "id", None)
    chat_id = getattr(chat, "id", None)
    chat_type = str(getattr(chat, "type", "")).lower()

    decision = security.security_manager.evaluate_human_actor(
        user_id=user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        is_bot=bool(getattr(from_user, "is_bot", False)),
        via_bot=getattr(message, "via_bot", None) is not None,
        sender_business_bot=getattr(message, "sender_business_bot", None) is not None,
        update_type="business_message" if _is_business_update(update) else "message",
        update_id=update.update_id,
    )
    if not decision.allowed:
        return await _apply_security_decision(
            update,
            context,
            decision,
            update_type="business_message" if _is_business_update(update) else "message",
            user_id=user_id,
            chat_id=chat_id,
            notify_user=not _is_business_update(update),
        )

    message_kind = _classify_message_kind(message)
    if message_kind != "text":
        decision = security.security_manager.check_non_text_gate(
            user_id=user_id,
            chat_id=chat_id,
            message_kind=message_kind,
            update_id=update.update_id,
        )
        if not decision.allowed:
            return await _apply_security_decision(
                update,
                context,
                decision,
                update_type="business_message" if _is_business_update(update) else "message",
                user_id=user_id,
                chat_id=chat_id,
                notify_user=not _is_business_update(update),
            )

    return True


async def _guard_callback_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    if query is None:
        return True

    from_user = getattr(query, "from_user", None)
    message = getattr(query, "message", None)
    chat = getattr(message, "chat", None)
    user_id = getattr(from_user, "id", None)
    chat_id = getattr(chat, "id", None)
    chat_type = str(getattr(chat, "type", "")).lower()

    decision = security.security_manager.evaluate_human_actor(
        user_id=user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        is_bot=bool(getattr(from_user, "is_bot", False)),
        update_type="callback_query",
        update_id=update.update_id,
    )
    if not decision.allowed:
        return await _apply_security_decision(
            update,
            context,
            decision,
            update_type="callback_query",
            user_id=user_id,
            chat_id=chat_id,
        )

    decision = security.security_manager.check_callback_gate(
        user_id=user_id,
        chat_id=chat_id,
        callback_data=query.data or "",
        update_id=update.update_id,
    )
    if not decision.allowed:
        return await _apply_security_decision(
            update,
            context,
            decision,
            update_type="callback_query",
            user_id=user_id,
            chat_id=chat_id,
        )

    return True


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
                                text=content.build_business_welcome_message(client_name),
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
            elif reason in {
                "from_user_is_bot",
                "sender_business_bot",
                "via_bot_message",
                "outgoing_private_message",
                "invalid_sender_chat_ids",
            }:
                actor = getattr(message, "from_user", None)
                chat = getattr(message, "chat", None)
                decision = security.security_manager.register_actor_violation(
                    user_id=getattr(actor, "id", None),
                    reason_code=reason,
                    payload={
                        "chat_id": getattr(chat, "id", None),
                        "chat_type": str(getattr(chat, "type", "")).lower(),
                    },
                    chat_id=getattr(chat, "id", None),
                    update_id=update.update_id,
                    update_type="business_message",
                )
                await _apply_security_decision(
                    update,
                    context,
                    decision,
                    update_type="business_message",
                    user_id=getattr(actor, "id", None),
                    chat_id=getattr(chat, "id", None),
                    notify_user=False,
                )
            logger.info("Skip business update %s: reason=%s", update.update_id, reason)
            return

        if not await _guard_message_update(update, context):
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
        if not await _guard_message_update(update, context):
            return
        await handle_message(update, context)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Роутер callback_data.
    """
    query = update.callback_query
    if not query:
        return

    if not await _guard_callback_update(update, context):
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
        ready_leads = database.db.get_leads_ready_for_notification(
            idle_minutes=config.PENDING_LEADS_IDLE_MINUTES
        )
        if not ready_leads:
            return

        batch = ready_leads[: config.PENDING_LEADS_JOB_MAX_BATCH]
        logger.info(
            "Pending leads ready for notification: %s (processing batch=%s, idle_minutes=%s)",
            len(ready_leads),
            len(batch),
            config.PENDING_LEADS_IDLE_MINUTES,
        )
        for lead in batch:
            lead_id = lead.get("id")
            user_id = lead.get("user_id")
            if not lead_id or not user_id:
                continue

            user_data = database.db.get_user_by_id(user_id) or {"id": user_id, "telegram_id": None}
            try:
                await asyncio.wait_for(
                    notify_admin_new_lead(
                        context=context,
                        lead_id=lead_id,
                        lead_data=lead,
                        user_data=user_data,
                        is_update=False,
                    ),
                    timeout=config.PENDING_LEADS_NOTIFY_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout while notifying pending lead %s (user_id=%s)",
                    lead_id,
                    user_id,
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
        first_run_delay = min(30, max(1, config.PENDING_LEADS_CHECK_INTERVAL_SECONDS // 2))
        application.job_queue.run_repeating(
            check_pending_leads_job,
            interval=config.PENDING_LEADS_CHECK_INTERVAL_SECONDS,
            first=first_run_delay,
            name="pending_leads_notifier",
            job_kwargs={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": config.PENDING_LEADS_JOB_MISFIRE_GRACE_SECONDS,
            },
        )
        logger.info(
            "Pending leads notifier enabled: interval=%ss idle=%sm batch=%s timeout=%.1fs",
            config.PENDING_LEADS_CHECK_INTERVAL_SECONDS,
            config.PENDING_LEADS_IDLE_MINUTES,
            config.PENDING_LEADS_JOB_MAX_BATCH,
            config.PENDING_LEADS_NOTIFY_TIMEOUT_SECONDS,
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
            allowed_updates=[
                "message",
                "callback_query",
                "business_connection",
                "business_message",
            ],
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
