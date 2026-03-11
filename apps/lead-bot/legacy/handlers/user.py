"""
Handlers: user
"""
from __future__ import annotations

import logging
import sqlite3
import time
from typing import Optional, Dict
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
import database
import ai_brain
import lead_qualifier
from config import get_config
config = get_config()
import utils
import email_sender
import security
import prompts
import content
import funnel
from handlers.helpers import extract_email, send_lead_magnet_email, notify_admin_new_lead
from handlers.markup import (
    consultation_cta_markup as _consultation_cta_markup,
    pdn_consent_markup as _pdn_consent_markup,
    transborder_consent_markup as _transborder_consent_markup,
)
from handlers.user_commands import (
    _is_pdn_consent_granted,
    _pdn_consent_prompt_text,
    _should_require_pdn_consent,
    ai_policy_command,
    consent_status_command,
    correct_data_command,
    delete_data_command,
    documents_command,
    export_data_command,
    help_command,
    marketing_consent_command,
    menu_command,
    privacy_command,
    profile_command,
    reset_command,
    revoke_consent_command,
    start_command,
    transborder_consent_command,
    user_agreement_command,
)
from handlers.user_admin_lookup import handle_admin_lookup_input
from handlers.user_cta_actions import (
    handle_handoff_request,
    handle_menu_button,
    offer_lead_magnet,
)
from handlers.user_message_helpers import (
    append_profile_name_context as _append_profile_name_context,
    build_new_phone_lead_payload as _build_new_phone_lead_payload,
    extract_phone_candidate as _extract_phone_candidate,
    looks_like_new_topic_after_handoff as _looks_like_new_topic_after_handoff,
    looks_like_plain_greeting as _looks_like_plain_greeting,
    looks_like_return_to_bot as _looks_like_return_to_bot,
    normalize_magnet_type as _normalize_magnet_type,
    persist_fasttrack_contact as _persist_fasttrack_contact,
    schedule_typing_indicator as _schedule_typing_indicator,
)
from handlers.user_non_text import handle_non_text_input as _handle_non_text_input
from handlers.user_profile_edit import handle_profile_edit_input
from handlers.user_routing import (
    maybe_handle_initial_entry,
    maybe_handle_personal_mode,
    maybe_handle_static_reply_action,
)
from handlers.start_payloads import process_pending_start_payload

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пользовательских сообщений."""
    try:
        user = update.effective_user
        original_message = update.effective_message
        if not user or not original_message:
            return

        message_text = original_message.text or ""
        message_preview = utils.mask_sensitive_data((message_text or "[non-text]")[:120])
        logger.info("Message from user %s: %s", user.id, message_preview[:50])

        # Получаем или создаем пользователя
        user_data = database.db.get_user_by_telegram_id(user.id)
        if not user_data:
            database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            user_data = database.db.get_user_by_telegram_id(user.id)
            if not user_data:
                return

        lead = database.db.get_lead_by_user_id(user_data["id"])
        consent_state = database.db.get_user_consent_state(user_data["id"])
        has_pdn_consent = _is_pdn_consent_granted(consent_state)
        has_transborder_consent = bool(consent_state.get("transborder_consent"))
        is_admin = user.id == config.ADMIN_TELEGRAM_ID
        allow_lead_processing = (not is_admin) or config.ALLOW_ADMIN_TEST_LEADS
        chat = update.effective_chat
        chat_id = int(chat.id) if chat and getattr(chat, "id", None) is not None else user.id
        chat_mode = database.db.get_chat_mode(chat_id)

        if is_admin:
            handled_admin_lookup = await handle_admin_lookup_input(update, context, message_text)
            if handled_admin_lookup:
                return

        if await maybe_handle_personal_mode(
            update=update,
            context=context,
            original_message=original_message,
            message_text=message_text,
            user=user,
            user_data=user_data,
            lead=lead,
            chat_id=chat_id,
            chat_mode=chat_mode,
        ):
            return

        history_preview = database.db.get_conversation_history(user_data["id"], limit=1)
        if await maybe_handle_initial_entry(
            original_message=original_message,
            message_text=message_text,
            user=user,
            user_data=user_data,
            lead=lead,
            history_exists=bool(history_preview),
        ):
            logger.info("Workspace entry UX sent for user %s", user.id)
            return

        if await maybe_handle_static_reply_action(
            update=update,
            context=context,
            original_message=original_message,
            message_text=message_text,
            user=user,
            user_data=user_data,
            consent_state=consent_state,
            is_admin=is_admin,
            allow_lead_processing=allow_lead_processing,
            consultation_requires_pdn=True,
            menu_handler=menu_command,
            profile_handler=profile_command,
            documents_handler=documents_command,
            reset_handler=reset_command,
        ):
            return

        # В non-text ветке поддерживаем сценарий демо (документ + email).
        if not message_text:
            if _should_require_pdn_consent(is_admin, consent_state):
                await utils.safe_reply_text(
                    original_message,
                    _pdn_consent_prompt_text("передаче контакта или материалов"),
                    reply_markup=_pdn_consent_markup(),
                    action="non_text_requires_pdn",
                )
                return
            await _handle_non_text_input(update, context, user_data, lead, allow_lead_processing)
            return

        if _should_require_pdn_consent(is_admin, consent_state):
            await utils.safe_reply_text(
                original_message,
                _pdn_consent_prompt_text("ИИ-разбору кейса"),
                reply_markup=_pdn_consent_markup(),
                action="message_requires_pdn",
            )
            return

        # 🛡️ ПРОВЕРКА БЕЗОПАСНОСТИ (только для текстовых сообщений)
        is_allowed, block_reason = security.security_manager.check_all_security(user.id, message_text)
        if not is_allowed:
            logger.warning(f"Security check failed for user {user.id}: {block_reason}")
            await original_message.reply_text(block_reason)
            return

        if await handle_profile_edit_input(
            update,
            context,
            message_text=message_text,
            user=user,
            user_data=user_data,
        ):
            return

        # Проверяем есть ли pending lead magnet и email в сообщении
        if lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered"):
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
                    return

            email = extract_email(message_text)
            if email:
                await send_lead_magnet_email(update, user_data, lead, email)
                return

        # Состояние воронки + A/B CTA
        funnel_state = database.db.get_user_funnel_state(user_data["id"])
        current_stage = funnel_state.get("conversation_stage") or "discover"
        cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_data["id"])
        cta_shown = bool(funnel_state.get("cta_shown"))
        if not funnel_state.get("cta_variant"):
            database.db.update_user_funnel_state(user_data["id"], cta_variant=cta_variant)

        # После handoff любое новое предметное сообщение считаем новым обращением:
        # открываем отдельный лид, чтобы не смешивать боли/задачи.
        if (
            allow_lead_processing
            and lead
            and current_stage == "handoff"
            and _looks_like_new_topic_after_handoff(message_text)
        ):
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
                cta_variant=cta_variant,
                cta_shown=False,
            )
            database.db.update_lead_funnel_state_by_id(
                new_lead_id,
                conversation_stage="discover",
                cta_variant=cta_variant,
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
                logger.warning(f"Failed to track new_topic_after_handoff: {analytics_error}")

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
            lead = new_lead_payload_db
            current_stage = "discover"
            cta_shown = False
            logger.info("New lead %s created from new topic after handoff for user %s", new_lead_id, user.id)

        # Обработка кнопок reply-меню
        if await maybe_handle_static_reply_action(
            update=update,
            context=context,
            original_message=original_message,
            message_text=message_text,
            user=user,
            user_data=user_data,
            consent_state=consent_state,
            is_admin=is_admin,
            allow_lead_processing=allow_lead_processing,
            consultation_requires_pdn=False,
            menu_handler=menu_command,
            profile_handler=profile_command,
            documents_handler=documents_command,
            reset_handler=reset_command,
        ):
            return

        # Проверяем триггеры передачи админу
        if ai_brain.ai_brain.check_handoff_trigger(message_text):
            if allow_lead_processing:
                _persist_fasttrack_contact(user_data["id"], user, message_text)
            await handle_handoff_request(update, context, source="trigger")
            return

        if allow_lead_processing and funnel.should_fast_track_handoff(message_text, lead):
            database.db.add_message(user_data["id"], "user", message_text)
            _persist_fasttrack_contact(user_data["id"], user, message_text)
            await handle_handoff_request(update, context, source="fasttrack")
            return

        if not is_admin and not has_transborder_consent:
            await utils.safe_reply_html(
                original_message,
                content.TRANSBORDER_REQUIRED_TEXT,
                reply_markup=_transborder_consent_markup(),
                action="transborder_required_message",
            )
            return

        # ПРОВЕРКА: если клиент повторяет одно и то же сообщение 3+ раза
        # И прошло более 30 минут с начала диалога - завершаем разговор
        conversation_history = database.db.get_conversation_history(user_data["id"])
        if conversation_history:
            user_messages = [msg for msg in conversation_history if msg["role"] == "user"]
            if len(user_messages) >= 3:
                last_three = [msg.get("content", msg.get("message", "")).strip().lower() for msg in user_messages[-3:]]
                if len(set(last_three)) == 1:
                    import datetime

                    first_message_time = datetime.datetime.fromisoformat(conversation_history[0]["timestamp"])
                    current_time = datetime.datetime.now()
                    time_elapsed = (current_time - first_message_time).total_seconds() / 60
                    if time_elapsed > 30:
                        await utils.safe_reply_html(
                            original_message,
                            content.REPEAT_LOOP_FALLBACK_TEXT,
                            action="repeat_loop_fallback",
                        )
                        return

        # Сохраняем сообщение пользователя
        database.db.add_message(user_data["id"], "user", message_text)

        # Получаем историю диалога (включая текущее сообщение)
        conversation_history = database.db.get_conversation_history(user_data["id"])
        lead_id = lead["id"] if lead else None
        lead_data = None
        merged_lead_data = dict(lead or {})
        response_stage = current_stage

        # Стадию ответа считаем без дополнительного LLM-запроса,
        # чтобы не задерживать пользовательский ответ.
        if allow_lead_processing:
            response_stage = funnel.infer_stage(
                previous_stage=current_stage,
                user_message=message_text,
                lead_data=merged_lead_data,
            )

        # Генерируем ответ через AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        _schedule_typing_indicator(original_message.chat, user_data["telegram_id"])

        start_generation = time.time()
        preview_enabled = config.STREAMING_PREVIEW
        funnel_context = _append_profile_name_context(
            funnel.build_stage_context(response_stage, cta_variant, cta_shown),
            user_data.get("first_name") or user.first_name,
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
                            logger.debug(f"Initial message sent: {len(full_response)} chars")
                        except TelegramError as e:
                            logger.warning(f"Failed to send initial message: {e}")
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
                        logger.debug(f"Message updated: {len(full_response)} chars")
                    except TelegramError as e:
                        logger.debug(f"Skipped update (rate limit): {e}")

        generation_time = time.time() - start_generation
        logger.info(f"Response generated in {generation_time:.2f}s ({len(full_response)} chars)")
        full_response = funnel.enforce_leadgen_response(
            response_text=full_response,
            stage=response_stage,
            user_message=message_text,
            cta_shown=cta_shown,
            cta_variant=cta_variant,
            lead_data=merged_lead_data,
        )
        full_response = utils.format_ai_text_as_plain_symbols(full_response)
        show_consultation_button = funnel.should_show_consultation_button(response_stage, cta_shown)
        consultation_button_sent = False

        if len(full_response) > 4096:
            logger.warning(f"Response too long ({len(full_response)} chars), splitting into parts")
            parts = utils.split_long_message(full_response, max_length=4000)

            if sent_message:
                try:
                    await sent_message.delete()
                except TelegramError:
                    pass

            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                await original_message.reply_text(part_msg)
                if i < len(parts) - 1:
                    await original_message.chat.send_action(action="typing")
                    await asyncio.sleep(0.5)
        else:
            if sent_message:
                try:
                    await utils.safe_edit_text(
                        sent_message,
                        full_response,
                        action="streaming_final_update",
                    )
                    logger.debug("Final message update sent")
                except TelegramError:
                    pass
            else:
                await utils.safe_reply_text(
                    original_message,
                    full_response,
                    action="assistant_final_message",
                )

        if show_consultation_button:
            try:
                await original_message.reply_text(
                    content.CONSULTATION_CTA_TEXT,
                    reply_markup=_consultation_cta_markup(),
                )
                consultation_button_sent = True
            except TelegramError as cta_error:
                logger.warning(f"Failed to send consultation CTA button: {cta_error}")

        database.db.add_message(user_data["id"], "assistant", full_response)

        # Аналитика: показ CTA (кнопка консультации / fallback в тексте)
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
                logger.warning(f"Failed to track cta_shown event: {analytics_error}")

        # 🛡️ УЧЕТ ИСПОЛЬЗОВАННЫХ ТОКЕНОВ
        user_tokens = security.security_manager.estimate_tokens(message_text)
        assistant_tokens = security.security_manager.estimate_tokens(full_response)
        system_tokens = security.security_manager.estimate_tokens(prompts.SYSTEM_PROMPT)
        total_tokens = user_tokens + assistant_tokens + system_tokens
        security.security_manager.add_tokens_used(total_tokens, user_id=user.id)
        logger.debug(
            f"Tokens used: user={user_tokens}, assistant={assistant_tokens}, "
            f"system={system_tokens}, total={total_tokens}"
        )

        # Обновляем воронку сразу после ответа, чтобы следующий апдейт
        # не ждал завершения LLM-экстракции данных лида.
        if allow_lead_processing:
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
                    logger.warning(f"Failed to track stage_changed event: {analytics_error}")

            cta_was_shown = cta_shown
            merged_snapshot = dict(merged_lead_data)
            conversation_snapshot = list(conversation_history)
            user_db_id = user_data["id"]

            async def _post_response_lead_processing() -> None:
                try:
                    extracted = await ai_brain.ai_brain.extract_lead_data_async(conversation_snapshot)
                    if not extracted:
                        return

                    telegram_profile_name = (user_data.get("first_name") or user.first_name or "").strip()
                    if telegram_profile_name:
                        extracted["name"] = telegram_profile_name

                    merged_snapshot.update({k: v for k, v in extracted.items() if v is not None})
                    processed_lead_id = lead_qualifier.lead_qualifier.process_lead_data(user_db_id, extracted)
                    if processed_lead_id:
                        database.db.update_lead_last_message_time(user_db_id)
                        logger.info(f"Lead {processed_lead_id} updated in background")
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
                            logger.warning(f"Failed to track lead magnet CTA show: {analytics_error}")
                except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError) as background_error:
                    logger.warning(f"Background lead processing failed for user {user_db_id}: {background_error}")

            asyncio.create_task(_post_response_lead_processing())

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError, OSError) as e:
        if "Peer_id_invalid" not in str(e):
            logger.error(f"Error in handle_message: {e}")
