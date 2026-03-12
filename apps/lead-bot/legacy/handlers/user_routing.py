from __future__ import annotations

from telegram import InlineKeyboardMarkup, Message, Update, User
from telegram.ext import ContextTypes

import content
import database
import utils
from config import get_config
from telegram_ui import normalize_button_text
from handlers.constants import ADMIN_PANEL_MENU
from handlers.markup import (
    consultation_contact_markup as _consultation_contact_markup,
    main_menu_markup as _main_menu_markup,
    pdn_consent_markup as _pdn_consent_markup,
    personal_mode_markup as _personal_mode_markup,
    workspace_markup_for as _workspace_markup_for,
)
from handlers.user_commands import (
    _pdn_consent_prompt_text,
    _should_require_pdn_consent,
)
from handlers.user_message_helpers import looks_like_plain_greeting, looks_like_return_to_bot

config = get_config()


def _button_text_equals(text: str | None, expected: str) -> bool:
    return normalize_button_text(text).casefold() == normalize_button_text(expected).casefold()


def _is_navigation_shortcut(message_text: str) -> bool:
    raw = (message_text or "").strip()
    if not raw:
        return False
    if _button_text_equals(raw, "🧭 Рабочий стол") or _button_text_equals(raw, "📋 Меню услуг"):
        return True
    return raw.lower() in ["/menu", "menu", "/меню", "меню"]


async def send_welcome_workspace(
    message: Message,
    *,
    first_name: str | None,
    user_id: int,
    lead: dict | None,
    welcome_action: str,
    workspace_action: str,
    emphasize_profile_choice: bool = True,
) -> None:
    await utils.safe_reply_html(
        message,
        content.build_welcome_message(first_name),
        reply_markup=_main_menu_markup(user_id),
        action=welcome_action,
    )
    selected_profile = database.db.get_user_offer_profile(user_id)
    workspace_markup = _workspace_markup_for(lead=lead, selected_profile=selected_profile)
    await utils.safe_reply_html(
        message,
        content.build_workspace_text(
            lead=lead,
            selected_profile=selected_profile,
            emphasize_profile_choice=emphasize_profile_choice,
        ),
        reply_markup=workspace_markup,
        action=workspace_action,
    )


async def send_workspace_entry(
    message: Message,
    *,
    user_id: int,
    lead: dict | None,
    workspace_action: str,
    emphasize_profile_choice: bool = True,
    include_context_intro: bool = False,
) -> None:
    selected_profile = database.db.get_user_offer_profile(user_id)
    workspace_markup = _workspace_markup_for(lead=lead, selected_profile=selected_profile)
    await utils.safe_reply_html(
        message,
        content.build_workspace_text(
            lead=lead,
            selected_profile=selected_profile,
            emphasize_profile_choice=emphasize_profile_choice,
            include_context_intro=include_context_intro,
        ),
        reply_markup=workspace_markup,
        action=workspace_action,
    )


async def maybe_handle_personal_mode(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    original_message: Message,
    message_text: str,
    user: User,
    user_data: dict,
    lead: dict | None,
    chat_id: int,
    chat_mode: str | None,
) -> bool:
    if _button_text_equals(message_text, "✉️ Личное обращение"):
        database.db.set_chat_mode(chat_id, "personal")
        await utils.safe_reply_text(
            original_message,
            "Чат переведен в личный режим.\n\n"
            "Теперь можете писать Андрею напрямую: бот не будет отвечать и не будет "
            "обрабатывать сообщения как лиды.\n\n"
            "Когда захотите снова пользоваться ботом, нажмите «↩️ Вернуться к боту».",
            reply_markup=_personal_mode_markup(),
            action="personal_mode_enabled",
        )
        return True

    if chat_mode == "personal":
        if looks_like_return_to_bot(message_text):
            database.db.set_chat_mode(chat_id, "bot")
            database.db.reset_user_funnel_state(user_data["id"])
            await send_welcome_workspace(
                original_message,
                first_name=user.first_name,
                user_id=user.id,
                lead=lead,
                welcome_action="personal_mode_return_text",
                workspace_action="personal_mode_return_workspace",
            )
        return True

    return False


async def maybe_handle_initial_entry(
    *,
    original_message: Message,
    message_text: str,
    user: User,
    user_data: dict,
    lead: dict | None,
    history_exists: bool,
) -> bool:
    if message_text and not history_exists and not _is_navigation_shortcut(message_text):
        await send_workspace_entry(
            original_message,
            user_id=user.id,
            lead=lead,
            workspace_action="forced_workspace_new_session",
            include_context_intro=True,
        )
        return True

    if message_text and looks_like_plain_greeting(message_text):
        await send_workspace_entry(
            original_message,
            user_id=user.id,
            lead=lead,
            workspace_action="workspace_on_greeting",
            include_context_intro=True,
        )
        return True

    return False


async def maybe_handle_static_reply_action(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    original_message: Message,
    message_text: str,
    user: User,
    user_data: dict,
    consent_state: dict,
    is_admin: bool,
    allow_lead_processing: bool,
    consultation_requires_pdn: bool,
    menu_handler,
    profile_handler,
    documents_handler,
    reset_handler,
) -> bool:
    if _is_navigation_shortcut(message_text):
        await menu_handler(update, context)
        return True

    if _button_text_equals(message_text, "👤 Мой профиль"):
        await profile_handler(update, context)
        return True

    if _button_text_equals(message_text, "📚 Документы"):
        await documents_handler(update, context)
        return True

    if _button_text_equals(message_text, "🔄 Начать заново"):
        await reset_handler(update, context)
        return True

    if _button_text_equals(message_text, "⬅️ Отмена"):
        await utils.safe_reply_text(
            original_message,
            "Ок, вернул основное меню.",
            reply_markup=_main_menu_markup(user.id),
            action="cancel_to_main_menu",
        )
        return True

    if _button_text_equals(message_text, "📞 Консультация") or _button_text_equals(message_text, "✉️ Заказать консультацию"):
        if consultation_requires_pdn and _should_require_pdn_consent(is_admin, consent_state):
            await utils.safe_reply_text(
                original_message,
                _pdn_consent_prompt_text("Консультации"),
                reply_markup=_pdn_consent_markup(),
                action="consultation_requires_pdn",
            )
            return True
        if allow_lead_processing:
            database.db.create_or_update_lead(
                user_data["id"],
                {
                    "name": user.first_name,
                    "lead_magnet_type": "consultation",
                    "lead_magnet_delivered": False,
                },
            )
        await utils.safe_reply_text(
            original_message,
            "Оставьте номер телефона, и команда свяжется с вами в ближайшее рабочее время.",
            reply_markup=_consultation_contact_markup(),
            action="consultation_phone_prompt",
        )
        return True

    if _button_text_equals(message_text, "⚙️ Админ-панель"):
        if is_admin:
            await utils.safe_reply_text(
                original_message,
                "⚙️ АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
                reply_markup=InlineKeyboardMarkup(ADMIN_PANEL_MENU),
                action="open_admin_panel_from_user_flow",
            )
        else:
            await original_message.reply_text("У вас нет доступа к этой функции")
        return True

    return False
