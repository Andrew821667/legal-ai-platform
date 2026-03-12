from __future__ import annotations

import dataclasses
import datetime
import logging
import sqlite3

from telegram import Message, Update, User
from telegram.ext import ContextTypes

import ai_brain
import content
import database
import funnel
import utils
from .helpers import extract_email, notify_admin_new_lead, send_lead_magnet_email
from .user_cta_actions import handle_handoff_request
from .user_message_helpers import (
    build_new_phone_lead_payload as _build_new_phone_lead_payload,
    extract_phone_candidate as _extract_phone_candidate,
    looks_like_new_topic_after_handoff as _looks_like_new_topic_after_handoff,
    normalize_magnet_type as _normalize_magnet_type,
    persist_fasttrack_contact as _persist_fasttrack_contact,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class LeadFlowState:
    lead: dict | None
    current_stage: str
    cta_variant: str
    cta_shown: bool


async def maybe_handle_pending_lead_magnet(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    user_data: dict,
    lead: dict | None,
    message_text: str,
) -> tuple[dict | None, bool]:
    if not (lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered")):
        return lead, False

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
            return lead, True

    email = extract_email(message_text)
    if email:
        await send_lead_magnet_email(update, user_data, lead, email)
        return lead, True

    return lead, False


def get_lead_flow_state(*, user_db_id: int, lead: dict | None) -> LeadFlowState:
    funnel_state = database.db.get_user_funnel_state(user_db_id)
    current_stage = funnel_state.get("conversation_stage") or "discover"
    cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_db_id)
    cta_shown = bool(funnel_state.get("cta_shown"))
    if not funnel_state.get("cta_variant"):
        database.db.update_user_funnel_state(user_db_id, cta_variant=cta_variant)
    return LeadFlowState(
        lead=lead,
        current_stage=current_stage,
        cta_variant=cta_variant,
        cta_shown=cta_shown,
    )


async def maybe_create_new_topic_lead(
    *,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    user_data: dict,
    message_text: str,
    allow_lead_processing: bool,
    state: LeadFlowState,
) -> LeadFlowState:
    lead = state.lead
    if not (
        allow_lead_processing
        and lead
        and state.current_stage == "handoff"
        and _looks_like_new_topic_after_handoff(message_text)
    ):
        return state

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
        cta_variant=state.cta_variant,
        cta_shown=False,
    )
    database.db.update_lead_funnel_state_by_id(
        new_lead_id,
        conversation_stage="discover",
        cta_variant=state.cta_variant,
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
        logger.warning("Failed to track new_topic_after_handoff: %s", analytics_error)

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
    logger.info("New lead %s created from new topic after handoff for user %s", new_lead_id, user.id)
    return LeadFlowState(
        lead=new_lead_payload_db,
        current_stage="discover",
        cta_variant=state.cta_variant,
        cta_shown=False,
    )


async def maybe_handle_handoff_shortcuts(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    user_data: dict,
    lead: dict | None,
    message_text: str,
    allow_lead_processing: bool,
) -> bool:
    if ai_brain.ai_brain.check_handoff_trigger(message_text):
        if allow_lead_processing:
            _persist_fasttrack_contact(user_data["id"], user, message_text)
        await handle_handoff_request(update, context, source="trigger")
        return True

    if allow_lead_processing and funnel.should_fast_track_handoff(message_text, lead):
        database.db.add_message(user_data["id"], "user", message_text)
        _persist_fasttrack_contact(user_data["id"], user, message_text)
        await handle_handoff_request(update, context, source="fasttrack")
        return True

    return False


async def maybe_handle_repeat_loop(*, original_message: Message, user_db_id: int) -> bool:
    conversation_history = database.db.get_conversation_history(user_db_id)
    if not conversation_history:
        return False

    user_messages = [message for message in conversation_history if message["role"] == "user"]
    if len(user_messages) < 3:
        return False

    last_three = [msg.get("content", msg.get("message", "")).strip().lower() for msg in user_messages[-3:]]
    if len(set(last_three)) != 1:
        return False

    first_message_time = datetime.datetime.fromisoformat(conversation_history[0]["timestamp"])
    current_time = datetime.datetime.now()
    time_elapsed = (current_time - first_message_time).total_seconds() / 60
    if time_elapsed <= 30:
        return False

    await utils.safe_reply_html(
        original_message,
        content.REPEAT_LOOP_FALLBACK_TEXT,
        action="repeat_loop_fallback",
    )
    return True
