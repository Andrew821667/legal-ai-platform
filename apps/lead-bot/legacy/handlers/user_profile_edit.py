"""
Profile edit branch extracted from the main user flow.
"""
from __future__ import annotations

import database
import utils
from telegram import Update
from telegram.ext import ContextTypes
from telegram_ui import normalize_button_text
from handlers.markup import (
    main_menu_markup as _main_menu_markup,
    profile_edit_cancel_markup as _profile_edit_cancel_markup,
)


def _button_text_equals(text: str | None, expected: str) -> bool:
    return normalize_button_text(text).casefold() == normalize_button_text(expected).casefold()


async def handle_profile_edit_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    message_text: str,
    user,
    user_data: dict,
) -> bool:
    profile_edit_field = context.user_data.get("profile_edit_field")
    if not profile_edit_field:
        return False

    original_message = update.effective_message
    if not original_message:
        return True

    if _button_text_equals(message_text, "⬅️ Отмена"):
        context.user_data.pop("profile_edit_field", None)
        await utils.safe_reply_text(
            original_message,
            "Редактирование отменено.",
            reply_markup=_main_menu_markup(user.id),
            action="profile_edit_cancel",
        )
        return True

    if profile_edit_field == "name":
        normalized_name = " ".join(message_text.split())
        if len(normalized_name) < 2:
            await utils.safe_reply_text(
                original_message,
                "Введите корректные ФИО (минимум 2 символа) или нажмите «⬅️ Отмена».",
                reply_markup=_profile_edit_cancel_markup(),
                action="profile_edit_name_validation",
            )
            return True

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
        return True

    if profile_edit_field == "email":
        new_email = message_text.strip()
        if not utils.validate_email(new_email):
            await utils.safe_reply_text(
                original_message,
                "Email выглядит некорректно. Введите корректный email или нажмите «⬅️ Отмена».",
                reply_markup=_profile_edit_cancel_markup(),
                action="profile_edit_email_validation",
            )
            return True

        database.db.create_or_update_lead(user_data["id"], {"email": new_email})
        context.user_data.pop("profile_edit_field", None)
        await utils.safe_reply_text(
            original_message,
            "✅ Email обновлен.",
            reply_markup=_main_menu_markup(user.id),
            action="profile_edit_email_success",
        )
        return True

    return False
