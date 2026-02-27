"""
Handlers: callbacks
"""
import logging
import os
import shutil
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
import content
import funnel
from handlers.constants import *
from handlers.helpers import notify_admin_new_lead

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


def _services_inline_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Услуги", callback_data="menu_services")],
            [InlineKeyboardButton("💰 Цены", callback_data="menu_prices")],
            [InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation")],
            [InlineKeyboardButton("📲 Оставить контакт", callback_data="menu_leave_contact")],
            [InlineKeyboardButton("✉️ Личное обращение", callback_data="menu_personal_request")],
            [InlineKeyboardButton("🔄 Начать сначала", callback_data="menu_restart")],
            [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
        ]
    )


def _contact_visibility_choice_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📲 Оставить номер телефона", callback_data="menu_contact_send_phone")],
            [InlineKeyboardButton("💬 Связаться в Telegram", callback_data="menu_contact_telegram_only")],
            [InlineKeyboardButton("🔄 Начать сначала", callback_data="menu_restart")],
        ]
    )


def _consultation_contact_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📲 Отправить телефон", request_contact=True)],
            [KeyboardButton("⬅️ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _admin_lookup_menu_markup(back_callback: str, back_label: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🗂️ Карточка по ID", callback_data="admin_lookup_card_prompt")],
        [InlineKeyboardButton("💬 История диалога по ID", callback_data="admin_lookup_dialog_prompt")],
        [InlineKeyboardButton("✏️ Редактировать ПД", callback_data="admin_lookup_edit_prompt")],
        [InlineKeyboardButton("🗑️ Отозвать согласие по ID", callback_data="admin_lookup_revoke_prompt")],
        [InlineKeyboardButton("👥 Открыть список пользователей", callback_data="admin_users_list")],
        [InlineKeyboardButton(back_label, callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(rows)


def _clear_admin_lookup_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_lookup_action", None)
    context.user_data.pop("admin_lookup_field", None)


async def _create_and_notify_instant_contact_lead(
    context: ContextTypes.DEFAULT_TYPE,
    user_db_id: int,
    user,
    *,
    source: str,
    lead_magnet_type: str,
    note: str,
) -> tuple[int, bool]:
    """
    Создает новый лид в 1 клик по кнопке "Оставить контакт" и сразу уведомляет админа.
    """
    previous_lead = database.db.get_lead_by_user_id(user_db_id) or {}
    user_state = database.db.get_user_funnel_state(user_db_id)
    cta_variant = user_state.get("cta_variant") or funnel.choose_cta_variant(user_db_id)

    payload = {
        "name": user.first_name if user else None,
        "email": previous_lead.get("email"),
        "phone": previous_lead.get("phone"),
        "company": previous_lead.get("company"),
        "pain_point": note,
        "temperature": "warm",
        "status": "new",
        "notification_sent": 0,
        "lead_magnet_type": lead_magnet_type,
        "lead_magnet_delivered": 1,
        "notes": f"[ONE_CLICK_CONTACT] {source}",
    }
    lead_id = database.db.create_new_lead(user_db_id, payload)

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
            "one_click_contact",
            payload={"source": source, "lead_magnet_type": lead_magnet_type},
            lead_id=lead_id,
        )
    except Exception as analytics_error:
        logger.warning(f"Failed to track one_click_contact: {analytics_error}")

    lead_payload = database.db.get_lead_by_id(lead_id) or {}
    await notify_admin_new_lead(
        context=context,
        lead_id=lead_id,
        lead_data=lead_payload,
        user_data={
            "id": user_db_id,
            "telegram_id": user.id if user else None,
            "username": user.username if user else None,
            "first_name": user.first_name if user else None,
        },
        is_update=False,
    )
    has_phone = bool((lead_payload.get("phone") or "").strip())
    return lead_id, has_phone


async def handle_business_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик inline кнопок меню для бизнес-чатов
    """
    try:
        query = update.callback_query
        try:
            await utils.safe_answer_callback(query, action="business_menu_answer")
        except Exception as answer_error:
            logger.warning(f"Failed to answer business menu callback: {answer_error}")
        
        callback_data = query.data or ""
        response_text = content.menu_response_by_key(callback_data)
        menu_markup = _services_inline_menu_markup()
        contact_actions = {"menu_consultation", "menu_personal_request", "menu_leave_contact"}

        is_business = bool(
            query.message
            and hasattr(query.message, "business_connection_id")
            and query.message.business_connection_id
        )

        user = query.from_user
        user_db_id = None
        if user:
            user_db_id = database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )

        if callback_data not in contact_actions:
            context.user_data.pop(BUSINESS_AWAITING_CONTACT_KEY, None)
            context.user_data.pop(BUSINESS_AWAITING_CONTACT_SOURCE_KEY, None)

        if callback_data == "menu_restart":
            if user_db_id:
                database.db.clear_conversation_history(user_db_id)
                database.db.reset_user_funnel_state(user_db_id)
            restart_text = "Историю очистил. Начинаем заново. Опишите задачу одним сообщением."
            if is_business:
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text=restart_text,
                    business_connection_id=query.message.business_connection_id,
                    reply_markup=menu_markup,
                )
            else:
                await utils.safe_edit_text(
                    query.message,
                    restart_text,
                    reply_markup=menu_markup,
                    action="menu_restart",
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
                latest_lead = database.db.get_lead_by_user_id(user_db_id) or {}
                source = "personal_request" if latest_lead.get("lead_magnet_type") == "personal_request" else "consultation"
                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = source
                response_text = (
                    "Отлично, пришлите номер телефона одним сообщением.\n"
                    "Пример: +7 999 123-45-67."
                )
                response_markup = menu_markup if is_business else _consultation_contact_markup()
            else:
                context.user_data.pop(BUSINESS_AWAITING_CONTACT_KEY, None)
                context.user_data.pop(BUSINESS_AWAITING_CONTACT_SOURCE_KEY, None)
                latest_lead = database.db.get_lead_by_user_id(user_db_id) or {}
                if latest_lead:
                    notes = (latest_lead.get("notes") or "").strip()
                    notes = f"{notes}\n[CONTACT_MODE] Клиент выбрал связь через Telegram без телефона".strip()
                    database.db.create_or_update_lead(user_db_id, {"notes": notes, "notification_sent": 0})
                    refreshed_lead = database.db.get_lead_by_user_id(user_db_id) or latest_lead
                    await notify_admin_new_lead(
                        context=context,
                        lead_id=refreshed_lead["id"],
                        lead_data=refreshed_lead,
                        user_data={
                            "id": user_db_id,
                            "telegram_id": user.id if user else None,
                            "username": user.username if user else None,
                            "first_name": user.first_name if user else None,
                        },
                        is_update=True,
                    )
                response_text = (
                    "Принято. Передал команде, что с вами лучше связаться в Telegram.\n"
                    "Если захотите ускорить связь, можете в любой момент отправить номер."
                )
                response_markup = menu_markup

            if is_business:
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text=response_text,
                    business_connection_id=query.message.business_connection_id,
                    reply_markup=response_markup,
                )
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action=f"{callback_data}_reply",
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
            if callback_data == "menu_personal_request":
                lead_magnet_type = "personal_request"
                notes = "Личное обращение к Андрею Попову"
                contact_source = "personal_request"
            elif callback_data == "menu_leave_contact":
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
                _, has_phone = await _create_and_notify_instant_contact_lead(
                    context=context,
                    user_db_id=user_db_id,
                    user=user,
                    source=contact_source,
                    lead_magnet_type=lead_magnet_type,
                    note=instant_note,
                )
                context.user_data.pop(BUSINESS_AWAITING_CONTACT_KEY, None)
                context.user_data.pop(BUSINESS_AWAITING_CONTACT_SOURCE_KEY, None)
                if has_phone:
                    response_text = (
                        "✅ Контакт передан команде.\n\n"
                        "Мы свяжемся с вами в ближайшее рабочее время."
                    )
                    response_markup = menu_markup
                else:
                    response_text = (
                        "⚠️ Контакт передан, но номер телефона не удалось получить "
                        "(он может быть скрыт в настройках Telegram).\n\n"
                        "Выберите, как удобнее продолжить:"
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

                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = contact_source

            if is_business:
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text=response_text,
                    business_connection_id=query.message.business_connection_id,
                    reply_markup=response_markup if callback_data == "menu_leave_contact" else menu_markup,
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
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=response_text,
                business_connection_id=query.message.business_connection_id,
                reply_markup=menu_markup,
            )
        else:
            await utils.safe_edit_text(
                query.message,
                response_text,
                reply_markup=menu_markup,
                action=f"{callback_data}_edit",
            )
            
    except Exception as e:
        logger.error(f"Error in handle_business_menu_callback: {e}")



async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback-обработчик редактирования полей профиля пользователя."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="profile_edit_answer")
    except Exception as answer_error:
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
    except Exception as answer_error:
        logger.warning(f"Failed to answer lead magnet callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)

    if not user_data:
        await utils.safe_reply_text(query.message, "Ошибка. Попробуйте /start", action="lead_magnet_no_user")
        return

    magnet_type = query.data.replace("magnet_", "")
    if magnet_type == "demo_analysis":
        magnet_type = "demo"

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
    except Exception as analytics_error:
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
    except Exception as answer_error:
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
        await utils.safe_reply_text(query.message, content.privacy_policy_text(), action="consent_doc_privacy")
        return

    if action == "consent_doc_transborder":
        await utils.safe_reply_text(query.message, content.transborder_policy_text(), action="consent_doc_transborder")
        return

    if action == "consent_pdn_no":
        await utils.safe_edit_text(query.message, content.CONSENT_DENIED_TEXT, action="consent_pdn_no")
        return

    if action == "consent_pdn_yes":
        database.db.grant_user_consent(user_data["id"])
        database.db.set_user_transborder_consent(user_data["id"], True)
        await utils.safe_edit_text(
            query.message,
            "✅ Согласие на обработку ПД и трансграничную передачу сохранено.\n\n"
            "AI-режим включен. Можно описать задачу в свободной форме.",
            action="consent_pdn_yes",
        )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await utils.safe_reply_text(
            query.message,
            welcome_message,
            reply_markup=reply_markup,
            action="consent_welcome_after_yes",
        )
        return

    if action in ("consent_transborder_yes", "consent_transborder_no"):
        transborder_enabled = action == "consent_transborder_yes"
        database.db.set_user_transborder_consent(user_data["id"], transborder_enabled)
        if transborder_enabled:
            await utils.safe_edit_text(
                query.message,
                "✅ Согласия сохранены. AI-режим включен.\n\n"
                "Можно описать задачу в свободной форме, и я помогу сформировать следующий шаг.",
                action="consent_transborder_yes",
            )
        else:
            await utils.safe_edit_text(
                query.message,
                "✅ Согласие на обработку ПД сохранено.\n"
                "ИИ-режим отключен до вашего разрешения на трансграничную передачу.\n\n"
                "Можно пользоваться меню и оставить заявку на консультацию.",
                action="consent_transborder_no",
            )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await utils.safe_reply_text(
            query.message,
            welcome_message,
            reply_markup=reply_markup,
            action="consent_welcome_after_transborder",
        )
        return

    await utils.safe_reply_text(query.message, "Неизвестное действие согласия. Попробуйте /start.", action="consent_unknown")


def _documents_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(DOCUMENTS_MENU)


def _documents_panel_text(selected_title: str | None = None, selected_body: str | None = None) -> str:
    base = (
        "📚 Документы и права пользователя\n\n"
        "Выберите пункт в меню ниже."
    )
    if not selected_title:
        return base
    return (
        f"{base}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"{selected_title}\n\n"
        f"{selected_body or ''}"
    ).strip()


def _clip_for_edit(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n\n…\n(Сокращено для экрана. Полная версия доступна через соответствующую команду.)"


def _admin_users_list_markup(users: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    for user in users:
        telegram_id = user.get("telegram_id")
        username = user.get("username")
        label = f"👤 ID {telegram_id} - @{username}" if username else f"👤 ID {telegram_id}"
        rows.append([InlineKeyboardButton(label[:60], callback_data=f"admin_user_detail_{telegram_id}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"admin_users_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="admin_users_page_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"admin_users_page_{page + 1}"))
    rows.append(nav_row)
    rows.append([InlineKeyboardButton("◀️ Назад в раздел пользователей", callback_data="admin_section_users")])
    return InlineKeyboardMarkup(rows)


def _admin_user_detail_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Экспорт данных", callback_data=f"admin_user_export_{telegram_id}")],
            [InlineKeyboardButton("🔄 Сбросить диалог", callback_data=f"admin_user_reset_dialog_{telegram_id}")],
            [InlineKeyboardButton("🗑️ Очистить данные", callback_data=f"admin_user_clear_confirm_{telegram_id}")],
            [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
        ]
    )


def _admin_user_clear_confirm_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data=f"admin_user_clear_{telegram_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_user_detail_{telegram_id}"),
            ]
        ]
    )


def _fetch_users_page(page: int = 1, per_page: int = 5) -> tuple[list[dict], int, int]:
    page = max(1, page)
    offset = (page - 1) * per_page

    conn = database.db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total = int((cursor.fetchone() or {"total": 0})["total"])
        total_pages = max(1, (total + per_page - 1) // per_page)
        if page > total_pages:
            page = total_pages
            offset = (page - 1) * per_page

        cursor.execute(
            """
            SELECT *
            FROM users
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        )
        users = [dict(row) for row in cursor.fetchall()]
        return users, total, total_pages
    finally:
        conn.close()


def _build_admin_users_page_text(users: list[dict], page: int, total_pages: int, total_users: int) -> str:
    lines = [
        "👥 Пользователи",
        "",
        f"Всего пользователей: {total_users}",
        f"Страница: {page}/{total_pages}",
        "",
        "Нажмите на пользователя для подробной карточки.",
        "Поиск вручную: /pdn_user <telegram_id>",
        "",
    ]
    for user in users:
        username = f"@{user.get('username')}" if user.get("username") else "без username"
        lines.append(
            f"ID {user.get('telegram_id')} | {username}\n"
            f"Имя: {user.get('first_name') or '—'} {user.get('last_name') or ''}\n"
            f"Создан: {user.get('created_at') or '—'}\n"
        )
    return "\n".join(lines).strip()


def _get_user_conversation_count(user_id: int) -> int:
    conn = database.db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM conversations WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return int((row or {"total": 0})["total"])
    finally:
        conn.close()


def _build_admin_user_detail_text(target_user: dict, lead: dict | None, consent: dict, conversations_count: int) -> str:
    lead = lead or {}
    return (
        f"👤 Карточка пользователя ID {target_user.get('telegram_id')}\n\n"
        f"Username: @{target_user.get('username') or '—'}\n"
        f"Имя: {target_user.get('first_name') or '—'} {target_user.get('last_name') or ''}\n"
        f"Регистрация: {target_user.get('created_at') or '—'}\n"
        f"Последняя активность: {target_user.get('last_interaction') or '—'}\n\n"
        f"Сообщений в диалоге: {conversations_count}\n\n"
        "Lead:\n"
        f"• Имя: {lead.get('name') or '—'}\n"
        f"• Email: {lead.get('email') or '—'}\n"
        f"• Телефон: {lead.get('phone') or '—'}\n"
        f"• Компания: {lead.get('company') or '—'}\n"
        f"• Температура: {lead.get('temperature') or '—'}\n"
        f"• Статус: {lead.get('status') or '—'}\n\n"
        "Согласия:\n"
        f"• ПД: {'✅' if consent.get('consent_given') else '❌'}\n"
        f"• Трансграничная передача: {'✅' if consent.get('transborder_consent') else '❌'}\n"
        f"• Отзыв: {'✅' if consent.get('consent_revoked') else '❌'}"
    )


async def handle_documents_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для раздела документов/прав пользователя."""
    _ = context
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="documents_answer")
    except Exception as answer_error:
        logger.warning(f"Failed to answer documents callback: {answer_error}")

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    action = query.data or ""

    if action == "doc_menu":
        await utils.safe_edit_text(
            query.message,
            _documents_panel_text(),
            reply_markup=_documents_panel_markup(),
            action="doc_menu",
        )
        return

    if action == "doc_privacy":
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📄 Политика ПД", content.privacy_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_privacy",
        )
        return
    if action == "doc_transborder":
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("🌍 Трансграничная передача", content.transborder_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_transborder",
        )
        return
    if action == "doc_user_agreement":
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📜 Пользовательское соглашение", content.user_agreement_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_user_agreement",
        )
        return
    if action == "doc_ai_policy":
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("🤖 Политика ИИ", content.ai_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_ai_policy",
        )
        return
    if action == "doc_marketing_consent":
        await utils.safe_edit_text(
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
        await utils.safe_edit_text(
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
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📑 Статус согласий", status_text)),
            reply_markup=_documents_panel_markup(),
            action="doc_consent_status",
        )
        return
    if action == "doc_export_data":
        payload = database.db.export_user_data(user_data["id"])
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📊 Экспорт данных", content.export_data_text(payload))),
            reply_markup=_documents_panel_markup(),
            action="doc_export_data",
        )
        return

    await utils.safe_edit_text(
        query.message,
        _documents_panel_text("⚠️ Неизвестное действие", "Используйте /documents."),
        reply_markup=_documents_panel_markup(),
        action="doc_unknown",
    )


def _format_users_for_admin(title: str, users: list[dict]) -> str:
    if not users:
        return f"{title}\n\nПользователи не найдены."

    lines = [title, ""]
    for user in users:
        consent = "✅" if user.get("consent_given") else "❌"
        revoked = "🗑️" if user.get("consent_revoked") else "—"
        username = f"@{user.get('username')}" if user.get("username") else "без username"
        lines.append(
            f"ID: {user.get('telegram_id')} | {username}\n"
            f"Имя: {user.get('first_name') or '—'} {user.get('last_name') or ''}\n"
            f"Согласие ПД: {consent} | Отзыв: {revoked}\n"
            f"Последняя активность: {user.get('last_interaction') or user.get('created_at') or '—'}\n"
        )
    return "\n".join(lines).strip()


async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок админ-панели"""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="admin_panel_answer")
    except Exception as answer_error:
        logger.warning(f"Failed to answer admin callback: {answer_error}")

    user = query.from_user

    # Проверка что это админ
    if user.id != config.ADMIN_TELEGRAM_ID:
        await query.message.reply_text("У вас нет доступа к этой функции")
        return

    action = query.data

    try:
        users_page_match = re.fullmatch(r"admin_users_page_(\d+)", action or "")
        user_detail_match = re.fullmatch(r"admin_user_detail_(\d+)", action or "")
        user_export_match = re.fullmatch(r"admin_user_export_(\d+)", action or "")
        user_reset_match = re.fullmatch(r"admin_user_reset_dialog_(\d+)", action or "")
        user_clear_confirm_match = re.fullmatch(r"admin_user_clear_confirm_(\d+)", action or "")
        user_clear_match = re.fullmatch(r"admin_user_clear_(\d+)", action or "")

        if action == "admin_users_page_noop":
            return

        if action in {"admin_panel", "admin_section_users", "admin_section_commands"}:
            # При выходе в разделы сбрасываем активный режим интерактивного поиска.
            _clear_admin_lookup_state(context)

        if action == "admin_users_list" or users_page_match:
            requested_page = int(users_page_match.group(1)) if users_page_match else 1
            users, total_users, total_pages = _fetch_users_page(page=requested_page, per_page=5)
            current_page = min(max(1, requested_page), total_pages)
            users_text = _build_admin_users_page_text(users, current_page, total_pages, total_users)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(users_text),
                reply_markup=_admin_users_list_markup(users, current_page, total_pages),
                action=f"admin_users_list_{current_page}",
            )
            return

        if user_detail_match:
            telegram_id = int(user_detail_match.group(1))
            target_user = database.db.get_user_by_telegram_id(telegram_id)
            if not target_user:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_detail_not_found",
                )
                return

            lead = database.db.get_lead_by_user_id(target_user["id"]) or {}
            consent = database.db.get_user_consent_state(target_user["id"])
            conversations_count = _get_user_conversation_count(target_user["id"])
            detail_text = _build_admin_user_detail_text(target_user, lead, consent, conversations_count)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(detail_text),
                reply_markup=_admin_user_detail_markup(telegram_id),
                action="admin_user_detail",
            )
            return

        if user_export_match:
            telegram_id = int(user_export_match.group(1))
            target_user = database.db.get_user_by_telegram_id(telegram_id)
            if not target_user:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_export_not_found",
                )
                return

            payload = database.db.export_user_data(target_user["id"])
            export_text = (
                f"🧾 Экспорт данных пользователя ID {telegram_id}\n\n"
                f"{content.export_data_text(payload)}"
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(export_text),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("◀️ К карточке", callback_data=f"admin_user_detail_{telegram_id}")],
                        [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
                    ]
                ),
                action="admin_user_export",
            )
            return

        if user_reset_match:
            telegram_id = int(user_reset_match.group(1))
            target_user = database.db.get_user_by_telegram_id(telegram_id)
            if not target_user:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_reset_not_found",
                )
                return

            database.db.clear_conversation_history(target_user["id"])
            database.db.reset_user_funnel_state(target_user["id"])

            lead = database.db.get_lead_by_user_id(target_user["id"]) or {}
            consent = database.db.get_user_consent_state(target_user["id"])
            detail_text = (
                "✅ Диалог пользователя сброшен.\n\n"
                + _build_admin_user_detail_text(target_user, lead, consent, 0)
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(detail_text),
                reply_markup=_admin_user_detail_markup(telegram_id),
                action="admin_user_reset_dialog",
            )
            return

        if user_clear_confirm_match:
            telegram_id = int(user_clear_confirm_match.group(1))
            await utils.safe_edit_text(
                query.message,
                (
                    f"⚠️ Подтвердите очистку данных пользователя ID {telegram_id}\n\n"
                    "Будут удалены сообщения диалога и анонимизированы данные лида.\n"
                    "Действие необратимо."
                ),
                reply_markup=_admin_user_clear_confirm_markup(telegram_id),
                action="admin_user_clear_confirm",
            )
            return

        if user_clear_match:
            telegram_id = int(user_clear_match.group(1))
            target_user = database.db.get_user_by_telegram_id(telegram_id)
            if not target_user:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_clear_not_found",
                )
                return

            result = database.db.revoke_user_consent_and_delete_data(target_user["id"])
            await utils.safe_edit_text(
                query.message,
                (
                    f"✅ Данные пользователя ID {telegram_id} очищены.\n\n"
                    f"Изменено профилей: {result.get('users_updated', 0)}\n"
                    f"Анонимизировано анкет: {result.get('leads_anonymized', 0)}\n"
                    f"Удалено сообщений: {result.get('messages_deleted', 0)}"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("◀️ К карточке", callback_data=f"admin_user_detail_{telegram_id}")],
                        [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
                    ]
                ),
                action="admin_user_clear",
            )
            return

        if action == "admin_section_leads":
            await utils.safe_edit_text(
                query.message,
                "📊 РАЗДЕЛ: ЛИДЫ И ВОРОНКА\n\nВыберите срез для просмотра:",
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_section_leads",
            )

        elif action == "admin_section_users":
            await utils.safe_edit_text(
                query.message,
                "👥 РАЗДЕЛ: ПОЛЬЗОВАТЕЛИ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_section_users",
            )

        elif action == "admin_section_export":
            await utils.safe_edit_text(
                query.message,
                "📥 РАЗДЕЛ: ЭКСПОРТ И ЛОГИ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                action="admin_section_export",
            )

        elif action == "admin_section_commands":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                (
                    "🧭 КОМАНДЫ И ПОИСК\n\n"
                    "Команды вручную больше не требуются.\n"
                    "Выберите действие кнопкой ниже, затем введите ID/значение по подсказке."
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_panel",
                    back_label="◀️ Назад в админ-панель",
                ),
                action="admin_section_commands",
            )

        elif action == "admin_users_recent":
            users = database.db.get_recent_users(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("🕒 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_recent",
            )

        elif action == "admin_users_no_consent":
            users = database.db.get_users_without_consent(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("⚠️ ПОЛЬЗОВАТЕЛИ БЕЗ СОГЛАСИЯ ПД (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_no_consent",
            )

        elif action == "admin_users_revoked":
            users = database.db.get_users_with_revoked_consent(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("🗑️ ОТОЗВАЛИ СОГЛАСИЕ (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_revoked",
            )

        elif action == "admin_users_lookup_help":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                (
                    "🔎 Поиск пользователя по ID\n\n"
                    "Выберите действие кнопкой ниже.\n"
                    "После выбора введите ID (и при необходимости новое значение)."
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_users_lookup_help",
            )

        elif action == "admin_lookup_card_prompt":
            context.user_data["admin_lookup_action"] = "card"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🗂️ Карточка по ID\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_card_prompt",
            )

        elif action == "admin_lookup_dialog_prompt":
            context.user_data["admin_lookup_action"] = "dialog"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "💬 История диалога по ID\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_dialog_prompt",
            )

        elif action == "admin_lookup_revoke_prompt":
            context.user_data["admin_lookup_action"] = "revoke"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🗑️ Отзыв согласия и очистка ПД\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_revoke_prompt",
            )

        elif action == "admin_lookup_edit_prompt":
            context.user_data["admin_lookup_action"] = "edit"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "✏️ Редактирование ПД\n\n"
                    "1) Выберите поле кнопкой ниже.\n"
                    "2) Затем отправьте сообщение в формате:\n"
                    "<telegram_id> <новое значение>\n\n"
                    "Пример: 321681061 new@email.com"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                action="admin_lookup_edit_prompt",
            )

        elif action and action.startswith("admin_lookup_edit_field_"):
            field = action.replace("admin_lookup_edit_field_", "", 1)
            valid_fields = {"first_name", "last_name", "username", "name", "email", "phone", "company"}
            if field not in valid_fields:
                await utils.safe_edit_text(
                    query.message,
                    "Неизвестное поле редактирования.",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                    action="admin_lookup_edit_field_invalid",
                )
            else:
                context.user_data["admin_lookup_action"] = "edit"
                context.user_data["admin_lookup_field"] = field
                await utils.safe_edit_text(
                    query.message,
                    (
                        f"✏️ Выбрано поле: `{field}`\n\n"
                        "Теперь отправьте сообщение:\n"
                        "<telegram_id> <новое значение>\n\n"
                        "Пример: 321681061 Новое значение"
                    ),
                    reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                    action="admin_lookup_edit_field_selected",
                )

        elif action == "admin_stats":
            stats_message = admin_interface.admin_interface.format_statistics(30)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(stats_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_stats",
            )

        elif action == "admin_funnel_report":
            report_message = admin_interface.admin_interface.format_funnel_report(30)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(report_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_funnel_report",
            )

        elif action == "admin_funnel_export_csv":
            csv_data = admin_interface.admin_interface.export_funnel_report_csv(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(
                document=csv_data.encode('utf-8'),
                filename=filename,
                caption="📥 Funnel report (CSV)"
            )

        elif action == "admin_funnel_export_md":
            md_data = admin_interface.admin_interface.export_funnel_report_markdown(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.md"
            await query.message.reply_document(
                document=md_data.encode('utf-8'),
                filename=filename,
                caption="📝 Funnel report (Markdown)"
            )

        elif action == "admin_security":
            stats = security.security_manager.get_stats()
            stats_since = stats['stats_start_time'].strftime("%d.%m.%Y %H:%M")
            stats_message = (
                "🛡️ СТАТИСТИКА БЕЗОПАСНОСТИ\n\n"
                f"📅 Статистика с: {stats_since}\n\n"
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
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(stats_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_security",
            )

        elif action == "admin_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_leads",
            )

        elif action == "admin_hot_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='hot', limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_hot_leads",
            )

        elif action == "admin_warm_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='warm', limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_warm_leads",
            )

        elif action == "admin_cold_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='cold', limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_cold_leads",
            )

        elif action == "admin_logs":
            import subprocess
            result = subprocess.run(['tail', '-50', config.LOG_FILE], capture_output=True, text=True)
            logs = result.stdout
            if not logs.strip():
                await utils.safe_edit_text(
                    query.message,
                    "📋 Логи пусты.",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                    action="admin_logs_empty",
                )
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await query.message.reply_document(
                    document=logs.encode("utf-8"),
                    filename=f"lead_bot_logs_tail_{timestamp}.txt",
                    caption="📋 Последние 50 строк логов",
                )

        elif action == "admin_export":
            csv_data = admin_interface.admin_interface.export_leads_to_csv()
            if csv_data:
                await query.message.reply_document(
                    document=csv_data.encode('utf-8') if isinstance(csv_data, str) else csv_data,
                    filename=f'leads_export_{datetime.now().strftime("%Y%m%d")}.csv',
                    caption="📥 Экспорт лидов"
                )
            else:
                await utils.safe_edit_text(
                    query.message,
                    "Ошибка при экспорте данных",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                    action="admin_export_error",
                )

        elif action == "admin_cleanup":
            cleanup_message = (
                "🗑️ ОЧИСТКА ДАННЫХ\n\n"
                "⚠️ ВНИМАНИЕ: Данные будут удалены безвозвратно!\n\n"
                "Выберите что очистить:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_CLEANUP_MENU)
            await utils.safe_edit_text(
                query.message,
                cleanup_message,
                reply_markup=reply_markup,
                action="admin_cleanup",
            )

        elif action == "admin_commands":
            await utils.safe_edit_text(
                query.message,
                (
                    "🧭 ДОСТУПНЫЕ АДМИН-КОМАНДЫ\n\n"
                    "/stats — общая статистика\n"
                    "/leads [hot|warm|cold] — список лидов\n"
                    "/export — выгрузка лидов в CSV\n"
                    "/view_conversation <telegram_id> — история диалога\n"
                    "/security_stats — статистика безопасности\n"
                    "/blacklist <telegram_id> [причина] — блокировка пользователя\n"
                    "/unblacklist <telegram_id> — снять блокировку\n"
                    "/pdn_user <telegram_id> — карточка ПД и согласий\n"
                    "/edit_pdn <telegram_id> <field> <value> — правка ПД\n"
                    "/revoke_user_consent <telegram_id> — отзыв согласия + очистка\n\n"
                    "Эти функции работают и доступны даже если не вынесены отдельной кнопкой."
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_commands",
            )

        elif action == "admin_panel":
            admin_panel_message = (
                "⚙️ АДМИН-ПАНЕЛЬ\n\n"
                "Выберите действие:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_PANEL_MENU)
            await utils.safe_edit_text(
                query.message,
                admin_panel_message,
                reply_markup=reply_markup,
                action="admin_panel",
            )

        elif action == "admin_close":
            await utils.safe_edit_text(query.message, "⚙️ Админ-панель закрыта", action="admin_close")

        else:
            await utils.safe_edit_text(
                query.message,
                "⚠️ Неизвестное действие админ-панели.",
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_unknown_action",
            )

    except Exception as e:
        logger.error(f"Error in handle_admin_panel_callback: {e}")
        await utils.safe_reply_text(query.message, f"Ошибка: {str(e)}", action="admin_panel_error")



async def handle_cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик cleanup операций"""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="cleanup_answer")
    except Exception as answer_error:
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
            security.security_manager.message_timestamps.clear()
            security.security_manager.token_usage.clear()
            security.security_manager.cooldowns.clear()
            security.security_manager.suspicious_users.clear()
            security.security_manager.blacklist.clear()
            security.security_manager.total_tokens_today = 0
            security.security_manager.reset_stats_time()

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
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()

            # Логи
            backup_file = _backup_and_truncate_log(config.LOG_FILE)

            # Безопасность
            security.security_manager.message_timestamps.clear()
            security.security_manager.token_usage.clear()
            security.security_manager.cooldowns.clear()
            security.security_manager.suspicious_users.clear()
            security.security_manager.blacklist.clear()
            security.security_manager.total_tokens_today = 0

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

    except Exception as e:
        logger.error(f"Error in handle_cleanup_callback: {e}")
        await utils.safe_reply_text(query.message, f"Ошибка: {str(e)}", action="cleanup_error")
