"""Акт выполненных работ — сторона бота.

Мастер составления похож на мастер договора (service_agreements.py): те же
два конечных автомата через context.user_data, тот же приём «создать
черновик → отдельной кнопкой отправить». Короче договора — у акта нет
двустороннего подписания, только сумма к оплате и текст, что сделано.

«Оплачено» подтверждает юрист сам: у самозанятого без ИП нет банковского API
для проверки зачислений, поэтому клик клиента «Я оплатил(а)» — заявление, а
не подтверждение, и кнопка «Отметить оплаченным» доступна юристу сразу же,
не дожидаясь этого клика.
"""

from __future__ import annotations

import asyncio
import logging

import admin_interface
import utils
from config import get_config
from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

config = get_config()
logger = logging.getLogger(__name__)

STATE_KEY = "work_act_state"
DATA_KEY = "work_act_data"

_FIELD_HINTS = (
    "Что сделано — текст акта.",
    "Сумма к оплате, в рублях.",
)

# Используется и здесь, и в карточке обращения (service_agreements.py) —
# единственное место, где статус акта переводится на человеческий язык.
ACT_STATUS_LABELS = {
    "draft": "черновик",
    "sent": "отправлен",
    "claimed_paid": "клиент отметил оплату",
    "paid": "оплачен",
}


def format_rub(amount_minor: int) -> str:
    rubles, kopecks = divmod(int(amount_minor), 100)
    whole = f"{rubles:,}".replace(",", " ")
    return f"{whole},{kopecks:02d} ₽" if kopecks else f"{whole} ₽"


def _rub_to_minor(text: str) -> int | None:
    cleaned = (
        text.replace(" ", "").replace("\xa0", "").replace(",", ".").replace("₽", "").replace("руб.", "").replace("руб", "")
    )
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value < 0:
        return None
    return round(value * 100)


def _clear(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop(STATE_KEY, None)
    ctx.user_data.pop(DATA_KEY, None)


async def _notify_admin(bot, text: str, reply_markup: InlineKeyboardMarkup) -> bool:
    try:
        await bot.send_message(chat_id=config.ADMIN_TELEGRAM_ID, text=text, reply_markup=reply_markup)
        return True
    except TelegramError as exc:
        logger.warning("Work act admin notification failed: %s", type(exc).__name__)
        return False


def _act_admin_markup(act_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Отметить оплаченным", callback_data=f"act_a:paid:{act_id}")]]
    )


async def start_act_wizard(message, context: ContextTypes.DEFAULT_TYPE, agreement: dict) -> None:
    """Начинает составление акта по подписанному договору.

    Дефолты — из договора: текст работ из scope_text/subject, сумма — его
    amount_minor. «-» на любом шаге принимает дефолт как есть.
    """
    default_description = (agreement.get("scope_text") or agreement.get("subject") or "").strip()
    context.user_data[STATE_KEY] = "act_wizard"
    context.user_data[DATA_KEY] = {
        "agreement_id": agreement["id"],
        "field_index": 0,
        "default_description": default_description,
        "default_amount_minor": agreement.get("amount_minor"),
    }
    hint = _FIELD_HINTS[0]
    if default_description:
        hint += (
            f"\n\nПо умолчанию — из договора:\n«{default_description[:500]}»"
            "\n\nОтправьте «-», чтобы взять этот текст как есть, или напишите свой."
        )
    await utils.safe_reply_text(
        message, hint + "\n\nДля отмены напишите /cancel.", action="work_act_wizard_start"
    )


async def _finish_wizard(message, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    act = await asyncio.to_thread(
        admin_interface.admin_interface.create_work_act,
        agreement_id=data["agreement_id"],
        description_text=data["description_text"],
        amount_minor=data["amount_minor"],
        prepared_by_telegram_user_id=config.ADMIN_TELEGRAM_ID,
    )
    _clear(context)
    if not act:
        await utils.safe_reply_text(
            message,
            "Составить акт не удалось. Проверьте, что договор подписан.",
            action="work_act_create_failed",
        )
        return
    await utils.safe_reply_text(
        message,
        f"Акт № {act['act_number']} готов.\n\n{act['description_text']}"
        f"\n\nК оплате: {format_rub(act['amount_minor'])}",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Отправить клиенту", callback_data=f"act_a:send:{act['id']}")]]
        ),
        action="work_act_draft_ready",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Обрабатывает шаги мастера. False — сообщение не наше, пусть идёт дальше."""
    if context.user_data.get(STATE_KEY) != "act_wizard":
        return False
    message = update.effective_message
    user = update.effective_user
    if not message or not user or user.id != config.ADMIN_TELEGRAM_ID:
        return False

    value = (text or "").strip()
    if value.lower() in {"/cancel", "отмена"}:
        _clear(context)
        await utils.safe_reply_text(message, "Действие отменено.", action="work_act_cancel")
        return True

    data = dict(context.user_data.get(DATA_KEY) or {})
    idx = int(data.get("field_index") or 0)

    if idx == 0:
        if value == "-":
            description = data.get("default_description") or ""
            if not description:
                await utils.safe_reply_text(
                    message,
                    "Для этого договора нет текста по умолчанию — опишите работу словами.",
                    action="work_act_no_default",
                )
                return True
        else:
            description = value
        if len(description) < 2:
            await utils.safe_reply_text(
                message, "Слишком коротко. Опишите, что сделано.", action="work_act_description_short"
            )
            return True
        data["description_text"] = description
        data["field_index"] = 1
        context.user_data[DATA_KEY] = data
        hint = _FIELD_HINTS[1]
        default_amount = data.get("default_amount_minor")
        if default_amount:
            hint += (
                f"\n\nПо умолчанию — сумма договора: {format_rub(default_amount)}."
                " Отправьте «-», чтобы взять её, или укажите свою."
            )
        await utils.safe_reply_text(message, hint, action="work_act_wizard_step")
        return True

    if value == "-":
        amount_minor = data.get("default_amount_minor")
        if not amount_minor:
            await utils.safe_reply_text(
                message,
                "В договоре нет суммы по умолчанию — укажите сумму в рублях.",
                action="work_act_no_default_amount",
            )
            return True
    else:
        amount_minor = _rub_to_minor(value)
    if not amount_minor or amount_minor <= 0:
        await utils.safe_reply_text(
            message,
            "Сумма — это число в рублях, например 80000 или 12 500,50.",
            action="work_act_amount_invalid",
        )
        return True
    data["amount_minor"] = amount_minor
    context.user_data[DATA_KEY] = data
    await _finish_wizard(message, context, data)
    return True


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="work_act_admin_callback")
    user = query.from_user
    if not user or user.id != config.ADMIN_TELEGRAM_ID:
        return
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    item_id = parts[2] if len(parts) > 2 else ""

    if action == "new":
        agreement = await asyncio.to_thread(
            admin_interface.admin_interface.get_service_agreement, item_id
        )
        if not agreement or agreement.get("status") != "signed":
            await utils.safe_reply_text(
                query.message,
                "Акт можно выставить только по подписанному договору.",
                action="work_act_new_invalid",
            )
            return
        await start_act_wizard(query.message, context, agreement)
        return

    if action == "send":
        act = await asyncio.to_thread(admin_interface.admin_interface.send_work_act, item_id)
        if not act:
            await utils.safe_reply_text(
                query.message,
                "Отправить акт не удалось. Проверьте, что у клиента есть диалог в Telegram.",
                action="work_act_send_failed",
            )
            return
        await utils.safe_reply_text(
            query.message,
            f"Акт № {act['act_number']} отправлен клиенту.\nК оплате: {format_rub(act['amount_minor'])}",
            reply_markup=_act_admin_markup(act["id"]),
            action="work_act_sent",
        )
        return

    if action == "paid":
        act = await asyncio.to_thread(
            admin_interface.admin_interface.mark_work_act_paid,
            item_id,
            paid_by_telegram_user_id=user.id,
        )
        if not act:
            await utils.safe_reply_text(
                query.message, "Отметить оплату не удалось.", action="work_act_paid_failed"
            )
            return
        await utils.safe_reply_text(
            query.message, f"Акт № {act['act_number']} отмечен оплаченным.", action="work_act_paid_ok"
        )
        return


async def handle_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«Я оплатил(а)» от клиента — заявление, не подтверждение."""
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="work_act_client_callback")
    user = query.from_user
    if not user:
        return
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    act_id = parts[2] if len(parts) > 2 else ""
    if action != "claim":
        return

    act = await asyncio.to_thread(
        admin_interface.admin_interface.claim_work_act_paid,
        act_id,
        telegram_user_id=user.id,
    )
    if not act:
        await utils.safe_reply_text(
            query.message,
            "Не получилось отметить оплату. Напишите юристу напрямую.",
            action="work_act_claim_failed",
        )
        return
    await utils.safe_reply_text(
        query.message,
        "Спасибо! Юрист проверит поступление и подтвердит.",
        action="work_act_claimed",
    )
    await _notify_admin(
        context.bot,
        f"Клиент отметил акт № {act['act_number']} как оплаченный — "
        f"{format_rub(act['amount_minor'])}. Проверьте зачисление.",
        _act_admin_markup(act["id"]),
    )
