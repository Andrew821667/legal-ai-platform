"""Договор юридических услуг в клиентской и административной версиях бота."""

from __future__ import annotations

import asyncio
import io
import logging
import uuid

import admin_interface
import utils
from config import get_config
from core_api_bridge import core_api_bridge
from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

config = get_config()
logger = logging.getLogger(__name__)

STATE_KEY = "service_agreement_state"
DATA_KEY = "service_agreement_data"

_ADMIN_FIELDS = (
    ("subject", "Кратко сформулируйте вопрос, по которому заключается договор."),
    ("scope_text", "Перечислите, что именно входит в работу."),
    ("exclusions_text", "Что не входит в работу без отдельного согласования?"),
    ("schedule_text", "Укажите сроки и этапы работы."),
    ("price_text", "Укажите полную стоимость услуг в рублях."),
    ("payment_terms", "Укажите порядок и сроки оплаты."),
)

_CLIENT_FIELDS = {
    "person": (
        ("full_name", "Укажите ваши фамилию, имя и отчество полностью."),
        ("contact", "Укажите телефон или email для связи по договору."),
        ("address", "Укажите адрес регистрации."),
        (
            "identity_document",
            "Укажите вид документа, серию, номер, кем и когда он выдан.",
        ),
    ),
    "organization": (
        ("org_name", "Укажите полное наименование организации или ИП."),
        ("inn", "Укажите ИНН: 10 или 12 цифр."),
        ("ogrn", "Укажите ОГРН или ОГРНИП: 13 или 15 цифр."),
        ("address", "Укажите юридический адрес."),
        ("full_name", "Укажите ФИО представителя полностью."),
        ("position", "Укажите должность представителя."),
        (
            "authority_basis",
            "Укажите основание полномочий: например, устав или доверенность с датой и номером.",
        ),
        ("contact", "Укажите телефон или email для связи по договору."),
    ),
}

_STATUS = {
    "draft": "черновик",
    "sent": "направлен",
    "viewed": "просмотрен",
    "signed": "подписан",
    "declined": "отклонён",
    "expired": "срок истёк",
    "superseded": "заменён новой редакцией",
    "cancelled": "отменён",
}

_CONFLICT = {
    "unchecked": "не проверен",
    "clear": "конфликтов нет",
    "potential": "нужна дополнительная проверка",
    "conflict": "обнаружен конфликт",
}

_NO_AGREEMENT_NOTE = "Обращение закрыто без заключения договора/соглашения."


def _clear(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    ctx.user_data.pop(STATE_KEY, None)
    ctx.user_data.pop(DATA_KEY, None)


def _doc_markup(agreement_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Открыть договор", callback_data=f"sa_c:open:{agreement_id}")],
            [
                InlineKeyboardButton("Подписать", callback_data=f"sa_c:sign:{agreement_id}"),
                InlineKeyboardButton("Задать вопрос", callback_data=f"sa_c:q:{agreement_id}"),
            ],
            [InlineKeyboardButton("Отказаться", callback_data=f"sa_c:no:{agreement_id}")],
        ]
    )


def _proposal_markup(agreement_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Заполнить данные и открыть проект",
                    callback_data=f"sa_c:open:{agreement_id}",
                )
            ],
            [InlineKeyboardButton("Задать вопрос", callback_data=f"sa_c:q:{agreement_id}")],
            [InlineKeyboardButton("Отказаться", callback_data=f"sa_c:no:{agreement_id}")],
        ]
    )


def _client_type_markup(agreement_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Физическое лицо",
                    callback_data=f"sa_c:person:{agreement_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Организация или ИП",
                    callback_data=f"sa_c:organization:{agreement_id}",
                )
            ],
            [InlineKeyboardButton("Задать вопрос", callback_data=f"sa_c:q:{agreement_id}")],
        ]
    )


def _admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("К обращениям", callback_data="sa_a:menu")]])


def _summary(item: dict) -> str:
    """Выжимка условий договора.

    Текст приходит из ядра: там же он собирается для отправки клиенту из
    рабочего места юриста. Пока формулировка жила здесь, второй отправитель
    означал бы вторую копию — а разошедшиеся копии на этой неделе уже дважды
    приводили к тихим сбоям.

    Локальная сборка осталась запасной: если ядро старой версии не прислало
    готовый текст, лучше показать собранный на месте, чем пустоту.
    """
    ready = item.get("summary_text")
    if ready:
        return str(ready)

    details = "заполнены" if item.get("client_details_complete") else "нужно заполнить"
    return (
        f"Договор № {item.get('agreement_number') or 'без номера'}\n"
        f"Статус: {_STATUS.get(item.get('status'), item.get('status') or 'неизвестен')}\n"
        f"Предмет: {item.get('subject') or 'не указан'}\n"
        f"Стоимость: {item.get('price_text') or 'не указана'}\n"
        f"Оплата: {item.get('payment_terms') or 'не указана'}\n"
        f"Данные клиента: {details}"
    )


def _client_value_error(field: str, value: str) -> str | None:
    if field == "inn" and (not value.isdigit() or len(value) not in {10, 12}):
        return "ИНН должен содержать 10 или 12 цифр. Введите его ещё раз."
    if field == "ogrn" and (not value.isdigit() or len(value) not in {13, 15}):
        return "ОГРН или ОГРНИП должен содержать 13 или 15 цифр. Введите его ещё раз."
    minimum = 5 if field in {"full_name", "address", "identity_document"} else 3
    if len(value) < minimum:
        return "Значение слишком короткое. Введите данные полностью."
    return None


async def _ask_client_type(message, agreement_id: str) -> None:
    await utils.safe_reply_text(
        message,
        "Перед подписанием заполните реквизиты стороны договора. Выберите, от чьего имени вы действуете.",
        reply_markup=_client_type_markup(agreement_id),
        action="agreement_client_type_prompt",
    )


async def _send_document(bot, chat_id: int, item: dict, caption: str) -> int | None:
    text = str(item.get("text") or "")
    if not text:
        return None
    data = io.BytesIO(text.encode("utf-8"))
    number = str(item.get("agreement_number") or "agreement").replace("/", "-")
    data.name = f"dogovor-{number}.txt"

    async def send():
        data.seek(0)
        return await bot.send_document(chat_id=chat_id, document=data, caption=caption)

    sent = await utils.telegram_call_with_retry(send, action="agreement_send_document")
    return getattr(sent, "message_id", None)


async def _notify_admin(bot, text: str, reply_markup: InlineKeyboardMarkup) -> bool:
    try:
        await bot.send_message(
            chat_id=config.ADMIN_TELEGRAM_ID,
            text=text,
            reply_markup=reply_markup,
        )
        return True
    except TelegramError as exc:
        logger.warning("Agreement admin notification failed: %s", type(exc).__name__)
        return False


async def show_admin_agreements(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает очередь юридических обращений администратору."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return
    if user.id != config.ADMIN_TELEGRAM_ID:
        await utils.safe_reply_text(
            message, "У вас нет доступа к этому разделу.", action="agreement_admin_denied"
        )
        return
    rows = await asyncio.to_thread(admin_interface.admin_interface.list_legal_intakes, 12)
    if not rows:
        await utils.safe_reply_text(
            message,
            "Юридических обращений пока нет или ядро временно недоступно.",
            reply_markup=_admin_back(),
            action="agreement_admin_empty",
        )
        return
    buttons = []
    for row in rows:
        name = str(row.get("lead_name") or "Без имени")[:24]
        state = str(row.get("status") or "received")
        buttons.append(
            [InlineKeyboardButton(f"{name} · {state}", callback_data=f"sa_a:i:{row['id']}")]
        )
    buttons.append([InlineKeyboardButton("В админ-панель", callback_data="admin_panel")])
    await utils.safe_reply_text(
        message,
        "Юридические обращения\n\nВыберите клиента. Договор можно направить только после NDA и проверки конфликта интересов.",
        reply_markup=InlineKeyboardMarkup(buttons),
        action="agreement_admin_list",
    )


async def _show_intake(message, intake_id: str) -> None:
    intake, agreements = await asyncio.gather(
        asyncio.to_thread(admin_interface.admin_interface.get_legal_intake, intake_id),
        asyncio.to_thread(
            admin_interface.admin_interface.list_service_agreements_for_intake, intake_id
        ),
    )
    if not intake:
        await utils.safe_reply_text(
            message,
            "Обращение не найдено.",
            reply_markup=_admin_back(),
            action="agreement_intake_missing",
        )
        return
    nda = await asyncio.to_thread(
        admin_interface.admin_interface.get_nda_status,
        str(intake.get("lead_id")),
    )
    latest = agreements[0] if agreements else None
    messages = []
    if latest:
        messages = await asyncio.to_thread(
            admin_interface.admin_interface.list_service_agreement_messages,
            str(latest["id"]),
        )
    text = (
        f"Обращение: {intake.get('lead_name') or 'Без имени'}\n"
        f"Контакт: {intake.get('lead_contact') or 'не указан'}\n"
        f"Компания: {intake.get('lead_company') or 'нет'}\n"
        f"Статус: {intake.get('status')}\n"
        f"Конфликт-проверка: {_CONFLICT.get(intake.get('conflict_status'), intake.get('conflict_status'))}\n"
        f"NDA: {'подписан' if (nda or {}).get('signed') else 'не подписан'}\n\n"
        f"Задача:\n{intake.get('description') or 'не указана'}"
    )
    if latest:
        text += f"\n\nПоследний договор:\n{_summary(latest)}"
    elif _NO_AGREEMENT_NOTE in str(intake.get("internal_note") or ""):
        text += "\n\nИтог: без заключения договора/соглашения."
    if messages:
        text += "\n\nПереписка по договору:"
        for entry in messages[-6:]:
            author = "Клиент" if entry.get("role") == "client" else "Юрист"
            body = " ".join(str(entry.get("text") or "").split())[:500]
            text += f"\n{author}: {body}"

    rows = [
        [
            InlineKeyboardButton("Конфликтов нет", callback_data=f"sa_a:conf:clear:{intake_id}"),
            InlineKeyboardButton(
                "Нужна проверка", callback_data=f"sa_a:conf:potential:{intake_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                "Конфликт обнаружен", callback_data=f"sa_a:conf:conflict:{intake_id}"
            )
        ],
    ]
    if not (nda or {}).get("signed") and intake.get("telegram_user_id"):
        rows.append(
            [InlineKeyboardButton("Попросить подписать NDA", callback_data=f"sa_a:nda:{intake_id}")]
        )
    if intake.get("conflict_status") == "clear" and (nda or {}).get("signed"):
        rows.append(
            [InlineKeyboardButton("Подготовить договор", callback_data=f"sa_a:new:{intake_id}")]
        )
    if latest and latest.get("status") == "draft":
        rows.append(
            [InlineKeyboardButton("Открыть черновик", callback_data=f"sa_a:d:{latest['id']}")]
        )
    if latest and latest.get("client_telegram_user_id"):
        rows.append(
            [InlineKeyboardButton("Ответить клиенту", callback_data=f"sa_a:reply:{latest['id']}")]
        )
    if not latest and intake.get("status") != "closed":
        rows.append(
            [
                InlineKeyboardButton(
                    "Без заключения договора/соглашения",
                    callback_data=f"sa_a:none:{intake_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("К обращениям", callback_data="sa_a:menu")])
    await utils.safe_reply_text(
        message,
        text[:3900],
        reply_markup=InlineKeyboardMarkup(rows),
        action="agreement_intake_detail",
    )


async def _start_wizard(message, context: ContextTypes.DEFAULT_TYPE, intake: dict) -> None:
    token = uuid.uuid4().hex[:12]
    context.user_data[STATE_KEY] = "admin_wizard"
    context.user_data[DATA_KEY] = {
        "intake_id": str(intake["id"]),
        "lead_id": str(intake["lead_id"]),
        "telegram_user_id": intake.get("telegram_user_id"),
        "field_index": 0,
        "token": token,
    }
    await utils.safe_reply_text(
        message,
        _ADMIN_FIELDS[0][1] + "\n\nДля отмены напишите /cancel.",
        action="agreement_admin_wizard_start",
    )


async def _finish_wizard(message, context: ContextTypes.DEFAULT_TYPE, data: dict) -> None:
    payload = {key: data[key] for key, _ in _ADMIN_FIELDS}
    payload.update(
        {
            "intake_id": data["intake_id"],
            "prepared_by_telegram_user_id": config.ADMIN_TELEGRAM_ID,
            "expires_in_days": 7,
        }
    )
    item = await asyncio.to_thread(
        admin_interface.admin_interface.create_service_agreement,
        payload,
        f"agreement:{data['intake_id']}:{data['token']}",
    )
    if not item:
        await utils.safe_reply_text(
            message,
            "Создать договор не удалось. Проверьте реквизиты Исполнителя, NDA и статус конфликт-проверки.",
            action="agreement_admin_create_failed",
        )
        return
    _clear(context)
    await _send_document(
        context.bot,
        message.chat_id,
        item,
        f"Точная редакция договора № {item['agreement_number']}",
    )
    await utils.safe_reply_text(
        message,
        _summary(item) + "\n\nПроверьте файл. После отправки эту редакцию изменить нельзя.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Отправить клиенту", callback_data=f"sa_a:send:{item['id']}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Составить заново", callback_data=f"sa_a:new:{data['intake_id']}"
                    )
                ],
                [InlineKeyboardButton("К обращению", callback_data=f"sa_a:i:{data['intake_id']}")],
            ]
        ),
        action="agreement_admin_preview",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    """Обрабатывает ввод юриста и клиента внутри договорного сценария."""
    state = context.user_data.get(STATE_KEY)
    if not state:
        return False
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return False
    value = (text or "").strip()
    if value.lower() in {"/cancel", "отмена"}:
        _clear(context)
        await utils.safe_reply_text(message, "Действие отменено.", action="agreement_flow_cancel")
        return True

    data = dict(context.user_data.get(DATA_KEY) or {})
    if state == "admin_wizard":
        if user.id != config.ADMIN_TELEGRAM_ID:
            _clear(context)
            return False
        idx = int(data.get("field_index") or 0)
        field = _ADMIN_FIELDS[idx][0]
        if len(value) < 2:
            await utils.safe_reply_text(
                message,
                "Ответ слишком короткий. Уточните формулировку.",
                action="agreement_admin_value_short",
            )
            return True
        data[field] = value
        idx += 1
        data["field_index"] = idx
        context.user_data[DATA_KEY] = data
        if idx < len(_ADMIN_FIELDS):
            await utils.safe_reply_text(
                message, _ADMIN_FIELDS[idx][1], action="agreement_admin_wizard_step"
            )
        else:
            await _finish_wizard(message, context, data)
        return True

    agreement_id = str(data.get("agreement_id") or "")
    if state == "client_details":
        client_type = str(data.get("client_type") or "")
        fields = _CLIENT_FIELDS.get(client_type)
        if not fields:
            _clear(context)
            return False
        idx = int(data.get("field_index") or 0)
        field = fields[idx][0]
        if error := _client_value_error(field, value):
            await utils.safe_reply_text(
                message,
                error,
                action="agreement_client_details_invalid",
            )
            return True
        data[field] = value
        idx += 1
        data["field_index"] = idx
        context.user_data[DATA_KEY] = data
        if idx < len(fields):
            await utils.safe_reply_text(
                message,
                fields[idx][1],
                action="agreement_client_details_step",
            )
            return True

        payload = {
            key: data.get(key)
            for key in (
                "client_type",
                "full_name",
                "contact",
                "address",
                "identity_document",
                "org_name",
                "inn",
                "ogrn",
                "position",
                "authority_basis",
            )
            if data.get(key) is not None
        }
        payload["telegram_user_id"] = user.id
        revised = await asyncio.to_thread(
            core_api_bridge.complete_service_agreement_client_details,
            agreement_id,
            payload,
        )
        if not revised:
            await utils.safe_reply_text(
                message,
                "Данные не удалось сохранить. Проверьте их и начните заполнение ещё раз из раздела договоров.",
                action="agreement_client_details_failed",
            )
            _clear(context)
            return True

        revised_id = str(revised["id"])
        _clear(context)
        try:
            message_id = await _send_document(
                context.bot,
                message.chat_id,
                revised,
                f"Точная редакция договора № {revised['agreement_number']}",
            )
        except TelegramError:
            await utils.safe_reply_text(
                message,
                "Реквизиты сохранены, но Telegram не доставил файл. Откройте актуальный договор ещё раз в разделе документов.",
                action="agreement_client_details_delivery_failed",
            )
            return True
        if message_id is None:
            await utils.safe_reply_text(
                message,
                "Реквизиты сохранены, но файл договора пока недоступен. Откройте его ещё раз в разделе документов.",
                action="agreement_client_details_document_missing",
            )
            return True
        viewed = await asyncio.to_thread(
            core_api_bridge.mark_service_agreement_viewed,
            revised_id,
            telegram_user_id=user.id,
            document_hash=str(revised["hash"]),
            message_id=message_id,
            callback_id=f"client-details:{message_id or user.id}",
        )
        if not viewed:
            await utils.safe_reply_text(
                message,
                "Реквизиты сохранены, но просмотр договора не удалось зафиксировать. Откройте договор ещё раз в разделе документов.",
                action="agreement_client_details_view_failed",
            )
            return True
        await utils.safe_reply_text(
            message,
            _summary(viewed)
            + "\n\nПроверьте реквизиты и условия в файле. После этого договор можно подписать.",
            reply_markup=_doc_markup(revised_id),
            action="agreement_client_details_saved",
        )
        await _notify_admin(
            context.bot,
            f"Клиент заполнил реквизиты по договору № {revised['agreement_number']}.",
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть обращение",
                            callback_data=f"sa_a:i:{revised['intake_id']}",
                        )
                    ]
                ]
            ),
        )
        return True

    if state == "client_question":
        saved = await asyncio.to_thread(
            core_api_bridge.add_service_agreement_question,
            agreement_id,
            telegram_user_id=user.id,
            text=value,
        )
        if not saved:
            await utils.safe_reply_text(
                message,
                "Вопрос не удалось отправить. Попробуйте ещё раз.",
                action="agreement_question_failed",
            )
            return True
        item = await asyncio.to_thread(core_api_bridge.get_service_agreement, agreement_id, user.id)
        _clear(context)
        notified = await _notify_admin(
            context.bot,
            f"Вопрос клиента по договору № {(item or {}).get('agreement_number', agreement_id)}:\n\n{value}",
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Ответить клиенту", callback_data=f"sa_a:reply:{agreement_id}"
                        )
                    ]
                ]
            ),
        )
        await utils.safe_reply_text(
            message,
            (
                "Вопрос передан юристу. Ответ придёт сюда."
                if notified
                else "Вопрос сохранён. Юрист увидит его в карточке договора."
            ),
            action="agreement_question_sent",
        )
        return True

    if state == "client_position":
        data["signer_position"] = value[:255]
        context.user_data[DATA_KEY] = data
        context.user_data[STATE_KEY] = "client_authority"
        await utils.safe_reply_text(
            message,
            "На каком основании вы действуете от имени организации? Например: устав, доверенность с датой и номером.",
            action="agreement_ask_authority",
        )
        return True

    if state == "client_authority":
        data["authority_basis"] = value[:500]
        context.user_data[DATA_KEY] = data
        context.user_data[STATE_KEY] = "client_confirm"
        await utils.safe_reply_text(
            message,
            "Проверьте данные:\n"
            f"Должность: {data.get('signer_position')}\n"
            f"Основание полномочий: {data.get('authority_basis')}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Подписать договор", callback_data=f"sa_c:confirm:{agreement_id}"
                        )
                    ]
                ]
            ),
            action="agreement_company_confirm",
        )
        return True

    if state == "admin_reply":
        if user.id != config.ADMIN_TELEGRAM_ID:
            _clear(context)
            return False
        item = await asyncio.to_thread(
            admin_interface.admin_interface.get_service_agreement, agreement_id
        )
        target = (item or {}).get("client_telegram_user_id")
        if not target:
            await utils.safe_reply_text(
                message, "Не найден Telegram-диалог клиента.", action="agreement_reply_no_target"
            )
            return True
        try:
            markup = (
                _doc_markup(agreement_id)
                if item.get("client_details_complete")
                else _proposal_markup(agreement_id)
            )
            await context.bot.send_message(
                chat_id=target,
                text=f"Ответ юриста по договору № {item.get('agreement_number')}:\n\n{value}",
                reply_markup=markup,
            )
        except TelegramError:
            await utils.safe_reply_text(
                message,
                "Telegram не доставил ответ клиенту.",
                action="agreement_reply_delivery_failed",
            )
            return True
        saved = await asyncio.to_thread(
            admin_interface.admin_interface.add_service_agreement_reply,
            agreement_id,
            telegram_user_id=user.id,
            text=value,
        )
        _clear(context)
        await utils.safe_reply_text(
            message,
            "Ответ доставлен клиенту."
            if saved
            else "Ответ доставлен, но запись в журнале не сохранилась.",
            action="agreement_reply_sent",
        )
        return True
    return False


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="agreement_admin_callback")
    if query.from_user.id != config.ADMIN_TELEGRAM_ID:
        await utils.safe_reply_text(
            query.message, "У вас нет доступа к этому разделу.", action="agreement_admin_denied"
        )
        return
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else "menu"

    if action == "menu":
        await show_admin_agreements(update, context)
        return
    if action == "i" and len(parts) == 3:
        await _show_intake(query.message, parts[2])
        return
    if action == "conf" and len(parts) == 4:
        state, intake_id = parts[2], parts[3]
        status_name = "conflict_check" if state != "clear" else "scope_preparation"
        await asyncio.to_thread(
            admin_interface.admin_interface.update_legal_intake,
            intake_id,
            {"conflict_status": state, "status": status_name},
        )
        await _show_intake(query.message, intake_id)
        return
    if action == "nda" and len(parts) == 3:
        intake = await asyncio.to_thread(admin_interface.admin_interface.get_legal_intake, parts[2])
        target = (intake or {}).get("telegram_user_id")
        if not target:
            await utils.safe_reply_text(
                query.message,
                "У клиента нет доступного Telegram-диалога.",
                action="agreement_nda_no_target",
            )
            return
        await utils.safe_send_message(
            context.bot,
            action="agreement_nda_invite",
            chat_id=target,
            text="Перед согласованием условий юридической помощи подпишите, пожалуйста, NDA.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть NDA",
                            callback_data=f"nda:open:{intake['lead_id']}",
                        )
                    ]
                ]
            ),
        )
        await utils.safe_reply_text(
            query.message,
            "Запрос на подписание NDA отправлен клиенту.",
            action="agreement_nda_requested",
        )
        return
    if action == "none" and len(parts) == 3:
        await utils.safe_reply_text(
            query.message,
            "Закрыть обращение без заключения договора/соглашения?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Подтвердить",
                            callback_data=f"sa_a:noneok:{parts[2]}",
                        )
                    ],
                    [InlineKeyboardButton("Назад", callback_data=f"sa_a:i:{parts[2]}")],
                ]
            ),
            action="agreement_without_confirmation",
        )
        return
    if action == "noneok" and len(parts) == 3:
        intake_id = parts[2]
        intake, agreements = await asyncio.gather(
            asyncio.to_thread(admin_interface.admin_interface.get_legal_intake, intake_id),
            asyncio.to_thread(
                admin_interface.admin_interface.list_service_agreements_for_intake,
                intake_id,
            ),
        )
        if not intake:
            await utils.safe_reply_text(
                query.message,
                "Обращение не найдено.",
                reply_markup=_admin_back(),
                action="agreement_without_intake_missing",
            )
            return
        if agreements:
            await utils.safe_reply_text(
                query.message,
                "По обращению уже создан договор. Сначала завершите работу с ним.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "К обращению",
                                callback_data=f"sa_a:i:{intake_id}",
                            )
                        ]
                    ]
                ),
                action="agreement_without_existing_agreement",
            )
            return
        note = str(intake.get("internal_note") or "").strip()
        if _NO_AGREEMENT_NOTE not in note:
            note = "\n".join(part for part in (note, _NO_AGREEMENT_NOTE) if part)
        updated = await asyncio.to_thread(
            admin_interface.admin_interface.update_legal_intake,
            intake_id,
            {"status": "closed", "internal_note": note},
        )
        if not updated:
            await utils.safe_reply_text(
                query.message,
                "Не удалось закрыть обращение.",
                reply_markup=_admin_back(),
                action="agreement_without_update_failed",
            )
            return
        await _show_intake(query.message, intake_id)
        return
    if action == "new" and len(parts) == 3:
        intake = await asyncio.to_thread(admin_interface.admin_interface.get_legal_intake, parts[2])
        if not intake or intake.get("conflict_status") != "clear":
            await utils.safe_reply_text(
                query.message,
                "Сначала завершите проверку конфликта интересов.",
                action="agreement_conflict_required",
            )
            return
        nda = await asyncio.to_thread(
            admin_interface.admin_interface.get_nda_status, str(intake["lead_id"])
        )
        if not (nda or {}).get("signed"):
            await utils.safe_reply_text(
                query.message,
                "Сначала клиент должен подписать NDA.",
                action="agreement_nda_required",
            )
            return
        await _start_wizard(query.message, context, intake)
        return
    if action == "d" and len(parts) == 3:
        item = await asyncio.to_thread(
            admin_interface.admin_interface.get_service_agreement, parts[2]
        )
        if not item:
            await utils.safe_reply_text(
                query.message, "Черновик не найден.", action="agreement_draft_missing"
            )
            return
        await _send_document(
            context.bot, query.message.chat_id, item, f"Договор № {item['agreement_number']}"
        )
        await utils.safe_reply_text(
            query.message,
            _summary(item),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Отправить клиенту", callback_data=f"sa_a:send:{item['id']}"
                        )
                    ]
                ]
            ),
            action="agreement_draft_opened",
        )
        return
    if action == "send" and len(parts) == 3:
        item = await asyncio.to_thread(
            admin_interface.admin_interface.get_service_agreement, parts[2]
        )
        target = (item or {}).get("client_telegram_user_id")
        if not item or not target or item.get("status") != "draft":
            await utils.safe_reply_text(
                query.message,
                "Черновик недоступен для отправки.",
                action="agreement_send_unavailable",
            )
            return
        sent = await context.bot.send_message(
            chat_id=target,
            text=(
                "Юрист подготовил проект договора.\n\n"
                + _summary(item)
                + "\n\nЗаполните свои реквизиты. После этого бот сформирует точную редакцию для проверки и подписания."
            ),
            reply_markup=_proposal_markup(str(item["id"])),
        )
        recorded = await asyncio.to_thread(
            admin_interface.admin_interface.mark_service_agreement_sent,
            str(item["id"]),
            chat_id=target,
            message_id=sent.message_id,
            telegram_user_id=query.from_user.id,
            callback_id=query.id,
        )
        if not recorded:
            try:
                await sent.delete()
            except TelegramError:
                pass
            await utils.safe_reply_text(
                query.message,
                "Отправка отменена: ядро не зафиксировало документ.",
                action="agreement_send_record_failed",
            )
            return
        await utils.safe_reply_text(
            query.message,
            "Проект договора отправлен клиенту для заполнения реквизитов.",
            reply_markup=_admin_back(),
            action="agreement_sent",
        )
        return
    if action == "reply" and len(parts) == 3:
        context.user_data[STATE_KEY] = "admin_reply"
        context.user_data[DATA_KEY] = {"agreement_id": parts[2]}
        await utils.safe_reply_text(
            query.message,
            "Напишите ответ клиенту. Для отмены: /cancel.",
            action="agreement_reply_prompt",
        )


async def handle_client_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="agreement_client_callback")
    user = query.from_user
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else "list"

    if action == "list":
        rows = await asyncio.to_thread(core_api_bridge.list_service_agreements, user.id)
        if not rows:
            await utils.safe_reply_text(
                query.message,
                "У вас пока нет договоров с юридической практикой.",
                action="agreement_client_empty",
            )
            return
        buttons = [
            [
                InlineKeyboardButton(
                    f"№ {row['agreement_number']} · {_STATUS.get(row['status'], row['status'])}",
                    callback_data=f"sa_c:open:{row['id']}",
                )
            ]
            for row in rows[:10]
        ]
        await utils.safe_reply_text(
            query.message,
            "Ваши договоры:",
            reply_markup=InlineKeyboardMarkup(buttons),
            action="agreement_client_list",
        )
        return
    if len(parts) != 3:
        return
    agreement_id = parts[2]
    item = await asyncio.to_thread(core_api_bridge.get_service_agreement, agreement_id, user.id)
    if not item:
        await utils.safe_reply_text(
            query.message,
            "Договор не найден или уже недоступен.",
            action="agreement_client_missing",
        )
        return
    if action == "open":
        if item.get("status") not in {"sent", "viewed", "signed"}:
            await utils.safe_reply_text(
                query.message, _summary(item), action="agreement_client_closed"
            )
            return
        if item.get("status") != "signed" and not item.get("client_details_complete"):
            await _ask_client_type(query.message, agreement_id)
            return
        try:
            message_id = await _send_document(
                context.bot,
                query.message.chat_id,
                item,
                f"Точная редакция договора № {item['agreement_number']}",
            )
        except TelegramError:
            await utils.safe_reply_text(
                query.message,
                "Telegram не доставил файл договора. Попробуйте открыть его ещё раз.",
                action="agreement_document_delivery_failed",
            )
            return
        if message_id is None:
            await utils.safe_reply_text(
                query.message,
                "Файл договора пока недоступен. Сообщите об этом юристу.",
                action="agreement_document_missing",
            )
            return
        if item.get("status") in {"sent", "viewed"}:
            viewed = await asyncio.to_thread(
                core_api_bridge.mark_service_agreement_viewed,
                agreement_id,
                telegram_user_id=user.id,
                document_hash=str(item["hash"]),
                message_id=message_id,
                callback_id=query.id,
            )
            if not viewed:
                await utils.safe_reply_text(
                    query.message,
                    "Просмотр не удалось зафиксировать. Подписание пока недоступно.",
                    action="agreement_view_failed",
                )
                return
        await utils.safe_reply_text(
            query.message,
            _summary(item),
            reply_markup=_doc_markup(agreement_id),
            action="agreement_opened",
        )
        return
    if action in _CLIENT_FIELDS:
        if item.get("status") != "sent" or item.get("client_details_complete"):
            await utils.safe_reply_text(
                query.message,
                "Эта редакция уже заполнена или недоступна. Откройте актуальный договор в разделе документов.",
                action="agreement_client_details_unavailable",
            )
            return
        context.user_data[STATE_KEY] = "client_details"
        context.user_data[DATA_KEY] = {
            "agreement_id": agreement_id,
            "client_type": action,
            "field_index": 0,
        }
        await utils.safe_reply_text(
            query.message,
            _CLIENT_FIELDS[action][0][1] + "\n\nДля отмены напишите /cancel.",
            action="agreement_client_details_start",
        )
        return
    if action == "q":
        context.user_data[STATE_KEY] = "client_question"
        context.user_data[DATA_KEY] = {"agreement_id": agreement_id}
        await utils.safe_reply_text(
            query.message,
            "Напишите вопрос по условиям. Его получит юрист.",
            action="agreement_question_prompt",
        )
        return
    if action == "sign":
        if item.get("status") == "signed":
            await utils.safe_reply_text(
                query.message, "Этот договор уже подписан.", action="agreement_already_signed"
            )
            return
        if not item.get("client_details_complete"):
            await _ask_client_type(query.message, agreement_id)
            return
        if item.get("status") == "sent":
            await utils.safe_reply_text(
                query.message,
                "Сначала откройте точный текст договора.",
                reply_markup=_doc_markup(agreement_id),
                action="agreement_open_required",
            )
            return
        data = {
            "agreement_id": agreement_id,
            "document_hash": item.get("hash"),
            "signer_position": item.get("client_position"),
            "authority_basis": item.get("client_authority_basis"),
        }
        context.user_data[DATA_KEY] = data
        if item.get("client_org") and not (
            data.get("signer_position") and data.get("authority_basis")
        ):
            context.user_data[STATE_KEY] = "client_position"
            await utils.safe_reply_text(
                query.message,
                "Укажите вашу должность в организации.",
                action="agreement_ask_position",
            )
            return
        context.user_data[STATE_KEY] = "client_confirm"
        await utils.safe_reply_text(
            query.message,
            _summary(item)
            + "\n\nНажимая кнопку, вы подписываете именно открытую редакцию договора.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Подписать договор", callback_data=f"sa_c:confirm:{agreement_id}"
                        )
                    ]
                ]
            ),
            action="agreement_sign_confirm",
        )
        return
    if action == "confirm":
        data = dict(context.user_data.get(DATA_KEY) or {})
        if (
            context.user_data.get(STATE_KEY) != "client_confirm"
            or data.get("agreement_id") != agreement_id
        ):
            await utils.safe_reply_text(
                query.message,
                "Сначала откройте договор и подтвердите данные.",
                action="agreement_confirm_out_of_order",
            )
            return
        signed = await asyncio.to_thread(
            core_api_bridge.sign_service_agreement,
            agreement_id,
            telegram_user_id=user.id,
            telegram_username=user.username,
            document_hash=str(item["hash"]),
            signer_position=data.get("signer_position"),
            authority_basis=data.get("authority_basis"),
            callback_id=query.id,
        )
        if not signed:
            await utils.safe_reply_text(
                query.message,
                "Подписание не зафиксировано. Попробуйте ещё раз.",
                action="agreement_sign_failed",
            )
            return
        _clear(context)
        await utils.safe_reply_text(
            query.message,
            f"Договор № {item['agreement_number']} подписан. Копия остаётся доступна в разделе документов.",
            action="agreement_signed",
        )
        await _notify_admin(
            context.bot,
            f"Клиент подписал договор № {item['agreement_number']}.",
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть обращение", callback_data=f"sa_a:i:{item['intake_id']}"
                        )
                    ]
                ]
            ),
        )
        return
    if action == "no":
        await utils.safe_reply_text(
            query.message,
            "Отказаться от предложенных условий? Юрист увидит отказ и сможет подготовить новую редакцию.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Да, отказаться", callback_data=f"sa_c:no_yes:{agreement_id}"
                        )
                    ]
                ]
            ),
            action="agreement_decline_confirm",
        )
        return
    if action == "no_yes":
        declined = await asyncio.to_thread(
            core_api_bridge.decline_service_agreement,
            agreement_id,
            telegram_user_id=user.id,
            reason=None,
            action_id=query.id,
        )
        if not declined:
            await utils.safe_reply_text(
                query.message, "Отказ не удалось зафиксировать.", action="agreement_decline_failed"
            )
            return
        _clear(context)
        await utils.safe_reply_text(
            query.message,
            "Отказ зафиксирован. Юрист свяжется с вами по условиям.",
            action="agreement_declined",
        )
        await _notify_admin(
            context.bot,
            f"Клиент отказался от договора № {item['agreement_number']}.",
            InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть обращение", callback_data=f"sa_a:i:{item['intake_id']}"
                        )
                    ]
                ]
            ),
        )
