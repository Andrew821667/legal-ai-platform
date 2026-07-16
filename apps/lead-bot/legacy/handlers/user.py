"""
Handlers: user
"""
from __future__ import annotations

import logging
import sqlite3
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
import database
from config import get_config
config = get_config()
import utils
import security
import content
from .markup import (
    pdn_consent_markup as _pdn_consent_markup,
    transborder_consent_markup as _transborder_consent_markup,
)
from .user_commands import (
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
from .user_admin_lookup import handle_admin_lookup_input
from .user_cta_actions import (
    handle_handoff_request,
    handle_menu_button,
    offer_lead_magnet,
)
from .user_ai_response import process_ai_response
from .user_lead_flow import (
    get_lead_flow_state,
    maybe_create_new_topic_lead,
    maybe_handle_handoff_shortcuts,
    maybe_handle_pending_lead_magnet,
    maybe_handle_repeat_loop,
)
from .contract_analysis import handle_contract_document, CONTRACT_ANALYSIS_WAITING_KEY
from .user_non_text import handle_non_text_input as _handle_non_text_input
from .user_profile_edit import handle_profile_edit_input
from .user_routing import (
    maybe_handle_initial_entry,
    maybe_handle_personal_mode,
    maybe_handle_static_reply_action,
)
from .start_payloads import process_pending_start_payload
from .legal_help import maybe_handle_legal_help_message

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
        user_data = database.db.get_local_user_by_telegram_id(user.id)
        if not user_data:
            database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            user_data = database.db.get_local_user_by_telegram_id(user.id)
            if not user_data:
                return

        lead = database.db.get_local_lead_by_user_id(user_data["id"])
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
            # Перехватываем документ если пользователь в режиме анализа договора
            if context.user_data.get(CONTRACT_ANALYSIS_WAITING_KEY):
                handled = await handle_contract_document(update, context, user_data)
                if handled:
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

        if await maybe_handle_legal_help_message(
            update=update,
            context=context,
            message_text=message_text,
            user=user,
            user_data=user_data,
        ):
            return

        lead, handled_pending_magnet = await maybe_handle_pending_lead_magnet(
            update=update,
            context=context,
            user=user,
            user_data=user_data,
            lead=lead,
            message_text=message_text,
        )
        if handled_pending_magnet:
            return

        flow_state = get_lead_flow_state(user_db_id=user_data["id"], lead=lead)
        flow_state = await maybe_create_new_topic_lead(
            context=context,
            user=user,
            user_data=user_data,
            message_text=message_text,
            allow_lead_processing=allow_lead_processing,
            state=flow_state,
        )
        lead = flow_state.lead
        current_stage = flow_state.current_stage
        cta_variant = flow_state.cta_variant
        cta_shown = flow_state.cta_shown

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
        if await maybe_handle_handoff_shortcuts(
            update=update,
            context=context,
            user=user,
            user_data=user_data,
            lead=lead,
            message_text=message_text,
            allow_lead_processing=allow_lead_processing,
        ):
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
        if await maybe_handle_repeat_loop(
            original_message=original_message,
            user_db_id=user_data["id"],
        ):
            return

        await process_ai_response(
            update=update,
            context=context,
            original_message=original_message,
            user=user,
            user_data=user_data,
            lead=lead,
            message_text=message_text,
            current_stage=current_stage,
            cta_variant=cta_variant,
            cta_shown=cta_shown,
            allow_lead_processing=allow_lead_processing,
        )

    except (sqlite3.Error, TelegramError, KeyError, AttributeError, ValueError, OSError) as e:
        if "Peer_id_invalid" not in str(e):
            logger.error(f"Error in handle_message: {e}")
