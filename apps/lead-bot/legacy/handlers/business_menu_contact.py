from __future__ import annotations

import logging
import sqlite3

from telegram import InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import content
import database
import funnel
import utils
from config import get_config
from handlers.callback_flows import has_pdn_consent as _has_pdn_consent
from handlers.constants import (
    BUSINESS_AWAITING_CONTACT_KEY,
    BUSINESS_AWAITING_CONTACT_SOURCE_KEY,
    BUSINESS_PENDING_CONTACT_KEY,
    CONSENT_PDN_MENU,
)
from handlers.helpers import notify_admin_new_lead
from handlers.markup import (
    business_phone_format_text as _business_phone_format_text,
    clear_business_contact_state as _clear_business_contact_state,
    consultation_contact_markup as _consultation_contact_markup,
    contact_visibility_choice_markup as _contact_visibility_choice_markup,
    personal_mode_markup as _personal_mode_markup,
    with_channel_button as _with_channel_button,
)
from handlers.business_menu_support import BusinessMenuResponder, BusinessMenuState

config = get_config()
logger = logging.getLogger(__name__)

CONTACT_ACTIONS = {"menu_consultation", "menu_leave_contact"}
CONTACT_FLOW_ACTIONS = CONTACT_ACTIONS | {"menu_contact_send_phone", "menu_contact_telegram_only"}


async def maybe_require_pdn_for_contact(
    *,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if not (
        state.user
        and state.user.id != config.ADMIN_TELEGRAM_ID
        and state.callback_data in CONTACT_FLOW_ACTIONS
        and not _has_pdn_consent(
            state.consent_state
            if state.consent_state is not None
            else (database.db.get_user_consent_state(state.user_db_id) if state.user_db_id else {})
        )
    ):
        return False

    await utils.safe_reply_html(
        responder.query.message,
        f"{content.pdn_consent_required_text('Консультации и передаче контакта')}\n\n{content.CONSENT_STEP_1_TEXT}",
        reply_markup=InlineKeyboardMarkup(CONSENT_PDN_MENU),
        action="menu_requires_pdn",
    )
    return True


async def maybe_handle_contact_choice_callbacks(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if state.callback_data not in {"menu_contact_send_phone", "menu_contact_telegram_only"}:
        return False

    if not state.user_db_id:
        await responder.reply_text(
            "Не удалось определить пользователя. Нажмите /start и повторите.",
            None,
            action="contact_choice_no_user",
        )
        return True

    user = state.user
    if state.callback_data == "menu_contact_send_phone":
        pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
        source = pending_contact.get("source") or "consultation"
        context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
        context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = source
        response_text = "Отлично, пришлите номер телефона.\n" f"{_business_phone_format_text()}"
        response_markup = state.menu_markup if responder.is_business else _consultation_contact_markup()
    else:
        pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
        previous_lead = database.db.get_lead_by_user_id(state.user_db_id) or {}
        notes_parts = []
        if pending_contact.get("notes"):
            notes_parts.append(str(pending_contact["notes"]).strip())
        notes_parts.append("[CONTACT_MODE] Клиент выбрал связь через Telegram без телефона")
        lead_payload = {
            "name": user.first_name if user else None,
            "email": previous_lead.get("email"),
            "company": previous_lead.get("company"),
            "pain_point": pending_contact.get("pain_point") or previous_lead.get("pain_point"),
            "temperature": "warm",
            "status": "new",
            "notification_sent": 0,
            "lead_magnet_type": pending_contact.get("lead_magnet_type")
            or previous_lead.get("lead_magnet_type")
            or "consultation",
            "lead_magnet_delivered": 1,
            "notes": "\n".join(part for part in notes_parts if part).strip(),
        }
        lead_id = database.db.create_new_lead(state.user_db_id, lead_payload)
        user_state = database.db.get_user_funnel_state(state.user_db_id)
        cta_variant = user_state.get("cta_variant") or funnel.choose_cta_variant(state.user_db_id)
        database.db.update_user_funnel_state(
            state.user_db_id,
            conversation_stage="handoff",
            cta_variant=cta_variant,
            cta_shown=True,
        )
        database.db.update_lead_funnel_state_by_id(
            lead_id,
            conversation_stage="handoff",
            cta_variant=cta_variant,
            cta_shown=True,
        )
        try:
            database.db.track_event(
                state.user_db_id,
                "contact_via_telegram_only",
                payload={"source": pending_contact.get("source") or "business_contact_choice"},
                lead_id=lead_id,
            )
        except (sqlite3.Error, KeyError) as analytics_error:
            logger.warning("Failed to track contact_via_telegram_only: %s", analytics_error)

        refreshed_lead = database.db.get_lead_by_id(lead_id) or {}
        await notify_admin_new_lead(
            context=context,
            lead_id=lead_id,
            lead_data=refreshed_lead,
            user_data={
                "id": state.user_db_id,
                "telegram_id": user.id if user else None,
                "username": user.username if user else None,
                "first_name": user.first_name if user else None,
            },
            is_update=False,
        )
        _clear_business_contact_state(context)
        response_text = (
            "Принято. Передал команде, что с вами лучше связаться в Telegram.\n"
            "Если захотите ускорить связь, можете в любой момент отправить номер."
        )
        response_text = content.with_channel_nurture(response_text, after_contact=True)
        response_markup = _with_channel_button(state.menu_markup)

    await responder.reply_text(
        response_text,
        response_markup,
        action=f"{state.callback_data}_reply",
    )
    return True


async def maybe_handle_personal_request(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if state.callback_data != "menu_personal_request":
        return False

    chat = getattr(responder.query.message, "chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is not None:
        database.db.set_chat_mode(int(chat_id), "personal")

    _clear_business_contact_state(context)

    response_text = (
        "Чат переведен в личный режим.\n\n"
        "Теперь можете писать Андрею напрямую: бот не будет отвечать и не будет "
        "обрабатывать сообщения как лиды.\n\n"
        "Когда захотите снова пользоваться ботом, нажмите «↩️ Вернуться к боту»."
    )
    await responder.reply_text(
        response_text,
        _personal_mode_markup(),
        action="menu_personal_request_mode_on",
    )
    return True


async def maybe_handle_contact_actions(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    state: BusinessMenuState,
    responder: BusinessMenuResponder,
) -> bool:
    if state.callback_data not in CONTACT_ACTIONS:
        return False

    if not state.user_db_id:
        await responder.reply_text(
            "Не удалось определить пользователя. Нажмите /start и повторите.",
            None,
            action="contact_action_no_user",
        )
        return True

    contact_source = "consultation"
    notes = None
    lead_magnet_type = "consultation"
    if state.callback_data == "menu_leave_contact":
        existing_lead = database.db.get_lead_by_user_id(state.user_db_id) or {}
        if existing_lead.get("lead_magnet_type") == "personal_request":
            lead_magnet_type = "personal_request"
            notes = existing_lead.get("notes") or "Личное обращение к Андрею Попову"
            contact_source = "personal_request"

    if state.callback_data == "menu_leave_contact":
        instant_note = (
            "Клиент нажал кнопку «Оставить контакт» и запросил связь с командой."
            if lead_magnet_type != "personal_request"
            else "Клиент нажал кнопку «Оставить контакт» для личного обращения."
        )
        _clear_business_contact_state(context)
        context.user_data[BUSINESS_PENDING_CONTACT_KEY] = {
            "source": contact_source,
            "lead_magnet_type": lead_magnet_type,
            "notes": instant_note if not notes else f"{notes}\n{instant_note}".strip(),
            "pain_point": instant_note,
        }
        response_text = (
            "Как удобнее передать контакт для связи?\n\n"
            "Если номер скрыт в настройках Telegram, просто выберите вариант ниже."
        )
        response_markup = _contact_visibility_choice_markup()
    else:
        lead_payload = {
            "name": state.user.first_name if state.user else None,
            "lead_magnet_type": lead_magnet_type,
            "lead_magnet_delivered": False,
            "notification_sent": 0,
        }
        if notes:
            lead_payload["notes"] = notes
        database.db.create_or_update_lead(state.user_db_id, lead_payload)

        context.user_data.pop(BUSINESS_PENDING_CONTACT_KEY, None)
        context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
        context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = contact_source
        response_text = "Отлично, пришлите номер телефона.\n" f"{_business_phone_format_text()}"
        response_markup = state.menu_markup if responder.is_business else _consultation_contact_markup()

    await responder.reply_text(
        response_text,
        response_markup if state.callback_data == "menu_leave_contact" else response_markup,
        action=f"{state.callback_data}_reply",
    )
    return True
