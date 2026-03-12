from __future__ import annotations

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup

import content
import database
from config import get_config
from .callback_flows import build_client_profile_text as _build_client_profile_text
from .constants import ADMIN_MENU, LEAD_MAGNET_MENU, MAIN_MENU, append_inline_url_row
from .markup import (
    documents_panel_markup as _documents_panel_markup,
    documents_panel_text as _documents_panel_text,
    offer_profile_markup as _offer_profile_markup,
    with_channel_button as _with_channel_button,
)
from .business_menu_support import BusinessMenuResponder, BusinessMenuState

config = get_config()

PROFILE_CALLBACK_MAP = {
    "menu_offer_set_inhouse": "inhouse",
    "menu_offer_set_law_firm": "law_firm",
    "menu_offer_set_business": "business",
    "menu_offer_set_universal": "universal",
    "menu_offer_set_auto": None,
}


async def maybe_handle_profile_callbacks(
    *,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if state.callback_data in PROFILE_CALLBACK_MAP:
        if not state.user_db_id:
            await responder.reply_text(
                "Не удалось определить пользователя. Нажмите /start и повторите.",
                None,
                action="offer_profile_no_user",
            )
            return True
        new_profile = PROFILE_CALLBACK_MAP[state.callback_data]
        database.db.set_user_offer_profile(state.user_db_id, new_profile)
        lead = database.db.get_lead_by_user_id(state.user_db_id) if state.user_db_id else None
        response_text = (
            f"{content.offer_profile_change_success_text(new_profile)}\n\n"
            f"{content.offer_profile_panel_text(lead=lead, selected_profile=new_profile)}"
        )
        await responder.send_html(
            response_text,
            _offer_profile_markup(new_profile),
            action="menu_offer_profile_set",
            clip=True,
        )
        return True

    if state.callback_data == "menu_offer_profile":
        await responder.send_html(
            content.offer_profile_panel_text(lead=state.lead, selected_profile=state.selected_profile),
            _offer_profile_markup(state.selected_profile),
            action="menu_offer_profile",
            clip=True,
        )
        return True

    return False


async def maybe_handle_view_callbacks(
    *,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if state.callback_data == "menu_restart":
        if state.user_db_id:
            database.db.clear_conversation_history(state.user_db_id)
            database.db.reset_user_funnel_state(state.user_db_id)
        await responder.send_text(
            "Историю очистил. Начинаем заново. Опишите задачу одним сообщением.",
            state.menu_markup,
            action="menu_restart",
        )
        return True

    if state.callback_data == "menu_return_to_bot":
        chat = getattr(responder.query.message, "chat", None)
        chat_id = getattr(chat, "id", None)
        if chat_id is not None:
            database.db.set_chat_mode(int(chat_id), "bot")

        if state.user_db_id:
            database.db.reset_user_funnel_state(state.user_db_id)

        user = state.user
        response_text = (
            content.build_business_welcome_message(user.first_name if user else "клиент")
            if responder.is_business
            else content.build_welcome_message(user.first_name if user else "клиент")
        )
        if responder.is_business:
            await responder.send_html(response_text, state.menu_markup, action="menu_return_to_bot")
        else:
            await responder.reply_text(
                response_text,
                ReplyKeyboardMarkup(
                    ADMIN_MENU if user and user.id == config.ADMIN_TELEGRAM_ID else MAIN_MENU,
                    resize_keyboard=True,
                ),
                action="menu_return_to_bot",
            )
        return True

    if state.callback_data == "menu_dashboard":
        await responder.send_html(
            content.build_workspace_text(lead=state.lead, selected_profile=state.selected_profile),
            state.menu_markup,
            action="menu_dashboard",
        )
        return True

    if state.callback_data == "menu_profile":
        if not state.user_db_id:
            await responder.reply_text(
                "Не удалось определить профиль. Нажмите /start и повторите.",
                None,
                action="menu_profile_no_user",
            )
            return True
        user_row = state.local_user or database.db.get_local_user_by_id(state.user_db_id) or {}
        lead = database.db.get_local_lead_by_user_id(state.user_db_id)
        consent_state = database.db.get_user_consent_state(state.user_db_id)
        await responder.send_text(
            _build_client_profile_text(user_row, lead, consent_state),
            state.menu_markup,
            action="menu_profile",
            clip=True,
        )
        return True

    if state.callback_data == "menu_documents":
        await responder.send_html(
            _documents_panel_text(),
            _documents_panel_markup(),
            action="menu_documents",
        )
        return True

    if state.callback_data == "menu_contract_ai":
        response_text = (
            f"{content.menu_response_by_key('menu_contract_ai', lead=state.lead, selected_profile=state.selected_profile)}\n\n"
            f"{content.LEAD_MAGNET_OFFER_TEXT}"
        )
        response_markup = _with_channel_button(InlineKeyboardMarkup(LEAD_MAGNET_MENU))
        response_markup = append_inline_url_row(
            response_markup,
            content.CONTRACT_AI_BUTTON_TEXT,
            content.contract_ai_public_url(),
            prepend=True,
        )
        await responder.send_html(
            response_text,
            response_markup,
            action="menu_contract_ai",
            clip=True,
        )
        return True

    return False
