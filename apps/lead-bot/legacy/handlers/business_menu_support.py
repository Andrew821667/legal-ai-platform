from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

import database
import utils
from handlers.markup import clip_for_edit as _clip_for_edit


@dataclass
class BusinessMenuState:
    callback_data: str
    user: Any
    user_db_id: int | None
    local_user: dict | None
    lead: dict | None
    selected_profile: str | None
    consent_state: dict | None
    menu_markup: InlineKeyboardMarkup


def resolve_local_callback_user(user) -> tuple[int | None, dict | None]:
    """Avoid a blind upsert on every callback when Telegram profile fields did not change."""
    if not user:
        return None, None

    local_user = database.db.get_local_user_by_telegram_id(user.id)
    if local_user:
        username = local_user.get("username") or None
        first_name = local_user.get("first_name") or None
        last_name = local_user.get("last_name") or None
        if (
            username == (user.username or None)
            and first_name == (user.first_name or None)
            and last_name == (user.last_name or None)
        ):
            return int(local_user["id"]), local_user

    user_db_id = database.db.create_or_update_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    return user_db_id, (database.db.get_local_user_by_id(user_db_id) if user_db_id else None)


class BusinessMenuResponder:
    def __init__(
        self,
        *,
        context: ContextTypes.DEFAULT_TYPE,
        query,
        callback_data: str,
        is_business: bool,
    ) -> None:
        self.context = context
        self.query = query
        self.callback_data = callback_data
        self.is_business = is_business

    async def _send_business_menu_message(self, text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
        await utils.safe_send_message(
            self.context.bot,
            action=f"business_menu:{self.callback_data or 'unknown'}",
            chat_id=self.query.message.chat.id,
            text=text,
            parse_mode="HTML",
            business_connection_id=self.query.message.business_connection_id,
            reply_markup=reply_markup,
        )

    async def send_html(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
        *,
        action: str,
        clip: bool = False,
    ) -> None:
        if self.is_business:
            await self._send_business_menu_message(text, reply_markup)
        else:
            payload = _clip_for_edit(text) if clip else text
            await utils.safe_edit_html(
                self.query.message,
                payload,
                reply_markup=reply_markup,
                action=action,
            )

    async def send_text(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None,
        *,
        action: str,
        clip: bool = False,
    ) -> None:
        if self.is_business:
            await self._send_business_menu_message(text, reply_markup)
        else:
            payload = _clip_for_edit(text) if clip else text
            await utils.safe_edit_text(
                self.query.message,
                payload,
                reply_markup=reply_markup,
                action=action,
            )

    async def reply_text(
        self,
        text: str,
        reply_markup,
        *,
        action: str,
    ) -> None:
        if self.is_business:
            await self._send_business_menu_message(text, reply_markup)
        else:
            await utils.safe_reply_text(
                self.query.message,
                text,
                action=action,
                reply_markup=reply_markup,
            )
