"""
Handlers: user
"""
import logging
import sqlite3
import time
import re
import asyncio
import json
import urllib.error
import urllib.request
from typing import Optional, Dict
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton
from telegram_ui import reply_button as KeyboardButton
from telegram_ui import normalize_button_text
import database
import ai_brain
import lead_qualifier
from config import Config
config = Config()
import utils
import email_sender
import security
import prompts
import content
import funnel
from handlers.constants import *
from handlers.helpers import extract_email, send_lead_magnet_email, notify_admin_new_lead

logger = logging.getLogger(__name__)
PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*(?:\d[\s\-()]*){10,11}")
_READER_START_PAYLOAD_RE = re.compile(r"^readerq_(?P<post_id>[0-9a-fA-F-]{36})$")
_EDITABLE_USER_FIELDS = {"first_name", "last_name", "username"}
_EDITABLE_LEAD_FIELDS = {"name", "email", "phone", "company"}
_PENDING_START_PAYLOAD_KEY = "pending_start_payload"


def _button_text_equals(text: str | None, expected: str) -> bool:
    return normalize_button_text(text).casefold() == normalize_button_text(expected).casefold()


def _extract_start_payload(context: ContextTypes.DEFAULT_TYPE) -> str:
    args = getattr(context, "args", None) or []
    if not args:
        return ""
    return str(args[0]).strip()


def _news_api_key() -> str:
    return (config.API_KEY_NEWS or config.API_KEY_ADMIN or config.API_KEY_BOT or "").strip()


def _fetch_post_context(post_id: str) -> Dict[str, str]:
    base_url = (config.CORE_API_URL or "").rstrip("/")
    api_key = _news_api_key()
    if not base_url or not api_key:
        return {}

    request = urllib.request.Request(
        url=f"{base_url}/api/v1/scheduled-posts/{post_id}",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.CORE_API_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        logger.warning("reader referral post fetch failed (%s): %s", error.code, post_id)
        return {}
    except Exception as error:
        logger.warning("reader referral post fetch error for %s: %s", post_id, error)
        return {}

    return {
        "title": str(payload.get("title") or "").strip(),
        "text": str(payload.get("text") or "").strip(),
        "source_url": str(payload.get("source_url") or "").strip(),
        "rubric": str(payload.get("rubric") or "").strip(),
        "format_type": str(payload.get("format_type") or "").strip(),
    }


def _build_reader_referral_lead_payload(
    *,
    user_first_name: str,
    post_id: str,
    post_context: Dict[str, str],
) -> Dict:
    title = (post_context.get("title") or "").strip()
    source_url = (post_context.get("source_url") or "").strip()
    rubric = (post_context.get("rubric") or "").strip()
    notes_parts = ["[READER_REFERRAL]", f"post_id={post_id}"]
    if title:
        notes_parts.append(f"title={title}")
    if source_url:
        notes_parts.append(f"source_url={source_url}")
    if rubric:
        notes_parts.append(f"rubric={rubric}")

    pain_point = (
        f"Нужно разобрать материал «{title}» и понять, как применить в юрфункции."
        if title
        else "Нужно разобрать материал из канала и применить в юридической работе."
    )
    return {
        "name": user_first_name or "Клиент из Reader",
        "pain_point": pain_point,
        "temperature": "warm",
        "status": "new",
        "service_category": "ai_legal_consulting",
        "specific_need": "Разбор публикации и план внедрения",
        "lead_magnet_type": "consultation",
        "lead_magnet_delivered": 0,
        "notification_sent": 0,
        "conversation_stage": "qualify",
        "cta_variant": "reader_referral",
        "cta_shown": 1,
        "notes": "\n".join(notes_parts)[:3500],
    }


async def _handle_reader_referral_start(
    *,
    message,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: Dict,
    user,
    post_id: str,
) -> bool:
    post_context = _fetch_post_context(post_id)
    lead_payload = _build_reader_referral_lead_payload(
        user_first_name=user.first_name or "",
        post_id=post_id,
        post_context=post_context,
    )

    lead_id = database.db.create_new_lead(user_data["id"], lead_payload)
    database.db.track_event(
        user_data["id"],
        "reader_referral_start",
        payload={
            "post_id": post_id,
            "post_title": post_context.get("title") or "",
            "source_url": post_context.get("source_url") or "",
        },
        lead_id=lead_id,
    )
    await notify_admin_new_lead(
        context,
        lead_id,
        lead_payload,
        user_data,
        is_update=False,
    )

    title = (post_context.get("title") or "").strip()
    title_block = f"Материал: {title}\n\n" if title else ""
    await utils.safe_reply_text(
        message,
        (
            "✅ Переход из ридер-бота принят, заявка создана.\n\n"
            f"{title_block}"
            "Можете сразу описать ваш вопрос по внедрению в 1-2 предложениях "
            "или отправить телефон кнопкой ниже."
        ),
        reply_markup=_consultation_contact_markup(),
        action="reader_referral_start",
    )
    return True


async def process_pending_start_payload(
    *,
    message,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: Dict,
    user,
) -> bool:
    payload = str((context.user_data or {}).pop(_PENDING_START_PAYLOAD_KEY, "") or "").strip()
    if not payload:
        return False

    match = _READER_START_PAYLOAD_RE.match(payload)
    if not match:
        return False

    return await _handle_reader_referral_start(
        message=message,
        context=context,
        user_data=user_data,
        user=user,
        post_id=match.group("post_id"),
    )

# Import admin panel function (avoid at module level due to potential circular import)
def get_show_admin_panel():
    from handlers.admin import show_admin_panel
    return show_admin_panel


def _pdn_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_PDN_MENU)


def _transborder_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_TRANSBORDER_MENU)


def _consultation_cta_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSULTATION_CTA_MENU)


def _documents_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(DOCUMENTS_MENU)


def _consultation_contact_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📲 Отправить телефон", request_contact=True)],
            [KeyboardButton("⬅️ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _services_inline_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(WORKSPACE_INLINE_MENU)


def _quick_nav_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(QUICK_NAV_MENU)


def _main_menu_markup(user_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(ADMIN_MENU if user_id == config.ADMIN_TELEGRAM_ID else MAIN_MENU, resize_keyboard=True)


def _profile_edit_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Исправить ФИО", callback_data="profile_edit_name"),
                InlineKeyboardButton("✉️ Исправить Email", callback_data="profile_edit_email"),
            ]
        ]
    )


def _profile_panel_markup(is_admin: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not is_admin:
        rows.extend(_profile_edit_markup().inline_keyboard)
    rows.extend(QUICK_NAV_MENU)
    return InlineKeyboardMarkup(rows)


def _personal_mode_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(PERSONAL_MODE_RETURN_MENU)


def _profile_edit_cancel_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("⬅️ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _clear_admin_lookup_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_lookup_action", None)
    context.user_data.pop("admin_lookup_field", None)


async def _handle_admin_lookup_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message_text: str,
) -> bool:
    action = context.user_data.get("admin_lookup_action")
    if not action:
        return False

    message = update.effective_message
    if not message:
        return True

    if message_text == "⬅️ Отмена":
        _clear_admin_lookup_state(context)
        await utils.safe_reply_text(
            message,
            "Ок, режим поиска/редактирования закрыт.",
            reply_markup=_main_menu_markup(config.ADMIN_TELEGRAM_ID),
            action="admin_lookup_cancel",
        )
        return True

    def _parse_id(raw: str) -> int | None:
        try:
            return int(raw.strip())
        except (TypeError, ValueError):
            return None

    if action == "card":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_card_invalid_id",
            )
            return True

        snapshot = admin_interface.admin_interface.get_user_snapshot(telegram_id)
        if not snapshot:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_card_not_found",
            )
            return True

        target_user = snapshot["user"]
        lead = snapshot.get("lead") or {}
        consent = snapshot.get("consent") or {}
        text = (
            f"🗂️ Карточка пользователя {telegram_id}\n\n"
            f"Username: @{target_user.get('username') or '—'}\n"
            f"Имя: {target_user.get('first_name') or '—'} {target_user.get('last_name') or ''}\n"
            f"Регистрация: {target_user.get('created_at') or '—'}\n"
            f"Последняя активность: {target_user.get('last_interaction') or '—'}\n\n"
            "Lead:\n"
            f"• Имя: {lead.get('name') or '—'}\n"
            f"• Email: {lead.get('email') or '—'}\n"
            f"• Телефон: {lead.get('phone') or '—'}\n"
            f"• Компания: {lead.get('company') or '—'}\n"
            f"• Статус: {lead.get('status') or '—'}\n\n"
            "Согласия:\n"
            f"• ПД: {'✅' if consent.get('consent_given') else '❌'}\n"
            f"• Трансграничная передача: {'✅' if consent.get('transborder_consent') else '❌'}\n"
            f"• Отозвано: {'✅' if consent.get('consent_revoked') else '❌'}"
        )
        await utils.safe_reply_text(message, text, action="admin_lookup_card_result")
        return True

    if action == "dialog":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_dialog_invalid_id",
            )
            return True

        target_user = database.db.get_user_by_telegram_id(telegram_id)
        if not target_user:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_dialog_not_found",
            )
            return True

        history = database.db.get_conversation_history(target_user["id"], limit=100)
        if not history:
            await utils.safe_reply_text(
                message,
                f"📝 История диалога ({telegram_id})\n\nДиалогов пока нет.",
                action="admin_lookup_dialog_empty",
            )
            return True

        lines = [f"📝 История диалога ({telegram_id})", ""]
        for item in history:
            role = "👤 Клиент" if item.get("role") == "user" else "🤖 Бот"
            ts = item.get("timestamp", "")
            text_part = item.get("message") or item.get("content") or ""
            lines.append(f"{role} [{ts}]:")
            lines.append(text_part)
            lines.append("")
        await utils.safe_reply_text(
            message,
            "\n".join(lines).strip(),
            action="admin_lookup_dialog_result",
        )
        return True

    if action == "revoke":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_revoke_invalid_id",
            )
            return True

        result = admin_interface.admin_interface.clear_user_data_by_telegram_id(telegram_id)
        if result is None:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_revoke_not_found",
            )
            return True

        await utils.safe_reply_text(
            message,
            (
                f"✅ Данные пользователя ID {telegram_id} очищены.\n\n"
                f"Изменено профилей: {result.get('users_updated', 0)}\n"
                f"Анонимизировано анкет: {result.get('leads_anonymized', 0)}\n"
                f"Удалено сообщений: {result.get('messages_deleted', 0)}"
            ),
            action="admin_lookup_revoke_done",
        )
        return True

    if action == "reset_new":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_reset_new_invalid_id",
            )
            return True

        result = admin_interface.admin_interface.reset_user_to_new_by_telegram_id(telegram_id)
        if result is None:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_reset_new_not_found",
            )
            return True

        await utils.safe_reply_text(
            message,
            (
                f"♻️ Пользователь ID {telegram_id} сброшен в состояние «как новый».\n\n"
                f"Лиды удалены: {result.get('leads_deleted', 0)}\n"
                f"Сообщения удалены: {result.get('messages_deleted', 0)}\n"
                f"Аналитика очищена: {result.get('events_deleted', 0)}"
            ),
            action="admin_lookup_reset_new_done",
        )
        return True

    if action == "delete_user":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_delete_user_invalid_id",
            )
            return True

        result = admin_interface.admin_interface.delete_user_by_telegram_id(telegram_id)
        if result is None:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_delete_user_not_found",
            )
            return True

        await utils.safe_reply_text(
            message,
            (
                f"🧨 Пользователь ID {telegram_id} полностью удален.\n\n"
                f"Профиль удален: {result.get('users_deleted', 0)}\n"
                f"Лиды удалены: {result.get('leads_deleted', 0)}\n"
                f"Сообщения удалены: {result.get('messages_deleted', 0)}\n"
                f"Аналитика удалена: {result.get('events_deleted', 0)}"
            ),
            action="admin_lookup_delete_user_done",
        )
        return True

    if action == "blacklist_add":
        parts = message_text.strip().split(maxsplit=1)
        telegram_id = _parse_id(parts[0]) if parts else None
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Формат: <telegram_id> [причина]\nНапример: 321681061 Спам/флуд",
                action="admin_blacklist_add_invalid",
            )
            return True

        reason = parts[1].strip() if len(parts) > 1 else "Заблокирован администратором через панель"
        security.security_manager.add_to_blacklist(telegram_id, reason)
        total_blocked = security.security_manager.get_stats().get("blacklisted_users", 0)
        await utils.safe_reply_text(
            message,
            (
                f"🚫 Пользователь {telegram_id} добавлен в черный список.\n"
                f"Причина: {reason}\n"
                f"Всего в списке: {total_blocked}"
            ),
            action="admin_blacklist_add_done",
        )
        return True

    if action == "blacklist_remove":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_blacklist_remove_invalid",
            )
            return True

        is_blocked, _ = security.security_manager.is_blacklisted(telegram_id)
        if not is_blocked:
            await utils.safe_reply_text(
                message,
                f"Пользователь {telegram_id} не найден в черном списке.",
                action="admin_blacklist_remove_not_found",
            )
            return True

        security.security_manager.remove_from_blacklist(telegram_id)
        total_blocked = security.security_manager.get_stats().get("blacklisted_users", 0)
        await utils.safe_reply_text(
            message,
            (
                f"✅ Пользователь {telegram_id} удален из черного списка.\n"
                f"Всего в списке: {total_blocked}"
            ),
            action="admin_blacklist_remove_done",
        )
        return True

    if action == "edit":
        field = context.user_data.get("admin_lookup_field")
        if not field:
            await utils.safe_reply_text(
                message,
                "Сначала выберите поле редактирования кнопкой в админ-панели.",
                action="admin_lookup_edit_no_field",
            )
            return True

        parts = message_text.strip().split(maxsplit=1)
        if len(parts) < 2:
            await utils.safe_reply_text(
                message,
                "Формат: <telegram_id> <новое значение>\nНапример: 321681061 new@email.com",
                action="admin_lookup_edit_bad_format",
            )
            return True

        telegram_id = _parse_id(parts[0])
        value = parts[1].strip()
        if telegram_id is None or not value:
            await utils.safe_reply_text(
                message,
                "Нужен корректный ID и новое значение.\nПример: 321681061 ООО Ромашка",
                action="admin_lookup_edit_bad_values",
            )
            return True

        target_user = database.db.get_user_by_telegram_id(telegram_id)
        if not target_user:
            await utils.safe_reply_text(
                message,
                f"Пользователь с ID {telegram_id} не найден.\nВведите другой ID или нажмите «⬅️ Отмена».",
                action="admin_lookup_edit_not_found",
            )
            return True

        if field in _EDITABLE_USER_FIELDS:
            updated = database.db.update_user_fields(target_user["id"], {field: value})
            if not updated:
                await utils.safe_reply_text(
                    message,
                    "Профиль пользователя не обновлен.",
                    action="admin_lookup_edit_user_not_updated",
                )
                return True
        elif field in _EDITABLE_LEAD_FIELDS:
            database.db.create_or_update_lead(target_user["id"], {field: value})
        else:
            await utils.safe_reply_text(
                message,
                f"Поле {field} недоступно для редактирования.",
                action="admin_lookup_edit_bad_field",
            )
            return True

        await utils.safe_reply_text(
            message,
            f"✅ Поле `{field}` обновлено для пользователя {telegram_id}.",
            action="admin_lookup_edit_done",
        )
        return True

    return False


def _is_pdn_consent_granted(consent_state: Dict) -> bool:
    return bool(consent_state.get("consent_given")) and not bool(consent_state.get("consent_revoked"))


def _format_profile_text(user_data: Dict, lead: Optional[Dict], consent_state: Dict, is_admin: bool) -> str:
    lead = lead or {}
    if is_admin:
        return (
            "👤 Ваш профиль\n\n"
            "Статус: Администратор\n"
            f"Имя: {user_data.get('first_name') or 'не указано'}\n"
            f"Фамилия: {user_data.get('last_name') or 'не указана'}\n"
            f"Username: @{user_data.get('username') or 'не указан'}\n"
            f"Telegram ID: {user_data.get('telegram_id')}\n\n"
            "Данные по заявке:\n"
            f"• Имя: {lead.get('name') or 'не указано'}\n"
            f"• Компания: {lead.get('company') or 'не указана'}\n"
            f"• Email: {lead.get('email') or 'не указан'}\n"
            f"• Телефон: {lead.get('phone') or 'не указан'}\n"
            f"• Температура: {lead.get('temperature') or 'не определена'}\n"
            f"• Статус: {lead.get('status') or 'new'}\n\n"
            f"{content.consent_status_text(consent_state)}"
        )

    return (
        "👤 Ваш профиль\n\n"
        f"Имя: {user_data.get('first_name') or 'не указано'}\n"
        f"Фамилия: {user_data.get('last_name') or 'не указана'}\n"
        f"Username: @{user_data.get('username') or 'не указан'}\n\n"
        "Контактные данные:\n"
        f"• Имя в заявке: {lead.get('name') or 'не указано'}\n"
        f"• Email: {lead.get('email') or 'не указан'}\n"
        f"• Телефон: {lead.get('phone') or 'не указан'}\n\n"
        f"{content.consent_user_status_text(consent_state)}\n\n"
        "Если в данных ошибка, используйте кнопки редактирования ниже."
    )


def _schedule_typing_indicator(chat, user_telegram_id: int) -> None:
    """Неблокирующий typing, чтобы сетевые лаги Telegram не тормозили ответ."""

    async def _send_typing() -> None:
        try:
            await asyncio.wait_for(chat.send_action(action="typing"), timeout=1.5)
            logger.info(f"Typing indicator sent for user {user_telegram_id}")
        except (asyncio.TimeoutError, TelegramError, OSError) as error:
            logger.debug(f"Typing indicator skipped for user {user_telegram_id}: {error}")

    asyncio.create_task(_send_typing())


def _append_profile_name_context(base_context: str, profile_first_name: Optional[str]) -> str:
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


def _extract_phone_candidate(text: str) -> Optional[str]:
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


def _persist_fasttrack_contact(user_db_id: int, user, message_text: str) -> None:
    payload: Dict[str, str] = {}
    email = extract_email(message_text)
    if email:
        payload["email"] = email

    phone = _extract_phone_candidate(message_text)
    if phone and utils.validate_phone(phone):
        payload["phone"] = utils.format_phone(phone)

    if payload:
        payload.setdefault("name", user.first_name)
        database.db.create_or_update_lead(user_db_id, payload)


def _looks_like_ack_only(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    return normalized in {
        "ок", "окей", "понял", "принял", "ясно", "спасибо", "благодарю",
        "хорошо", "договорились", "супер", "круто",
    }


def _looks_like_plain_greeting(text: str) -> bool:
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


def _looks_like_return_to_bot(text: str) -> bool:
    normalized = normalize_button_text(text).strip().lower()
    return normalized in {
        "↩️ вернуться к боту",
        "вернуться к боту",
        "вернуться",
        "/bot",
        "бот",
    }


def _looks_like_new_topic_after_handoff(text: str) -> bool:
    normalized = normalize_button_text(text).strip().lower()
    if not normalized:
        return False
    if _looks_like_ack_only(normalized):
        return False
    if _extract_phone_candidate(normalized):
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


def _build_new_phone_lead_payload(
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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        start_payload = _extract_start_payload(context)
        if start_payload:
            context.user_data[_PENDING_START_PAYLOAD_KEY] = start_payload
        logger.info(f"User {user.id} started bot")

        # Создаем или обновляем пользователя в БД
        user_id = database.db.create_or_update_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        chat = update.effective_chat
        if chat is not None:
            database.db.set_chat_mode(int(chat.id), "bot")

        # Для пользователей (кроме админа) сначала обязателен сбор согласия на ПД.
        if user.id != config.ADMIN_TELEGRAM_ID:
            consent_state = database.db.get_user_consent_state(user_id)
            if not _is_pdn_consent_granted(consent_state):
                consent_text = content.CONSENT_STEP_1_TEXT
                if _READER_START_PAYLOAD_RE.match(start_payload):
                    consent_text = (
                        f"{consent_text}\n\n"
                        "После подтверждения согласия сразу подхвачу ваш запрос по материалу из ридер-бота."
                    )
                await utils.safe_reply_text(
                    update.message,
                    consent_text,
                    reply_markup=_pdn_consent_markup(),
                    action="start_consent_step_1",
                )
                return

        # Приветственное сообщение + рабочий стол
        welcome_message = content.build_welcome_message(user.first_name)
        reply_markup = _main_menu_markup(user.id)
        workspace_markup = _services_inline_menu_markup()

        await utils.safe_reply_text(
            update.message,
            welcome_message,
            reply_markup=reply_markup,
            action="start_welcome",
        )
        await utils.safe_reply_text(
            update.message,
            content.WORKSPACE_TEXT,
            reply_markup=workspace_markup,
            action="start_workspace",
        )
        logger.info("Workspace sent on /start for user %s", user.id)

        user_data = database.db.get_user_by_id(user_id)
        if user_data:
            await process_pending_start_payload(
                message=update.message,
                context=context,
                user_data=user_data,
                user=user,
            )

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as e:
        logger.error(f"Error in start_command: {e}")
        await utils.safe_reply_text(update.message, "Произошла ошибка. Попробуйте еще раз.", action="start_fallback_error")



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await utils.safe_reply_text(
        update.message,
        content.HELP_MESSAGE,
        reply_markup=_quick_nav_markup(),
        action="help_command",
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile - карточка пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="profile_no_user")
        return

    snapshot = admin_interface.admin_interface.get_user_snapshot(user.id) or {
        "user": user_data,
        "lead": database.db.get_lead_by_user_id(user_data["id"]),
        "consent": database.db.get_user_consent_state(user_data["id"]),
    }
    lead = snapshot.get("lead")
    consent_state = snapshot.get("consent", {})
    is_admin = user.id == config.ADMIN_TELEGRAM_ID
    reply_markup = _profile_panel_markup(is_admin)
    await utils.safe_reply_text(
        update.message,
        _format_profile_text(snapshot.get("user", user_data), lead, consent_state, is_admin),
        reply_markup=reply_markup,
        action="profile_command",
    )


async def documents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /documents - список документов и действий по данным."""
    _ = context
    await utils.safe_reply_text(
        update.message,
        content.documents_list_text(),
        reply_markup=_documents_markup(),
        action="documents_command",
    )



async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /privacy - политика обработки ПД."""
    _ = context
    await utils.safe_reply_text(update.message, content.privacy_policy_text(), action="privacy_command")


async def user_agreement_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /user_agreement - пользовательское соглашение."""
    _ = context
    await utils.safe_reply_text(update.message, content.user_agreement_text(), action="user_agreement_command")


async def ai_policy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai_policy - политика использования ИИ."""
    _ = context
    await utils.safe_reply_text(update.message, content.ai_policy_text(), action="ai_policy_command")


async def marketing_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /marketing_consent - условия рассылок."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    await utils.safe_reply_text(update.message, content.marketing_consent_text(), action="marketing_consent_command")
    if user_data:
        database.db.set_user_marketing_consent(user_data["id"], True)


async def transborder_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transborder_consent - условия и управление согласием."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="transborder_no_user")
        return
    snapshot = admin_interface.admin_interface.get_user_snapshot(user.id) or {
        "consent": database.db.get_user_consent_state(user_data["id"])
    }
    consent_state = snapshot.get("consent", {})
    message = content.transborder_policy_text()
    if bool(consent_state.get("transborder_consent")):
        await utils.safe_reply_text(
            update.message,
            f"{message}\n\nСтатус: ✅ согласие активно.",
            action="transborder_status_active",
        )
        return
    await utils.safe_reply_text(
        update.message,
        f"{message}\n\nСтатус: ❌ согласие не дано.",
        reply_markup=_transborder_consent_markup(),
        action="transborder_status_missing",
    )


async def consent_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /consent_status - текущий статус согласий пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="consent_status_no_user")
        return
    snapshot = admin_interface.admin_interface.get_user_snapshot(user.id) or {"consent": database.db.get_user_consent_state(user_data["id"])}
    consent_state = snapshot.get("consent", {})
    is_admin = user.id == config.ADMIN_TELEGRAM_ID
    text = content.consent_status_text(consent_state) if is_admin else content.consent_user_status_text(consent_state)
    await utils.safe_reply_text(
        update.message,
        text,
        action="consent_status_command",
    )


async def export_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export_data - выгрузка данных пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(update.message, "Сначала выполните /start.", action="export_data_no_user")
        return
    payload = admin_interface.admin_interface.export_user_data(user.id)
    if not payload:
        await utils.safe_reply_text(update.message, "Данные пользователя не найдены.", action="export_data_not_found")
        return
    await utils.safe_reply_text(update.message, content.export_data_text(payload), action="export_data_command")


async def revoke_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /revoke_consent - отзыв согласий и удаление ПД."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return

    result = admin_interface.admin_interface.clear_user_data_by_telegram_id(user.id)
    if result is None:
        await utils.safe_reply_text(
            update.message,
            "Не удалось обработать отзыв согласия. Попробуйте позже.",
            action="revoke_consent_not_found",
        )
        return

    await utils.safe_reply_text(
        update.message,
        (
            f"{content.CONSENT_REVOKED_TEXT}\n\n"
            f"Изменено профилей: {result.get('users_updated', 0)}\n"
            f"Анонимизировано анкет: {result.get('leads_anonymized', 0)}\n"
            f"Удалено сообщений диалога: {result.get('messages_deleted', 0)}"
        ),
        action="revoke_consent_command",
    )


async def delete_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delete_data - алиас для /revoke_consent."""
    await revoke_consent_command(update, context)


async def correct_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /correct_data - запрос на исправление данных пользователем."""
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text(
            "Использование:\n"
            "/correct_data <что исправить>\n\n"
            "Пример:\n"
            "/correct_data Исправьте email на example@mail.ru"
        )
        return

    admin_text = (
        "📝 Запрос на исправление данных\n\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Имя: {user.first_name or '—'}\n\n"
        f"Запрос:\n{text}"
    )

    try:
        await context.bot.send_message(chat_id=config.ADMIN_TELEGRAM_ID, text=admin_text)
    except TelegramError as e:
        logger.warning(f"Failed to notify admin about correct_data request: {e}")

    await update.message.reply_text("✅ Запрос на исправление данных отправлен команде.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if user_data:
            # Очищаем историю диалога
            database.db.clear_conversation_history(user_data['id'])
            database.db.reset_user_funnel_state(user_data['id'])
            logger.info(f"Conversation reset for user {user.id}")

            await update.message.reply_text(
                "История диалога очищена. Начнем сначала!\n\n"
                "Чем могу помочь вам сегодня?"
            )
        else:
            await start_command(update, context)

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as e:
        logger.error(f"Error in reset_command: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте /start")



async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu - открывает рабочий стол."""
    try:
        reply_markup = _services_inline_menu_markup()
        
        # Используем effective_message вместо message (может быть None)
        message = update.effective_message
        if message:
            await message.reply_text(
                content.MENU_HEADER_TEXT,
                reply_markup=reply_markup
            )
            logger.info(f"Menu shown to user {update.effective_user.id}")
        
    except (TelegramError, KeyError, AttributeError) as e:
        logger.error(f"Error in menu_command: {e}")
        try:
            if update.effective_message:
                await update.effective_message.reply_text("Произошла ошибка. Попробуйте /start")
        except TelegramError:
            pass



def _normalize_magnet_type(value: Optional[str]) -> str:
    if value == "demo_analysis":
        return "demo"
    return value or ""


async def _handle_non_text_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_data: Dict,
    lead: Optional[Dict],
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
        logger.warning(f"Skipping non-text message update type: {update.update_id}")
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
        "Для демо-анализа можно приложить документ с подписью, где указан email."
    )
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пользовательских сообщений."""
    try:
        user = update.effective_user
        original_message = update.effective_message
        if not user or not original_message:
            return

        message_text = original_message.text or ""
        logger.info(f"Message from user {user.id}: {(message_text or '[non-text]')[:50]}")

        # Получаем или создаем пользователя
        user_data = database.db.get_user_by_telegram_id(user.id)
        if not user_data:
            database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            user_data = database.db.get_user_by_telegram_id(user.id)
            if not user_data:
                return

        lead = database.db.get_lead_by_user_id(user_data["id"])
        consent_state = database.db.get_user_consent_state(user_data["id"])
        has_pdn_consent = _is_pdn_consent_granted(consent_state)
        has_transborder_consent = bool(consent_state.get("transborder_consent"))
        is_admin = user.id == config.ADMIN_TELEGRAM_ID
        allow_lead_processing = (not is_admin) or config.ALLOW_ADMIN_TEST_LEADS
        chat = update.effective_chat
        chat_id = int(chat.id) if chat and getattr(chat, "id", None) is not None else user.id
        chat_mode = database.db.get_chat_mode(chat_id)

        if is_admin:
            handled_admin_lookup = await _handle_admin_lookup_input(update, context, message_text)
            if handled_admin_lookup:
                return

        if _button_text_equals(message_text, "✉️ Личное обращение"):
            database.db.set_chat_mode(chat_id, "personal")
            await utils.safe_reply_text(
                original_message,
                "Чат переведен в личный режим.\n\n"
                "Теперь можете писать Андрею напрямую: бот не будет отвечать и не будет "
                "обрабатывать сообщения как лиды.\n\n"
                "Когда захотите снова пользоваться ботом, нажмите «↩️ Вернуться к боту».",
                reply_markup=_personal_mode_markup(),
                action="personal_mode_enabled",
            )
            return

        if chat_mode == "personal":
            if _looks_like_return_to_bot(message_text):
                database.db.set_chat_mode(chat_id, "bot")
                database.db.reset_user_funnel_state(user_data["id"])
                await utils.safe_reply_text(
                    original_message,
                    content.build_welcome_message(user.first_name),
                    reply_markup=_main_menu_markup(user.id),
                    action="personal_mode_return_text",
                )
            return

        if not is_admin and not has_pdn_consent:
            await original_message.reply_text(
                content.CONSENT_STEP_1_TEXT,
                reply_markup=_pdn_consent_markup(),
            )
            return

        # В новой сессии всегда сначала показываем стартовый UX
        # (приветствие + рабочий стол), даже если пользователь сразу пишет вопрос.
        history_preview = database.db.get_conversation_history(user_data["id"], limit=1)
        if message_text and not history_preview:
            await utils.safe_reply_text(
                original_message,
                content.build_welcome_message(user.first_name),
                reply_markup=_main_menu_markup(user.id),
                action="forced_welcome_new_session",
            )
            await utils.safe_reply_text(
                original_message,
                content.WORKSPACE_TEXT,
                reply_markup=_services_inline_menu_markup(),
                action="forced_workspace_new_session",
            )
            logger.info("Workspace sent on new session for user %s", user.id)
            return

        # На самом первом входящем сообщении-приветствии всегда отдаем
        # фиксированное приветствие, а не LLM-генерацию.
        if message_text and _looks_like_plain_greeting(message_text):
            await utils.safe_reply_text(
                original_message,
                content.build_welcome_message(user.first_name),
                reply_markup=_main_menu_markup(user.id),
                action="fixed_welcome_on_greeting",
            )
            await utils.safe_reply_text(
                original_message,
                content.WORKSPACE_TEXT,
                reply_markup=_services_inline_menu_markup(),
                action="workspace_on_greeting",
            )
            logger.info("Workspace sent on greeting for user %s", user.id)
            return

        # В non-text ветке поддерживаем сценарий демо (документ + email).
        if not message_text:
            await _handle_non_text_input(update, context, user_data, lead, allow_lead_processing)
            return

        # 🛡️ ПРОВЕРКА БЕЗОПАСНОСТИ (только для текстовых сообщений)
        is_allowed, block_reason = security.security_manager.check_all_security(user.id, message_text)
        if not is_allowed:
            logger.warning(f"Security check failed for user {user.id}: {block_reason}")
            await original_message.reply_text(block_reason)
            return

        profile_edit_field = context.user_data.get("profile_edit_field")
        if profile_edit_field:
            if _button_text_equals(message_text, "⬅️ Отмена"):
                context.user_data.pop("profile_edit_field", None)
                await utils.safe_reply_text(
                    original_message,
                    "Редактирование отменено.",
                    reply_markup=_main_menu_markup(user.id),
                    action="profile_edit_cancel",
                )
                return

            if profile_edit_field == "name":
                normalized_name = " ".join(message_text.split())
                if len(normalized_name) < 2:
                    await utils.safe_reply_text(
                        original_message,
                        "Введите корректные ФИО (минимум 2 символа) или нажмите «⬅️ Отмена».",
                        reply_markup=_profile_edit_cancel_markup(),
                        action="profile_edit_name_validation",
                    )
                    return

                parts = normalized_name.split(maxsplit=1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""
                database.db.create_or_update_user(
                    telegram_id=user.id,
                    username=user_data.get("username") or user.username,
                    first_name=first_name,
                    last_name=last_name,
                )
                database.db.create_or_update_lead(user_data["id"], {"name": normalized_name})
                context.user_data.pop("profile_edit_field", None)
                await utils.safe_reply_text(
                    original_message,
                    "✅ ФИО обновлены.",
                    reply_markup=_main_menu_markup(user.id),
                    action="profile_edit_name_success",
                )
                return

            if profile_edit_field == "email":
                new_email = message_text.strip()
                if not utils.validate_email(new_email):
                    await utils.safe_reply_text(
                        original_message,
                        "Email выглядит некорректно. Введите корректный email или нажмите «⬅️ Отмена».",
                        reply_markup=_profile_edit_cancel_markup(),
                        action="profile_edit_email_validation",
                    )
                    return

                database.db.create_or_update_lead(user_data["id"], {"email": new_email})
                context.user_data.pop("profile_edit_field", None)
                await utils.safe_reply_text(
                    original_message,
                    "✅ Email обновлен.",
                    reply_markup=_main_menu_markup(user.id),
                    action="profile_edit_email_success",
                )
                return

        # Проверяем есть ли pending lead magnet и email в сообщении
        if lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered"):
            normalized = _normalize_magnet_type(lead.get("lead_magnet_type"))
            if normalized != lead.get("lead_magnet_type"):
                database.db.create_or_update_lead(user_data["id"], {"lead_magnet_type": normalized})
                lead = database.db.get_lead_by_user_id(user_data["id"])

            if normalized == "consultation":
                phone_candidate = _extract_phone_candidate(message_text)
                if phone_candidate and utils.validate_phone(phone_candidate):
                    formatted_phone = utils.format_phone(phone_candidate)
                    new_lead_id = database.db.create_new_lead(
                        user_data["id"],
                        _build_new_phone_lead_payload(
                            lead,
                            first_name=user.first_name,
                            phone=formatted_phone,
                            source="consultation_phone_text",
                        ),
                    )
                    await handle_handoff_request(
                        update,
                        context,
                        source="consultation_phone_text",
                        lead_id_override=new_lead_id,
                        is_update_override=False,
                    )
                    return

            email = extract_email(message_text)
            if email:
                await send_lead_magnet_email(update, user_data, lead, email)
                return

        # Состояние воронки + A/B CTA
        funnel_state = database.db.get_user_funnel_state(user_data["id"])
        current_stage = funnel_state.get("conversation_stage") or "discover"
        cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_data["id"])
        cta_shown = bool(funnel_state.get("cta_shown"))
        if not funnel_state.get("cta_variant"):
            database.db.update_user_funnel_state(user_data["id"], cta_variant=cta_variant)

        # После handoff любое новое предметное сообщение считаем новым обращением:
        # открываем отдельный лид, чтобы не смешивать боли/задачи.
        if (
            allow_lead_processing
            and lead
            and current_stage == "handoff"
            and _looks_like_new_topic_after_handoff(message_text)
        ):
            carried_lead = dict(lead)
            new_lead_payload = {
                "name": user.first_name,
                "email": carried_lead.get("email"),
                "phone": carried_lead.get("phone"),
                "company": carried_lead.get("company"),
                "pain_point": message_text[:1000],
                "temperature": "cold",
                "status": "new",
                "notification_sent": 0,
                "lead_magnet_type": None,
                "lead_magnet_delivered": 0,
                "notes": (
                    f"{(carried_lead.get('notes') or '').strip()}\n"
                    f"[NEW_TOPIC] Новый кейс после handoff: {message_text[:300]}"
                ).strip(),
            }
            new_lead_id = database.db.create_new_lead(user_data["id"], new_lead_payload)
            database.db.update_user_funnel_state(
                user_data["id"],
                conversation_stage="discover",
                cta_variant=cta_variant,
                cta_shown=False,
            )
            database.db.update_lead_funnel_state_by_id(
                new_lead_id,
                conversation_stage="discover",
                cta_variant=cta_variant,
                cta_shown=False,
            )

            try:
                database.db.track_event(
                    user_data["id"],
                    "new_topic_after_handoff",
                    payload={"message": message_text[:300], "from_stage": "handoff", "to_stage": "discover"},
                    lead_id=new_lead_id,
                )
            except (sqlite3.Error, KeyError) as analytics_error:
                logger.warning(f"Failed to track new_topic_after_handoff: {analytics_error}")

            new_lead_payload_db = database.db.get_lead_by_id(new_lead_id) or {}
            await notify_admin_new_lead(
                context=context,
                lead_id=new_lead_id,
                lead_data=new_lead_payload_db,
                user_data={
                    "id": user_data["id"],
                    "telegram_id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                },
                is_update=False,
            )
            lead = new_lead_payload_db
            current_stage = "discover"
            cta_shown = False
            logger.info("New lead %s created from new topic after handoff for user %s", new_lead_id, user.id)

        # Обработка кнопок reply-меню
        if (
            _button_text_equals(message_text, "🧭 Рабочий стол")
            or _button_text_equals(message_text, "📋 Меню услуг")
            or message_text.strip().lower() in ["/menu", "menu", "/меню", "меню"]
        ):
            await menu_command(update, context)
            return

        if _button_text_equals(message_text, "📞 Консультация") or _button_text_equals(message_text, "✉️ Заказать консультацию"):
            if allow_lead_processing:
                database.db.create_or_update_lead(
                    user_data["id"],
                    {
                        "name": user.first_name,
                        "lead_magnet_type": "consultation",
                        "lead_magnet_delivered": False,
                    },
                )
            await utils.safe_reply_text(
                original_message,
                "Оставьте номер телефона, и команда свяжется с вами в ближайшее рабочее время.",
                reply_markup=_consultation_contact_markup(),
                action="consultation_phone_prompt",
            )
            return

        if _button_text_equals(message_text, "⬅️ Отмена"):
            await utils.safe_reply_text(
                original_message,
                "Ок, вернул основное меню.",
                reply_markup=_main_menu_markup(user.id),
                action="cancel_to_main_menu",
            )
            return

        if _button_text_equals(message_text, "👤 Мой профиль"):
            await profile_command(update, context)
            return

        if _button_text_equals(message_text, "📚 Документы"):
            await documents_command(update, context)
            return

        if _button_text_equals(message_text, "🔄 Начать заново"):
            await reset_command(update, context)
            return

        # Админ-панель (только для админа)
        if _button_text_equals(message_text, "⚙️ Админ-панель"):
            if user.id == config.ADMIN_TELEGRAM_ID:
                show_admin_panel_func = get_show_admin_panel()
                await show_admin_panel_func(update, context)
            else:
                await original_message.reply_text("У вас нет доступа к этой функции")
            return

        # Проверяем триггеры передачи админу
        if ai_brain.ai_brain.check_handoff_trigger(message_text):
            if allow_lead_processing:
                _persist_fasttrack_contact(user_data["id"], user, message_text)
            await handle_handoff_request(update, context, source="trigger")
            return

        if allow_lead_processing and funnel.should_fast_track_handoff(message_text, lead):
            database.db.add_message(user_data["id"], "user", message_text)
            _persist_fasttrack_contact(user_data["id"], user, message_text)
            await handle_handoff_request(update, context, source="fasttrack")
            return

        if not is_admin and not has_transborder_consent:
            await original_message.reply_text(
                content.TRANSBORDER_REQUIRED_TEXT,
                reply_markup=_transborder_consent_markup(),
            )
            return

        # ПРОВЕРКА: если клиент повторяет одно и то же сообщение 3+ раза
        # И прошло более 30 минут с начала диалога - завершаем разговор
        conversation_history = database.db.get_conversation_history(user_data["id"])
        if conversation_history:
            user_messages = [msg for msg in conversation_history if msg["role"] == "user"]
            if len(user_messages) >= 3:
                last_three = [msg.get("content", msg.get("message", "")).strip().lower() for msg in user_messages[-3:]]
                if len(set(last_three)) == 1:
                    import datetime

                    first_message_time = datetime.datetime.fromisoformat(conversation_history[0]["timestamp"])
                    current_time = datetime.datetime.now()
                    time_elapsed = (current_time - first_message_time).total_seconds() / 60
                    if time_elapsed > 30:
                        await original_message.reply_text(content.REPEAT_LOOP_FALLBACK_TEXT)
                        return

        # Сохраняем сообщение пользователя
        database.db.add_message(user_data["id"], "user", message_text)

        # Получаем историю диалога (включая текущее сообщение)
        conversation_history = database.db.get_conversation_history(user_data["id"])
        lead_id = lead["id"] if lead else None
        lead_data = None
        merged_lead_data = dict(lead or {})
        response_stage = current_stage

        # Стадию ответа считаем без дополнительного LLM-запроса,
        # чтобы не задерживать пользовательский ответ.
        if allow_lead_processing:
            response_stage = funnel.infer_stage(
                previous_stage=current_stage,
                user_message=message_text,
                lead_data=merged_lead_data,
            )

        # Генерируем ответ через AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        _schedule_typing_indicator(original_message.chat, user_data["telegram_id"])

        start_generation = time.time()
        preview_enabled = config.STREAMING_PREVIEW
        funnel_context = _append_profile_name_context(
            funnel.build_stage_context(response_stage, cta_variant, cta_shown),
            user_data.get("first_name") or user.first_name,
        )
        async for chunk in ai_brain.ai_brain.generate_response_stream(
            conversation_history,
            funnel_context=funnel_context,
        ):
            full_response += chunk
            chunk_buffer += chunk

            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 2.0)
                or (len(chunk_buffer) > 300 and current_time - last_update_time >= 3.0)
            )

            if preview_enabled and should_update:
                if sent_message is None:
                    if len(full_response.strip()) >= 100:
                        try:
                            preview_text = utils.format_ai_text_as_plain_symbols(full_response)
                            sent_message = await utils.safe_reply_text(
                                original_message,
                                preview_text,
                                action="streaming_initial_preview",
                            )
                            last_update_length = len(preview_text)
                            last_update_time = current_time
                            chunk_buffer = ""
                            logger.debug(f"Initial message sent: {len(full_response)} chars")
                        except TelegramError as e:
                            logger.warning(f"Failed to send initial message: {e}")
                else:
                    try:
                        preview_text = utils.format_ai_text_as_plain_symbols(full_response)
                        await utils.safe_edit_text(
                            sent_message,
                            preview_text,
                            action="streaming_preview_update",
                        )
                        last_update_length = len(preview_text)
                        last_update_time = current_time
                        chunk_buffer = ""
                        logger.debug(f"Message updated: {len(full_response)} chars")
                    except TelegramError as e:
                        logger.debug(f"Skipped update (rate limit): {e}")

        generation_time = time.time() - start_generation
        logger.info(f"Response generated in {generation_time:.2f}s ({len(full_response)} chars)")
        full_response = funnel.enforce_leadgen_response(
            response_text=full_response,
            stage=response_stage,
            user_message=message_text,
            cta_shown=cta_shown,
            cta_variant=cta_variant,
            lead_data=merged_lead_data,
        )
        full_response = utils.format_ai_text_as_plain_symbols(full_response)
        show_consultation_button = funnel.should_show_consultation_button(response_stage, cta_shown)
        consultation_button_sent = False

        if len(full_response) > 4096:
            logger.warning(f"Response too long ({len(full_response)} chars), splitting into parts")
            parts = utils.split_long_message(full_response, max_length=4000)

            if sent_message:
                try:
                    await sent_message.delete()
                except TelegramError:
                    pass

            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                await original_message.reply_text(part_msg)
                if i < len(parts) - 1:
                    await original_message.chat.send_action(action="typing")
                    await asyncio.sleep(0.5)
        else:
            if sent_message:
                try:
                    await utils.safe_edit_text(
                        sent_message,
                        full_response,
                        action="streaming_final_update",
                    )
                    logger.debug("Final message update sent")
                except TelegramError:
                    pass
            else:
                await utils.safe_reply_text(
                    original_message,
                    full_response,
                    action="assistant_final_message",
                )

        if show_consultation_button:
            try:
                await original_message.reply_text(
                    content.CONSULTATION_CTA_TEXT,
                    reply_markup=_consultation_cta_markup(),
                )
                consultation_button_sent = True
            except TelegramError as cta_error:
                logger.warning(f"Failed to send consultation CTA button: {cta_error}")

        database.db.add_message(user_data["id"], "assistant", full_response)

        # Аналитика: показ CTA (кнопка консультации / fallback в тексте)
        cta_visible_now = consultation_button_sent or funnel.is_cta_shown(full_response, cta_variant)
        if not cta_shown and cta_visible_now:
            database.db.update_user_funnel_state(
                user_data["id"],
                cta_variant=cta_variant,
                cta_shown=True,
            )
            database.db.update_lead_funnel_state(
                user_data["id"],
                cta_variant=cta_variant,
                cta_shown=True,
            )
            cta_shown = True
            try:
                database.db.track_event(
                    user_data["id"],
                    "cta_shown",
                    payload={
                        "variant": cta_variant,
                        "stage": response_stage,
                        "source": "consultation_button" if consultation_button_sent else "assistant_response",
                    },
                    lead_id=lead_id,
                )
            except (sqlite3.Error, KeyError) as analytics_error:
                logger.warning(f"Failed to track cta_shown event: {analytics_error}")

        # 🛡️ УЧЕТ ИСПОЛЬЗОВАННЫХ ТОКЕНОВ
        user_tokens = security.security_manager.estimate_tokens(message_text)
        assistant_tokens = security.security_manager.estimate_tokens(full_response)
        system_tokens = security.security_manager.estimate_tokens(prompts.SYSTEM_PROMPT)
        total_tokens = user_tokens + assistant_tokens + system_tokens
        security.security_manager.add_tokens_used(total_tokens, user_id=user.id)
        logger.debug(
            f"Tokens used: user={user_tokens}, assistant={assistant_tokens}, "
            f"system={system_tokens}, total={total_tokens}"
        )

        # Обновляем воронку сразу после ответа, чтобы следующий апдейт
        # не ждал завершения LLM-экстракции данных лида.
        if allow_lead_processing:
            if lead_id:
                database.db.update_lead_last_message_time(user_data["id"])

            next_stage = response_stage
            database.db.update_user_funnel_state(
                user_data["id"],
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )
            database.db.update_lead_funnel_state(
                user_data["id"],
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )

            if next_stage != current_stage:
                try:
                    database.db.track_event(
                        user_data["id"],
                        "stage_changed",
                        payload={"from": current_stage, "to": next_stage},
                        lead_id=lead_id,
                    )
                except (sqlite3.Error, KeyError) as analytics_error:
                    logger.warning(f"Failed to track stage_changed event: {analytics_error}")

            cta_was_shown = cta_shown
            merged_snapshot = dict(merged_lead_data)
            conversation_snapshot = list(conversation_history)
            user_db_id = user_data["id"]

            async def _post_response_lead_processing() -> None:
                try:
                    extracted = await ai_brain.ai_brain.extract_lead_data_async(conversation_snapshot)
                    if not extracted:
                        return

                    telegram_profile_name = (user_data.get("first_name") or user.first_name or "").strip()
                    if telegram_profile_name:
                        extracted["name"] = telegram_profile_name

                    merged_snapshot.update({k: v for k, v in extracted.items() if v is not None})
                    processed_lead_id = lead_qualifier.lead_qualifier.process_lead_data(user_db_id, extracted)
                    if processed_lead_id:
                        database.db.update_lead_last_message_time(user_db_id)
                        logger.info(f"Lead {processed_lead_id} updated in background")
                        temperature = extracted.get("temperature") or extracted.get("lead_temperature", "cold")
                        should_notify = (
                            temperature in ["hot", "warm"]
                            or (
                                extracted.get("name")
                                and (extracted.get("email") or extracted.get("phone"))
                                and extracted.get("pain_point")
                            )
                        )
                        if should_notify:
                            await notify_admin_new_lead(
                                context=context,
                                lead_id=processed_lead_id,
                                lead_data=extracted,
                                user_data=user_data,
                            )

                    lead_after = database.db.get_lead_by_user_id(user_db_id)
                    lead_magnet_already_selected = bool(lead_after and lead_after.get("lead_magnet_type"))
                    if (
                        not lead_magnet_already_selected
                        and not cta_was_shown
                        and ai_brain.ai_brain.should_offer_lead_magnet(extracted)
                    ):
                        await offer_lead_magnet(update, context)
                        database.db.update_user_funnel_state(
                            user_db_id,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        database.db.update_lead_funnel_state(
                            user_db_id,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        try:
                            database.db.track_event(
                                user_db_id,
                                "cta_shown",
                                payload={"variant": cta_variant, "stage": next_stage, "source": "lead_magnet_offer"},
                                lead_id=processed_lead_id,
                            )
                        except (sqlite3.Error, KeyError) as analytics_error:
                            logger.warning(f"Failed to track lead magnet CTA show: {analytics_error}")
                except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as background_error:
                    logger.warning(f"Background lead processing failed for user {user_db_id}: {background_error}")

            asyncio.create_task(_post_response_lead_processing())

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError, OSError) as e:
        if "Peer_id_invalid" not in str(e):
            logger.error(f"Error in handle_message: {e}")



async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    """Обработчик кнопок меню"""
    _ = context
    response = content.menu_response_by_button(button_text)
    await update.message.reply_text(response)



async def offer_lead_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предложение lead magnet"""
    _ = context
    reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
    await update.message.reply_text(content.LEAD_MAGNET_OFFER_TEXT, reply_markup=reply_markup)



async def handle_handoff_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    source: str = "trigger",
    lead_id_override: Optional[int] = None,
    is_update_override: Optional[bool] = None,
):
    """Обработка запроса на передачу админу"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if not user_data:
            await update.message.reply_text("Ошибка. Попробуйте /start")
            return

        # Уведомляем пользователя
        await utils.safe_reply_text(
            update.message,
            content.HANDOFF_ACK_TEXT,
            reply_markup=_main_menu_markup(user.id),
            action="handoff_ack",
        )
        await utils.safe_reply_text(
            update.message,
            "Навигация:",
            reply_markup=_quick_nav_markup(),
            action="handoff_quick_nav",
        )

        # Создаем лид только если его нет, либо используем явно переданный lead_id.
        lead = database.db.get_lead_by_user_id(user_data['id'])
        if lead_id_override is not None:
            lead_id = lead_id_override
            lead_payload_override = database.db.get_lead_by_id(lead_id)
            if lead_payload_override:
                lead = lead_payload_override
            is_update = bool(is_update_override) if is_update_override is not None else False
        else:
            if not lead:
                lead_id = database.db.create_or_update_lead(user_data['id'], {
                    'name': user.first_name
                })
                is_update = bool(is_update_override) if is_update_override is not None else False
            else:
                lead_id = lead['id']
                is_update = bool(is_update_override) if is_update_override is not None else True

        funnel_state = database.db.get_user_funnel_state(user_data['id'])
        previous_stage = funnel_state.get('conversation_stage') or 'discover'
        cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user_data['id'])

        database.db.update_user_funnel_state(
            user_data['id'],
            conversation_stage='handoff',
            cta_variant=cta_variant
        )
        if lead_id_override is not None:
            database.db.update_lead_funnel_state_by_id(
                lead_id,
                conversation_stage='handoff',
                cta_variant=cta_variant
            )
        else:
            database.db.update_lead_funnel_state(
                user_data['id'],
                conversation_stage='handoff',
                cta_variant=cta_variant
            )

        if previous_stage != 'handoff':
            try:
                database.db.track_event(
                    user_data['id'],
                    "stage_changed",
                    payload={"from": previous_stage, "to": "handoff"},
                    lead_id=lead_id
                )
            except (sqlite3.Error, KeyError) as analytics_error:
                logger.warning(f"Failed to track handoff stage change: {analytics_error}")

        lead_payload = database.db.get_lead_by_id(lead_id) or {}
        await notify_admin_new_lead(
            context=context,
            lead_id=lead_id,
            lead_data=lead_payload,
            user_data=user_data,
            is_update=is_update,
        )

        try:
            database.db.track_event(
                user_data['id'],
                "handoff_done",
                payload={"source": source, "cta_variant": cta_variant},
                lead_id=lead_id
            )
        except (sqlite3.Error, KeyError) as analytics_error:
            logger.warning(f"Failed to track handoff_done event: {analytics_error}")

        logger.info(f"Handoff request from user {user.id}")

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as e:
        logger.error(f"Error in handle_handoff_request: {e}")
