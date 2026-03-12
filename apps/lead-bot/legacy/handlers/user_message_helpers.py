"""
Message-level helpers extracted from the main user flow.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, Optional

import database
import utils
from telegram.error import TelegramError
from telegram_ui import normalize_button_text
from .helpers import extract_email

logger = logging.getLogger(__name__)

PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*(?:\d[\s\-()]*){10,11}")


def schedule_typing_indicator(chat, user_telegram_id: int) -> None:
    """Неблокирующий typing, чтобы сетевые лаги Telegram не тормозили ответ."""

    async def _send_typing() -> None:
        try:
            await asyncio.wait_for(chat.send_action(action="typing"), timeout=1.5)
            logger.info("Typing indicator sent for user %s", utils.mask_telegram_id(user_telegram_id))
        except (asyncio.TimeoutError, TelegramError, OSError) as error:
            logger.debug(
                "Typing indicator skipped for user %s: %s",
                utils.mask_telegram_id(user_telegram_id),
                error,
            )

    asyncio.create_task(_send_typing())


def append_profile_name_context(base_context: str, profile_first_name: Optional[str]) -> str:
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


def extract_phone_candidate(text: str) -> Optional[str]:
    raw = (text or "").strip()
    if not raw:
        return None

    match = PHONE_RE.search(raw)
    if not match:
        if re.fullmatch(r"[\d\s()+\-]{10,20}", raw):
            digits = re.sub(r"\D", "", raw)
            if 10 <= len(digits) <= 12:
                return digits
        return None
    return match.group(0)


def persist_fasttrack_contact(user_db_id: int, user, message_text: str) -> None:
    payload: Dict[str, str] = {}
    email = extract_email(message_text)
    if email:
        payload["email"] = email

    phone = extract_phone_candidate(message_text)
    if phone and utils.validate_phone(phone):
        payload["phone"] = utils.format_phone(phone)

    if payload:
        payload.setdefault("name", user.first_name)
        database.db.create_or_update_lead(user_db_id, payload)


def looks_like_ack_only(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    return normalized in {
        "ок", "окей", "понял", "принял", "ясно", "спасибо", "благодарю",
        "хорошо", "договорились", "супер", "круто",
    }


def looks_like_plain_greeting(text: str) -> bool:
    normalized = normalize_button_text(text).strip().lower()
    if not normalized:
        return False
    compact = normalized.replace("!", "").replace(".", "").replace(",", "").strip()
    greeting_prefixes = (
        "привет",
        "здравств",
        "добрый день",
        "добрый вечер",
        "доброе утро",
        "hello",
        "hi",
    )
    return any(compact.startswith(prefix) for prefix in greeting_prefixes)


def looks_like_return_to_bot(text: str) -> bool:
    normalized = normalize_button_text(text).strip().lower()
    return normalized in {
        "↩️ вернуться к боту",
        "вернуться к боту",
        "вернуться",
        "/bot",
        "бот",
    }


def looks_like_new_topic_after_handoff(text: str) -> bool:
    normalized = normalize_button_text(text).strip().lower()
    if not normalized:
        return False
    if looks_like_ack_only(normalized):
        return False
    if extract_phone_candidate(normalized):
        return False
    if normalized in {
        "/menu", "menu", "/меню", "меню",
        "/reset", "reset", "сброс",
        "меню услуг", "консультация", "заказать консультацию",
        "рабочий стол",
        "личное обращение", "мой профиль", "документы",
        "начать заново", "админ-панель",
    }:
        return False
    return len(normalized) >= 3


def build_new_phone_lead_payload(
    previous_lead: Optional[Dict],
    *,
    first_name: str,
    phone: str,
    source: str,
) -> Dict:
    lead = previous_lead or {}
    notes = (lead.get("notes") or "").strip()
    notes = f"{notes}\n[PHONE_CAPTURE] source={source}".strip()
    return {
        "name": first_name,
        "email": lead.get("email"),
        "phone": phone,
        "company": lead.get("company"),
        "pain_point": lead.get("pain_point"),
        "temperature": "warm",
        "status": "new",
        "lead_magnet_type": "consultation",
        "lead_magnet_delivered": True,
        "notification_sent": 0,
        "notes": notes,
    }


def normalize_magnet_type(value: Optional[str]) -> str:
    if value == "demo_analysis":
        return "demo"
    if value == "report_sample":
        return "sample_report"
    return value or ""
