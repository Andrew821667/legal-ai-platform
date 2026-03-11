from __future__ import annotations

import asyncio
import logging
import sqlite3
import time

from telegram import Message, Update, User
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import ai_brain
import content
import database
import funnel
import lead_qualifier
import prompts
import security
import utils
from config import get_config
from handlers.helpers import notify_admin_new_lead
from handlers.markup import consultation_cta_markup as _consultation_cta_markup
from handlers.user_cta_actions import offer_lead_magnet
from handlers.user_message_helpers import (
    append_profile_name_context as _append_profile_name_context,
    schedule_typing_indicator as _schedule_typing_indicator,
)

config = get_config()
logger = logging.getLogger(__name__)


async def _stream_response_text(
    *,
    original_message: Message,
    user_data: dict,
    user_first_name: str | None,
    conversation_history: list[dict],
    response_stage: str,
    cta_variant: str,
    cta_shown: bool,
) -> str:
    full_response = ""
    sent_message = None
    chunk_buffer = ""
    last_update_length = 0
    last_update_time = 0.0

    _schedule_typing_indicator(original_message.chat, user_data["telegram_id"])

    start_generation = time.time()
    preview_enabled = config.STREAMING_PREVIEW
    funnel_context = _append_profile_name_context(
        funnel.build_stage_context(response_stage, cta_variant, cta_shown),
        user_first_name,
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
                        logger.debug("Initial message sent: %s chars", len(full_response))
                    except TelegramError as error:
                        logger.warning("Failed to send initial message: %s", error)
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
                    logger.debug("Message updated: %s chars", len(full_response))
                except TelegramError as error:
                    logger.debug("Skipped update (rate limit): %s", error)

    generation_time = time.time() - start_generation
    logger.info("Response generated in %.2fs (%s chars)", generation_time, len(full_response))
    return full_response, sent_message


async def _deliver_final_response(
    *,
    original_message: Message,
    sent_message: Message | None,
    full_response: str,
) -> None:
    if len(full_response) > 4096:
        logger.warning("Response too long (%s chars), splitting into parts", len(full_response))
        parts = utils.split_long_message(full_response, max_length=4000)

        if sent_message:
            try:
                await sent_message.delete()
            except TelegramError:
                pass

        for index, part in enumerate(parts):
            part_message = f"[Часть {index + 1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
            await original_message.reply_text(part_message)
            if index < len(parts) - 1:
                await original_message.chat.send_action(action="typing")
                await asyncio.sleep(0.5)
        return

    if sent_message:
        try:
            await utils.safe_edit_text(
                sent_message,
                full_response,
                action="streaming_final_update",
            )
            logger.debug("Final message update sent")
            return
        except TelegramError:
            pass

    await utils.safe_reply_text(
        original_message,
        full_response,
        action="assistant_final_message",
    )


async def _maybe_send_consultation_cta(
    *,
    original_message: Message,
    response_stage: str,
    cta_shown: bool,
) -> bool:
    if not funnel.should_show_consultation_button(response_stage, cta_shown):
        return False

    try:
        await original_message.reply_text(
            content.CONSULTATION_CTA_TEXT,
            reply_markup=_consultation_cta_markup(),
        )
        return True
    except TelegramError as error:
        logger.warning("Failed to send consultation CTA button: %s", error)
        return False


def _track_tokens(*, user_id: int, message_text: str, full_response: str) -> None:
    user_tokens = security.security_manager.estimate_tokens(message_text)
    assistant_tokens = security.security_manager.estimate_tokens(full_response)
    system_tokens = security.security_manager.estimate_tokens(prompts.SYSTEM_PROMPT)
    total_tokens = user_tokens + assistant_tokens + system_tokens
    security.security_manager.add_tokens_used(total_tokens, user_id=user_id)
    logger.debug(
        "Tokens used: user=%s, assistant=%s, system=%s, total=%s",
        user_tokens,
        assistant_tokens,
        system_tokens,
        total_tokens,
    )


def _schedule_post_response_lead_processing(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User,
    user_data: dict,
    conversation_history: list[dict],
    cta_variant: str,
    cta_was_shown: bool,
    next_stage: str,
) -> None:
    user_db_id = user_data["id"]

    async def _post_response_lead_processing() -> None:
        try:
            extracted = await ai_brain.ai_brain.extract_lead_data_async(list(conversation_history))
            if not extracted:
                return

            telegram_profile_name = (user_data.get("first_name") or user.first_name or "").strip()
            if telegram_profile_name:
                extracted["name"] = telegram_profile_name

            processed_lead_id = lead_qualifier.lead_qualifier.process_lead_data(user_db_id, extracted)
            if processed_lead_id:
                database.db.update_lead_last_message_time(user_db_id)
                logger.info("Lead %s updated in background", processed_lead_id)
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
                    logger.warning("Failed to track lead magnet CTA show: %s", analytics_error)
        except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as background_error:
            logger.warning("Background lead processing failed for user %s: %s", user_db_id, background_error)

    asyncio.create_task(_post_response_lead_processing())


async def process_ai_response(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    original_message: Message,
    user: User,
    user_data: dict,
    lead: dict | None,
    message_text: str,
    current_stage: str,
    cta_variant: str,
    cta_shown: bool,
    allow_lead_processing: bool,
) -> None:
    database.db.add_message(user_data["id"], "user", message_text)

    conversation_history = database.db.get_conversation_history(user_data["id"])
    lead_id = lead["id"] if lead else None
    merged_lead_data = dict(lead or {})
    response_stage = current_stage

    if allow_lead_processing:
        response_stage = funnel.infer_stage(
            previous_stage=current_stage,
            user_message=message_text,
            lead_data=merged_lead_data,
        )

    full_response, sent_message = await _stream_response_text(
        original_message=original_message,
        user_data=user_data,
        user_first_name=user_data.get("first_name") or user.first_name,
        conversation_history=conversation_history,
        response_stage=response_stage,
        cta_variant=cta_variant,
        cta_shown=cta_shown,
    )

    full_response = funnel.enforce_leadgen_response(
        response_text=full_response,
        stage=response_stage,
        user_message=message_text,
        cta_shown=cta_shown,
        cta_variant=cta_variant,
        lead_data=merged_lead_data,
    )
    full_response = utils.format_ai_text_as_plain_symbols(full_response)

    await _deliver_final_response(
        original_message=original_message,
        sent_message=sent_message,
        full_response=full_response,
    )
    consultation_button_sent = await _maybe_send_consultation_cta(
        original_message=original_message,
        response_stage=response_stage,
        cta_shown=cta_shown,
    )

    database.db.add_message(user_data["id"], "assistant", full_response)

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
            logger.warning("Failed to track cta_shown event: %s", analytics_error)

    _track_tokens(
        user_id=user.id,
        message_text=message_text,
        full_response=full_response,
    )

    if not allow_lead_processing:
        return

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
            logger.warning("Failed to track stage_changed event: %s", analytics_error)

    _schedule_post_response_lead_processing(
        update=update,
        context=context,
        user=user,
        user_data=user_data,
        conversation_history=conversation_history,
        cta_variant=cta_variant,
        cta_was_shown=cta_shown,
        next_stage=next_stage,
    )
