"""
Admin and runtime callback handlers extracted from the main callback router.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import subprocess
from datetime import datetime

from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import inline_button as InlineKeyboardButton

import admin_interface
import content
import database
import security
import utils
from config import get_config
from handlers.constants import (
    ADMIN_CLEANUP_MENU,
    ADMIN_EDIT_FIELD_MENU,
    ADMIN_EXPORT_MENU,
    ADMIN_LEADS_MENU,
    ADMIN_PANEL_MENU,
    ADMIN_RUNTIME_MENU,
    ADMIN_SECURITY_MENU,
    ADMIN_USERS_MENU,
)
from handlers.markup import (
    admin_lookup_menu_markup as _admin_lookup_menu_markup,
    admin_user_clear_confirm_markup as _admin_user_clear_confirm_markup,
    admin_user_delete_confirm_markup as _admin_user_delete_confirm_markup,
    admin_user_detail_markup as _admin_user_detail_markup,
    admin_user_reset_new_confirm_markup as _admin_user_reset_new_confirm_markup,
    admin_users_list_markup as _admin_users_list_markup,
    clip_for_edit as _clip_for_edit,
)

config = get_config()
logger = logging.getLogger(__name__)


def _clear_admin_lookup_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_lookup_action", None)
    context.user_data.pop("admin_lookup_field", None)


def _fetch_users_page(page: int = 1, per_page: int = 5) -> tuple[list[dict], int, int]:
    page = max(1, page)
    total = admin_interface.admin_interface.get_total_users_count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page
    users = admin_interface.admin_interface.get_recent_users(limit=per_page, offset=offset)
    return users, total, total_pages


def _build_admin_users_page_text(users: list[dict], page: int, total_pages: int, total_users: int) -> str:
    lines = [
        "👥 Пользователи",
        "",
        f"Всего пользователей: {total_users}",
        f"Страница: {page}/{total_pages}",
        "",
        "Нажмите на пользователя для подробной карточки.",
        "Для поиска по ID используйте кнопку «🔎 Поиск / карточка по ID».",
        "Для сброса/удаления по ID используйте кнопки «♻️» и «🧨» в разделе пользователей.",
        "",
    ]
    for user in users:
        username = f"@{user.get('username')}" if user.get("username") else "без username"
        lines.append(
            f"ID {user.get('telegram_id')} | {username}\n"
            f"Имя: {user.get('first_name') or '—'} {user.get('last_name') or ''}\n"
            f"Создан: {user.get('created_at') or '—'}\n"
        )
    return "\n".join(lines).strip()


def _get_user_conversation_count(user_id: int | None) -> int:
    if not user_id:
        return 0
    conn = database.db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM conversations WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return int((row or {"total": 0})["total"])
    finally:
        conn.close()


def _build_admin_user_detail_text(target_user: dict, lead: dict | None, consent: dict, conversations_count: int) -> str:
    lead = lead or {}
    return (
        f"👤 Карточка пользователя ID {target_user.get('telegram_id')}\n\n"
        f"Username: @{target_user.get('username') or '—'}\n"
        f"Имя: {target_user.get('first_name') or '—'} {target_user.get('last_name') or ''}\n"
        f"Регистрация: {target_user.get('created_at') or '—'}\n"
        f"Последняя активность: {target_user.get('last_interaction') or '—'}\n\n"
        f"Сообщений в диалоге: {conversations_count}\n\n"
        "Lead:\n"
        f"• Имя: {lead.get('name') or '—'}\n"
        f"• Email: {lead.get('email') or '—'}\n"
        f"• Телефон: {lead.get('phone') or '—'}\n"
        f"• Компания: {lead.get('company') or '—'}\n"
        f"• Температура: {lead.get('temperature') or '—'}\n"
        f"• Статус: {lead.get('status') or '—'}\n\n"
        "Согласия:\n"
        f"• ПД: {'✅' if consent.get('consent_given') else '❌'}\n"
        f"• Трансграничная передача: {'✅' if consent.get('transborder_consent') else '❌'}\n"
        f"• Отзыв: {'✅' if consent.get('consent_revoked') else '❌'}"
    )


def _format_users_for_admin(title: str, users: list[dict]) -> str:
    if not users:
        return f"{title}\n\nПользователи не найдены."

    lines = [title, ""]
    for user in users:
        consent = "✅" if user.get("consent_given") else "❌"
        revoked = "🗑️" if user.get("consent_revoked") else "—"
        username = f"@{user.get('username')}" if user.get("username") else "без username"
        lines.append(
            f"ID: {user.get('telegram_id')} | {username}\n"
            f"Имя: {user.get('first_name') or '—'} {user.get('last_name') or ''}\n"
            f"Согласие ПД: {consent} | Отзыв: {revoked}\n"
            f"Последняя активность: {user.get('last_interaction') or user.get('created_at') or '—'}\n"
        )
    return "\n".join(lines).strip()


def _format_blacklist_for_admin() -> str:
    blocked = security.security_manager.list_blacklist(limit=300)
    if not blocked:
        return "📋 Черный список\n\nСписок пуст."
    lines = [
        "📋 Черный список",
        "",
        f"Всего заблокировано: {len(blocked)}",
        "",
    ]
    for item in blocked:
        telegram_id = item.get("telegram_user_id")
        reason = (item.get("reason") or "").strip()
        lines.append(f"• {telegram_id} — {reason}" if reason else f"• {telegram_id}")
    return "\n".join(lines)


def _detect_runtime_preset() -> str:
    sm = security.security_manager
    minute = sm.RATE_LIMITS.get("messages_per_minute")
    hour = sm.RATE_LIMITS.get("messages_per_hour")
    day = sm.RATE_LIMITS.get("messages_per_day")
    cooldown = round(float(sm.COOLDOWN_SECONDS), 1)
    max_len = int(sm.MAX_MESSAGE_LENGTH)
    if (minute, hour, day, cooldown, max_len) == (20, 120, 400, 0.3, 6000):
        return "soft"
    if (minute, hour, day, cooldown, max_len) == (10, 50, 200, 1.0, 4000):
        return "standard"
    if (minute, hour, day, cooldown, max_len) == (6, 30, 120, 1.5, 3000):
        return "strict"
    return "custom"


def _apply_runtime_preset(preset_name: str) -> str:
    sm = security.security_manager
    if preset_name == "soft":
        sm.RATE_LIMITS = {
            "messages_per_minute": 20,
            "messages_per_hour": 120,
            "messages_per_day": 400,
        }
        sm.COOLDOWN_SECONDS = 0.3
        sm.MAX_MESSAGE_LENGTH = 6000
        return "🟢 Применен мягкий пресет."
    if preset_name == "strict":
        sm.RATE_LIMITS = {
            "messages_per_minute": 6,
            "messages_per_hour": 30,
            "messages_per_day": 120,
        }
        sm.COOLDOWN_SECONDS = 1.5
        sm.MAX_MESSAGE_LENGTH = 3000
        return "🔴 Применен строгий пресет."

    sm.RATE_LIMITS = {
        "messages_per_minute": 10,
        "messages_per_hour": 50,
        "messages_per_day": 200,
    }
    sm.COOLDOWN_SECONDS = 1.0
    sm.MAX_MESSAGE_LENGTH = 4000
    return "🟡 Применен стандартный пресет."


def _format_runtime_settings_for_admin() -> str:
    sm = security.security_manager
    preset = _detect_runtime_preset()
    preset_label = {
        "soft": "🟢 soft",
        "standard": "🟡 standard",
        "strict": "🔴 strict",
        "custom": "⚪ custom",
    }[preset]
    return (
        "⚙️ Runtime-настройки лид-бота\n\n"
        f"Профиль лимитов: {preset_label}\n\n"
        "Анти-спам:\n"
        f"• в минуту: {sm.RATE_LIMITS['messages_per_minute']}\n"
        f"• в час: {sm.RATE_LIMITS['messages_per_hour']}\n"
        f"• в день: {sm.RATE_LIMITS['messages_per_day']}\n"
        f"• cooldown: {sm.COOLDOWN_SECONDS:.1f} сек\n"
        f"• макс длина сообщения: {sm.MAX_MESSAGE_LENGTH}\n\n"
        "Диалог/LLM:\n"
        f"• streaming preview: {'ON' if config.STREAMING_PREVIEW else 'OFF'}\n"
        f"• timeout LLM: {config.LLM_TIMEOUT_SECONDS:.1f} сек\n"
        f"• тест-лиды админа: {'ON' if config.ALLOW_ADMIN_TEST_LEADS else 'OFF'}\n\n"
        "Pending leads:\n"
        f"• idle timeout: {config.PENDING_LEADS_IDLE_MINUTES} мин\n"
        f"• batch size: {config.PENDING_LEADS_JOB_MAX_BATCH}\n"
        f"• check interval: {config.PENDING_LEADS_CHECK_INTERVAL_SECONDS} сек (после рестарта для нового расписания)"
    )


async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок админ-панели."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="admin_panel_answer")
    except TelegramError as answer_error:
        logger.warning(f"Failed to answer admin callback: {answer_error}")

    user = query.from_user
    if user.id != config.ADMIN_TELEGRAM_ID:
        await query.message.reply_text("У вас нет доступа к этой функции")
        return

    action = query.data

    try:
        users_page_match = re.fullmatch(r"admin_users_page_(\d+)", action or "")
        user_detail_match = re.fullmatch(r"admin_user_detail_(\d+)", action or "")
        user_export_match = re.fullmatch(r"admin_user_export_(\d+)", action or "")
        user_reset_match = re.fullmatch(r"admin_user_reset_dialog_(\d+)", action or "")
        user_reset_new_confirm_match = re.fullmatch(r"admin_user_reset_new_confirm_(\d+)", action or "")
        user_reset_new_match = re.fullmatch(r"admin_user_reset_new_(\d+)", action or "")
        user_clear_confirm_match = re.fullmatch(r"admin_user_clear_confirm_(\d+)", action or "")
        user_clear_match = re.fullmatch(r"admin_user_clear_(\d+)", action or "")
        user_delete_confirm_match = re.fullmatch(r"admin_user_delete_confirm_(\d+)", action or "")
        user_delete_match = re.fullmatch(r"admin_user_delete_(\d+)", action or "")

        if action == "admin_users_page_noop":
            return

        if action in {"admin_panel", "admin_section_users", "admin_section_commands", "admin_section_security"}:
            _clear_admin_lookup_state(context)

        if action == "admin_users_list" or users_page_match:
            requested_page = int(users_page_match.group(1)) if users_page_match else 1
            users, total_users, total_pages = _fetch_users_page(page=requested_page, per_page=5)
            current_page = min(max(1, requested_page), total_pages)
            users_text = _build_admin_users_page_text(users, current_page, total_pages, total_users)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(users_text),
                reply_markup=_admin_users_list_markup(users, current_page, total_pages),
                action=f"admin_users_list_{current_page}",
            )
            return

        if user_detail_match:
            telegram_id = int(user_detail_match.group(1))
            snapshot = await admin_interface.admin_interface.get_user_snapshot_async(telegram_id)
            if not snapshot:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_detail_not_found",
                )
                return

            target_user = snapshot["user"]
            conversations_count = _get_user_conversation_count(target_user.get("id"))
            detail_text = _build_admin_user_detail_text(
                target_user,
                snapshot.get("lead"),
                snapshot.get("consent", {}),
                conversations_count,
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(detail_text),
                reply_markup=_admin_user_detail_markup(telegram_id),
                action="admin_user_detail",
            )
            return

        if user_export_match:
            telegram_id = int(user_export_match.group(1))
            snapshot = await admin_interface.admin_interface.get_user_snapshot_async(telegram_id)
            if not snapshot:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_export_not_found",
                )
                return

            payload = await admin_interface.admin_interface.export_user_data_async(telegram_id)
            export_text = (
                f"🧾 Экспорт данных пользователя ID {telegram_id}\n\n"
                f"{content.export_data_text(payload)}"
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(export_text),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("◀️ К карточке", callback_data=f"admin_user_detail_{telegram_id}")],
                        [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
                    ]
                ),
                action="admin_user_export",
            )
            return

        if user_reset_match:
            telegram_id = int(user_reset_match.group(1))
            if not admin_interface.admin_interface.reset_user_dialog_by_telegram_id(telegram_id):
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_reset_not_found",
                )
                return

            snapshot = await admin_interface.admin_interface.get_user_snapshot_async(telegram_id) or {
                "user": admin_interface.admin_interface.get_user_by_telegram_id(telegram_id) or {},
                "lead": {},
                "consent": {},
            }
            detail_text = (
                "✅ Диалог пользователя сброшен.\n\n"
                + _build_admin_user_detail_text(snapshot.get("user", {}), snapshot.get("lead"), snapshot.get("consent", {}), 0)
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(detail_text),
                reply_markup=_admin_user_detail_markup(telegram_id),
                action="admin_user_reset_dialog",
            )
            return

        if user_clear_confirm_match:
            telegram_id = int(user_clear_confirm_match.group(1))
            await utils.safe_edit_text(
                query.message,
                (
                    f"⚠️ Подтвердите очистку данных пользователя ID {telegram_id}\n\n"
                    "Будут удалены сообщения диалога и анонимизированы данные лида.\n"
                    "Действие необратимо."
                ),
                reply_markup=_admin_user_clear_confirm_markup(telegram_id),
                action="admin_user_clear_confirm",
            )
            return

        if user_reset_new_confirm_match:
            telegram_id = int(user_reset_new_confirm_match.group(1))
            await utils.safe_edit_text(
                query.message,
                (
                    f"⚠️ Подтвердите сброс пользователя ID {telegram_id} в состояние «как новый»\n\n"
                    "Будут удалены все лиды, диалоги и аналитика пользователя.\n"
                    "Профиль Telegram сохранится."
                ),
                reply_markup=_admin_user_reset_new_confirm_markup(telegram_id),
                action="admin_user_reset_new_confirm",
            )
            return

        if user_delete_confirm_match:
            telegram_id = int(user_delete_confirm_match.group(1))
            await utils.safe_edit_text(
                query.message,
                (
                    f"⚠️ Подтвердите ПОЛНОЕ удаление пользователя ID {telegram_id}\n\n"
                    "Будет удален профиль пользователя и все связанные данные.\n"
                    "Действие необратимо."
                ),
                reply_markup=_admin_user_delete_confirm_markup(telegram_id),
                action="admin_user_delete_confirm",
            )
            return

        if user_clear_match:
            telegram_id = int(user_clear_match.group(1))
            result = admin_interface.admin_interface.clear_user_data_by_telegram_id(telegram_id)
            if result is None:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_clear_not_found",
                )
                return

            await utils.safe_edit_text(
                query.message,
                (
                    f"✅ Данные пользователя ID {telegram_id} очищены.\n\n"
                    f"Изменено профилей: {result.get('users_updated', 0)}\n"
                    f"Анонимизировано анкет: {result.get('leads_anonymized', 0)}\n"
                    f"Удалено сообщений: {result.get('messages_deleted', 0)}"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("◀️ К карточке", callback_data=f"admin_user_detail_{telegram_id}")],
                        [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
                    ]
                ),
                action="admin_user_clear",
            )
            return

        if user_reset_new_match:
            telegram_id = int(user_reset_new_match.group(1))
            result = admin_interface.admin_interface.reset_user_to_new_by_telegram_id(telegram_id)
            if result is None:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_reset_new_not_found",
                )
                return

            await utils.safe_edit_text(
                query.message,
                (
                    f"♻️ Пользователь ID {telegram_id} сброшен в состояние «как новый».\n\n"
                    f"Лиды удалены: {result.get('leads_deleted', 0)}\n"
                    f"Сообщения удалены: {result.get('messages_deleted', 0)}\n"
                    f"Аналитика очищена: {result.get('events_deleted', 0)}"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("◀️ К карточке", callback_data=f"admin_user_detail_{telegram_id}")],
                        [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
                    ]
                ),
                action="admin_user_reset_new",
            )
            return

        if user_delete_match:
            telegram_id = int(user_delete_match.group(1))
            result = admin_interface.admin_interface.delete_user_by_telegram_id(telegram_id)
            if result is None:
                await utils.safe_edit_text(
                    query.message,
                    "❌ Пользователь не найден.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                    ),
                    action="admin_user_delete_not_found",
                )
                return

            await utils.safe_edit_text(
                query.message,
                (
                    f"🧨 Пользователь ID {telegram_id} полностью удален.\n\n"
                    f"Профиль удален: {result.get('users_deleted', 0)}\n"
                    f"Лиды удалены: {result.get('leads_deleted', 0)}\n"
                    f"Сообщения удалены: {result.get('messages_deleted', 0)}\n"
                    f"Аналитика удалена: {result.get('events_deleted', 0)}"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")]]
                ),
                action="admin_user_delete",
            )
            return

        if action == "admin_section_leads":
            await utils.safe_edit_text(
                query.message,
                "📊 РАЗДЕЛ: ЛИДЫ И ВОРОНКА\n\nВыберите срез для просмотра:",
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_section_leads",
            )

        elif action == "admin_section_users":
            await utils.safe_edit_text(
                query.message,
                "👥 РАЗДЕЛ: ПОЛЬЗОВАТЕЛИ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_section_users",
            )

        elif action == "admin_section_export":
            await utils.safe_edit_text(
                query.message,
                "📥 РАЗДЕЛ: ЭКСПОРТ И ЛОГИ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                action="admin_section_export",
            )

        elif action == "admin_section_security" or action == "admin_security":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                "🛡️ РАЗДЕЛ: БЕЗОПАСНОСТЬ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_section_security",
            )

        elif action == "admin_runtime_settings":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                _format_runtime_settings_for_admin(),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action="admin_runtime_settings",
            )

        elif action == "admin_section_commands":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                (
                    "🧭 КОМАНДЫ И ПОИСК\n\n"
                    "Команды вручную больше не требуются.\n"
                    "Выберите действие кнопкой ниже, затем введите ID/значение по подсказке."
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_panel",
                    back_label="◀️ Назад в админ-панель",
                ),
                action="admin_section_commands",
            )

        elif action == "admin_users_recent":
            users = admin_interface.admin_interface.get_recent_users(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("🕒 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_recent",
            )

        elif action == "admin_users_no_consent":
            users = admin_interface.admin_interface.get_users_without_consent(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("⚠️ ПОЛЬЗОВАТЕЛИ БЕЗ СОГЛАСИЯ ПД (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_no_consent",
            )

        elif action == "admin_users_revoked":
            users = admin_interface.admin_interface.get_users_with_revoked_consent(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(_format_users_for_admin("🗑️ ОТОЗВАЛИ СОГЛАСИЕ (20)", users)),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
                action="admin_users_revoked",
            )

        elif action == "admin_users_lookup_help":
            _clear_admin_lookup_state(context)
            await utils.safe_edit_text(
                query.message,
                (
                    "🔎 Поиск пользователя по ID\n\n"
                    "Выберите действие кнопкой ниже.\n"
                    "После выбора введите ID (и при необходимости новое значение)."
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_users_lookup_help",
            )

        elif action == "admin_lookup_card_prompt":
            context.user_data["admin_lookup_action"] = "card"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🗂️ Карточка по ID\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_card_prompt",
            )

        elif action == "admin_lookup_dialog_prompt":
            context.user_data["admin_lookup_action"] = "dialog"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "💬 История диалога по ID\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_dialog_prompt",
            )

        elif action == "admin_lookup_revoke_prompt":
            context.user_data["admin_lookup_action"] = "revoke"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🗑️ Отзыв согласия и очистка ПД\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_revoke_prompt",
            )

        elif action == "admin_lookup_reset_new_prompt":
            context.user_data["admin_lookup_action"] = "reset_new"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "♻️ Сброс пользователя «как новый»\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Будут удалены диалоги, лиды и аналитика, профиль останется.\n\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_reset_new_prompt",
            )

        elif action == "admin_lookup_delete_prompt":
            context.user_data["admin_lookup_action"] = "delete_user"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🧨 Полное удаление пользователя\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Будет удален профиль и все связанные данные.\n\n"
                    "Пример: 321681061"
                ),
                reply_markup=_admin_lookup_menu_markup(
                    back_callback="admin_section_users",
                    back_label="◀️ Назад в раздел пользователей",
                ),
                action="admin_lookup_delete_prompt",
            )

        elif action == "admin_lookup_edit_prompt":
            context.user_data["admin_lookup_action"] = "edit"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "✏️ Редактирование ПД\n\n"
                    "1) Выберите поле кнопкой ниже.\n"
                    "2) Затем отправьте сообщение в формате:\n"
                    "<telegram_id> <новое значение>\n\n"
                    "Пример: 321681061 new@email.com"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                action="admin_lookup_edit_prompt",
            )

        elif action and action.startswith("admin_lookup_edit_field_"):
            field = action.replace("admin_lookup_edit_field_", "", 1)
            valid_fields = {"first_name", "last_name", "username", "name", "email", "phone", "company"}
            if field not in valid_fields:
                await utils.safe_edit_text(
                    query.message,
                    "Неизвестное поле редактирования.",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                    action="admin_lookup_edit_field_invalid",
                )
            else:
                context.user_data["admin_lookup_action"] = "edit"
                context.user_data["admin_lookup_field"] = field
                await utils.safe_edit_text(
                    query.message,
                    (
                        f"✏️ Выбрано поле: `{field}`\n\n"
                        "Теперь отправьте сообщение:\n"
                        "<telegram_id> <новое значение>\n\n"
                        "Пример: 321681061 Новое значение"
                    ),
                    reply_markup=InlineKeyboardMarkup(ADMIN_EDIT_FIELD_MENU),
                    action="admin_lookup_edit_field_selected",
                )

        elif action == "admin_stats":
            stats_message = admin_interface.admin_interface.format_statistics(30)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(stats_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_stats",
            )

        elif action == "admin_funnel_report":
            report_message = admin_interface.admin_interface.format_funnel_report(30)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(report_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_funnel_report",
            )

        elif action == "admin_funnel_export_csv":
            csv_data = admin_interface.admin_interface.export_funnel_report_csv(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(
                document=csv_data.encode("utf-8"),
                filename=filename,
                caption="📥 Funnel report (CSV)",
            )

        elif action == "admin_funnel_export_md":
            md_data = admin_interface.admin_interface.export_funnel_report_markdown(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.md"
            await query.message.reply_document(
                document=md_data.encode("utf-8"),
                filename=filename,
                caption="📝 Funnel report (Markdown)",
            )

        elif action == "admin_security_stats":
            stats = security.security_manager.get_stats()
            stats_since = stats["stats_start_time"].strftime("%d.%m.%Y %H:%M")
            stats_message = (
                "🛡️ СТАТИСТИКА БЕЗОПАСНОСТИ\n\n"
                f"📅 Статистика с: {stats_since}\n\n"
                f"📊 Токены:\n"
                f"• Использовано сегодня: {stats['total_tokens_today']:,}\n"
                f"• Дневной бюджет: {stats['daily_budget']:,}\n"
                f"• Осталось: {stats['budget_remaining']:,}\n"
                f"• Использовано: {stats['budget_percentage']:.1f}%\n\n"
                f"🚫 Безопасность:\n"
                f"• Заблокированных пользователей: {stats['blacklisted_users']}\n"
                f"• Подозрительных пользователей: {stats['suspicious_users']}\n\n"
                f"⚙️ Лимиты:\n"
                f"• Сообщений в минуту: {security.security_manager.RATE_LIMITS['messages_per_minute']}\n"
                f"• Сообщений в час: {security.security_manager.RATE_LIMITS['messages_per_hour']}\n"
                f"• Сообщений в день: {security.security_manager.RATE_LIMITS['messages_per_day']}\n"
                f"• Cooldown: {security.security_manager.COOLDOWN_SECONDS} сек\n"
                f"• Макс длина сообщения: {security.security_manager.MAX_MESSAGE_LENGTH} символов"
            )
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(stats_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_security_stats",
            )

        elif action == "admin_blacklist_list":
            await utils.safe_edit_text(
                query.message,
                _format_blacklist_for_admin(),
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_blacklist_list",
            )

        elif action == "admin_blacklist_add_prompt":
            context.user_data["admin_lookup_action"] = "blacklist_add"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "🚫 Блокировка пользователя\n\n"
                    "Введите сообщение в формате:\n"
                    "<telegram_id> [причина]\n\n"
                    "Примеры:\n"
                    "321681061\n"
                    "321681061 Спам/флуд"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_blacklist_add_prompt",
            )

        elif action == "admin_blacklist_remove_prompt":
            context.user_data["admin_lookup_action"] = "blacklist_remove"
            context.user_data.pop("admin_lookup_field", None)
            await utils.safe_edit_text(
                query.message,
                (
                    "✅ Разблокировка пользователя\n\n"
                    "Введите Telegram ID пользователя одним сообщением.\n"
                    "Пример: 321681061"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_blacklist_remove_prompt",
            )

        elif action == "admin_security_reset":
            security.security_manager.reset_runtime_state(clear_blacklist=False)
            await utils.safe_edit_text(
                query.message,
                (
                    "✅ Счетчики безопасности сброшены.\n\n"
                    f"Статистика пересчитана с {security.security_manager.stats_start_time.strftime('%d.%m.%Y %H:%M')}."
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_SECURITY_MENU),
                action="admin_security_reset",
            )

        elif action in {"admin_runtime_preset_soft", "admin_runtime_preset_standard", "admin_runtime_preset_strict"}:
            preset_key = action.rsplit("_", 1)[-1]
            apply_message = _apply_runtime_preset(preset_key)
            await utils.safe_edit_text(
                query.message,
                f"{apply_message}\n\n{_format_runtime_settings_for_admin()}",
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action=action,
            )

        elif action == "admin_runtime_toggle_streaming":
            config.STREAMING_PREVIEW = not config.STREAMING_PREVIEW
            await utils.safe_edit_text(
                query.message,
                (
                    f"🎬 Streaming preview: {'ON' if config.STREAMING_PREVIEW else 'OFF'}\n\n"
                    f"{_format_runtime_settings_for_admin()}"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action="admin_runtime_toggle_streaming",
            )

        elif action == "admin_runtime_toggle_admin_test":
            config.ALLOW_ADMIN_TEST_LEADS = not config.ALLOW_ADMIN_TEST_LEADS
            await utils.safe_edit_text(
                query.message,
                (
                    f"🧪 Тест-лиды админа: {'ON' if config.ALLOW_ADMIN_TEST_LEADS else 'OFF'}\n\n"
                    f"{_format_runtime_settings_for_admin()}"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action="admin_runtime_toggle_admin_test",
            )

        elif action in {"admin_runtime_timeout_15", "admin_runtime_timeout_25", "admin_runtime_timeout_40"}:
            config.LLM_TIMEOUT_SECONDS = float(action.split("_")[-1])
            await utils.safe_edit_text(
                query.message,
                (
                    f"🕒 Timeout LLM обновлен: {config.LLM_TIMEOUT_SECONDS:.0f} сек\n\n"
                    f"{_format_runtime_settings_for_admin()}"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action=action,
            )

        elif action in {"admin_runtime_idle_3", "admin_runtime_idle_5", "admin_runtime_idle_10"}:
            config.PENDING_LEADS_IDLE_MINUTES = int(action.split("_")[-1])
            await utils.safe_edit_text(
                query.message,
                (
                    f"⏱ Idle timeout обновлен: {config.PENDING_LEADS_IDLE_MINUTES} мин\n\n"
                    f"{_format_runtime_settings_for_admin()}"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action=action,
            )

        elif action in {"admin_runtime_batch_10", "admin_runtime_batch_20", "admin_runtime_batch_50"}:
            config.PENDING_LEADS_JOB_MAX_BATCH = int(action.split("_")[-1])
            await utils.safe_edit_text(
                query.message,
                (
                    f"📦 Batch size обновлен: {config.PENDING_LEADS_JOB_MAX_BATCH}\n\n"
                    f"{_format_runtime_settings_for_admin()}"
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_RUNTIME_MENU),
                action=action,
            )

        elif action == "admin_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(limit=20)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_leads",
            )

        elif action == "admin_hot_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature="hot", limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_hot_leads",
            )

        elif action == "admin_warm_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature="warm", limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_warm_leads",
            )

        elif action == "admin_cold_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature="cold", limit=10)
            await utils.safe_edit_text(
                query.message,
                _clip_for_edit(leads_message),
                reply_markup=InlineKeyboardMarkup(ADMIN_LEADS_MENU),
                action="admin_cold_leads",
            )

        elif action == "admin_logs":
            result = subprocess.run(["tail", "-50", config.LOG_FILE], capture_output=True, text=True)
            logs = result.stdout
            if not logs.strip():
                await utils.safe_edit_text(
                    query.message,
                    "📋 Логи пусты.",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                    action="admin_logs_empty",
                )
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await query.message.reply_document(
                    document=logs.encode("utf-8"),
                    filename=f"lead_bot_logs_tail_{timestamp}.txt",
                    caption="📋 Последние 50 строк логов",
                )

        elif action == "admin_export":
            csv_data = admin_interface.admin_interface.export_leads_to_csv()
            if csv_data:
                await query.message.reply_document(
                    document=csv_data.encode("utf-8") if isinstance(csv_data, str) else csv_data,
                    filename=f"leads_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    caption="📥 Экспорт лидов",
                )
            else:
                await utils.safe_edit_text(
                    query.message,
                    "Ошибка при экспорте данных",
                    reply_markup=InlineKeyboardMarkup(ADMIN_EXPORT_MENU),
                    action="admin_export_error",
                )

        elif action == "admin_cleanup":
            cleanup_message = (
                "🗑️ ОЧИСТКА ДАННЫХ\n\n"
                "⚠️ ВНИМАНИЕ: Данные будут удалены безвозвратно!\n\n"
                "Выберите что очистить:"
            )
            await utils.safe_edit_text(
                query.message,
                cleanup_message,
                reply_markup=InlineKeyboardMarkup(ADMIN_CLEANUP_MENU),
                action="admin_cleanup",
            )

        elif action == "admin_commands":
            await utils.safe_edit_text(
                query.message,
                (
                    "🧭 ДОСТУПНЫЕ АДМИН-КОМАНДЫ\n\n"
                    "/stats — общая статистика\n"
                    "/leads [hot|warm|cold] — список лидов\n"
                    "/export — выгрузка лидов в CSV\n"
                    "/view_conversation <telegram_id> — история диалога\n"
                    "/security_stats — статистика безопасности\n"
                    "/blacklist <telegram_id> [причина] — блокировка пользователя\n"
                    "/unblacklist <telegram_id> — снять блокировку\n"
                    "/pdn_user <telegram_id> — карточка ПД и согласий\n"
                    "/edit_pdn <telegram_id> <field> <value> — правка ПД\n"
                    "/revoke_user_consent <telegram_id> — отзыв согласия + очистка\n\n"
                    "Эти функции работают и доступны даже если не вынесены отдельной кнопкой."
                ),
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_commands",
            )

        elif action == "admin_panel":
            await utils.safe_edit_text(
                query.message,
                "⚙️ АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_panel",
            )

        elif action == "admin_close":
            await utils.safe_edit_text(query.message, "⚙️ Админ-панель закрыта", action="admin_close")

        else:
            await utils.safe_edit_text(
                query.message,
                "⚠️ Неизвестное действие админ-панели.",
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="admin_unknown_action",
            )

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as error:
        logger.error(f"Error in handle_admin_panel_callback: {error}")
        await utils.safe_reply_text(query.message, f"Ошибка: {str(error)}", action="admin_panel_error")
