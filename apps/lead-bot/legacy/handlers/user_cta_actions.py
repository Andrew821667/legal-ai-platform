"""
CTA and handoff actions extracted from the main user handler.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional

import content
import database
import funnel
import utils
from config import get_config
from telegram import InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from .constants import LEAD_MAGNET_MENU
from .helpers import notify_admin_new_lead
from .markup import (
    consultation_cta_markup as _consultation_cta_markup,
    main_menu_markup as _main_menu_markup,
    quick_nav_markup_for as _quick_nav_markup_for,
    with_channel_button as _with_channel_button,
)

config = get_config()
logger = logging.getLogger(__name__)


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    """Обработчик кнопок меню."""
    _ = context
    user = update.effective_user
    lead = None
    selected_profile = None
    if user:
        user_row = database.db.get_user_by_telegram_id(user.id)
        if user_row:
            lead = database.db.get_lead_by_user_id(user_row["id"])
            selected_profile = database.db.get_user_offer_profile(user_row["id"])
    response = content.menu_response_by_button(
        button_text,
        lead=lead,
        selected_profile=selected_profile,
    )
    await utils.safe_reply_html(update.message, response, action="menu_button_response")


async def offer_lead_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предложение lead magnet."""
    _ = context
    reply_markup = _with_channel_button(InlineKeyboardMarkup(LEAD_MAGNET_MENU))
    await utils.safe_reply_html(
        update.message,
        content.with_channel_nurture(content.LEAD_MAGNET_OFFER_TEXT),
        reply_markup=reply_markup,
        action="lead_magnet_offer",
    )


async def handle_handoff_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    source: str = "trigger",
    lead_id_override: Optional[int] = None,
    is_update_override: Optional[bool] = None,
):
    """Обработка запроса на передачу админу."""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if not user_data:
            await update.message.reply_text("Ошибка. Попробуйте /start")
            return

        await utils.safe_reply_html(
            update.message,
            content.with_channel_nurture(content.HANDOFF_ACK_TEXT, after_contact=True),
            reply_markup=_main_menu_markup(user.id),
            action="handoff_ack",
        )
        await utils.safe_reply_text(
            update.message,
            "Навигация:",
            reply_markup=_with_channel_button(
                _quick_nav_markup_for(
                    lead=database.db.get_lead_by_user_id(user_data["id"]),
                    selected_profile=database.db.get_user_offer_profile(user_data["id"]),
                ),
                prepend=True,
            ),
            action="handoff_quick_nav",
        )

        lead = database.db.get_lead_by_user_id(user_data["id"])
        if lead_id_override is not None:
            lead_id = lead_id_override
            lead_payload_override = database.db.get_lead_by_id(lead_id)
            if lead_payload_override:
                lead = lead_payload_override
            is_update = bool(is_update_override) if is_update_override is not None else False
        else:
            if not lead:
                lead_id = database.db.create_or_update_lead(
                    user_data["id"],
                    {"name": user.first_name},
                )
                is_update = bool(is_update_override) if is_update_override is not None else False
            else:
                lead_id = lead["id"]
                is_update = bool(is_update_override) if is_update_override is not None else True

        funnel_state = database.db.get_user_funnel_state(user_data["id"])
        previous_stage = funnel_state.get("conversation_stage") or "discover"
        cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_data["id"])

        database.db.update_user_funnel_state(
            user_data["id"],
            conversation_stage="handoff",
            cta_variant=cta_variant,
        )
        if lead_id_override is not None:
            database.db.update_lead_funnel_state_by_id(
                lead_id,
                conversation_stage="handoff",
                cta_variant=cta_variant,
            )
        else:
            database.db.update_lead_funnel_state(
                user_data["id"],
                conversation_stage="handoff",
                cta_variant=cta_variant,
            )

        if previous_stage != "handoff":
            try:
                database.db.track_event(
                    user_data["id"],
                    "stage_changed",
                    payload={"from": previous_stage, "to": "handoff"},
                    lead_id=lead_id,
                )
            except (sqlite3.Error, KeyError) as analytics_error:
                logger.warning("Failed to track handoff stage change: %s", analytics_error)

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
                user_data["id"],
                "handoff_done",
                payload={"source": source, "cta_variant": cta_variant},
                lead_id=lead_id,
            )
        except (sqlite3.Error, KeyError) as analytics_error:
            logger.warning("Failed to track handoff_done event: %s", analytics_error)

        logger.info("Handoff request from user %s", user.id)

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as error:
        logger.error("Error in handle_handoff_request: %s", error)
