"""
Admin lookup / edit flow extracted from the main user handler.
"""
from __future__ import annotations

from typing import Optional

import admin_interface
import database
import security
import utils
from config import get_config
from telegram import Update
from telegram.ext import ContextTypes
from handlers.markup import main_menu_markup as _main_menu_markup

config = get_config()

_EDITABLE_USER_FIELDS = {"first_name", "last_name", "username"}
_EDITABLE_LEAD_FIELDS = {"name", "email", "phone", "company"}


def clear_admin_lookup_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("admin_lookup_action", None)
    context.user_data.pop("admin_lookup_field", None)


def _parse_id(raw: str) -> Optional[int]:
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return None


async def handle_admin_lookup_input(
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
        clear_admin_lookup_state(context)
        await utils.safe_reply_text(
            message,
            "Ок, режим поиска/редактирования закрыт.",
            reply_markup=_main_menu_markup(config.ADMIN_TELEGRAM_ID),
            action="admin_lookup_cancel",
        )
        return True

    if action == "card":
        telegram_id = _parse_id(message_text)
        if telegram_id is None:
            await utils.safe_reply_text(
                message,
                "Введите корректный Telegram ID числом.\nНапример: 321681061",
                action="admin_lookup_card_invalid_id",
            )
            return True

        snapshot = await admin_interface.admin_interface.get_user_snapshot_async(telegram_id)
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
