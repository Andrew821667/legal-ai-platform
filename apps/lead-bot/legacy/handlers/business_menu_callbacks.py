from __future__ import annotations

import logging
import sqlite3

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

import content
import database
import funnel
import utils
from config import get_config
from lead_perf import log_span_timing, perf_start
from handlers.callback_flows import (
    build_client_profile_text as _build_client_profile_text,
    has_pdn_consent as _has_pdn_consent,
)
from handlers.constants import (
    ADMIN_MENU,
    BUSINESS_AWAITING_CONTACT_KEY,
    BUSINESS_AWAITING_CONTACT_SOURCE_KEY,
    BUSINESS_PENDING_CONTACT_KEY,
    CONSENT_PDN_MENU,
    LEAD_MAGNET_MENU,
    MAIN_MENU,
    append_inline_url_row,
)
from handlers.helpers import notify_admin_new_lead
from handlers.markup import (
    business_phone_format_text as _business_phone_format_text,
    clear_business_contact_state as _clear_business_contact_state,
    clip_for_edit as _clip_for_edit,
    consultation_contact_markup as _consultation_contact_markup,
    contact_visibility_choice_markup as _contact_visibility_choice_markup,
    documents_panel_markup as _documents_panel_markup,
    documents_panel_text as _documents_panel_text,
    offer_profile_markup as _offer_profile_markup,
    personal_mode_markup as _personal_mode_markup,
    with_channel_button as _with_channel_button,
    workspace_markup_for as _workspace_markup_for,
)

config = get_config()
logger = logging.getLogger(__name__)


def _resolve_local_callback_user(user) -> tuple[int | None, dict | None]:
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
        contact_actions = {"menu_consultation", "menu_leave_contact"}

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
            user_db_id, local_user = _resolve_local_callback_user(user)
            lead = database.db.get_local_lead_by_user_id(user_db_id) if user_db_id else None
            selected_profile = (local_user or {}).get("offer_profile_override") or None
        menu_markup = _workspace_markup_for(lead=lead, selected_profile=selected_profile)

        async def _send_business_menu_message(text: str, reply_markup: InlineKeyboardMarkup | None) -> None:
            await utils.safe_send_message(
                context.bot,
                action=f"business_menu:{callback_data or 'unknown'}",
                chat_id=query.message.chat.id,
                text=text,
                parse_mode="HTML",
                business_connection_id=query.message.business_connection_id,
                reply_markup=reply_markup,
            )

        profile_callback_map = {
            "menu_offer_set_inhouse": "inhouse",
            "menu_offer_set_law_firm": "law_firm",
            "menu_offer_set_business": "business",
            "menu_offer_set_universal": "universal",
            "menu_offer_set_auto": None,
        }
        if callback_data in profile_callback_map:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="offer_profile_no_user",
                )
                return
            new_profile = profile_callback_map[callback_data]
            database.db.set_user_offer_profile(user_db_id, new_profile)
            lead = database.db.get_lead_by_user_id(user_db_id) if user_db_id else None
            response_text = content.offer_profile_change_success_text(new_profile)
            response_text = (
                f"{response_text}\n\n"
                f"{content.offer_profile_panel_text(lead=lead, selected_profile=new_profile)}"
            )
            response_markup = _offer_profile_markup(new_profile)
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_offer_profile_set",
                )
            return

        if callback_data == "menu_offer_profile":
            response_text = content.offer_profile_panel_text(lead=lead, selected_profile=selected_profile)
            response_markup = _offer_profile_markup(selected_profile)
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_offer_profile",
                )
            return

        response_text = content.menu_response_by_key(
            callback_data,
            lead=lead,
            selected_profile=selected_profile,
        )

        contact_flow_actions = contact_actions | {"menu_contact_send_phone", "menu_contact_telegram_only"}
        if callback_data not in contact_flow_actions:
            _clear_business_contact_state(context)

        if (
            user
            and user.id != config.ADMIN_TELEGRAM_ID
            and callback_data in contact_flow_actions
            and not _has_pdn_consent(
                consent_state
                if consent_state is not None
                else (database.db.get_user_consent_state(user_db_id) if user_db_id else {})
            )
        ):
            await utils.safe_reply_html(
                query.message,
                f"{content.pdn_consent_required_text('Консультации и передаче контакта')}\n\n{content.CONSENT_STEP_1_TEXT}",
                reply_markup=InlineKeyboardMarkup(CONSENT_PDN_MENU),
                action="menu_requires_pdn",
            )
            return

        if callback_data == "menu_restart":
            if user_db_id:
                database.db.clear_conversation_history(user_db_id)
                database.db.reset_user_funnel_state(user_db_id)
            restart_text = "Историю очистил. Начинаем заново. Опишите задачу одним сообщением."
            if is_business:
                await _send_business_menu_message(restart_text, menu_markup)
            else:
                await utils.safe_edit_text(
                    query.message,
                    restart_text,
                    reply_markup=menu_markup,
                    action="menu_restart",
                )
            return

        if callback_data == "menu_return_to_bot":
            chat_id = getattr(getattr(query, "message", None), "chat", None)
            chat_id = getattr(chat_id, "id", None)
            if chat_id is not None:
                database.db.set_chat_mode(int(chat_id), "bot")

            if user_db_id:
                database.db.reset_user_funnel_state(user_db_id)

            if is_business:
                response_text = content.build_business_welcome_message(user.first_name if user else "клиент")
            else:
                response_text = content.build_welcome_message(user.first_name if user else "клиент")
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_reply_html(
                    query.message,
                    response_text,
                    action="menu_return_to_bot",
                    reply_markup=ReplyKeyboardMarkup(
                        ADMIN_MENU if user and user.id == config.ADMIN_TELEGRAM_ID else MAIN_MENU,
                        resize_keyboard=True,
                    ),
                )
            return

        if callback_data == "menu_dashboard":
            response_text = content.build_workspace_text(lead=lead, selected_profile=selected_profile)
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    response_text,
                    reply_markup=menu_markup,
                    action="menu_dashboard",
                )
            return

        if callback_data == "menu_profile":
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить профиль. Нажмите /start и повторите.",
                    action="menu_profile_no_user",
                )
                return
            user_row = local_user or database.db.get_local_user_by_id(user_db_id) or {}
            lead = database.db.get_local_lead_by_user_id(user_db_id)
            consent_state = database.db.get_user_consent_state(user_db_id)
            response_text = _build_client_profile_text(user_row, lead, consent_state)
            if is_business:
                await _send_business_menu_message(response_text, menu_markup)
            else:
                await utils.safe_edit_text(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=menu_markup,
                    action="menu_profile",
                )
            return

        if callback_data == "menu_documents":
            response_text = _documents_panel_text()
            docs_markup = _documents_panel_markup()
            if is_business:
                await _send_business_menu_message(response_text, docs_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    response_text,
                    reply_markup=docs_markup,
                    action="menu_documents",
                )
            return

        if callback_data == "menu_contract_ai":
            response_text = (
                f"{content.menu_response_by_key('menu_contract_ai', lead=lead, selected_profile=selected_profile)}\n\n"
                f"{content.LEAD_MAGNET_OFFER_TEXT}"
            )
            response_markup = _with_channel_button(InlineKeyboardMarkup(LEAD_MAGNET_MENU))
            response_markup = append_inline_url_row(
                response_markup,
                content.CONTRACT_AI_BUTTON_TEXT,
                content.contract_ai_public_url(),
                prepend=True,
            )
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_edit_html(
                    query.message,
                    _clip_for_edit(response_text),
                    reply_markup=response_markup,
                    action="menu_contract_ai",
                )
            return

        if callback_data in {"menu_contact_send_phone", "menu_contact_telegram_only"}:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="contact_choice_no_user",
                )
                return

            if callback_data == "menu_contact_send_phone":
                pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
                source = pending_contact.get("source") or "consultation"
                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = source
                response_text = "Отлично, пришлите номер телефона.\n" f"{_business_phone_format_text()}"
                response_markup = menu_markup if is_business else _consultation_contact_markup()
            else:
                pending_contact = context.user_data.get(BUSINESS_PENDING_CONTACT_KEY) or {}
                previous_lead = database.db.get_lead_by_user_id(user_db_id) or {}
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
                lead_id = database.db.create_new_lead(user_db_id, lead_payload)
                user_state = database.db.get_user_funnel_state(user_db_id)
                cta_variant = user_state.get("cta_variant") or funnel.choose_cta_variant(user_db_id)
                database.db.update_user_funnel_state(
                    user_db_id,
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
                        user_db_id,
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
                        "id": user_db_id,
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
                response_markup = _with_channel_button(menu_markup)

            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action=f"{callback_data}_reply",
                    reply_markup=response_markup,
                )
            return

        if callback_data == "menu_personal_request":
            chat = getattr(query.message, "chat", None)
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
            response_markup = _personal_mode_markup()
            if is_business:
                await _send_business_menu_message(response_text, response_markup)
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action="menu_personal_request_mode_on",
                    reply_markup=response_markup,
                )
            return

        if callback_data in contact_actions:
            if not user_db_id:
                await utils.safe_reply_text(
                    query.message,
                    "Не удалось определить пользователя. Нажмите /start и повторите.",
                    action="contact_action_no_user",
                )
                return
            contact_source = "consultation"
            notes = None
            lead_magnet_type = "consultation"
            if callback_data == "menu_leave_contact":
                existing_lead = database.db.get_lead_by_user_id(user_db_id) or {}
                if existing_lead.get("lead_magnet_type") == "personal_request":
                    lead_magnet_type = "personal_request"
                    notes = existing_lead.get("notes") or "Личное обращение к Андрею Попову"
                    contact_source = "personal_request"

            if callback_data == "menu_leave_contact":
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
                    "name": user.first_name if user else None,
                    "lead_magnet_type": lead_magnet_type,
                    "lead_magnet_delivered": False,
                    "notification_sent": 0,
                }
                if notes:
                    lead_payload["notes"] = notes
                database.db.create_or_update_lead(user_db_id, lead_payload)

                context.user_data.pop(BUSINESS_PENDING_CONTACT_KEY, None)
                context.user_data[BUSINESS_AWAITING_CONTACT_KEY] = True
                context.user_data[BUSINESS_AWAITING_CONTACT_SOURCE_KEY] = contact_source
                response_text = "Отлично, пришлите номер телефона.\n" f"{_business_phone_format_text()}"
                response_markup = menu_markup if is_business else _consultation_contact_markup()

            if is_business:
                await _send_business_menu_message(
                    response_text,
                    response_markup if callback_data == "menu_leave_contact" else menu_markup,
                )
            else:
                await utils.safe_reply_text(
                    query.message,
                    response_text,
                    action=f"{callback_data}_reply",
                    reply_markup=(
                        response_markup
                        if callback_data == "menu_leave_contact"
                        else _consultation_contact_markup()
                    ),
                )
            return

        if is_business:
            reply_markup = (
                _with_channel_button(menu_markup)
                if callback_data in {"menu_services", "menu_prices", "menu_help"}
                else menu_markup
            )
            await _send_business_menu_message(response_text, reply_markup)
        else:
            reply_markup = (
                _with_channel_button(menu_markup)
                if callback_data in {"menu_services", "menu_prices", "menu_help"}
                else menu_markup
            )
            await utils.safe_edit_html(
                query.message,
                response_text,
                reply_markup=reply_markup,
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
