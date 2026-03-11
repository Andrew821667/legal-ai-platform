"""
Handlers: callbacks
"""
from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import time
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton
from telegram_ui import reply_button as KeyboardButton
import database
import ai_brain
import lead_qualifier
import admin_interface
from config import get_config
config = get_config()
import utils
import email_sender
import security
import prompts
import content
import funnel
from lead_perf import log_span_timing, perf_start
from handlers.constants import (
    ADMIN_CLEANUP_MENU,
    ADMIN_EDIT_FIELD_MENU,
    ADMIN_EXPORT_MENU,
    ADMIN_LEADS_MENU,
    ADMIN_MENU,
    ADMIN_PANEL_MENU,
    ADMIN_RUNTIME_MENU,
    ADMIN_SECURITY_MENU,
    ADMIN_USERS_MENU,
    BUSINESS_AWAITING_CONTACT_KEY,
    BUSINESS_AWAITING_CONTACT_SOURCE_KEY,
    BUSINESS_PENDING_CONTACT_KEY,
    CONSENT_PDN_MENU,
    LEAD_MAGNET_MENU,
    MAIN_MENU,
    append_inline_url_row,
)
from handlers.helpers import notify_admin_new_lead
from handlers.markup import (
    admin_lookup_menu_markup as _admin_lookup_menu_markup,
    admin_user_clear_confirm_markup as _admin_user_clear_confirm_markup,
    admin_user_delete_confirm_markup as _admin_user_delete_confirm_markup,
    admin_user_detail_markup as _admin_user_detail_markup,
    admin_user_reset_new_confirm_markup as _admin_user_reset_new_confirm_markup,
    admin_users_list_markup as _admin_users_list_markup,
    business_phone_format_text as _business_phone_format_text,
    clear_business_contact_state as _clear_business_contact_state,
    clip_for_edit as _clip_for_edit,
    consultation_contact_markup as _consultation_contact_markup,
    contact_visibility_choice_markup as _contact_visibility_choice_markup,
    documents_panel_markup as _documents_panel_markup,
    documents_panel_text as _documents_panel_text,
    offer_profile_markup as _offer_profile_markup,
    personal_mode_markup as _personal_mode_markup,
    with_channel_button as _with_channel_button,
    workspace_markup_for as _workspace_markup_for,
)
from handlers.admin_callbacks import handle_admin_panel_callback
from handlers.start_payloads import process_pending_start_payload

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


def _build_client_profile_text(user_row: dict, lead: dict | None, consent_state: dict) -> str:
    lead = lead or {}
    full_name = " ".join(
        part
        for part in (
            (user_row.get("first_name") or "").strip(),
            (user_row.get("last_name") or "").strip(),
        )
        if part
    ) or "—"
    username = user_row.get("username")
    username_text = f"@{username}" if username else "не указан"
    name_in_lead = lead.get("name") or full_name
    consent_hint = content.consent_user_status_text(consent_state)
    return (
        "👤 Ваш профиль\n\n"
        f"Имя профиля: {full_name}\n"
        f"Username: {username_text}\n\n"
        "Контактные данные:\n"
        f"• Имя в заявке: {name_in_lead}\n"
        f"• Email: {lead.get('email') or 'не указан'}\n"
        f"• Телефон: {lead.get('phone') or 'не указан'}\n"
        f"• Компания: {lead.get('company') or 'не указана'}\n\n"
        f"{consent_hint}\n\n"
        "Чтобы исправить ФИО или email, используйте кнопку «👤 Профиль» на рабочем столе."
    )


def _has_pdn_consent(consent_state: dict | None) -> bool:
    consent_state = consent_state or {}
    return bool(consent_state.get("consent_given")) and not bool(consent_state.get("consent_revoked"))


def _clear_admin_lookup_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_lookup_action", None)
    context.user_data.pop("admin_lookup_field", None)


def _resolve_local_callback_user(user) -> tuple[int | None, dict | None]:
    """Avoid a blind upsert on every callback when Telegram profile fields did not change."""
    if not user:
        return None, None

    local_user = database.db.get_local_user_by_telegram_id(user.id)
    if local_user:
        username = local_user.get("username") or None
        first_name = local_user.get("first_name") or None
        last_name = local_user.get("last_name") or None
        if (
            username == (user.username or None)
            and first_name == (user.first_name or None)
            and last_name == (user.last_name or None)
        ):
            return int(local_user["id"]), local_user

    user_db_id = database.db.create_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    return user_db_id, (database.db.get_local_user_by_id(user_db_id) if user_db_id else None)


async def handle_business_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик inline кнопок меню для бизнес-чатов
    """
    started_at = perf_start()
    callback_data = ""
    try:
        query = update.callback_query
        try:
            await utils.safe_answer_callback(query, action="business_menu_answer")
        except TelegramError as answer_error:
            logger.warning(f"Failed to answer business menu callback: {answer_error}")
        
        callback_data = query.data or ""
        contact_actions = {"menu_consultation", "menu_leave_contact"}

        is_business = bool(
            query.message
            and hasattr(query.message, "business_connection_id")
            and query.message.business_connection_id
        )

        user = query.from_user
        user_db_id = None
        local_user = None
        lead = None
        selected_profile = None
        consent_state = None
        if user:
            user_db_id, local_user = _resolve_local_callback_user(user)
            lead = database.db.get_local_lead_by_user_id(user_db_id) if user_db_id else None
            selected_profile = (local_user or {}).get("offer_profile_override") or None
        menu_markup = _workspace_markup_for(lead=lead, selected_profile=selected_profile)

        async def _send_business_menu_message(text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
            await utils.safe_send_message(
                context.bot,
                action=f"business_menu:{callback_data or 'unknown'}",
                chat_id=query.message.chat.id,
                text=text,
                parse_mode="HTML",
                business_connection_id=query.message.business_connection_id,
                reply_markup=reply_markup,
            )

        profile_callback_map = {
            "menu_offer_set_inhouse": "inhouse",
            "menu_offer_set_law_firm": "law_firm",
            "menu_offer_set_business": "business",
            "menu_offer_set_universal": "universal",
            "menu_offer_set_auto": None,
        }
        if callback_data in profile_callback_map:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="offer_profile_no_user",
                )
                return
            new_profile = profile_callback_map[callback_data]
            database.db.set_user_offer_profile(user_db_id, new_profile)
            lead = database.db.get_lead_by_user_id(user_db_id) if user_db_id else None
            response_text = content.offer_profile_change_success_text(new_profile)
            response_text = (
                f"{response_text}\n\n"
                f"{content.offer_profile_panel_text(lead=lead, selected_profile=new_profile)}"
            )
            response_markup = _offer_profile_markup(new_profile)
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_offer_profile_set",
                )
            return

        if callback_data == "menu_offer_profile":
            response_text = content.offer_profile_panel_text(lead=lead, selected_profile=selected_profile)
            response_markup = _offer_profile_markup(selected_profile)
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_offer_profile",
                )
            return

        response_text = content.menu_response_by_key(
            callback_data,
            lead=lead,
            selected_profile=selected_profile,
        )

        contact_flow_actions = contact_actions | {"menu_contact_send_phone", "menu_contact_telegram_only"}
        if callback_data not in contact_flow_actions:
            _clear_business_contact_state(context)

        if (
            user
            and user.id != config.ADMIN_TELEGRAM_ID
            and callback_data in contact_flow_actions
            and not _has_pdn_consent(
                consent_state
                if consent_state is not None
                else (database.db.get_user_consent_state(user_db_id) if user_db_id else {})
            )
        ):
            await utils.safe_reply_html(
                query.message,
                f"{content.pdn_consent_required_text('Консультации и передаче контакта')}\n\n{content.CONSENT_STEP_1_TEXT}",
                reply_markup=InlineKeyboardMarkup(CONSENT_PDN_MENU),
                action="menu_requires_pdn",
            )
            return

        if callback_data == "menu_restart":
            if user_db_id:
                database.db.clear_conversation_history(user_db_id)
                database.db.reset_user_funnel_state(user_db_id)
            restart_text = "Историю очистил. Начинаем заново. Опишите задачу одним сообщением."
            if is_business:
                await _send_business_menu_message(restart_text, menu_markup)
            else:
                await utils.safe_edit_text(
                    query.message,
                    restart_text,
                    reply_markup=menu_markup,
                    action="menu_restart",
                )
            return

        if callback_data == "menu_return_to_bot":
            chat_id = getattr(getattr(query, "message", None), "chat", None)
            chat_id = getattr(chat_id, "id", None)
            if chat_id is not None:
                database.db.set_chat_mode(int(chat_id), "bot")

            if user_db_id:
                database.db.reset_user_funnel_state(user_db_id)

            if is_business:
                response_text = content.build_business_welcome_message(user.first_name if user else "клиент")
            else:
                response_text = content.build_welcome_message(user.first_name if user else "клиент")
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_reply_html(
                    query.message,
                    response_text,
                    action="menu_return_to_bot",
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_MENU if user and user.id == config.ADMIN_TELEGRAM_ID else MAIN_MENU,
                        resize_keyboard=True,
                    ),
                )
            return

        if callback_data == "menu_dashboard":
            response_text = content.build_workspace_text(lead=lead, selected_profile=selected_profile)
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    response_text,
                    reply_markup=menu_markup,
                    action="menu_dashboard",
                )
            return

        if callback_data == "menu_profile":
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить профиль. Нажмите /start и повторите.",
                    action="menu_profile_no_user",
                )
                return
            user_row = local_user or database.db.get_local_user_by_id(user_db_id) or {}
            lead = database.db.get_local_lead_by_user_id(user_db_id)
            consent_state = database.db.get_user_consent_state(user_db_id)
            response_text = _build_client_profile_text(user_row, lead, consent_state)
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_edit_text(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=menu_markup,
                    action="menu_profile",
                )
            return

        if callback_data == "menu_documents":
            response_text = _documents_panel_text()
            docs_markup = _documents_panel_markup()
            if is_business:
                await _send_business_menu_message(response_text, docs_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    response_text,
                    reply_markup=docs_markup,
                    action="menu_documents",
                )
            return

        if callback_data == "menu_contract_ai":
            response_text = (
                f"{content.menu_response_by_key('menu_contract_ai', lead=lead, selected_profile=selected_profile)}\n\n"
                f"{content.LEAD_MAGNET_OFFER_TEXT}"
            )
            response_markup = _with_channel_button(InlineKeyboardMarkup(LEAD_MAGNET_MENU))
            response_markup = append_inline_url_row(
                response_markup,
                content.CONTRACT_AI_BUTTON_TEXT,
                content.contract_ai_public_url(),
                prepend=True,
            )
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_contract_ai",
                )
            return

        if callback_data in {"menu_contact_send_phone", "menu_contact_telegram_only"}:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="contact_choice_no_user",
                )
                return

            if callback_data == "menu_contact_send_phone":
                pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
                source = pending_contact.get("source") or "consultation"
                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = source
                response_text = (
                    "Отлично, пришлите номер телефона.\n"
                    f"{_business_phone_format_text()}"
                )
                response_markup = menu_markup if is_business else _consultation_contact_markup()
            else:
                pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
                previous_lead = database.db.get_lead_by_user_id(user_db_id) or {}
                notes_parts = []
                if pending_contact.get("notes"):
                    notes_parts.append(str(pending_contact["notes"]).strip())
                notes_parts.append("[CONTACT_MODE] Клиент выбрал связь через Telegram без телефона")
                lead_payload = {
                    "name": user.first_name if user else None,
                    "email": previous_lead.get("email"),
                    "company": previous_lead.get("company"),
                    "pain_point": pending_contact.get("pain_point") or previous_lead.get("pain_point"),
                    "temperature": "warm",
                    "status": "new",
                    "notification_sent": 0,
                    "lead_magnet_type": pending_contact.get("lead_magnet_type") or previous_lead.get("lead_magnet_type") or "consultation",
                    "lead_magnet_delivered": 1,
                    "notes": "\n".join(part for part in notes_parts if part).strip(),
                }
                lead_id = database.db.create_new_lead(user_db_id, lead_payload)
                user_state = database.db.get_user_funnel_state(user_db_id)
                cta_variant = user_state.get("cta_variant") or funnel.choose_cta_variant(user_db_id)
                database.db.update_user_funnel_state(
                    user_db_id,
                    conversation_stage="handoff",
                    cta_variant=cta_variant,
                    cta_shown=True,
                )
                database.db.update_lead_funnel_state_by_id(
                    lead_id,
                    conversation_stage="handoff",
                    cta_variant=cta_variant,
                    cta_shown=True,
                )
                try:
                    database.db.track_event(
                        user_db_id,
                        "contact_via_telegram_only",
                        payload={"source": pending_contact.get("source") or "business_contact_choice"},
                        lead_id=lead_id,
                    )
                except (sqlite3.Error, KeyError) as analytics_error:
                    logger.warning(f"Failed to track contact_via_telegram_only: {analytics_error}")

                refreshed_lead = database.db.get_lead_by_id(lead_id) or {}
                await notify_admin_new_lead(
                    context=context,
                    lead_id=lead_id,
                    lead_data=refreshed_lead,
                    user_data={
                        "id": user_db_id,
                        "telegram_id": user.id if user else None,
                        "username": user.username if user else None,
                        "first_name": user.first_name if user else None,
                    },
                    is_update=False,
                )
                _clear_business_contact_state(context)
                response_text = (
                    "Принято. Передал команде, что с вами лучше связаться в Telegram.\n"
                    "Если захотите ускорить связь, можете в любой момент отправить номер."
                )
                response_text = content.with_channel_nurture(response_text, after_contact=True)
                response_markup = _with_channel_button(menu_markup)

            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action=f"{callback_data}_reply",
                    reply_markup=response_markup,
                )
            return

        if callback_data == "menu_personal_request":
            chat = getattr(query.message, "chat", None)
            chat_id = getattr(chat, "id", None)
            if chat_id is not None:
                database.db.set_chat_mode(int(chat_id), "personal")

            _clear_business_contact_state(context)

            response_text = (
                "Чат переведен в личный режим.\n\n"
                "Теперь можете писать Андрею напрямую: бот не будет отвечать и не будет "
                "обрабатывать сообщения как лиды.\n\n"
                "Когда захотите снова пользоваться ботом, нажмите «↩️ Вернуться к боту»."
            )
            response_markup = _personal_mode_markup()
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action="menu_personal_request_mode_on",
                    reply_markup=response_markup,
                )
            return

        if callback_data in contact_actions:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="contact_action_no_user",
                )
                return
            contact_source = "consultation"
            notes = None
            lead_magnet_type = "consultation"
            if callback_data == "menu_leave_contact":
                existing_lead = database.db.get_lead_by_user_id(user_db_id) or {}
                if existing_lead.get("lead_magnet_type") == "personal_request":
                    lead_magnet_type = "personal_request"
                    notes = existing_lead.get("notes") or "Личное обращение к Андрею Попову"
                    contact_source = "personal_request"

            if callback_data == "menu_leave_contact":
                instant_note = (
                    "Клиент нажал кнопку «Оставить контакт» и запросил связь с командой."
                    if lead_magnet_type != "personal_request"
                    else "Клиент нажал кнопку «Оставить контакт» для личного обращения."
                )
                _clear_business_contact_state(context)
                context.user_data[BUSINESS_PENDING_CONTACT_KEY] = {
                    "source": contact_source,
                    "lead_magnet_type": lead_magnet_type,
                    "notes": instant_note if not notes else f"{notes}\n{instant_note}".strip(),
                    "pain_point": instant_note,
                }
                response_text = (
                    "Как удобнее передать контакт для связи?\n\n"
                    "Если номер скрыт в настройках Telegram, просто выберите вариант ниже."
                )
                response_markup = _contact_visibility_choice_markup()
            else:
                lead_payload = {
                    "name": user.first_name if user else None,
                    "lead_magnet_type": lead_magnet_type,
                    "lead_magnet_delivered": False,
                    "notification_sent": 0,
                }
                if notes:
                    lead_payload["notes"] = notes
                database.db.create_or_update_lead(user_db_id, lead_payload)

                context.user_data.pop(BUSINESS_PENDING_CONTACT_KEY, None)
                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = contact_source
                response_text = (
                    "Отлично, пришлите номер телефона.\n"
                    f"{_business_phone_format_text()}"
                )
                response_markup = menu_markup if is_business else _consultation_contact_markup()

            if is_business:
                await _send_business_menu_message(
                    response_text,
                    response_markup if callback_data == "menu_leave_contact" else menu_markup,
                )
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action=f"{callback_data}_reply",
                    reply_markup=(
                        response_markup
                        if callback_data == "menu_leave_contact"
                        else _consultation_contact_markup()
                    ),
                )
            return

        if is_business:
            reply_markup = (
                _with_channel_button(menu_markup)
                if callback_data in {"menu_services", "menu_prices", "menu_help"}
                else menu_markup
            )
            await _send_business_menu_message(response_text, reply_markup)
        else:
            reply_markup = (
                _with_channel_button(menu_markup)
                if callback_data in {"menu_services", "menu_prices", "menu_help"}
                else menu_markup
            )
            await utils.safe_edit_html(
                query.message,
                response_text,
                reply_markup=reply_markup,
                action=f"{callback_data}_edit",
            )
        log_span_timing(
            "lead.menu.callback",
            started_at,
            ok=True,
            callback_data=callback_data or "unknown",
            business_mode=is_business,
        )
            
    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as e:
        log_span_timing(
            "lead.menu.callback",
            started_at,
            ok=False,
            error=type(e).__name__,
            force=True,
            callback_data=callback_data or "unknown",
        )
        logger.error(f"Error in handle_business_menu_callback: {e}")



async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback-обработчик редактирования полей профиля пользователя."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="profile_edit_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer profile callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(query.message, "Сначала выполните /start.", action="profile_edit_no_user")
        return

    action = query.data or ""
    cancel_markup = ReplyKeyboardMarkup(
        [[KeyboardButton("⬅️ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if action == "profile_edit_name":
        context.user_data["profile_edit_field"] = "name"
        await utils.safe_reply_text(
            query.message,
            "Введите корректные ФИО одной строкой.\nНапример: Иван Иванов\n\nДля выхода нажмите «⬅️ Отмена».",
            reply_markup=cancel_markup,
            action="profile_edit_name_prompt",
        )
        return

    if action == "profile_edit_email":
        context.user_data["profile_edit_field"] = "email"
        await utils.safe_reply_text(
            query.message,
            "Введите корректный email.\nНапример: user@example.com\n\nДля выхода нажмите «⬅️ Отмена».",
            reply_markup=cancel_markup,
            action="profile_edit_email_prompt",
        )
        return

    await utils.safe_reply_text(query.message, "Неизвестное действие профиля.", action="profile_edit_unknown")


async def handle_lead_magnet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора lead magnet"""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="lead_magnet_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer lead magnet callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)

    if not user_data:
        await utils.safe_reply_text(query.message, "Ошибка. Попробуйте /start", action="lead_magnet_no_user")
        return

    if user.id != config.ADMIN_TELEGRAM_ID and not _has_pdn_consent(database.db.get_user_consent_state(user_data["id"])):
        await utils.safe_reply_text(
            query.message,
            f"{content.pdn_consent_required_text('получению материалов и фиксации заявки')}\n\n{content.CONSENT_STEP_1_TEXT}",
            reply_markup=InlineKeyboardMarkup(CONSENT_PDN_MENU),
            action="lead_magnet_requires_pdn",
        )
        return

    magnet_type = query.data.replace("magnet_", "")
    if magnet_type == "demo_analysis":
        magnet_type = "demo"
    if magnet_type == "report_sample":
        magnet_type = "sample_report"

    # Сохраняем выбор lead magnet
    lead = database.db.get_lead_by_user_id(user_data['id'])
    if not lead:
        lead_id = database.db.create_or_update_lead(
            user_data["id"],
            {"name": user.first_name, "lead_magnet_type": magnet_type, "lead_magnet_delivered": False},
        )
        lead = database.db.get_lead_by_id(lead_id)
    else:
        lead_qualifier.lead_qualifier.update_lead_magnet(lead["id"], magnet_type)
        lead_id = lead["id"]

    lead_payload = database.db.get_lead_by_id(lead_id) or {}
    await notify_admin_new_lead(
        context=context,
        lead_id=lead_id,
        lead_data=lead_payload,
        user_data=user_data,
        is_update=bool(lead),
    )

    funnel_state = database.db.get_user_funnel_state(user_data['id'])
    cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user_data['id'])
    current_stage = funnel_state.get('conversation_stage') or 'discover'
    target_stage = 'handoff' if magnet_type == 'consultation' else 'propose'
    next_stage = funnel.advance_stage(current_stage, target_stage)

    database.db.update_user_funnel_state(
        user_data['id'],
        conversation_stage=next_stage,
        cta_variant=cta_variant,
        cta_shown=True,
    )
    database.db.update_lead_funnel_state(
        user_data['id'],
        conversation_stage=next_stage,
        cta_variant=cta_variant,
        cta_shown=True,
    )

    try:
        if not funnel_state.get("cta_shown"):
            database.db.track_event(
                user_data["id"],
                "cta_shown",
                payload={"variant": cta_variant, "stage": current_stage, "source": "implicit_by_click"},
                lead_id=lead_id,
            )

        database.db.track_event(
            user_data['id'],
            "cta_clicked",
            payload={
                "variant": cta_variant,
                "magnet_type": magnet_type,
                "from_stage": current_stage,
                "to_stage": next_stage,
            },
            lead_id=lead_id
        )
        if next_stage != current_stage:
            database.db.track_event(
                user_data['id'],
                "stage_changed",
                payload={"from": current_stage, "to": next_stage, "reason": "cta_clicked"},
                lead_id=lead_id
            )
    except (sqlite3.Error, KeyError) as analytics_error:
        logger.warning(f"Failed to track CTA click analytics: {analytics_error}")

    selection_text = content.LEAD_MAGNET_SELECTION_MESSAGES.get(magnet_type, "Спасибо!")
    consultation_markup = None
    if magnet_type == "consultation" and (not query.message or not getattr(query.message, "business_connection_id", None)):
        consultation_markup = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Отправить телефон", request_contact=True)],
                [KeyboardButton("⬅️ Отмена")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    if query.message and hasattr(query.message, "business_connection_id") and query.message.business_connection_id:
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=selection_text,
            business_connection_id=query.message.business_connection_id,
        )
    else:
        await utils.safe_reply_text(
            query.message,
            selection_text,
            action="lead_magnet_selection",
            reply_markup=consultation_markup,
        )



async def handle_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для согласий на ПД и трансграничную передачу."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="consent_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer consent callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        user_id = database.db.create_or_update_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        user_data = database.db.get_user_by_id(user_id)

    if not user_data:
        await utils.safe_reply_text(
            query.message,
            "Ошибка инициализации профиля. Нажмите /start еще раз.",
            action="consent_profile_error",
        )
        return

    action = query.data or ""

    if action == "consent_doc_privacy":
        await utils.safe_reply_html(query.message, content.privacy_policy_text(), action="consent_doc_privacy")
        return

    if action == "consent_doc_transborder":
        await utils.safe_reply_html(query.message, content.transborder_policy_text(), action="consent_doc_transborder")
        return

    if action == "consent_pdn_no":
        await utils.safe_edit_html(query.message, content.CONSENT_DENIED_TEXT, action="consent_pdn_no")
        return

    if action == "consent_pdn_yes":
        database.db.grant_user_consent(user_data["id"])
        await utils.safe_edit_html(
            query.message,
            "<b>✅ Согласие на обработку ПД сохранено.</b>\n\n"
            "Теперь можно оставить заявку, передать контакт и получать материалы.\n"
            "Для ИИ-разбора кейса понадобится отдельное согласие на трансграничную передачу.",
            action="consent_pdn_yes",
        )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await utils.safe_reply_html(
            query.message,
            welcome_message,
            reply_markup=reply_markup,
            action="consent_welcome_after_yes",
        )
        await utils.safe_reply_html(
            query.message,
            content.build_workspace_text(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
                emphasize_profile_choice=True,
            ),
            reply_markup=_workspace_markup_for(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
            ),
            action="consent_workspace_after_yes",
        )
        await process_pending_start_payload(
            message=query.message,
            context=context,
            user_data=user_data,
            user=user,
        )
        return

    if action in ("consent_transborder_yes", "consent_transborder_no"):
        transborder_enabled = action == "consent_transborder_yes"
        database.db.set_user_transborder_consent(user_data["id"], transborder_enabled)
        if transborder_enabled:
            await utils.safe_edit_html(
                query.message,
                "<b>✅ Согласия сохранены.</b> ИИ-режим включен.\n\n"
                "Можно описать задачу в свободной форме, и я помогу сформировать следующий шаг.",
                action="consent_transborder_yes",
            )
        else:
            await utils.safe_edit_html(
                query.message,
                "<b>✅ Согласие на обработку ПД сохранено.</b>\n"
                "ИИ-режим отключен до вашего разрешения на трансграничную передачу.\n\n"
                "Можно пользоваться меню и оставить заявку на консультацию.",
                action="consent_transborder_no",
            )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await utils.safe_reply_html(
            query.message,
            welcome_message,
            reply_markup=reply_markup,
            action="consent_welcome_after_transborder",
        )
        await utils.safe_reply_html(
            query.message,
            content.build_workspace_text(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
                emphasize_profile_choice=True,
            ),
            reply_markup=_workspace_markup_for(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
            ),
            action="consent_workspace_after_transborder",
        )
        await process_pending_start_payload(
            message=query.message,
            context=context,
            user_data=user_data,
            user=user,
        )
        return

    await utils.safe_reply_text(query.message, "Неизвестное действие согласия. Попробуйте /start.", action="consent_unknown")


async def handle_documents_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для раздела документов/прав пользователя."""
    _ = context
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="documents_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer documents callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    action = query.data or ""

    if action == "doc_menu":
        await utils.safe_edit_html(
            query.message,
            _documents_panel_text(),
            reply_markup=_documents_panel_markup(),
            action="doc_menu",
        )
        return

    if action == "doc_privacy":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📄 Политика ПД", content.privacy_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_privacy",
        )
        return
    if action == "doc_transborder":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("🌍 Трансграничная передача", content.transborder_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_transborder",
        )
        return
    if action == "doc_user_agreement":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📜 Пользовательское соглашение", content.user_agreement_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_user_agreement",
        )
        return
    if action == "doc_ai_policy":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("🤖 Политика ИИ", content.ai_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_ai_policy",
        )
        return
    if action == "doc_marketing_consent":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(
                _documents_panel_text(
                    "📣 Согласие на рассылки",
                    content.marketing_consent_text(),
                )
            ),
            reply_markup=_documents_panel_markup(),
            action="doc_marketing_consent",
        )
        if user_data:
            database.db.set_user_marketing_consent(user_data["id"], True)
        return

    if not user_data:
        await utils.safe_edit_html(
            query.message,
            _documents_panel_text("⚠️ Ошибка", "Сначала выполните /start."),
            reply_markup=_documents_panel_markup(),
            action="doc_no_user",
        )
        return

    if action == "doc_consent_status":
        consent_state = database.db.get_user_consent_state(user_data["id"])
        is_admin = user.id == config.ADMIN_TELEGRAM_ID
        status_text = content.consent_status_text(consent_state) if is_admin else content.consent_user_status_text(consent_state)
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📑 Статус согласий", status_text)),
            reply_markup=_documents_panel_markup(),
            action="doc_consent_status",
        )
        return
    if action == "doc_export_data":
        payload = await admin_interface.admin_interface.export_user_data_async(user.id)
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📊 Экспорт данных", content.export_data_text(payload))),
            reply_markup=_documents_panel_markup(),
            action="doc_export_data",
        )
        return

    await utils.safe_edit_html(
        query.message,
        _documents_panel_text("⚠️ Неизвестное действие", "Используйте /documents."),
        reply_markup=_documents_panel_markup(),
        action="doc_unknown",
    )


async def handle_cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик cleanup операций"""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="cleanup_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer cleanup callback: {answer_error}")

    user = query.from_user

    # Проверка что это админ
    if user.id != config.ADMIN_TELEGRAM_ID:
        await utils.safe_reply_text(query.message, "У вас нет доступа к этой функции", action="cleanup_access_denied")
        return

    action = query.data

    try:
        if action == "cleanup_conversations":
            # Очистка всех диалогов
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
                logger.info(f"Admin {user.id} cleared {count} conversations")
            finally:
                conn.close()

        elif action == "cleanup_leads":
            # Очистка всех лидов
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
                logger.info(f"Admin {user.id} cleared {count} leads")
            finally:
                conn.close()

        elif action == "cleanup_logs":
            # Очистка логов без rename, чтобы FileHandler не потерял текущий файл.
            backup_file = _backup_and_truncate_log(config.LOG_FILE)
            if backup_file:
                await utils.safe_edit_text(
                    query.message,
                    f"✅ Логи очищены\nBackup: {backup_file}",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_logs",
                )
                logger.info(f"Admin {user.id} cleared logs, backup: {backup_file}")
            else:
                await utils.safe_edit_text(
                    query.message,
                    "Файл логов не найден",
                    reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                    action="cleanup_logs_not_found",
                )

        elif action == "cleanup_security":
            # Сброс счетчиков безопасности
            security.security_manager.reset_runtime_state(clear_blacklist=True)

            new_time = security.security_manager.stats_start_time.strftime("%d.%m.%Y %H:%M")
            await utils.safe_edit_text(
                query.message,
                f"✅ Счетчики безопасности сброшены\n📅 Статистика теперь с: {new_time}",
                reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                action="cleanup_security",
            )
            logger.info(f"Admin {user.id} reset security counters")

        elif action == "cleanup_all":
            # Очистка всего
            conn = database.db.get_connection()
            cursor = conn.cursor()

            try:
                # Диалоги
                cursor.execute("DELETE FROM conversations")
                conv_count = cursor.rowcount

                # Лиды
                cursor.execute("DELETE FROM leads")
                leads_count = cursor.rowcount

                # Уведомления
                cursor.execute("DELETE FROM admin_notifications")
                notif_count = cursor.rowcount

                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise
            finally:
                conn.close()

            # Логи
            backup_file = _backup_and_truncate_log(config.LOG_FILE)

            # Безопасность
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
            logger.warning(f"Admin {user.id} cleared ALL data")

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, IOError) as e:
        logger.error(f"Error in handle_cleanup_callback: {e}")
        await utils.safe_reply_text(query.message, f"Ошибка: {str(e)}", action="cleanup_error")
