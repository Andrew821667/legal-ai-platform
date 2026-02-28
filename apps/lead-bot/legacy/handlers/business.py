"""
Handlers: business
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
from config import Config
config = Config()
import utils
import email_sender
import security
import prompts
import content
import funnel
from handlers.constants import *
from handlers.helpers import notify_admin_new_lead, extract_email

logger = logging.getLogger(__name__)
PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*(?:\d[\s\-()]*){10,11}")


def _schedule_business_typing(context: ContextTypes.DEFAULT_TYPE, message, user_id: int) -> None:
    """Неблокирующий typing-индикатор для бизнес-диалогов."""

    async def _send_typing() -> None:
        try:
            await asyncio.wait_for(
                context.bot.send_chat_action(
                    chat_id=message.chat.id,
                    action="typing",
                    business_connection_id=message.business_connection_id,
                ),
                timeout=1.5,
            )
            logger.info(f"[Business] Typing indicator sent for user {user_id}")
        except Exception as error:
            logger.debug(f"[Business] Typing indicator skipped for user {user_id}: {error}")

    asyncio.create_task(_send_typing())


def _append_profile_name_context(base_context: str, profile_first_name: str | None) -> str:
    name = (profile_first_name or "").strip()
    if name:
        return (
            f"{base_context}\n"
            f"Имя пользователя в профиле Telegram: {name}.\n"
            "Если обращаешься по имени, используй только это имя профиля Telegram. "
            "Не извлекай имя из текста сообщения клиента."
        )
    return (
        f"{base_context}\n"
        "Если обращаешься к пользователю, используй нейтральную форму без имени. "
        "Не извлекай имя из текста сообщения клиента."
    )


def _extract_phone_candidate(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None

    match = PHONE_RE.search(raw)
    if not match:
        # Фолбэк: если пользователь прислал только номер без +7/8 (например 9991234567).
        if re.fullmatch(r"[\d\s()+\-]{10,20}", raw):
            digits = re.sub(r"\D", "", raw)
            if 10 <= len(digits) <= 12:
                return digits
        return None
    return match.group(0)


def _persist_fasttrack_contact(user_db_id: int, first_name: str, text: str) -> None:
    payload = {}
    email = extract_email(text)
    if email:
        payload["email"] = email

    phone = _extract_phone_candidate(text)
    if phone and utils.validate_phone(phone):
        payload["phone"] = utils.format_phone(phone)

    if payload:
        payload.setdefault("name", first_name)
        database.db.create_or_update_lead(user_db_id, payload)


def _business_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Услуги", callback_data="menu_services"),
                InlineKeyboardButton("💰 Цены", callback_data="menu_prices"),
            ],
            [
                InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
                InlineKeyboardButton("📲 Контакт", callback_data="menu_leave_contact"),
            ],
            [
                InlineKeyboardButton("✉️ Личное обращение", callback_data="menu_personal_request"),
            ],
            [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
        ]
    )


def build_business_menu_markup() -> InlineKeyboardMarkup:
    """Публичный доступ к business-меню для роутера в bot.py."""
    return _business_menu_markup()


def _personal_mode_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(PERSONAL_MODE_RETURN_MENU)


def _clear_business_contact_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(BUSINESS_AWAITING_CONTACT_KEY, None)
    context.user_data.pop(BUSINESS_AWAITING_CONTACT_SOURCE_KEY, None)


def _looks_like_ack_only(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    ack_tokens = {
        "ок", "окей", "понял", "принял", "ясно", "спасибо", "благодарю",
        "хорошо", "договорились", "супер", "круто",
    }
    return normalized in ack_tokens


def _looks_like_plain_greeting(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in {
        "привет",
        "здравствуйте",
        "добрый день",
        "добрый вечер",
        "доброе утро",
        "hello",
        "hi",
    }


def _looks_like_return_to_bot(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in {
        "↩️ вернуться к боту",
        "вернуться к боту",
        "вернуться",
        "/bot",
        "бот",
    }


def _looks_like_new_topic_after_handoff(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    if _looks_like_ack_only(normalized):
        return False
    if _extract_phone_candidate(normalized):
        return False
    if normalized in {"/menu", "menu", "/меню", "меню", "/reset", "reset", "сброс"}:
        return False
    return len(normalized) >= 3


async def _send_business_handoff_and_notify(
    context: ContextTypes.DEFAULT_TYPE,
    message,
    user_db_id: int,
    user_telegram_id: int,
    username: str | None,
    first_name: str,
    source: str,
    *,
    is_update: bool,
) -> int:
    lead = database.db.get_lead_by_user_id(user_db_id)
    if not lead:
        lead_id = database.db.create_or_update_lead(user_db_id, {"name": first_name})
    else:
        lead_id = lead["id"]

    funnel_state = database.db.get_user_funnel_state(user_db_id)
    previous_stage = funnel_state.get("conversation_stage") or "discover"
    cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_db_id)

    database.db.update_user_funnel_state(
        user_db_id,
        conversation_stage="handoff",
        cta_variant=cta_variant,
    )
    database.db.update_lead_funnel_state(
        user_db_id,
        conversation_stage="handoff",
        cta_variant=cta_variant,
    )

    if previous_stage != "handoff":
        try:
            database.db.track_event(
                user_db_id,
                "stage_changed",
                payload={"from": previous_stage, "to": "handoff"},
                lead_id=lead_id,
            )
        except Exception as analytics_error:
            logger.warning(f"[Business] Failed to track handoff stage change: {analytics_error}")

    lead_payload = database.db.get_lead_by_id(lead_id) or {}
    await notify_admin_new_lead(
        context=context,
        lead_id=lead_id,
        lead_data=lead_payload,
        user_data={
            "id": user_db_id,
            "telegram_id": user_telegram_id,
            "username": username,
            "first_name": first_name,
        },
        is_update=is_update,
    )

    try:
        database.db.track_event(
            user_db_id,
            "handoff_done",
            payload={"source": source, "cta_variant": cta_variant},
            lead_id=lead_id,
        )
    except Exception as analytics_error:
        logger.warning(f"[Business] Failed to track handoff_done ({source}): {analytics_error}")

    return lead_id


def _is_business_processing_allowed(message) -> bool:
    connection_id = getattr(message, "business_connection_id", None)
    chat_id = getattr(getattr(message, "chat", None), "id", None)

    if not database.db.is_business_connection_enabled(connection_id):
        logger.info("[Business] Skip message: connection disabled (%s)", connection_id)
        return False
    if chat_id is not None and not database.db.is_chat_enabled(int(chat_id)):
        logger.info("[Business] Skip message: chat disabled (%s)", chat_id)
        return False
    return True


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подключения/отключения Business аккаунта"""
    try:
        if update.business_connection:
            connection = update.business_connection
            database.db.set_business_connection_state(
                connection_id=str(connection.id),
                user_chat_id=getattr(connection, "user_chat_id", None),
                is_enabled=bool(connection.is_enabled),
            )
            if connection.is_enabled:
                logger.info(f"✅ Business connection enabled: {connection.id} for user {connection.user_chat_id}")
                await context.bot.send_message(
                    chat_id=connection.user_chat_id,
                    text="✅ Бот успешно подключен к вашему Telegram Business аккаунту!\n\n"
                         "Теперь я буду автоматически отвечать на сообщения ваших клиентов."
                )
            else:
                logger.info(f"❌ Business connection disabled: {connection.id}")
                if getattr(connection, "user_chat_id", None):
                    await context.bot.send_message(
                        chat_id=connection.user_chat_id,
                        text="ℹ️ Business-автоответы отключены. Бот больше не будет отвечать в business-чатах.",
                    )
    except Exception as e:
        logger.error(f"Error in handle_business_connection: {e}", exc_info=True)



async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений через Business аккаунт"""
    try:
        if not update.business_message:
            return
            
        message = update.business_message
        if not _is_business_processing_allowed(message):
            return

        if not message.from_user:
            logger.info("[Business] Skip message without from_user, update=%s", update.update_id)
            return

        user_id = message.from_user.id
        text = message.text or ""
        
        logger.info(f"📨 Business message from {user_id}: {text}")
        
        # Получаем пользователя
        user = database.db.create_or_update_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        is_admin = user_id == config.ADMIN_TELEGRAM_ID
        allow_lead_processing = (not is_admin) or config.ALLOW_ADMIN_TEST_LEADS
        chat_id = getattr(getattr(message, "chat", None), "id", None)
        chat_mode = database.db.get_chat_mode(int(chat_id)) if chat_id is not None else "bot"
        
        # Обработка команды /start для бизнес-чата
        if text == "/start":
            _clear_business_contact_state(context)
            if chat_id is not None:
                database.db.set_chat_mode(int(chat_id), "bot")
            welcome_message = content.build_welcome_message(message.from_user.first_name)
            
            # Для бизнес-чатов используем InlineKeyboard (ReplyKeyboard не поддерживается)
            reply_markup = _business_menu_markup()
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=welcome_message,
                reply_markup=reply_markup,
                business_connection_id=message.business_connection_id
            )
            return
        
        # Обработка кнопок меню для бизнес-чата (удалено - используем callback)
        # Inline кнопки обрабатываются через callback_query
        
        # Обработка команды /menu для бизнес-чата
        if text.strip().lower() in ['/menu', 'menu', '/меню', 'меню']:
            reply_markup = _business_menu_markup()
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.MENU_HEADER_TEXT,
                reply_markup=reply_markup,
                business_connection_id=message.business_connection_id
            )
            logger.info(f"[Business] Menu shown to user {user_id}")
            return
        
        # Обработка команды сброса
        if text in {"🔄 Начать заново", "🔄 Начать сначала"} or text.strip().lower() in {"/reset", "reset", "сброс"}:
            _clear_business_contact_state(context)
            user_data = database.db.get_user_by_telegram_id(user_id)
            if user_data:
                database.db.clear_conversation_history(user_data['id'])
                database.db.reset_user_funnel_state(user_data['id'])
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="История диалога очищена. Начнем сначала!\n\nЧем могу помочь вам сегодня?",
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id
            )
            return

        if text == "✉️ Личное обращение":
            if chat_id is not None:
                database.db.set_chat_mode(int(chat_id), "personal")
            _clear_business_contact_state(context)
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=(
                    "Чат переведен в личный режим.\n\n"
                    "Теперь можете писать Андрею напрямую: бот не будет отвечать и не будет "
                    "обрабатывать сообщения как лиды.\n\n"
                    "Когда захотите снова пользоваться ботом, нажмите «↩️ Вернуться к боту»."
                ),
                reply_markup=_personal_mode_markup(),
                business_connection_id=message.business_connection_id,
            )
            return

        if chat_mode == "personal":
            if _looks_like_return_to_bot(text):
                if chat_id is not None:
                    database.db.set_chat_mode(int(chat_id), "bot")
                database.db.reset_user_funnel_state(user)
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=content.build_welcome_message(message.from_user.first_name),
                    reply_markup=_business_menu_markup(),
                    business_connection_id=message.business_connection_id,
                )
            return

        # На первом сообщении-приветствии в business-режиме отдаем
        # фиксированное приветствие без участия LLM.
        if text and _looks_like_plain_greeting(text):
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.build_welcome_message(message.from_user.first_name),
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id,
            )
            return

        lead = database.db.get_lead_by_user_id(user) if allow_lead_processing else None
        funnel_state = database.db.get_user_funnel_state(user)
        current_stage = funnel_state.get("conversation_stage") or "discover"
        awaiting_contact = bool(context.user_data.get(BUSINESS_AWAITING_CONTACT_KEY))
        awaiting_contact_source = context.user_data.get(BUSINESS_AWAITING_CONTACT_SOURCE_KEY) or "consultation"

        # Если после handoff появляется новая предметная боль/вопрос — открываем новый лид.
        if (
            allow_lead_processing
            and lead
            and current_stage == "handoff"
            and not awaiting_contact
            and _looks_like_new_topic_after_handoff(text)
        ):
            carried_lead = dict(lead)
            new_lead_payload = {
                "name": message.from_user.first_name,
                "email": carried_lead.get("email"),
                "phone": carried_lead.get("phone"),
                "company": carried_lead.get("company"),
                "pain_point": text[:1000],
                "temperature": "cold",
                "status": "new",
                "notification_sent": 0,
                "lead_magnet_type": None,
                "lead_magnet_delivered": 0,
                "notes": (
                    f"{(carried_lead.get('notes') or '').strip()}\n"
                    f"[NEW_TOPIC] Новый кейс после handoff: {text[:300]}"
                ).strip(),
            }
            new_lead_id = database.db.create_new_lead(user, new_lead_payload)
            cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user)

            database.db.update_user_funnel_state(
                user,
                conversation_stage="discover",
                cta_variant=cta_variant,
                cta_shown=False,
            )
            database.db.update_lead_funnel_state_by_id(
                new_lead_id,
                conversation_stage="discover",
                cta_variant=cta_variant,
                cta_shown=False,
            )
            try:
                database.db.track_event(
                    user,
                    "new_topic_after_handoff",
                    payload={"message": text[:300], "from_stage": "handoff", "to_stage": "discover"},
                    lead_id=new_lead_id,
                )
            except Exception as analytics_error:
                logger.warning(f"[Business] Failed to track new_topic_after_handoff: {analytics_error}")

            new_lead_payload_db = database.db.get_lead_by_id(new_lead_id) or {}
            await notify_admin_new_lead(
                context=context,
                lead_id=new_lead_id,
                lead_data=new_lead_payload_db,
                user_data={
                    "id": user,
                    "telegram_id": user_id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                },
                is_update=False,
            )
            logger.info("[Business] New lead %s created from new topic for user %s", new_lead_id, user_id)
            lead = new_lead_payload_db
            funnel_state = database.db.get_user_funnel_state(user)
            current_stage = funnel_state.get("conversation_stage") or "discover"

        # Сценарий: клиент прислал телефон в business-диалоге.
        phone_from_contact = getattr(getattr(message, "contact", None), "phone_number", None)
        phone_candidate = phone_from_contact or _extract_phone_candidate(text)
        if not phone_candidate and awaiting_contact and text:
            # Более мягкая попытка, когда пользователь уже в явном режиме "оставить контакт".
            digits = re.sub(r"\D", "", text)
            if 10 <= len(digits) <= 12:
                phone_candidate = digits

        if allow_lead_processing and awaiting_contact and (
            not phone_candidate or not utils.validate_phone(phone_candidate)
        ):
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=(
                    "Не удалось распознать номер.\n"
                    "Отправьте телефон одним сообщением, например: +7 999 123-45-67."
                ),
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id,
            )
            return

        if allow_lead_processing and phone_candidate and utils.validate_phone(phone_candidate):
            formatted_phone = utils.format_phone(phone_candidate)
            lead_magnet_type = (lead.get("lead_magnet_type") if lead else None) or "consultation"
            if awaiting_contact_source == "personal_request":
                lead_magnet_type = "personal_request"

            previous_lead = lead or {}
            extracted_from_text = _extract_phone_candidate(text)
            pain_point = previous_lead.get("pain_point")
            if text and not extracted_from_text:
                pain_point = text[:1000]
            lead_payload = {
                "name": message.from_user.first_name,
                "email": previous_lead.get("email"),
                "phone": formatted_phone,
                "company": previous_lead.get("company"),
                "pain_point": pain_point,
                "temperature": "warm",
                "status": "new",
                "lead_magnet_type": lead_magnet_type,
                "lead_magnet_delivered": True,
                "notification_sent": 0,
            }
            if lead_magnet_type == "personal_request":
                notes = (previous_lead.get("notes") or "").strip()
                lead_payload["notes"] = f"{notes}\nЛичное обращение (business)".strip()

            lead_id = database.db.create_new_lead(user, lead_payload)
            database.db.update_lead_last_message_time(user)
            _clear_business_contact_state(context)

            await context.bot.send_message(
                chat_id=message.chat.id,
                text=(
                    "Спасибо, номер получил. Передаю обращение команде.\n\n"
                    "Если хотите, можете сразу описать дополнительный вопрос или новую задачу."
                ),
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id,
            )

            await _send_business_handoff_and_notify(
                context=context,
                message=message,
                user_db_id=user,
                user_telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                source=f"business_phone_capture:{lead_magnet_type}",
                is_update=False,
            )
            logger.info("[Business] Phone captured and handoff sent for lead %s user %s", lead_id, user_id)
            return

        # Явный handoff-запрос
        if ai_brain.ai_brain.check_handoff_trigger(text):
            if allow_lead_processing:
                _persist_fasttrack_contact(user, message.from_user.first_name, text)
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.HANDOFF_ACK_TEXT,
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id
            )
            await _send_business_handoff_and_notify(
                context=context,
                message=message,
                user_db_id=user,
                user_telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                source="business_trigger",
                is_update=bool(lead),
            )
            _clear_business_contact_state(context)
            return

        if allow_lead_processing and funnel.should_fast_track_handoff(text, lead):
            database.db.add_message(user, 'user', text)
            _persist_fasttrack_contact(user, message.from_user.first_name, text)
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.HANDOFF_ACK_TEXT,
                reply_markup=_business_menu_markup(),
                business_connection_id=message.business_connection_id,
            )
            await _send_business_handoff_and_notify(
                context=context,
                message=message,
                user_db_id=user,
                user_telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                source="business_fasttrack",
                is_update=bool(lead),
            )
            _clear_business_contact_state(context)
            return

        # Pending lead-magnet в business flow: принимаем email и подтверждаем отправку.
        lead = database.db.get_lead_by_user_id(user)
        if lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered"):
            magnet_type = lead.get("lead_magnet_type")
            if magnet_type == "demo_analysis":
                magnet_type = "demo"
                database.db.create_or_update_lead(user, {"lead_magnet_type": "demo"})
                lead = database.db.get_lead_by_user_id(user)

            email = extract_email(text) if text else None
            if email:
                user_name = message.from_user.first_name
                success = False
                if magnet_type == "consultation":
                    success = email_sender.email_sender.send_consultation_confirmation(email, user_name)
                elif magnet_type == "checklist":
                    success = email_sender.email_sender.send_checklist(email, user_name)
                elif magnet_type == "demo":
                    success = email_sender.email_sender.send_demo_request_confirmation(email, user_name)

                if success:
                    if not lead.get("email"):
                        database.db.create_or_update_lead(user, {"email": email})
                    lead_qualifier.lead_qualifier.mark_lead_magnet_delivered(lead["id"])
                    base_message = content.LEAD_MAGNET_SENT_MESSAGES.get(magnet_type, "✅ Спасибо! Письмо отправлено.")
                    await context.bot.send_message(
                        chat_id=message.chat.id,
                        text=f"{base_message}\n\nКонтакт для отправки: {email}",
                        business_connection_id=message.business_connection_id,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=message.chat.id,
                        text=f"Произошла ошибка при отправке email.\n\n{content.DIRECT_CONTACTS_TEXT}",
                        business_connection_id=message.business_connection_id,
                    )
                return

            if magnet_type == "demo" and (getattr(message, "document", None) or getattr(message, "photo", None)):
                file_marker = "photo"
                if getattr(message, "document", None):
                    file_marker = f"document:{message.document.file_name or message.document.file_id}"
                existing_notes = (lead.get("notes") or "").strip()
                notes = f"{existing_notes}\nДокумент для демо: {file_marker}".strip()
                database.db.create_or_update_lead(user, {"notes": notes})
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text="Документ получил. Теперь укажите email, и команда отправит дальнейшие шаги.",
                    business_connection_id=message.business_connection_id,
                )
                return

        if not text:
            logger.warning(f"[Business] Skipping non-text message update: {update.update_id}")
            return

        funnel_state = database.db.get_user_funnel_state(user)
        current_stage = funnel_state.get('conversation_stage') or 'discover'
        cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user)
        cta_shown = bool(funnel_state.get('cta_shown'))
        if not funnel_state.get('cta_variant'):
            database.db.update_user_funnel_state(user, cta_variant=cta_variant)
        
        # Сохраняем сообщение пользователя
        database.db.add_message(user, 'user', text)
        
        # Получаем историю диалога
        conversation_history = database.db.get_conversation_history(user)
        
        menu_markup = _business_menu_markup()

        lead_snapshot = database.db.get_lead_by_user_id(user) if allow_lead_processing else None
        lead_id = lead_snapshot["id"] if lead_snapshot else None
        merged_lead_data = dict(lead_snapshot or {})
        response_stage = current_stage

        # Стадию ответа считаем без дополнительного pre-LLM шага,
        # чтобы пользователь не ждал лишний запрос к модели.
        if allow_lead_processing:
            response_stage = funnel.infer_stage(
                previous_stage=current_stage,
                user_message=text,
                lead_data=merged_lead_data,
            )

        # Получаем ответ от AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        _schedule_business_typing(context, message, user_id)

        # Собираем ответ от OpenAI и постепенно обновляем сообщение
        start_generation = time.time()
        preview_enabled = config.STREAMING_PREVIEW
        funnel_context = _append_profile_name_context(
            funnel.build_stage_context(response_stage, cta_variant, cta_shown),
            message.from_user.first_name,
        )
        async for chunk in ai_brain.ai_brain.generate_response_stream(
            conversation_history,
            funnel_context=funnel_context
        ):
            full_response += chunk
            chunk_buffer += chunk

            # Обновляем сообщение когда накопилось достаточно новых символов
            # ИЛИ прошло достаточно времени (для избежания rate limit)
            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 3.5) or  # Каждые 150 символов И минимум 3.5 сек (было 2)
                (len(chunk_buffer) > 300 and current_time - last_update_time >= 5.0)  # Или каждые 5 секунд при 300+ символах (было 3)
            )

            if preview_enabled and should_update:
                if sent_message is None:
                    # Первая отправка - когда накопилось хотя бы 100 символов (снижаем частоту обновлений)
                    if len(full_response.strip()) >= 100:
                        try:
                            sent_message = await context.bot.send_message(
                                chat_id=message.chat.id,
                                text=full_response,
                                business_connection_id=message.business_connection_id,
                            )
                            last_update_length = len(full_response)
                            last_update_time = current_time
                            chunk_buffer = ""
                            logger.debug(f"[Business] Initial message sent: {len(full_response)} chars")
                        except Exception as e:
                            logger.warning(f"[Business] Failed to send initial message: {e}")
                else:
                    # Обновляем существующее сообщение
                    try:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=full_response,
                            business_connection_id=message.business_connection_id,
                        )
                        last_update_length = len(full_response)
                        last_update_time = current_time
                        chunk_buffer = ""
                        logger.debug(f"[Business] Message updated: {len(full_response)} chars")
                    except Exception as e:
                        # Telegram rate limit - просто пропускаем это обновление
                        logger.debug(f"[Business] Skipped update (rate limit): {e}")
                        pass

        # Финальное обновление с полным текстом
        generation_time = time.time() - start_generation
        logger.info(f"[Business] Response generated in {generation_time:.2f}s ({len(full_response)} chars)")
        full_response = funnel.enforce_leadgen_response(
            response_text=full_response,
            stage=response_stage,
            user_message=text,
            cta_shown=cta_shown,
            cta_variant=cta_variant,
            lead_data=merged_lead_data,
        )

        # Проверяем нужно ли разбить на части (лимит Telegram 4096 символов)
        if len(full_response) > 4096:
            logger.warning(f"[Business] Response too long ({len(full_response)} chars), splitting into parts")
            # Разбиваем на части
            parts = utils.split_long_message(full_response, max_length=4000)
            
            # Удаляем первое сообщение если оно было отправлено
            if sent_message:
                try:
                    await context.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id
                    )
                except Exception:
                    pass
            
            # Отправляем по частям
            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                part_markup = menu_markup if i == len(parts) - 1 else None
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=part_msg,
                    business_connection_id=message.business_connection_id,
                    reply_markup=part_markup,
                )
                # Небольшая задержка между частями
                if i < len(parts) - 1:
                    await context.bot.send_chat_action(
                        chat_id=message.chat.id,
                        action="typing",
                        business_connection_id=message.business_connection_id
                    )
                    await asyncio.sleep(0.5)
        else:
            # Обычное обновление для коротких сообщений
            if sent_message:
                try:
                    await context.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        text=full_response,
                        business_connection_id=message.business_connection_id,
                        reply_markup=menu_markup,
                    )
                    logger.debug("[Business] Final message update sent")
                except Exception:
                    pass
            else:
                # Если текст был слишком коротким для постепенного вывода
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=full_response,
                    business_connection_id=message.business_connection_id,
                    reply_markup=menu_markup,
                )

        # Сохраняем ответ
        database.db.add_message(user, 'assistant', full_response)

        # Аналитика: показ CTA (A/B)
        if not cta_shown and funnel.is_cta_shown(full_response, cta_variant):
            database.db.update_user_funnel_state(
                user,
                cta_variant=cta_variant,
                cta_shown=True
            )
            database.db.update_lead_funnel_state(
                user,
                cta_variant=cta_variant,
                cta_shown=True
            )
            try:
                database.db.track_event(
                    user,
                    "cta_shown",
                    payload={"variant": cta_variant, "stage": response_stage, "source": "assistant_response"},
                )
            except Exception as analytics_error:
                logger.warning(f"[Business] Failed to track cta_shown: {analytics_error}")
            cta_shown = True
        
        # Фиксируем stage сразу, чтобы следующий апдейт не ждал LLM-экстракцию.
        if allow_lead_processing:
            if lead_id:
                database.db.update_lead_last_message_time(user)

            next_stage = response_stage
            database.db.update_user_funnel_state(
                user,
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )
            database.db.update_lead_funnel_state(
                user,
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )

            if next_stage != current_stage:
                try:
                    database.db.track_event(
                        user,
                        "stage_changed",
                        payload={"from": current_stage, "to": next_stage},
                        lead_id=lead_id,
                    )
                except Exception as analytics_error:
                    logger.warning(f"[Business] Failed to track stage_changed: {analytics_error}")

            cta_was_shown = cta_shown
            conversation_snapshot = list(conversation_history)

            async def _post_response_lead_processing() -> None:
                try:
                    extracted = await ai_brain.ai_brain.extract_lead_data_async(conversation_snapshot)
                    if not extracted:
                        return

                    telegram_profile_name = (message.from_user.first_name or "").strip()
                    if telegram_profile_name:
                        extracted["name"] = telegram_profile_name

                    processed_lead_id = lead_qualifier.lead_qualifier.process_lead_data(user, extracted)
                    if processed_lead_id:
                        temperature = extracted.get("temperature") or extracted.get("lead_temperature", "cold")
                        should_notify = (
                            temperature in ["hot", "warm"]
                            or (
                                extracted.get("name")
                                and (extracted.get("email") or extracted.get("phone"))
                                and extracted.get("pain_point")
                            )
                        )
                        logger.info(
                            f"[Business] Lead {processed_lead_id}: "
                            f"temperature={temperature}, should_notify={should_notify}"
                        )
                        database.db.update_lead_last_message_time(user)

                        if should_notify:
                            await notify_admin_new_lead(
                                context,
                                processed_lead_id,
                                extracted,
                                {"id": user, "telegram_id": user_id},
                            )

                    existing_lead = database.db.get_lead_by_user_id(user)
                    lead_magnet_already_selected = bool(existing_lead and existing_lead.get("lead_magnet_type"))
                    if (
                        not lead_magnet_already_selected
                        and not cta_was_shown
                        and ai_brain.ai_brain.should_offer_lead_magnet(extracted)
                    ):
                        reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
                        await context.bot.send_message(
                            chat_id=message.chat.id,
                            text=content.LEAD_MAGNET_OFFER_TEXT,
                            reply_markup=reply_markup,
                            business_connection_id=message.business_connection_id,
                        )

                        database.db.update_user_funnel_state(
                            user,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        database.db.update_lead_funnel_state(
                            user,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        try:
                            database.db.track_event(
                                user,
                                "cta_shown",
                                payload={"variant": cta_variant, "stage": next_stage, "source": "lead_magnet_offer"},
                                lead_id=processed_lead_id,
                            )
                        except Exception as analytics_error:
                            logger.warning(f"[Business] Failed to track lead magnet CTA show: {analytics_error}")
                except Exception as background_error:
                    logger.warning(f"[Business] Background lead processing failed for user {user_id}: {background_error}")

            asyncio.create_task(_post_response_lead_processing())

        logger.info(f"✅ [Business] Response sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in handle_business_message: {e}", exc_info=True)
        try:
            if update.business_message:
                await context.bot.send_message(
                    chat_id=update.business_message.chat.id,
                    text="❌ Произошла ошибка. Попробуйте позже.",
                    business_connection_id=update.business_message.business_connection_id
                )
        except:
            pass
