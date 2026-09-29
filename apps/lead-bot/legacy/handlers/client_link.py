"""
Объединение Telegram с кабинетом на сайте: бот выдаёт одноразовый код.

Клиент вошёл на сайт через Яндекс ID (Telegram без VPN не открывается) и видит
пустой кабинет — дела у него в Telegram. Код видит только владелец этого
Telegram и вводит его в кабинете сам; после этого ядро присылает сюда почту
учётной записи с вопросом «Объединить?» — объединяется только по «Да».
Код рождается здесь, а не ссылкой с сайта: «нажмите в боте» чужой прислал бы
одной кнопкой и получил бы чужие дела.
"""
from __future__ import annotations

import html
import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import utils
from config import get_config
from core_api_bridge import core_api_bridge

logger = logging.getLogger(__name__)
config = get_config()

LINK_START_PAYLOAD = "link"


def _profile_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🌐 Открыть кабинет на сайте", url=config.CLIENT_CABINET_PROFILE_URL)]]
    )


def link_code_text(result: dict | None) -> str:
    if not result:
        return "Сейчас не получилось выдать код. Попробуйте через пару минут: /link"
    if result.get("linked"):
        email = html.escape(str(result.get("email_masked") or ""))
        return (
            f"Этот Telegram уже объединён с кабинетом на сайте ({email}).\n\n"
            "Отвязать можно в кабинете: Профиль → «Отвязать Telegram»."
        )
    code = html.escape(str(result.get("code") or ""))
    minutes = int(result.get("ttl_minutes") or 10)
    return (
        "🔗 <b>Код для объединения с кабинетом на сайте</b>\n\n"
        f"<code>{code}</code>\n\n"
        f"Введите его на сайте: Личный кабинет → Профиль → «Объединить с Telegram». "
        f"Код действует {minutes} минут. После этого я пришлю сюда почту учётной записи "
        "и спрошу, объединять ли, — без вашего «Да» ничего не объединится.\n\n"
        "После объединения в кабинете на сайте будут видны ваши дела и документы из Telegram.\n\n"
        "⚠️ Никому не сообщайте код — даже нам. Если объединение запрашивали не вы, "
        "просто не вводите его нигде."
    )


async def send_link_code(message, user) -> bool:
    result = core_api_bridge.issue_link_code(telegram_user_id=user.id, telegram_username=user.username)
    if result is None:
        logger.warning("link code was not issued for user %s", user.id)
    await utils.safe_reply_html(
        message,
        link_code_text(result),
        reply_markup=_profile_markup() if result else None,
        action="client_link_code",
    )
    return True


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/link — код для объединения Telegram с кабинетом на сайте."""
    _ = context
    if update.message is None or update.effective_user is None:
        return
    await send_link_code(update.message, update.effective_user)


def decision_text(action: str, result: dict | None) -> str:
    """Что ответить на кнопку под вопросом «Объединить?» или под уведомлением."""
    email = html.escape(str((result or {}).get("email") or ""))
    status = (result or {}).get("status")
    if action == "ok" and status == "linked":
        return (
            f"✅ Готово: ваш Telegram объединён с учётной записью сайта {email}.\n\n"
            "Обновите страницу кабинета — дела и документы из Telegram уже там."
        )
    if action == "no" and status == "declined":
        return (
            "Отменено — ничего не объединено.\n\n"
            "Если код на сайте вводили не вы, никому его не сообщайте. Новый код — только по вашей команде /link."
        )
    if action == "undo" and status == "unlinked":
        return f"Отвязано: учётная запись {email} больше не видит ваши дела из Telegram."
    return "Этот запрос устарел или уже обработан. Если нужно объединить — запросите новый код: /link"


async def handle_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопки clink:ok|no:<код> под «Объединить?» и clink:undo:<учётная запись>."""
    _ = context
    query = update.callback_query
    if query is None or query.from_user is None:
        return
    parts = (query.data or "").split(":", 2)
    action, ref = (parts[1], parts[2]) if len(parts) == 3 else ("", "")
    result = None
    try:
        ref_id = str(uuid.UUID(ref))
    except ValueError:
        ref_id = ""
    if ref_id and action in ("ok", "no"):
        result = core_api_bridge.decide_link(code_id=ref_id, telegram_user_id=query.from_user.id, accept=action == "ok")
    elif ref_id and action == "undo":
        result = core_api_bridge.owner_unlink(account_id=ref_id, telegram_user_id=query.from_user.id)
    try:
        await query.answer()
    except TelegramError:
        pass
    text = decision_text(action, result)
    try:
        await query.edit_message_text(text, parse_mode="HTML")
    except TelegramError:
        if query.message is not None:
            await utils.safe_reply_html(query.message, text, action="client_link_decision")
