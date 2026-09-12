"""Обращение в инженерную практику — и в гибридную, автоматизацию юридической функции.

Тот же путь, что у юридического обращения (legal_help): согласие на
обработку данных → пара кнопок → одно сообщение с описанием → обращение в
ядре. Раньше «🛠 Инженерная практика» была текстом с просьбой оставить
контакт, и задача клиента дальше сбора контакта не уходила: ни обращения,
ни NDA, ни договора. Теперь это обращение с практикой engineering или
hybrid, и дальше оно идёт по общему циклу — уточнения, NDA, договор по
шаблону разработки, акты.

Отдельный модуль, а не ветка внутри legal_help: там тип клиента, здесь —
ещё и категория задачи, и тексты другие. Общая механика — в ядре.
"""

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
from .start_payloads import PENDING_START_PAYLOAD_KEY
from .user_commands import _is_pdn_consent_granted, _pdn_consent_prompt_text

logger = logging.getLogger(__name__)
config = get_config()

MODE_KEY = "engineering_help_mode"
PRACTICE_KEY = "engineering_help_practice"
CATEGORY_KEY = "engineering_help_category"
CLIENT_TYPE_KEY = "engineering_help_client_type"

ENGINEERING_START_PAYLOAD = "engineering_help"
HYBRID_START_PAYLOAD = "hybrid_help"

# Категории — те же ключи, что PRACTICE_CATEGORIES в ядре: проверка там,
# здесь только подписи для кнопок.
ENGINEERING_CATEGORIES: dict[str, str] = {
    "telegram_bot": "Telegram-бот",
    "website": "Сайт",
    "miniapp": "Mini App",
    "internal_tool": "Внутренняя программа",
    "ai_module": "AI-модуль",
    "integration": "Интеграция с CRM/1С/ЭДО",
    "other": "Другое",
}

HYBRID_CATEGORIES: dict[str, str] = {
    "contracts_flow": "Договорная работа",
    "claims_flow": "Претензии и споры",
    "compliance": "Комплаенс",
    "document_flow": "Документооборот",
    "staff_consulting": "Консультирование сотрудников",
    "other": "Другое",
}

CATEGORIES_BY_PRACTICE = {
    "engineering": ENGINEERING_CATEGORIES,
    "hybrid": HYBRID_CATEGORIES,
}

PRACTICE_TITLE = {
    "engineering": "Инженерная практика",
    "hybrid": "Автоматизация юридической функции",
}

_CLIENT_TYPES = {
    "company": "Компания",
    "entrepreneur": "ИП",
    "individual": "Частное лицо",
    "unknown": "Пока не определено",
}

_DESCRIBE_PROMPT = {
    "engineering": (
        "Одним сообщением опишите задачу: что нужно автоматизировать и как это делается "
        "сейчас — вручную, в таблице, в другой системе. Если есть срок или готовое "
        "техническое задание, упомяните. Файлы пока не присылайте — их попросим позже."
    ),
    "hybrid": (
        "Одним сообщением опишите юридический процесс, который хотите автоматизировать: "
        "что в него входит, как он идёт сейчас, где теряется время или возникает риск. "
        "Если есть срок — упомяните. Файлы пока не присылайте — их попросим позже."
    ),
}


START_BUTTON_TEXT = {
    "engineering": "🛠 Описать задачу инженерам",
    "hybrid": "⚙️ Автоматизировать юридический процесс",
}


def start_button(practice: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(START_BUTTON_TEXT[practice], callback_data=f"eng_help_start:{practice}")


def with_start_buttons(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Два входа первыми строками над обычным меню — там, где практика описана словами.

    Гибрид живёт под той же кнопкой меню, что и инженерная практика: у него
    инженерная механика с юридической составляющей, и отдельный пункт в и без
    того длинном меню ничего бы не добавил.
    """
    rows = [list(row) for row in markup.inline_keyboard]
    return InlineKeyboardMarkup([[start_button("engineering")], [start_button("hybrid")], *rows])


def category_markup(practice: str) -> InlineKeyboardMarkup:
    items = list(CATEGORIES_BY_PRACTICE[practice].items())
    rows = []
    for i in range(0, len(items), 2):
        rows.append(
            [
                InlineKeyboardButton(title, callback_data=f"eng_cat:{key}")
                for key, title in items[i : i + 2]
            ]
        )
    return InlineKeyboardMarkup(rows)


def client_type_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Компания", callback_data="eng_client:company"),
                InlineKeyboardButton("ИП", callback_data="eng_client:entrepreneur"),
            ],
            [
                InlineKeyboardButton("Частное лицо", callback_data="eng_client:individual"),
                InlineKeyboardButton("Не уверен", callback_data="eng_client:unknown"),
            ],
        ]
    )


async def prompt_category(message, context: ContextTypes.DEFAULT_TYPE, practice: str) -> None:
    context.user_data[MODE_KEY] = "choose_category"
    context.user_data[PRACTICE_KEY] = practice
    for key in (CATEGORY_KEY, CLIENT_TYPE_KEY):
        context.user_data.pop(key, None)
    question = (
        "Что нужно сделать?" if practice == "engineering" else "Какой процесс автоматизируем?"
    )
    await utils.safe_reply_text(
        message,
        f"{PRACTICE_TITLE[practice]}\n\n{question}",
        reply_markup=category_markup(practice),
        action="engineering_help_choose_category",
    )


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE, practice: str) -> None:
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
        context.user_data[PENDING_START_PAYLOAD_KEY] = (
            ENGINEERING_START_PAYLOAD if practice == "engineering" else HYBRID_START_PAYLOAD
        )
        await utils.safe_reply_html(
            message,
            _pdn_consent_prompt_text("передаче задачи инженерам"),
            reply_markup=pdn_consent_markup(),
            action="engineering_help_requires_pdn",
        )
        return

    await prompt_category(message, context, practice)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="engineering_help_callback")
    data = query.data or ""

    if data.startswith("eng_help_start:"):
        practice = data.partition(":")[2]
        if practice not in CATEGORIES_BY_PRACTICE:
            practice = "engineering"
        await _start(update, context, practice)
        return

    if data.startswith("eng_cat:"):
        practice = context.user_data.get(PRACTICE_KEY) or "engineering"
        category = data.partition(":")[2]
        if category not in CATEGORIES_BY_PRACTICE.get(practice, {}):
            await utils.safe_reply_text(query.message, "Не удалось выбрать категорию. Попробуйте ещё раз.")
            return
        context.user_data[CATEGORY_KEY] = category
        context.user_data[MODE_KEY] = "choose_client_type"
        await utils.safe_reply_text(
            query.message,
            f"Выбрано: {CATEGORIES_BY_PRACTICE[practice][category]}.\n\nОт чьего имени задача?",
            reply_markup=client_type_markup(),
            action="engineering_help_choose_client_type",
        )
        return

    if data.startswith("eng_client:"):
        client_type = data.partition(":")[2]
        if client_type not in _CLIENT_TYPES:
            await utils.safe_reply_text(query.message, "Не удалось выбрать тип клиента. Попробуйте ещё раз.")
            return
        practice = context.user_data.get(PRACTICE_KEY) or "engineering"
        context.user_data[CLIENT_TYPE_KEY] = client_type
        context.user_data[MODE_KEY] = "awaiting_description"
        await utils.safe_reply_text(
            query.message,
            f"Выбрано: {_CLIENT_TYPES[client_type]}.\n\n{_DESCRIBE_PROMPT[practice]}",
            action="engineering_help_awaiting_description",
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
    practice: str,
    category: str,
    client_type: str,
    description: str,
) -> None:
    chat_id = config.LEADS_CHAT_ID or config.ADMIN_TELEGRAM_ID
    text = (
        f"{PRACTICE_TITLE[practice].upper()}: ОБРАЩЕНИЕ СОХРАНЕНО В РЕЗЕРВЕ\n\n"
        f"Задача: {CATEGORIES_BY_PRACTICE[practice].get(category, category)}\n"
        f"Клиент: {_CLIENT_TYPES.get(client_type, _CLIENT_TYPES['unknown'])}\n"
        f"Имя: {user.full_name or user.first_name or 'не указано'}\n"
        f"Контакт: {_contact_for(user)}\n\n"
        f"Описание:\n{description[:1000]}\n\n"
        f"Локальный ID: {lead_id}"
    )
    try:
        await utils.telegram_call_with_retry(
            lambda: context.bot.send_message(chat_id=chat_id, text=text),
            action="engineering_help_fallback_notify",
        )
    except Exception as error:
        logger.warning("Failed to notify admin about fallback engineering intake %s: %s", lead_id, error)


async def maybe_handle_message(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
    user: User,
    user_data: dict,
) -> bool:
    if context.user_data.get(MODE_KEY) != "awaiting_description":
        return False

    description = (message_text or "").strip()
    if len(description) < 20:
        await utils.safe_reply_text(
            update.effective_message,
            "Добавьте немного деталей: что нужно получить, как это делается сейчас и есть ли срок.",
            action="engineering_help_description_too_short",
        )
        return True

    practice = context.user_data.get(PRACTICE_KEY) or "engineering"
    category = context.user_data.get(CATEGORY_KEY) or "other"
    client_type = context.user_data.get(CLIENT_TYPE_KEY, "unknown")
    created_at = datetime.now(timezone.utc).isoformat()
    title = PRACTICE_TITLE[practice]
    local_payload = {
        "name": user.full_name or user.first_name,
        "pain_point": description[:3500],
        "temperature": "warm",
        "status": "new",
        "service_category": f"{practice}:{category}",
        "specific_need": title,
        "conversation_stage": "handoff",
        "cta_variant": "engineering_help",
        "cta_shown": 1,
        "notes": f"[{practice.upper()}_HELP] category={category} client_type={client_type}",
    }
    lead_id = database.db.create_new_local_lead(user_data["id"], local_payload)
    payload = {
        "source": "telegram_bot",
        "telegram_user_id": user.id,
        "name": user.full_name or user.first_name,
        "contact": _contact_for(user),
        "client_type": client_type,
        "legal_area": "other",
        "practice": practice,
        "category": category,
        "description": description[:4000],
        "urgency": "no_deadline",
        "source_context": f"legacy_lead_id={lead_id};entry=lead_bot",
        "consent_accepted": True,
        "consent_version": "engineering-help-v1",
        "consent_at": created_at,
    }
    result = await asyncio.to_thread(
        core_api_bridge.create_legal_intake,
        payload,
        idempotency_key=f"engineering-help-tg-{user.id}-{update.effective_message.message_id}",
    )
    if result is None:
        logger.warning("Engineering intake %s saved locally because core-api did not confirm it", lead_id)
        await _notify_admin_fallback(
            context,
            lead_id=lead_id,
            user=user,
            practice=practice,
            category=category,
            client_type=client_type,
            description=description,
        )

    database.db.track_event(
        user_data["id"],
        "engineering_help_submitted",
        payload={"practice": practice, "category": category, "client_type": client_type, "core_confirmed": result is not None},
        lead_id=lead_id,
    )
    for key in (MODE_KEY, PRACTICE_KEY, CATEGORY_KEY, CLIENT_TYPE_KEY):
        context.user_data.pop(key, None)
    await utils.safe_reply_text(
        update.effective_message,
        (
            "Задача принята и передана команде. Мы изучим описание и свяжемся с вами, "
            "чтобы уточнить детали, сроки и стоимость."
            if practice == "engineering"
            else "Задача принята и передана юристам и инженерам. Мы изучим описание процесса и "
            "свяжемся с вами, чтобы уточнить детали, сроки и стоимость."
        ),
        action="engineering_help_submitted",
    )
    return True
