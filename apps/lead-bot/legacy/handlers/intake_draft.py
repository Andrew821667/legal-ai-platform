"""Черновик обращения к юристу из разговора с ассистентом.

Человек описал ассистенту свою юридическую задачу, а чтобы она дошла до
юриста, ему приходилось заново идти в «Юридическую помощь» и описывать всё
ещё раз. Теперь под ответом ассистента — «Передать задачу юристу»: бот
собирает черновик из собственных сообщений человека (не пересказ модели —
чтобы ничего не исказить и не приписать), показывает его и отправляет только
после явного выбора «кому нужна помощь» (решение владельца 16.09: черновик +
кнопка, не автовыполнение). Отправка — той же дорогой, что из меню
(legal_help.submit_legal_help).
"""
from __future__ import annotations

import html
import logging
import re
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database
import utils

logger = logging.getLogger(__name__)

DRAFT_KEY = "intake_draft"
OFFERED_AT_KEY = "intake_draft_offered_at"
DRAFT_TTL_SECONDS = 30 * 60
OFFER_EVERY_SECONDS = 24 * 3600
MAX_MESSAGES = 6
MAX_CHARS = 3000
MIN_CHARS = 20

CLIENT_TYPES = {
    "company": "Компания",
    "entrepreneur": "ИП",
    "individual": "Частное лицо",
    "unknown": "Не уверен",
}

OFFER_TEXT = (
    "Могу передать эту задачу юристу: соберу обращение из того, что вы написали, "
    "и покажу перед отправкой."
)

# Спросили про NDA — сразу дать открыть его, а не объяснять, где искать.
_NDA_MENTION = re.compile(r"\bnda\b|конфиденциальн|неразглаш", re.IGNORECASE)


def offer_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📝 Передать задачу юристу", callback_data="idraft:make")]])


def nda_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔒 Соглашение о конфиденциальности", callback_data="nda:open")]])


def mentions_nda(text: str | None) -> bool:
    return bool(_NDA_MENTION.search(text or ""))


def draft_from_history(history: list[dict]) -> str:
    """Последние сообщения человека подряд — его же словами, до MAX_CHARS."""
    parts: list[str] = []
    total = 0
    for row in reversed(history or []):
        if row.get("role") != "user":
            continue
        text = " ".join(str(row.get("message") or "").split())
        if not text:
            continue
        if parts and total + len(text) > MAX_CHARS:
            break
        parts.append(text[:MAX_CHARS])
        total += len(text)
        if len(parts) >= MAX_MESSAGES:
            break
    return "\n\n".join(reversed(parts))


def draft_markup() -> InlineKeyboardMarkup:
    types = [InlineKeyboardButton(f"✅ {label}", callback_data=f"idraft:send:{key}") for key, label in CLIENT_TYPES.items()]
    return InlineKeyboardMarkup(
        [
            types[:2],
            types[2:],
            [InlineKeyboardButton("✏️ Описать заново", callback_data="legal_help_start")],
            [InlineKeyboardButton("✖ Не отправлять", callback_data="idraft:cancel")],
        ]
    )


def draft_text(draft: str) -> str:
    return (
        "📝 <b>Черновик обращения юристу</b>\n\n"
        f"<blockquote>{html.escape(draft)}</blockquote>\n\n"
        "Проверьте текст. Если всё верно — выберите, кому нужна помощь, и обращение уйдёт юристу. "
        "Паспортные данные и реквизиты сейчас не нужны."
    )


async def offer_draft(message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Кнопка «Передать задачу юристу» под ответом — не чаще раза в сутки."""
    user_data = getattr(context, "user_data", None)
    if user_data is None:
        return False
    now = time.time()
    if now - float(user_data.get(OFFERED_AT_KEY) or 0) < OFFER_EVERY_SECONDS:
        return False
    user_data[OFFERED_AT_KEY] = now
    await utils.safe_reply_text(message, OFFER_TEXT, reply_markup=offer_markup(), action="intake_draft_offer")
    return True


async def offer_nda(message) -> None:
    await utils.safe_reply_text(
        message,
        "Соглашение о конфиденциальности можно открыть и подписать здесь:",
        reply_markup=nda_markup(),
        action="assistant_nda_button",
    )


async def handle_draft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """idraft:make | idraft:send:<тип клиента> | idraft:cancel."""
    query = update.callback_query
    if query is None or query.from_user is None:
        return
    await utils.safe_answer_callback(query, action="intake_draft_answer")
    user = query.from_user
    action, _, client_type = (query.data or "").removeprefix("idraft:").partition(":")
    user_row = database.db.get_user_by_telegram_id(user.id)
    if not user_row:
        await utils.safe_reply_text(query.message, "Ошибка. Попробуйте /start", action="intake_draft_no_user")
        return

    if action == "make":
        history = database.db.get_conversation_history(user_row["id"])
        draft = draft_from_history(history)
        if len(draft) < MIN_CHARS:
            from .legal_help import prompt_legal_help_client_type

            await prompt_legal_help_client_type(query.message, context)
            return
        context.user_data[DRAFT_KEY] = {"text": draft, "at": time.time()}
        await utils.safe_reply_html(query.message, draft_text(draft), reply_markup=draft_markup(), action="intake_draft_shown")
        return

    if action == "cancel":
        context.user_data.pop(DRAFT_KEY, None)
        await utils.safe_edit_text(query.message, "Хорошо, не отправляю. Если передумаете — «Юридическая помощь» в меню.",
                                   action="intake_draft_cancelled")
        return

    if action == "send" and client_type in CLIENT_TYPES:
        stored = context.user_data.get(DRAFT_KEY) or {}
        if not stored.get("text") or time.time() - float(stored.get("at") or 0) > DRAFT_TTL_SECONDS:
            context.user_data.pop(DRAFT_KEY, None)
            await utils.safe_reply_text(
                query.message,
                "Черновик устарел — нажмите «Передать задачу юристу» ещё раз или опишите задачу через «Юридическая помощь».",
                action="intake_draft_expired",
            )
            return
        context.user_data.pop(DRAFT_KEY, None)
        from .legal_help import submit_legal_help

        await submit_legal_help(
            context=context,
            user=user,
            user_data=user_row,
            description=stored["text"],
            client_type=client_type,
            idempotency_key=f"legal-help-draft-{user.id}-{query.message.message_id}",
            entry="assistant_draft",
        )
        await utils.safe_edit_text(
            query.message,
            "✅ Обращение передано юристу. Мы изучим его и свяжемся с вами, чтобы уточнить детали, сроки и стоимость.",
            action="intake_draft_sent",
        )
        return

    logger.warning("Unknown intake draft action: %s", query.data)
