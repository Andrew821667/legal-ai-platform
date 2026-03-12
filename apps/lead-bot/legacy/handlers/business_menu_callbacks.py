from __future__ import annotations

import logging
import sqlite3

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import content
import database
import utils
from lead_perf import log_span_timing, perf_start
from .business_menu_contact import (
    CONTACT_FLOW_ACTIONS,
    maybe_handle_contact_actions,
    maybe_handle_contact_choice_callbacks,
    maybe_handle_personal_request,
    maybe_require_pdn_for_contact,
)
from .business_menu_support import (
    BusinessMenuResponder,
    BusinessMenuState,
    resolve_local_callback_user,
)
from .business_menu_views import (
    maybe_handle_profile_callbacks,
    maybe_handle_view_callbacks,
)
from .markup import (
    clear_business_contact_state as _clear_business_contact_state,
    with_channel_button as _with_channel_button,
    workspace_markup_for as _workspace_markup_for,
)

logger = logging.getLogger(__name__)


async def handle_business_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок меню для business и обычных чатов."""
    started_at = perf_start()
    callback_data = ""
    try:
        query = update.callback_query
        try:
            await utils.safe_answer_callback(query, action="business_menu_answer")
        except TelegramError as answer_error:
            logger.warning("Failed to answer business menu callback: %s", answer_error)

        callback_data = query.data or ""
        is_business = bool(
            query.message
            and hasattr(query.message, "business_connection_id")
            and query.message.business_connection_id
        )

        user = query.from_user
        user_db_id = None
        local_user = None
        lead = None
        selected_profile = None
        consent_state = None
        if user:
            user_db_id, local_user = resolve_local_callback_user(user)
            lead = database.db.get_local_lead_by_user_id(user_db_id) if user_db_id else None
            selected_profile = (local_user or {}).get("offer_profile_override") or None

        state = BusinessMenuState(
            callback_data=callback_data,
            user=user,
            user_db_id=user_db_id,
            local_user=local_user,
            lead=lead,
            selected_profile=selected_profile,
            consent_state=consent_state,
            menu_markup=_workspace_markup_for(lead=lead, selected_profile=selected_profile),
        )
        responder = BusinessMenuResponder(
            context=context,
            query=query,
            callback_data=callback_data,
            is_business=is_business,
        )

        if await maybe_handle_profile_callbacks(state=state, responder=responder):
            return

        if callback_data not in CONTACT_FLOW_ACTIONS:
            _clear_business_contact_state(context)

        if await maybe_require_pdn_for_contact(state=state, responder=responder):
            return

        if await maybe_handle_view_callbacks(state=state, responder=responder):
            return

        if await maybe_handle_contact_choice_callbacks(
            context=context,
            state=state,
            responder=responder,
        ):
            return

        if await maybe_handle_personal_request(
            context=context,
            state=state,
            responder=responder,
        ):
            return

        if await maybe_handle_contact_actions(
            context=context,
            state=state,
            responder=responder,
        ):
            return

        response_text = content.menu_response_by_key(
            callback_data,
            lead=state.lead,
            selected_profile=state.selected_profile,
        )
        reply_markup = (
            _with_channel_button(state.menu_markup)
            if callback_data in {"menu_services", "menu_prices", "menu_help"}
            else state.menu_markup
        )
        await responder.send_html(
            response_text,
            reply_markup,
            action=f"{callback_data}_edit",
        )
        log_span_timing(
            "lead.menu.callback",
            started_at,
            ok=True,
            callback_data=callback_data or "unknown",
            business_mode=is_business,
        )

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as error:
        log_span_timing(
            "lead.menu.callback",
            started_at,
            ok=False,
            error=type(error).__name__,
            force=True,
            callback_data=callback_data or "unknown",
        )
        logger.error("Error in handle_business_menu_callback: %s", error)
