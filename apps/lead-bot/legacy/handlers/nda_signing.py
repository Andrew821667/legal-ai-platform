"""Подписание соглашения о конфиденциальности.

Один сценарий на два входа: кнопку в меню и предложение внутри уточняющего
диалога. Держать две реализации было бы приглашением к расхождению — правки в
одной тихо не доезжали бы в другую.

Почему клиент вводит данные сам. Аккаунт Telegram подтверждает канал, но не
личность: за подписью, состоящей из одного telegram_user_id, при споре пришлось
бы доказывать, кто за ним стоял. Введённые своей рукой ФИО и контакт эту дыру
закрывают — не полностью, но соразмерно этапу первичной консультации. Просить
паспортные данные ради полноты значило бы убить простоту, ради которой всё
затевалось.

Три вопроса — сознательный предел. Больше похоже на анкету и отпугивает на
шаге, где человек ещё только решает, доверять ли нам.
"""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

import database
import utils
from config import get_config
from core_api_bridge import core_api_bridge
from handlers.constants import workspace_row

logger = logging.getLogger(__name__)
config = get_config()

STAGE_KEY = "nda_flow_stage"
DATA_KEY = "nda_flow_data"
LEAD_KEY = "nda_flow_lead_id"
HASH_KEY = "nda_flow_hash"
RETURN_KEY = "nda_flow_return"

STAGE_NAME = "await_name"
STAGE_CONTACT = "await_contact"
STAGE_ORG = "await_org"

# Куда вернуться после подписания.
RETURN_MENU = "menu"
RETURN_DIALOG = "dialog"

_SELF_MARKERS = ("от себя", "себя", "физлицо", "физическое", "нет", "-", "—", "частное")

_MIN_NAME_PARTS = 2


def intro_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Читать текст соглашения", callback_data="nda:text")],
            [InlineKeyboardButton("Подписать", callback_data="nda:begin")],
            [InlineKeyboardButton("Не сейчас", callback_data="nda:cancel")],
        ]
    )


def confirm_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Подписать", callback_data="nda:confirm")],
            [InlineKeyboardButton("Исправить", callback_data="nda:begin")],
            [InlineKeyboardButton("Отмена", callback_data="nda:cancel")],
        ]
    )


async def _notify_admin_signed(
    bot, *, intake_id: str | None, signer_name: str, lead_id: str | None = None
) -> bool:
    callback = f"sa_a:i:{intake_id}" if intake_id else "sa_a:menu"
    text = (
        "Клиент подписал NDA.\n\n"
        f"Клиент: {signer_name}\n"
        "Следующий шаг: провести проверку конфликта интересов, "
        "затем подготовить соглашение об оказании юридической помощи."
    )
    try:
        await utils.safe_send_message(
            bot,
            action="nda_admin_signed",
            chat_id=config.ADMIN_TELEGRAM_ID,
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [
                    *workspace_row(lead_id),
                    [InlineKeyboardButton("Открыть обращение", callback_data=callback)],
                ]
            ),
        )
        return True
    except TelegramError as exc:
        logger.warning("NDA admin notification failed: %s", type(exc).__name__)
        return False


def build_intro(*, signed: bool, status: dict | None) -> str:
    """Что видит клиент, открыв подписание."""
    if signed and status:
        lines = [
            "Соглашение о конфиденциальности уже подписано.",
            "",
            f"Дата: {str(status.get('signed_at') or '')[:10]}",
        ]
        if status.get("signer_full_name"):
            lines.append(f"Подписант: {status['signer_full_name']}")
        if status.get("signer_org"):
            lines.append(f"Организация: {status['signer_org']}")
        lines.extend(
            [
                "",
                "Подписывать повторно не нужно — соглашение действует на все "
                "ваши обращения.",
            ]
        )
        return "\n".join(lines)

    return "\n".join(
        [
            "Соглашение о конфиденциальности",
            "",
            "Оно письменно закрепляет, что мы не раскрываем полученное от вас "
            "и используем материалы только для вашего вопроса.",
            "",
            "Подписание займёт минуту: понадобятся ваши ФИО и контакт — без них "
            "подпись не имеет силы. Мы зафиксируем дату и текст, который вы "
            "видели.",
            "",
            "Подписывается один раз и действует на все ваши обращения.",
        ]
    )


def build_summary(data: dict) -> str:
    lines = [
        "Проверьте перед подписанием:",
        "",
        f"ФИО: {data.get('signer_full_name', '')}",
        f"Контакт: {data.get('signer_contact', '')}",
    ]
    org = data.get("signer_org")
    lines.append(f"Организация: {org}" if org else "Подписывает: от себя лично")
    lines.extend(
        [
            "",
            "Нажимая «Подписать», вы соглашаетесь с текстом соглашения. "
            "Это простая электронная подпись: мы сохраним дату, ваши данные "
            "и контрольную сумму документа.",
        ]
    )
    return "\n".join(lines)


def looks_like_full_name(text: str) -> bool:
    """Хотя бы имя и фамилия.

    Проверка намеренно мягкая: отсеивает «да» и «Иван», но не спорит с людьми,
    у которых непривычное для нас имя.
    """
    parts = [p for p in (text or "").replace(".", " ").split() if len(p) > 1]
    return len(parts) >= _MIN_NAME_PARTS


def looks_like_contact(text: str) -> bool:
    """Телефон или почта."""
    value = (text or "").strip()
    if "@" in value and "." in value.split("@")[-1]:
        return True
    digits = [c for c in value if c.isdigit()]
    return len(digits) >= 10


def is_signing_for_self(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return not lowered or any(lowered.startswith(m) for m in _SELF_MARKERS)


def is_active(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return bool(context.user_data.get(STAGE_KEY))


def _reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in (STAGE_KEY, DATA_KEY, HASH_KEY):
        context.user_data.pop(key, None)


def _resolve_lead_id(context: ContextTypes.DEFAULT_TYPE, user_data: dict | None) -> str | None:
    """Идентификатор клиента в платформе.

    В диалоге он уже известен, из меню его нужно найти: подписание может
    начаться до того, как человек оставил обращение.
    """
    known = context.user_data.get(LEAD_KEY) or context.user_data.get("intake_dialog_lead_id")
    if known:
        return str(known)
    if not user_data:
        # Кнопка меню не приносит запись пользователя — находим сами.
        telegram_id = context.user_data.get("_nda_telegram_id")
        if not telegram_id:
            return None
        user_data = database.db.get_user_by_telegram_id(telegram_id)
        if not user_data:
            return None
    lead = database.db.get_local_lead_by_user_id(user_data.get("id"))
    core_id = (lead or {}).get("core_lead_id")
    return str(core_id) if core_id else None


async def open_signing(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_data: dict | None = None,
    return_to: str = RETURN_MENU,
    lead_id: str | None = None,
) -> None:
    """Показывает состояние соглашения и предлагает подписать."""
    message = update.effective_message or (
        update.callback_query.message if update.callback_query else None
    )
    if not message:
        return

    user = update.effective_user
    if user is not None:
        context.user_data["_nda_telegram_id"] = user.id
    context.user_data[RETURN_KEY] = return_to

    status = None
    resolved_lead_id = lead_id
    if not resolved_lead_id and user is not None:
        core_ctx = await asyncio.to_thread(
            core_api_bridge.get_nda_context_by_telegram,
            user.id,
        )
        if isinstance(core_ctx, dict) and core_ctx.get("lead_id"):
            resolved_lead_id = str(core_ctx["lead_id"])
            status = core_ctx

    if not resolved_lead_id:
        resolved_lead_id = _resolve_lead_id(context, user_data)
    if resolved_lead_id and status is None:
        status = await asyncio.to_thread(
            core_api_bridge.get_nda_status,
            resolved_lead_id,
            telegram_user_id=getattr(user, "id", None),
        )

    if lead_id and status is None:
        await utils.safe_reply_text(
            message,
            "Не удалось открыть соглашение по этому обращению. "
            "Попробуйте ещё раз или напишите юристу в этом диалоге.",
            action="nda_bound_lead_unavailable",
        )
        return

    context.user_data[LEAD_KEY] = resolved_lead_id

    signed = bool(isinstance(status, dict) and status.get("signed"))
    if signed:
        _reset(context)
        await utils.safe_reply_text(
            message, build_intro(signed=True, status=status), action="nda_already_signed"
        )
        return

    if not resolved_lead_id:
        # Подписывать нечего: клиент ещё не завёл обращение, и соглашение не
        # к чему привязать. Молча показывать кнопку подписания было бы обманом.
        await utils.safe_reply_text(
            message,
            "Чтобы подписать соглашение, нужно сначала оставить обращение — "
            "оно привязывается к вашему делу. Откройте «Юридическая практика», "
            "а вернуться к подписанию можно в любой момент.",
            action="nda_no_lead",
        )
        return

    await utils.safe_reply_text(
        message,
        build_intro(signed=False, status=None),
        reply_markup=intro_markup(),
        action="nda_intro",
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки сценария подписания."""
    query = update.callback_query
    if not query:
        return
    await utils.safe_answer_callback(query, action="nda_callback")

    payload = (query.data or "").partition(":")[2]
    action, _, lead_id = payload.partition(":")
    message = query.message

    if action == "open":
        await open_signing(update, context, lead_id=lead_id or None)
        return

    if action == "cancel":
        _reset(context)
        await utils.safe_reply_text(
            message,
            "Хорошо, к соглашению можно вернуться в любой момент. "
            "Документы примем и без него — просто отметим это в карточке.",
            action="nda_cancelled",
        )
        return

    if action == "text":
        document = await asyncio.to_thread(core_api_bridge.get_nda_document)
        if not isinstance(document, dict) or not document.get("text"):
            await utils.safe_reply_text(
                message,
                "Не удалось загрузить текст соглашения. Попробуйте позже.",
                reply_markup=intro_markup(),
                action="nda_text_failed",
            )
            return
        # Запоминаем контрольную сумму показанного текста: подпись должна
        # относиться именно к той редакции, которую человек прочитал.
        context.user_data[HASH_KEY] = document.get("hash")
        await utils.safe_reply_text(message, str(document["text"])[:4000], action="nda_text")
        await utils.safe_reply_text(
            message, "Подписать?", reply_markup=intro_markup(), action="nda_text_confirm"
        )
        return

    if action == "begin":
        if not context.user_data.get(HASH_KEY):
            document = await asyncio.to_thread(core_api_bridge.get_nda_document)
            if not isinstance(document, dict) or not document.get("text") or not document.get("hash"):
                await utils.safe_reply_text(
                    message,
                    "Не удалось загрузить текст соглашения. Попробуйте позже.",
                    reply_markup=intro_markup(),
                    action="nda_begin_text_failed",
                )
                return
            context.user_data[HASH_KEY] = document["hash"]
            await utils.safe_reply_text(
                message,
                str(document["text"])[:4000],
                action="nda_text_before_sign",
            )
        context.user_data[STAGE_KEY] = STAGE_NAME
        context.user_data[DATA_KEY] = {}
        await utils.safe_reply_text(
            message,
            "Как вас зовут? Укажите фамилию, имя и отчество полностью — "
            "они войдут в соглашение.",
            action="nda_ask_name",
        )
        return

    if action == "confirm":
        await _sign(update, context, message)
        return


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
) -> bool:
    """Ответы клиента на вопросы сценария. True — сообщение обработано."""
    stage = context.user_data.get(STAGE_KEY)
    if not stage:
        return False

    message = update.effective_message
    text = (message_text or "").strip()
    data = dict(context.user_data.get(DATA_KEY) or {})

    if stage == STAGE_NAME:
        if not looks_like_full_name(text):
            await utils.safe_reply_text(
                message,
                "Нужны фамилия и имя целиком — так соглашение будет иметь силу. "
                "Например: Иванов Иван Иванович.",
                action="nda_name_invalid",
            )
            return True
        data["signer_full_name"] = text[:255]
        context.user_data[DATA_KEY] = data
        context.user_data[STAGE_KEY] = STAGE_CONTACT
        await utils.safe_reply_text(
            message,
            "Телефон или электронная почта — по ним юрист сможет с вами связаться.",
            action="nda_ask_contact",
        )
        return True

    if stage == STAGE_CONTACT:
        if not looks_like_contact(text):
            await utils.safe_reply_text(
                message,
                "Это не похоже на телефон или почту. Напишите номер целиком "
                "или адрес вида имя@почта.ру.",
                action="nda_contact_invalid",
            )
            return True
        data["signer_contact"] = text[:255]
        context.user_data[DATA_KEY] = data
        context.user_data[STAGE_KEY] = STAGE_ORG
        await utils.safe_reply_text(
            message,
            "Подписываете от себя или от компании?\n\n"
            "Если от компании — напишите её название и ИНН: обязательства "
            "примет она. Если от себя — так и напишите.",
            action="nda_ask_org",
        )
        return True

    if stage == STAGE_ORG:
        if not is_signing_for_self(text):
            data["signer_org"] = text[:500]
        context.user_data[DATA_KEY] = data
        context.user_data.pop(STAGE_KEY, None)
        await utils.safe_reply_text(
            message,
            build_summary(data),
            reply_markup=confirm_markup(),
            action="nda_summary",
        )
        return True

    return False


async def _sign(update: Update, context: ContextTypes.DEFAULT_TYPE, message) -> None:
    """Фиксирует подпись и сообщает результат."""
    data = dict(context.user_data.get(DATA_KEY) or {})
    lead_id = context.user_data.get(LEAD_KEY)
    user = update.effective_user

    if not lead_id or not data.get("signer_full_name") or not data.get("signer_contact"):
        await utils.safe_reply_text(
            message,
            "Не хватает данных для подписания. Начнём заново?",
            reply_markup=intro_markup(),
            action="nda_incomplete",
        )
        return

    document_hash = context.user_data.get(HASH_KEY)
    if not document_hash:
        # Подписывают, не открыв текст. Хеш всё равно нужен: подпись должна
        # относиться к конкретной редакции, а не к «документу вообще».
        document = await asyncio.to_thread(core_api_bridge.get_nda_document)
        if isinstance(document, dict):
            document_hash = document.get("hash")

    result = await asyncio.to_thread(
        core_api_bridge.sign_nda,
        lead_id=str(lead_id),
        telegram_user_id=getattr(user, "id", None),
        telegram_username=getattr(user, "username", None),
        signer_name=getattr(user, "full_name", None),
        document_hash=str(document_hash or ""),
        signer_full_name=data["signer_full_name"],
        signer_contact=data["signer_contact"],
        signer_org=data.get("signer_org"),
    )

    if not isinstance(result, dict) or not result.get("signed"):
        logger.warning("Не удалось зафиксировать подписание NDA для %s", lead_id)
        await utils.safe_reply_text(
            message,
            "Не удалось зафиксировать подписание — попробуйте ещё раз чуть позже. "
            "Документы примем и без соглашения, юрист увидит отметку в карточке.",
            action="nda_sign_failed",
        )
        _reset(context)
        return

    _reset(context)
    already = bool(result.get("already_signed"))

    # Диалог должен узнать о подписи: дальше он предлагает прислать документы
    # и помечает каждый из них отметкой о соглашении.
    context.user_data["intake_dialog_nda_signed"] = True

    await utils.safe_reply_text(
        message,
        "Соглашение уже было подписано ранее — оно действует."
        if already
        else "Соглашение подписано. Дата и текст зафиксированы, копия хранится "
        "у нас; по вашему запросу пришлём её в любой момент.",
        action="nda_signed",
    )
    if not already:
        await _notify_admin_signed(
            context.bot,
            intake_id=result.get("intake_id"),
            signer_name=data["signer_full_name"],
            lead_id=str(lead_id),
        )
