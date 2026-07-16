"""Human-led legal-help intake flow for the production lead bot."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import InlineKeyboardMarkup, Update, User
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

import database
import utils
from config import get_config
from core_api_bridge import core_api_bridge
from .markup import pdn_consent_markup
from .start_payloads import LEGAL_HELP_START_PAYLOAD, PENDING_START_PAYLOAD_KEY
from .user_commands import _is_pdn_consent_granted, _pdn_consent_prompt_text

logger = logging.getLogger(__name__)
config = get_config()

LEGAL_HELP_MODE_KEY = "legal_help_mode"
LEGAL_HELP_CLIENT_TYPE_KEY = "legal_help_client_type"

_CLIENT_TYPES = {
    "company": "Компания",
    "entrepreneur": "ИП",
    "individual": "Частное лицо",
    "unknown": "Пока не определено",
}


def legal_help_client_type_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Компания", callback_data="legal_client:company"),
                InlineKeyboardButton("ИП", callback_data="legal_client:entrepreneur"),
            ],
            [
                InlineKeyboardButton("Частное лицо", callback_data="legal_client:individual"),
                InlineKeyboardButton("Не уверен", callback_data="legal_client:unknown"),
            ],
        ]
    )


async def prompt_legal_help_client_type(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[LEGAL_HELP_MODE_KEY] = "choose_client_type"
    context.user_data.pop(LEGAL_HELP_CLIENT_TYPE_KEY, None)
    await utils.safe_reply_text(
        message,
        "Юридическая помощь\n\nКому нужна помощь?",
        reply_markup=legal_help_client_type_markup(),
        action="legal_help_choose_client_type",
    )


async def _start_legal_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    message = query.message if query else update.effective_message
    if not user or not message:
        return

    user_id = database.db.create_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    consent_state = database.db.get_user_consent_state(user_id)
    if not _is_pdn_consent_granted(consent_state):
        context.user_data[PENDING_START_PAYLOAD_KEY] = LEGAL_HELP_START_PAYLOAD
        await utils.safe_reply_html(
            message,
            _pdn_consent_prompt_text("передаче обращения юристу"),
            reply_markup=pdn_consent_markup(),
            action="legal_help_requires_pdn",
        )
        return

    await prompt_legal_help_client_type(message, context)


async def handle_legal_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="legal_help_callback")

    if query.data == "legal_help_start":
        await _start_legal_help(update, context)
        return

    client_type = (query.data or "").partition(":")[2]
    if client_type not in _CLIENT_TYPES:
        await utils.safe_reply_text(query.message, "Не удалось выбрать тип клиента. Попробуйте еще раз.")
        return

    context.user_data[LEGAL_HELP_MODE_KEY] = "awaiting_description"
    context.user_data[LEGAL_HELP_CLIENT_TYPE_KEY] = client_type
    await utils.safe_reply_text(
        query.message,
        (
            f"Выбрано: {_CLIENT_TYPES[client_type]}.\n\n"
            "Одним сообщением опишите проблему или задачу, желаемый срок и регион, если он важен. "
            "На первом этапе не отправляйте паспортные данные, реквизиты документов и файлы."
        ),
        action="legal_help_awaiting_description",
    )


def _contact_for(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f"tg:{user.id}"


async def _notify_admin_fallback(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    lead_id: int,
    user: User,
    client_type: str,
    description: str,
) -> None:
    chat_id = config.LEADS_CHAT_ID or config.ADMIN_TELEGRAM_ID
    text = (
        "ЮРИДИЧЕСКОЕ ОБРАЩЕНИЕ СОХРАНЕНО В РЕЗЕРВЕ\n\n"
        f"Клиент: {_CLIENT_TYPES.get(client_type, _CLIENT_TYPES['unknown'])}\n"
        f"Имя: {user.full_name or user.first_name or 'не указано'}\n"
        f"Контакт: {_contact_for(user)}\n\n"
        f"Описание:\n{description[:1000]}\n\n"
        f"Локальный ID: {lead_id}"
    )
    try:
        await utils.telegram_call_with_retry(
            lambda: context.bot.send_message(chat_id=chat_id, text=text),
            action="legal_help_fallback_notify",
        )
    except Exception as error:
        logger.warning("Failed to notify admin about fallback legal intake %s: %s", lead_id, error)


async def maybe_handle_legal_help_message(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
    user: User,
    user_data: dict,
) -> bool:
    if context.user_data.get(LEGAL_HELP_MODE_KEY) != "awaiting_description":
        return False

    description = (message_text or "").strip()
    if len(description) < 20:
        await utils.safe_reply_text(
            update.effective_message,
            "Добавьте немного деталей: что произошло, какой результат нужен и есть ли срок.",
            action="legal_help_description_too_short",
        )
        return True

    client_type = context.user_data.get(LEGAL_HELP_CLIENT_TYPE_KEY, "unknown")
    created_at = datetime.now(timezone.utc).isoformat()
    local_payload = {
        "name": user.full_name or user.first_name,
        "pain_point": description[:3500],
        "temperature": "warm",
        "status": "new",
        "service_category": "legal_services",
        "specific_need": "Юридическая помощь",
        "conversation_stage": "handoff",
        "cta_variant": "legal_help",
        "cta_shown": 1,
        "notes": f"[LEGAL_HELP] client_type={client_type}",
    }
    lead_id = database.db.create_new_local_lead(user_data["id"], local_payload)
    payload = {
        "source": "telegram_bot",
        "telegram_user_id": user.id,
        "name": user.full_name or user.first_name,
        "contact": _contact_for(user),
        "client_type": client_type,
        "legal_area": "other",
        "description": description[:4000],
        "urgency": "no_deadline",
        "source_context": f"legacy_lead_id={lead_id};entry=lead_bot",
        "consent_accepted": True,
        "consent_version": "legal-help-v1",
        "consent_at": created_at,
    }
    result = await asyncio.to_thread(
        core_api_bridge.create_legal_intake,
        payload,
        idempotency_key=f"legal-help-tg-{user.id}-{update.effective_message.message_id}",
    )

    if result is None:
        logger.warning("Legal intake %s saved locally because core-api did not confirm it", lead_id)
        await _notify_admin_fallback(
            context,
            lead_id=lead_id,
            user=user,
            client_type=client_type,
            description=description,
        )

    database.db.track_event(
        user_data["id"],
        "legal_help_submitted",
        payload={"client_type": client_type, "core_confirmed": result is not None},
        lead_id=lead_id,
    )
    context.user_data.pop(LEGAL_HELP_MODE_KEY, None)
    context.user_data.pop(LEGAL_HELP_CLIENT_TYPE_KEY, None)
    await utils.safe_reply_text(
        update.effective_message,
        (
            "Обращение принято и передано юристу. Мы изучим описание и свяжемся с вами, "
            "чтобы уточнить детали, сроки и стоимость работы."
        ),
        action="legal_help_submitted",
    )
    return True
