"""
Shared reply/inline markup builders for lead-bot handlers.
"""
from __future__ import annotations

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram_ui import inline_button as InlineKeyboardButton
from telegram_ui import reply_button as KeyboardButton

import content
from config import get_config
from handlers.constants import (
    ADMIN_MENU,
    CONSENT_PDN_MENU,
    CONSENT_TRANSBORDER_MENU,
    CONSULTATION_CTA_MENU,
    DOCUMENTS_MENU,
    MAIN_MENU,
    PERSONAL_MODE_RETURN_MENU,
    QUICK_NAV_MENU,
    WORKSPACE_INLINE_MENU,
    BUSINESS_AWAITING_CONTACT_KEY,
    BUSINESS_AWAITING_CONTACT_SOURCE_KEY,
    BUSINESS_PENDING_CONTACT_KEY,
    append_inline_url_row,
    build_quick_nav_menu,
    build_workspace_inline_menu,
)

config = get_config()


def pdn_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_PDN_MENU)


def transborder_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_TRANSBORDER_MENU)


def consultation_cta_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSULTATION_CTA_MENU)


def documents_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(DOCUMENTS_MENU)


def consultation_contact_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📲 Отправить телефон", request_contact=True)],
            [KeyboardButton("⬅️ Отмена")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def services_inline_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(WORKSPACE_INLINE_MENU)


def workspace_markup_for(
    lead: dict | None = None,
    selected_profile: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        build_workspace_inline_menu(
            content.offer_profile_cta_label(
                lead=lead,
                selected_profile=selected_profile,
            )
        )
    )


def quick_nav_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(QUICK_NAV_MENU)


def quick_nav_markup_for(
    lead: dict | None = None,
    selected_profile: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        build_quick_nav_menu(
            content.offer_profile_cta_label(
                lead=lead,
                selected_profile=selected_profile,
            )
        )
    )


def with_channel_button(
    markup: InlineKeyboardMarkup,
    *,
    prepend: bool = False,
) -> InlineKeyboardMarkup:
    return append_inline_url_row(
        markup,
        content.CHANNEL_BUTTON_TEXT,
        content.public_channel_url(),
        prepend=prepend,
    )


def main_menu_markup(user_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        ADMIN_MENU if user_id == config.ADMIN_TELEGRAM_ID else MAIN_MENU,
        resize_keyboard=True,
    )


def profile_edit_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Исправить ФИО", callback_data="profile_edit_name"),
                InlineKeyboardButton("✉️ Исправить Email", callback_data="profile_edit_email"),
            ]
        ]
    )


def profile_panel_markup(
    is_admin: bool,
    lead: dict | None = None,
    selected_profile: str | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not is_admin:
        rows.extend(profile_edit_markup().inline_keyboard)
    rows.extend(
        build_quick_nav_menu(
            content.offer_profile_cta_label(
                lead=lead,
                selected_profile=selected_profile,
            )
        )
    )
    return InlineKeyboardMarkup(rows)


def personal_mode_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(PERSONAL_MODE_RETURN_MENU)


def profile_edit_cancel_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("⬅️ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def clear_business_contact_state(context) -> None:
    context.user_data.pop(BUSINESS_AWAITING_CONTACT_KEY, None)
    context.user_data.pop(BUSINESS_AWAITING_CONTACT_SOURCE_KEY, None)
    context.user_data.pop(BUSINESS_PENDING_CONTACT_KEY, None)


def contact_visibility_choice_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📲 Оставить номер телефона", callback_data="menu_contact_send_phone")],
            [InlineKeyboardButton("💬 Связаться в Telegram", callback_data="menu_contact_telegram_only")],
        ]
    )


def offer_profile_markup(selected_profile: str | None = None) -> InlineKeyboardMarkup:
    def _label(text: str, *, active: bool) -> str:
        return f"✅ {text}" if active else text

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _label("🏢 Юр. отдел", active=selected_profile == "inhouse"),
                    callback_data="menu_offer_set_inhouse",
                ),
                InlineKeyboardButton(
                    _label("⚖️ Юрфирма", active=selected_profile == "law_firm"),
                    callback_data="menu_offer_set_law_firm",
                ),
            ],
            [
                InlineKeyboardButton(
                    _label("📈 Бизнес", active=selected_profile == "business"),
                    callback_data="menu_offer_set_business",
                ),
                InlineKeyboardButton(
                    _label("📦 Общий", active=selected_profile == "universal"),
                    callback_data="menu_offer_set_universal",
                ),
            ],
            [
                InlineKeyboardButton(
                    _label("🧭 Автоопределение", active=selected_profile is None),
                    callback_data="menu_offer_set_auto",
                )
            ],
            [InlineKeyboardButton("🧭 Рабочий стол", callback_data="menu_dashboard")],
        ]
    )


def business_phone_format_text() -> str:
    return (
        "Отправьте номер одним сообщением в одном из форматов:\n"
        "• +7 999 123-45-67\n"
        "• 8 999 123-45-67\n"
        "• 89991234567"
    )


def admin_lookup_menu_markup(back_callback: str, back_label: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🗂️ Карточка по ID", callback_data="admin_lookup_card_prompt")],
        [InlineKeyboardButton("💬 История диалога по ID", callback_data="admin_lookup_dialog_prompt")],
        [InlineKeyboardButton("✏️ Редактировать ПД", callback_data="admin_lookup_edit_prompt")],
        [InlineKeyboardButton("🗑️ Отозвать согласие по ID", callback_data="admin_lookup_revoke_prompt")],
        [InlineKeyboardButton("♻️ Сделать как новый по ID", callback_data="admin_lookup_reset_new_prompt")],
        [InlineKeyboardButton("🧨 Полностью удалить по ID", callback_data="admin_lookup_delete_prompt")],
        [InlineKeyboardButton("👥 Открыть список пользователей", callback_data="admin_users_list")],
        [InlineKeyboardButton(back_label, callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(rows)


def documents_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(DOCUMENTS_MENU)


def documents_panel_text(
    selected_title: str | None = None,
    selected_body: str | None = None,
) -> str:
    base = "<b>📚 Документы и права пользователя</b>\n\nВыберите пункт в меню ниже."
    if not selected_title:
        return base
    return (
        f"{base}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"<b>{selected_title}</b>\n\n"
        f"{selected_body or ''}"
    ).strip()


def clip_for_edit(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    return (
        f"{text[:limit].rstrip()}\n\n…\n"
        "(Сокращено для экрана. Полная версия доступна через соответствующую команду.)"
    )


def admin_users_list_markup(
    users: list[dict],
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    rows = []
    for user in users:
        telegram_id = user.get("telegram_id")
        username = user.get("username")
        label = f"👤 ID {telegram_id} - @{username}" if username else f"👤 ID {telegram_id}"
        rows.append([InlineKeyboardButton(label[:60], callback_data=f"admin_user_detail_{telegram_id}")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("◀️", callback_data=f"admin_users_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="admin_users_page_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"admin_users_page_{page + 1}"))
    rows.append(nav_row)
    rows.append([InlineKeyboardButton("◀️ Назад в раздел пользователей", callback_data="admin_section_users")])
    return InlineKeyboardMarkup(rows)


def admin_user_detail_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧾 Экспорт данных", callback_data=f"admin_user_export_{telegram_id}")],
            [InlineKeyboardButton("🔄 Сбросить диалог", callback_data=f"admin_user_reset_dialog_{telegram_id}")],
            [InlineKeyboardButton("♻️ Сделать как новый", callback_data=f"admin_user_reset_new_confirm_{telegram_id}")],
            [InlineKeyboardButton("🗑️ Очистить данные", callback_data=f"admin_user_clear_confirm_{telegram_id}")],
            [InlineKeyboardButton("🧨 Полностью удалить", callback_data=f"admin_user_delete_confirm_{telegram_id}")],
            [InlineKeyboardButton("◀️ К списку пользователей", callback_data="admin_users_list")],
        ]
    )


def admin_user_clear_confirm_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data=f"admin_user_clear_{telegram_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_user_detail_{telegram_id}"),
            ]
        ]
    )


def admin_user_reset_new_confirm_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да, сбросить", callback_data=f"admin_user_reset_new_{telegram_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_user_detail_{telegram_id}"),
            ]
        ]
    )


def admin_user_delete_confirm_markup(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"admin_user_delete_{telegram_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"admin_user_detail_{telegram_id}"),
            ]
        ]
    )
