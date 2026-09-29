"""
Объединение Telegram с кабинетом на сайте: бот выдаёт одноразовый код.

Клиент вошёл на сайт через Яндекс ID (Telegram без VPN не открывается) и видит
пустой кабинет — дела у него в Telegram. Код видит только владелец этого
Telegram, вводит его в кабинете сам — это и доказательство, и согласие.
Код рождается здесь, а не ссылкой с сайта: «нажмите в боте» чужой прислал бы
одной кнопкой и получил бы чужие дела.
"""
from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
        f"Введите его на сайте: Личный кабинет → Профиль → «Привязать Telegram». "
        f"Код действует {minutes} минут.\n\n"
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
