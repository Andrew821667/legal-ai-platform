"""
Command handlers and related helper functions for the user flow.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Dict, Optional

import admin_interface
import content
import database
import utils
from config import get_config
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .markup import (
    documents_markup as _documents_markup,
)
from .markup import (
    pdn_consent_markup as _pdn_consent_markup,
)
from .markup import (
    profile_panel_markup as _profile_panel_markup,
)
from .markup import (
    quick_nav_markup_for as _quick_nav_markup_for,
)
from .markup import (
    start_markup_for as _start_markup_for,
)
from .markup import (
    transborder_consent_markup as _transborder_consent_markup,
)
from .markup import (
    web_open_markup as _web_open_markup,
)
from .markup import (
    workspace_markup_for as _workspace_markup_for,
)
from .start_payloads import (
    _CONTRACT_START_PAYLOAD_RE,
    _READER_START_PAYLOAD_RE,
    process_pending_start_payload,
)
from .start_payloads import (
    PENDING_START_PAYLOAD_KEY as _PENDING_START_PAYLOAD_KEY,
)

config = get_config()
logger = logging.getLogger(__name__)


def _get_local_user_and_lead(telegram_id: int) -> tuple[dict | None, dict | None]:
    user_row = database.db.get_local_user_by_telegram_id(telegram_id)
    if not user_row:
        return None, None
    lead = database.db.get_local_lead_by_user_id(user_row["id"])
    return user_row, lead


def _extract_start_payload(context: ContextTypes.DEFAULT_TYPE) -> str:
    args = getattr(context, "args", None) or []
    if not args:
        return ""
    return str(args[0]).strip()


def _is_pdn_consent_granted(consent_state: Dict) -> bool:
    return bool(consent_state.get("consent_given")) and not bool(consent_state.get("consent_revoked"))


def _should_require_pdn_consent(is_admin: bool, consent_state: Dict) -> bool:
    return not is_admin and not _is_pdn_consent_granted(consent_state)


def _pdn_consent_prompt_text(action_label: str | None = None) -> str:
    return f"{content.pdn_consent_required_text(action_label)}\n\n{content.CONSENT_STEP_1_TEXT}"


def _format_profile_text(user_data: Dict, lead: Optional[Dict], consent_state: Dict, is_admin: bool) -> str:
    lead = lead or {}
    if is_admin:
        return (
            "👤 Ваш профиль\n\n"
            "Статус: Администратор\n"
            f"Имя: {user_data.get('first_name') or 'не указано'}\n"
            f"Фамилия: {user_data.get('last_name') or 'не указана'}\n"
            f"Username: @{user_data.get('username') or 'не указан'}\n"
            f"Telegram ID: {user_data.get('telegram_id')}\n\n"
            "Данные по заявке:\n"
            f"• Имя: {lead.get('name') or 'не указано'}\n"
            f"• Компания: {lead.get('company') or 'не указана'}\n"
            f"• Email: {lead.get('email') or 'не указан'}\n"
            f"• Телефон: {lead.get('phone') or 'не указан'}\n"
            f"• Температура: {lead.get('temperature') or 'не определена'}\n"
            f"• Статус: {lead.get('status') or 'new'}\n\n"
            f"{content.consent_status_text(consent_state)}"
        )

    return (
        "👤 Ваш профиль\n\n"
        f"Имя: {user_data.get('first_name') or 'не указано'}\n"
        f"Фамилия: {user_data.get('last_name') or 'не указана'}\n"
        f"Username: @{user_data.get('username') or 'не указан'}\n\n"
        "Контактные данные:\n"
        f"• Имя в заявке: {lead.get('name') or 'не указано'}\n"
        f"• Email: {lead.get('email') or 'не указан'}\n"
        f"• Телефон: {lead.get('phone') or 'не указан'}\n\n"
        f"{content.consent_user_status_text(consent_state)}\n\n"
        "Если в данных ошибка, используйте кнопки редактирования ниже."
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        start_payload = _extract_start_payload(context)
        if start_payload:
            context.user_data[_PENDING_START_PAYLOAD_KEY] = start_payload
        logger.info("User %s started bot", user.id)

        existing_user = database.db.get_local_user_by_telegram_id(user.id)
        existing_consent_state = (
            database.db.get_user_consent_state(existing_user["id"])
            if existing_user
            else {}
        )
        needs_pdn_consent = _should_require_pdn_consent(
            user.id == config.ADMIN_TELEGRAM_ID,
            existing_consent_state,
        )
        if needs_pdn_consent:
            consent_text = _pdn_consent_prompt_text()
            if _READER_START_PAYLOAD_RE.match(start_payload):
                consent_text = (
                    f"{consent_text}\n\n"
                    "После подтверждения согласия сразу подхвачу ваш запрос по материалу из ридер-бота."
                )
            elif _CONTRACT_START_PAYLOAD_RE.match(start_payload):
                consent_text = (
                    f"{consent_text}\n\n"
                    "После подтверждения согласия сразу переведу вас в сервис проверки договоров Contract_AI_System."
                )
            await utils.safe_reply_html(
                update.message,
                consent_text,
                reply_markup=_pdn_consent_markup(),
                action="start_consent_step_1",
            )
            logger.info("Start consent prompt sent on /start for user %s", user.id)
            return

        user_id = database.db.create_or_update_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        chat = update.effective_chat
        if chat is not None:
            database.db.set_chat_mode(int(chat.id), "bot")

        lead = database.db.get_local_lead_by_user_id(user_id)
        selected_profile = database.db.get_user_offer_profile(user_id)
        start_markup = _start_markup_for(lead=lead, selected_profile=selected_profile)

        await utils.safe_reply_html(
            update.message,
            content.build_start_entry_text(
                first_name=user.first_name,
                lead=lead,
                selected_profile=selected_profile,
                emphasize_profile_choice=True,
            ),
            reply_markup=start_markup,
            action="start_entry",
        )
        logger.info("Start entry sent on /start for user %s", user.id)

        user_data = database.db.get_local_user_by_id(user_id)
        if user_data:
            await process_pending_start_payload(
                message=update.message,
                context=context,
                user_data=user_data,
                user=user,
            )

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as error:
        logger.error("Error in start_command: %s", error)
        await utils.safe_reply_text(
            update.message,
            "Произошла ошибка. Попробуйте еще раз.",
            action="start_fallback_error",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    _ = context
    lead = None
    selected_profile = None
    user = update.effective_user
    if user:
        user_row, lead = _get_local_user_and_lead(user.id)
        if user_row:
            selected_profile = database.db.get_user_offer_profile(user_row["id"])
    await utils.safe_reply_html(
        update.message,
        content.HELP_MESSAGE,
        reply_markup=_quick_nav_markup_for(lead=lead, selected_profile=selected_profile),
        action="help_command",
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile - карточка пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="profile_no_user")
        return

    local_user = database.db.get_local_user_by_id(user_data["id"]) or user_data
    lead = database.db.get_local_lead_by_user_id(user_data["id"])
    consent_state = database.db.get_user_consent_state(user_data["id"])
    selected_profile = database.db.get_user_offer_profile(user_data["id"])
    is_admin = user.id == config.ADMIN_TELEGRAM_ID
    reply_markup = _profile_panel_markup(is_admin, lead=lead, selected_profile=selected_profile)
    await utils.safe_reply_text(
        update.message,
        _format_profile_text(local_user, lead, consent_state, is_admin),
        reply_markup=reply_markup,
        action="profile_command",
    )


async def documents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /documents - список документов и действий по данным."""
    _ = context
    await utils.safe_reply_html(
        update.message,
        content.documents_list_text(),
        reply_markup=_documents_markup(),
        action="documents_command",
    )


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /privacy - политика обработки ПД."""
    _ = context
    await utils.safe_reply_html(
        update.message,
        content.privacy_policy_text(),
        reply_markup=_web_open_markup("privacy"),
        action="privacy_command",
    )


async def user_agreement_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /user_agreement - пользовательское соглашение."""
    _ = context
    await utils.safe_reply_html(
        update.message,
        content.user_agreement_text(),
        reply_markup=_web_open_markup("user_agreement"),
        action="user_agreement_command",
    )


async def ai_policy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai_policy - политика использования ИИ."""
    _ = context
    await utils.safe_reply_html(
        update.message,
        content.ai_policy_text(),
        reply_markup=_web_open_markup("ai_policy"),
        action="ai_policy_command",
    )


async def marketing_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /marketing_consent - условия рассылок."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    await utils.safe_reply_html(
        update.message,
        content.marketing_consent_text(),
        reply_markup=_web_open_markup("marketing_consent"),
        action="marketing_consent_command",
    )
    if user_data:
        database.db.set_user_marketing_consent(user_data["id"], True)


async def transborder_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transborder_consent - условия и управление согласием."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="transborder_no_user")
        return
    consent_state = database.db.get_user_consent_state(user_data["id"])
    message = content.transborder_policy_text()
    if bool(consent_state.get("transborder_consent")):
        await utils.safe_reply_html(
            update.message,
            f"{message}\n\n<b>Статус:</b> ✅ согласие активно.",
            reply_markup=_web_open_markup("transborder"),
            action="transborder_status_active",
        )
        return
    await utils.safe_reply_html(
        update.message,
        f"{message}\n\n<b>Статус:</b> ❌ согласие не дано.",
        reply_markup=_transborder_consent_markup(),
        action="transborder_status_missing",
    )


async def consent_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /consent_status - текущий статус согласий пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="consent_status_no_user")
        return
    consent_state = database.db.get_user_consent_state(user_data["id"])
    is_admin = user.id == config.ADMIN_TELEGRAM_ID
    text = content.consent_status_text(consent_state) if is_admin else content.consent_user_status_text(consent_state)
    await utils.safe_reply_html(update.message, text, action="consent_status_command")


async def export_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export_data - выгрузка данных пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="export_data_no_user")
        return
    payload = await admin_interface.admin_interface.export_user_data_async(user.id)
    if not payload:
        await utils.safe_reply_text(update.message, "Данные пользователя не найдены.", action="export_data_not_found")
        return
    await utils.safe_reply_text(update.message, content.export_data_text(payload), action="export_data_command")


async def revoke_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /revoke_consent - отзыв согласий и удаление ПД."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_local_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return

    result = admin_interface.admin_interface.clear_user_data_by_telegram_id(user.id)
    if result is None:
        await utils.safe_reply_text(
            update.message,
            "Не удалось обработать отзыв согласия. Попробуйте позже.",
            action="revoke_consent_not_found",
        )
        return

    await utils.safe_reply_html(
        update.message,
        (
            f"{content.CONSENT_REVOKED_TEXT}\n\n"
            f"<b>Изменено профилей:</b> {result.get('users_updated', 0)}\n"
            f"<b>Анонимизировано анкет:</b> {result.get('leads_anonymized', 0)}\n"
            f"<b>Удалено сообщений диалога:</b> {result.get('messages_deleted', 0)}"
        ),
        action="revoke_consent_command",
    )


async def delete_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delete_data - алиас для /revoke_consent."""
    await revoke_consent_command(update, context)


async def correct_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /correct_data - запрос на исправление данных пользователем."""
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text(
            "Использование:\n"
            "/correct_data <что исправить>\n\n"
            "Пример:\n"
            "/correct_data Исправьте email на example@mail.ru"
        )
        return

    admin_text = (
        "📝 Запрос на исправление данных\n\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Имя: {user.first_name or '—'}\n\n"
        f"Запрос:\n{text}"
    )

    try:
        await context.bot.send_message(chat_id=config.ADMIN_TELEGRAM_ID, text=admin_text)
    except TelegramError as error:
        logger.warning("Failed to notify admin about correct_data request: %s", error)

    await update.message.reply_text("✅ Запрос на исправление данных отправлен команде.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset"""
    try:
        user = update.effective_user
        user_data = database.db.get_local_user_by_telegram_id(user.id)

        if user_data:
            database.db.clear_conversation_history(user_data["id"])
            database.db.reset_user_funnel_state(user_data["id"])
            logger.info("Conversation reset for user %s", user.id)

            await update.message.reply_text(
                content.RESET_MESSAGE,
                parse_mode="HTML",
            )
        else:
            await start_command(update, context)

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as error:
        logger.error("Error in reset_command: %s", error)
        await update.message.reply_text("Произошла ошибка. Попробуйте /start")


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu - открывает рабочий стол."""
    _ = context
    try:
        lead = None
        selected_profile = None
        user = update.effective_user
        if user:
            user_row = database.db.get_local_user_by_telegram_id(user.id)
            if user_row:
                lead = database.db.get_local_lead_by_user_id(user_row["id"])
                selected_profile = database.db.get_user_offer_profile(user_row["id"])
        reply_markup = _workspace_markup_for(lead=lead, selected_profile=selected_profile)

        message = update.effective_message
        if message:
            await utils.safe_reply_html(
                message,
                content.build_workspace_text(lead=lead, selected_profile=selected_profile),
                reply_markup=reply_markup,
                action="menu_command_workspace",
            )
            logger.info("Menu shown to user %s", update.effective_user.id)

    except (TelegramError, KeyError, AttributeError) as error:
        logger.error("Error in menu_command: %s", error)
        try:
            if update.effective_message:
                await update.effective_message.reply_text("Произошла ошибка. Попробуйте /start")
        except TelegramError:
            pass
