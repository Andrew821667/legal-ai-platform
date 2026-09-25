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
import io
import logging
from decimal import Decimal, InvalidOperation

import admin_interface
import utils
from config import get_config
from admin_access import is_admin_user
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
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0 or value > 10**11:
        return None
    minor = value * 100
    return int(minor) if minor == minor.to_integral_value() else None


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
    state = context.user_data.get(STATE_KEY)
    if state == "act_review_text":
        return await _handle_review_text(update, context, text)
    if state in ("act_objection", "act_cancel"):
        return await _handle_note(update, context, text, state)
    if context.user_data.get(STATE_KEY) != "act_wizard":
        return False
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_admin_user(config, user.id):
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
    if not user or not is_admin_user(config, user.id):
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

    if action == "cancel":
        context.user_data[STATE_KEY] = "act_cancel"
        context.user_data[DATA_KEY] = {"act_id": item_id}
        await utils.safe_reply_text(query.message, "Почему отзываете акт? Напишите причину или /cancel.", action="work_act_cancel_reason")
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
    if action in ("open", "accept", "object"):
        act = await asyncio.to_thread(
            admin_interface.admin_interface.get_work_act_document, act_id, telegram_user_id=user.id,
        )
        if not act or not act.get("text") or act.get("cancelled_at"):
            await utils.safe_reply_text(query.message, "Этот акт недоступен. Свяжитесь с исполнителем.", action="work_act_unavailable")
            return
        payload = {"telegram_user_id": user.id, "document_hash": act["document_hash"],
                   "callback_id": str(query.id)}
        if action == "open":
            text = act["text"]
            for offset in range(0, len(text), 3500):
                await context.bot.send_message(chat_id=user.id, text=text[offset:offset + 3500])
            viewed = await asyncio.to_thread(
                admin_interface.admin_interface.work_act_client_action, act_id, "viewed", payload,
            )
            if not viewed:
                await utils.safe_reply_text(query.message, "Не удалось подтвердить просмотр. Откройте акт повторно.", action="work_act_view_failed")
                return
            rows = [] if act.get("accepted_at") or act.get("objected_at") else [
                [InlineKeyboardButton("Принимаю работу", callback_data=f"act_c:accept:{act_id}")],
                [InlineKeyboardButton("Есть замечания", callback_data=f"act_c:object:{act_id}")],
            ]
            await utils.safe_reply_text(query.message,
                "Работа принята." if act.get("accepted_at") else "Замечания переданы исполнителю." if act.get("objected_at") else "Решение по акту:",
                reply_markup=InlineKeyboardMarkup(rows), action="work_act_read")
        elif action == "object":
            context.user_data[STATE_KEY] = "act_objection"
            context.user_data[DATA_KEY] = {"act_id": act_id, **payload}
            await utils.safe_reply_text(query.message, "Напишите замечания к работе одним сообщением или /cancel.", action="work_act_objections_prompt")
        else:
            result = await asyncio.to_thread(
                admin_interface.admin_interface.work_act_client_action, act_id, "accept", payload,
            )
            await utils.safe_reply_text(query.message,
                "Приёмка работы зафиксирована." if result else "Не удалось принять акт. Сначала откройте полный текст; при наличии замечаний нужна новая редакция.",
                action="work_act_accept")
            if result:
                await _notify_admin(context.bot, f"Клиент принял работу по акту № {act['act_number']}.", _act_admin_markup(act_id))
        return
    if action in ("rv", "rvp"):
        await _handle_review_button(query, context, user, action, act_id, parts[3] if len(parts) > 3 else "")
        return
    if action == "qr":
        # Платёжный QR (ГОСТ Р 56042): банк сам заполнит получателя, сумму и
        # назначение. Сканировать с другого устройства или открыть картинку из
        # галереи в приложении банка.
        qr = await asyncio.to_thread(
            admin_interface.admin_interface.get_work_act_payment_qr, act_id, telegram_user_id=user.id,
        )
        if not qr:
            await utils.safe_reply_text(
                query.message,
                "QR для этого акта недоступен — оплатите переводом по реквизитам из сообщения с актом.",
                action="work_act_qr_unavailable",
            )
            return
        photo = io.BytesIO(qr)
        photo.name = "qr-oplata.png"
        await context.bot.send_photo(
            chat_id=user.id,
            photo=photo,
            caption=(
                "QR для оплаты: отсканируйте в приложении банка (или откройте эту картинку "
                "из галереи) — получатель, сумма и назначение заполнятся сами. "
                "После перевода нажмите «Я оплатил(а)»."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Я оплатил(а)", callback_data=f"act_c:claim:{act_id}")]]
            ),
        )
        return
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


def _consent_markup(act_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Можно опубликовать на сайте (только имя)", callback_data=f"act_c:rvp:{act_id}:1")],
            [InlineKeyboardButton("Только для юриста", callback_data=f"act_c:rvp:{act_id}:0")],
        ]
    )


async def _handle_review_button(query, context, user, action: str, act_id: str, value: str) -> None:
    """Оценка 1–5 из просьбы об отзыве и согласие на публикацию (см. core client_reviews)."""
    if action == "rv":
        if value not in {"1", "2", "3", "4", "5"}:
            return
        result = await asyncio.to_thread(
            admin_interface.admin_interface.work_act_review, act_id, {"telegram_user_id": user.id, "score": int(value)}
        )
        if not result:
            await utils.safe_reply_text(query.message, "Не удалось сохранить оценку. Попробуйте позже.", action="review_score_failed")
            return
        context.user_data[STATE_KEY] = "act_review_text"
        context.user_data[DATA_KEY] = {"act_id": act_id}
        await utils.safe_reply_text(
            query.message,
            "Спасибо за оценку! Если хотите, напишите пару слов о работе — что понравилось или что можно "
            "улучшить. Или /cancel, если не хотите.",
            action="review_score_saved",
        )
        return
    result = await asyncio.to_thread(
        admin_interface.admin_interface.work_act_review,
        act_id,
        {"telegram_user_id": user.id, "publish_consent": value == "1"},
    )
    await utils.safe_reply_text(
        query.message,
        ("Спасибо! Отзыв поможет другим клиентам." if value == "1" else "Спасибо! Отзыв увидит только юрист.")
        if result
        else "Не удалось сохранить. Попробуйте позже.",
        action="review_consent_saved",
    )


async def _handle_review_text(update, context, text: str) -> bool:
    user, message = update.effective_user, update.effective_message
    if not user or not message:
        return False
    value = (text or "").strip()
    if value.lower() in ("/cancel", "отмена"):
        _clear(context)
        await utils.safe_reply_text(message, "Хорошо, спасибо за оценку!", action="review_text_cancel")
        return True
    if not 2 <= len(value) <= 2000:
        await utils.safe_reply_text(message, "Нужно от 2 до 2000 символов.", action="review_text_length")
        return True
    act_id = dict(context.user_data.get(DATA_KEY) or {}).get("act_id", "")
    result = await asyncio.to_thread(
        admin_interface.admin_interface.work_act_review, act_id, {"telegram_user_id": user.id, "text": value}
    )
    if not result:
        await utils.safe_reply_text(message, "Не удалось сохранить отзыв. Попробуйте ещё раз.", action="review_text_failed")
        return True
    _clear(context)
    await utils.safe_reply_text(
        message,
        "Спасибо за отзыв! Можно показать его на сайте? Будет видно только ваше имя, без фамилии и контактов.",
        reply_markup=_consent_markup(act_id),
        action="review_text_saved",
    )
    return True


async def _handle_note(update, context, text: str, state: str) -> bool:
    user, message = update.effective_user, update.effective_message
    if not user or not message:
        return False
    if state == "act_cancel" and not is_admin_user(config, user.id):
        _clear(context)
        return False
    value = (text or "").strip()
    if value.lower() in ("/cancel", "отмена"):
        _clear(context)
        await utils.safe_reply_text(message, "Действие отменено.", action="work_act_note_cancel")
        return True
    limit = 1000 if state == "act_cancel" else 4000
    if not 3 <= len(value) <= limit:
        await utils.safe_reply_text(message, f"Нужно от 3 до {limit} символов.", action="work_act_note_length")
        return True
    data = dict(context.user_data.get(DATA_KEY) or {})
    if state == "act_cancel":
        result = await asyncio.to_thread(admin_interface.admin_interface.cancel_work_act, data["act_id"], value)
    else:
        result = await asyncio.to_thread(admin_interface.admin_interface.work_act_client_action,
            data["act_id"], "object", {"telegram_user_id": user.id, "document_hash": data["document_hash"],
            "callback_id": f"message:{message.message_id}", "text": value})
    if not result:
        await utils.safe_reply_text(message, "Не удалось сохранить. Попробуйте ещё раз или свяжитесь с исполнителем.", action="work_act_note_failed")
        return True
    _clear(context)
    await utils.safe_reply_text(message, "Акт отозван." if state == "act_cancel" else "Замечания сохранены и переданы исполнителю.", action="work_act_note_saved")
    if state == "act_objection":
        await _notify_admin(context.bot, f"Замечания к акту № {result['act_number']}:\n{value[:3000]}",
            InlineKeyboardMarkup([[InlineKeyboardButton("Отозвать акт", callback_data=f"act_a:cancel:{result['id']}")]]))
    return True
