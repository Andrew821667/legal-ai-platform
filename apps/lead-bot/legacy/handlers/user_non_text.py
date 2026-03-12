"""
Non-text branch extracted from the main user flow.
"""
from __future__ import annotations

import logging
from typing import Optional

import database
import utils
from telegram import Update
from telegram.ext import ContextTypes
from .helpers import extract_email, send_lead_magnet_email
from .markup import consultation_contact_markup as _consultation_contact_markup
from .user_cta_actions import handle_handoff_request
from .user_message_helpers import (
    build_new_phone_lead_payload as _build_new_phone_lead_payload,
    normalize_magnet_type as _normalize_magnet_type,
)

logger = logging.getLogger(__name__)


async def handle_non_text_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,
    lead: Optional[dict],
    allow_lead_processing: bool,
) -> bool:
    """
    Обрабатывает non-text сообщения в сценарии lead magnet.
    Возвращает True, если сообщение обработано и основной flow продолжать не нужно.
    """
    message = update.effective_message
    if not message:
        return True

    if allow_lead_processing and getattr(message, "contact", None):
        phone = message.contact.phone_number or ""
        if phone and utils.validate_phone(phone):
            formatted_phone = utils.format_phone(phone)
            new_lead_id = database.db.create_new_lead(
                user_data["id"],
                _build_new_phone_lead_payload(
                    lead,
                    first_name=update.effective_user.first_name if update.effective_user else "",
                    phone=formatted_phone,
                    source="consultation_contact_telegram",
                ),
            )
            await handle_handoff_request(
                update,
                context,
                source="consultation_contact",
                lead_id_override=new_lead_id,
                is_update_override=False,
            )
            return True

    if not lead or not lead.get("lead_magnet_type") or lead.get("lead_magnet_delivered"):
        logger.warning("Skipping non-text message update type: %s", update.update_id)
        return True

    magnet_type = _normalize_magnet_type(lead.get("lead_magnet_type"))
    if magnet_type != lead.get("lead_magnet_type"):
        database.db.create_or_update_lead(user_data["id"], {"lead_magnet_type": magnet_type})
        lead = database.db.get_lead_by_user_id(user_data["id"])

    caption_text = message.caption or ""
    email = extract_email(caption_text)
    if email:
        await send_lead_magnet_email(update, user_data, lead, email)
        return True

    if magnet_type == "consultation":
        await utils.safe_reply_text(
            message,
            "Для заявки на консультацию отправьте номер телефона кнопкой ниже.",
            reply_markup=_consultation_contact_markup(),
            action="consultation_phone_prompt_non_text",
        )
        return True

    if magnet_type == "demo" and (message.document or message.photo):
        file_marker = "photo"
        if message.document:
            file_marker = f"document:{message.document.file_name or message.document.file_id}"

        existing_notes = (lead.get("notes") or "").strip()
        notes = f"{existing_notes}\nДокумент для демо: {file_marker}".strip()
        database.db.create_or_update_lead(user_data["id"], {"notes": notes})
        await message.reply_text(
            "Документ получил. Теперь укажите email, и мы отправим подтверждение и дальнейшие шаги."
        )
        return True

    await message.reply_text(
        "Чтобы продолжить, отправьте email в текстовом сообщении.\n"
        "Для демонстрационного разбора можно приложить документ с подписью, где указан email."
    )
    return True
