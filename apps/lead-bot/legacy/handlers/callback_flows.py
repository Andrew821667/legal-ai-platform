from __future__ import annotations

import logging
import sqlite3

from telegram import InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram_ui import reply_button as KeyboardButton

import admin_interface
import content
import database
import funnel
import lead_qualifier
import utils
from config import get_config
from .constants import CONSENT_PDN_MENU
from .helpers import notify_admin_new_lead
from .markup import (
    clip_for_edit as _clip_for_edit,
    documents_panel_markup as _documents_panel_markup,
    documents_panel_text as _documents_panel_text,
    workspace_markup_for as _workspace_markup_for,
)
from .start_payloads import process_pending_start_payload

config = get_config()
logger = logging.getLogger(__name__)


def build_client_profile_text(user_row: dict, lead: dict | None, consent_state: dict) -> str:
    lead = lead or {}
    full_name = " ".join(
        part
        for part in (
            (user_row.get("first_name") or "").strip(),
            (user_row.get("last_name") or "").strip(),
        )
        if part
    ) or "—"
    username = user_row.get("username")
    username_text = f"@{username}" if username else "не указан"
    name_in_lead = lead.get("name") or full_name
    consent_hint = content.consent_user_status_text(consent_state)
    return (
        "👤 Ваш профиль\n\n"
        f"Имя профиля: {full_name}\n"
        f"Username: {username_text}\n\n"
        "Контактные данные:\n"
        f"• Имя в заявке: {name_in_lead}\n"
        f"• Email: {lead.get('email') or 'не указан'}\n"
        f"• Телефон: {lead.get('phone') or 'не указан'}\n"
        f"• Компания: {lead.get('company') or 'не указана'}\n\n"
        f"{consent_hint}\n\n"
        "Чтобы исправить ФИО или email, используйте кнопку «👤 Профиль» на рабочем столе."
    )


def has_pdn_consent(consent_state: dict | None) -> bool:
    consent_state = consent_state or {}
    return bool(consent_state.get("consent_given")) and not bool(consent_state.get("consent_revoked"))


async def handle_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback-обработчик редактирования полей профиля пользователя."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="profile_edit_answer")
    except TelegramError as answer_error:
        logger.warning("Failed to answer profile callback: %s", answer_error)

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await utils.safe_reply_text(query.message, "Сначала выполните /start.", action="profile_edit_no_user")
        return

    action = query.data or ""
    cancel_markup = ReplyKeyboardMarkup(
        [[KeyboardButton("⬅️ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    if action == "profile_edit_name":
        context.user_data["profile_edit_field"] = "name"
        await utils.safe_reply_text(
            query.message,
            "Введите корректные ФИО одной строкой.\nНапример: Иван Иванов\n\nДля выхода нажмите «⬅️ Отмена».",
            reply_markup=cancel_markup,
            action="profile_edit_name_prompt",
        )
        return

    if action == "profile_edit_email":
        context.user_data["profile_edit_field"] = "email"
        await utils.safe_reply_text(
            query.message,
            "Введите корректный email.\nНапример: user@example.com\n\nДля выхода нажмите «⬅️ Отмена».",
            reply_markup=cancel_markup,
            action="profile_edit_email_prompt",
        )
        return

    await utils.safe_reply_text(query.message, "Неизвестное действие профиля.", action="profile_edit_unknown")


async def handle_lead_magnet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора lead magnet."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="lead_magnet_answer")
    except TelegramError as answer_error:
        logger.warning("Failed to answer lead magnet callback: %s", answer_error)

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)

    if not user_data:
        await utils.safe_reply_text(query.message, "Ошибка. Попробуйте /start", action="lead_magnet_no_user")
        return

    if user.id != config.ADMIN_TELEGRAM_ID and not has_pdn_consent(database.db.get_user_consent_state(user_data["id"])):
        await utils.safe_reply_text(
            query.message,
            f"{content.pdn_consent_required_text('получению материалов и фиксации заявки')}\n\n{content.CONSENT_STEP_1_TEXT}",
            reply_markup=InlineKeyboardMarkup(CONSENT_PDN_MENU),
            action="lead_magnet_requires_pdn",
        )
        return

    magnet_type = query.data.replace("magnet_", "")
    if magnet_type == "demo_analysis":
        magnet_type = "demo"
    if magnet_type == "report_sample":
        magnet_type = "sample_report"

    lead = database.db.get_lead_by_user_id(user_data["id"])
    if not lead:
        lead_id = database.db.create_or_update_lead(
            user_data["id"],
            {"name": user.first_name, "lead_magnet_type": magnet_type, "lead_magnet_delivered": False},
        )
        lead = database.db.get_lead_by_id(lead_id)
    else:
        lead_qualifier.lead_qualifier.update_lead_magnet(lead["id"], magnet_type)
        lead_id = lead["id"]

    lead_payload = database.db.get_lead_by_id(lead_id) or {}
    await notify_admin_new_lead(
        context=context,
        lead_id=lead_id,
        lead_data=lead_payload,
        user_data=user_data,
        is_update=bool(lead),
    )

    funnel_state = database.db.get_user_funnel_state(user_data["id"])
    cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_data["id"])
    current_stage = funnel_state.get("conversation_stage") or "discover"
    target_stage = "handoff" if magnet_type == "consultation" else "propose"
    next_stage = funnel.advance_stage(current_stage, target_stage)

    database.db.update_user_funnel_state(
        user_data["id"],
        conversation_stage=next_stage,
        cta_variant=cta_variant,
        cta_shown=True,
    )
    database.db.update_lead_funnel_state(
        user_data["id"],
        conversation_stage=next_stage,
        cta_variant=cta_variant,
        cta_shown=True,
    )

    try:
        if not funnel_state.get("cta_shown"):
            database.db.track_event(
                user_data["id"],
                "cta_shown",
                payload={"variant": cta_variant, "stage": current_stage, "source": "implicit_by_click"},
                lead_id=lead_id,
            )

        database.db.track_event(
            user_data["id"],
            "cta_clicked",
            payload={
                "variant": cta_variant,
                "magnet_type": magnet_type,
                "from_stage": current_stage,
                "to_stage": next_stage,
            },
            lead_id=lead_id,
        )
        if next_stage != current_stage:
            database.db.track_event(
                user_data["id"],
                "stage_changed",
                payload={"from": current_stage, "to": next_stage, "reason": "cta_clicked"},
                lead_id=lead_id,
            )
    except (sqlite3.Error, KeyError) as analytics_error:
        logger.warning("Failed to track CTA click analytics: %s", analytics_error)

    selection_text = content.LEAD_MAGNET_SELECTION_MESSAGES.get(magnet_type, "Спасибо!")
    consultation_markup = None
    if magnet_type == "consultation" and (not query.message or not getattr(query.message, "business_connection_id", None)):
        consultation_markup = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📲 Отправить телефон", request_contact=True)],
                [KeyboardButton("⬅️ Отмена")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
    if query.message and getattr(query.message, "business_connection_id", None):
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=selection_text,
            business_connection_id=query.message.business_connection_id,
        )
    else:
        await utils.safe_reply_text(
            query.message,
            selection_text,
            action="lead_magnet_selection",
            reply_markup=consultation_markup,
        )


async def handle_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для согласий на ПД и трансграничную передачу."""
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="consent_answer")
    except TelegramError as answer_error:
        logger.warning("Failed to answer consent callback: %s", answer_error)

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        user_id = database.db.create_or_update_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        user_data = database.db.get_user_by_id(user_id)

    if not user_data:
        await utils.safe_reply_text(
            query.message,
            "Ошибка инициализации профиля. Нажмите /start еще раз.",
            action="consent_profile_error",
        )
        return

    action = query.data or ""

    if action == "consent_doc_privacy":
        await utils.safe_reply_html(query.message, content.privacy_policy_text(), action="consent_doc_privacy")
        return

    if action == "consent_doc_transborder":
        await utils.safe_reply_html(query.message, content.transborder_policy_text(), action="consent_doc_transborder")
        return

    if action == "consent_pdn_no":
        await utils.safe_edit_html(query.message, content.CONSENT_DENIED_TEXT, action="consent_pdn_no")
        return

    if action == "consent_pdn_yes":
        database.db.grant_user_consent(user_data["id"])
        await utils.safe_edit_html(
            query.message,
            "<b>✅ Согласие на обработку ПД сохранено.</b>\n\n"
            "Теперь можно оставить заявку, передать контакт и получать материалы.\n"
            "Для ИИ-разбора кейса понадобится отдельное согласие на трансграничную передачу.",
            action="consent_pdn_yes",
        )

        await utils.safe_reply_html(
            query.message,
            content.build_workspace_text(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
                emphasize_profile_choice=True,
            ),
            reply_markup=_workspace_markup_for(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
            ),
            action="consent_workspace_after_yes",
        )
        await process_pending_start_payload(
            message=query.message,
            context=context,
            user_data=user_data,
            user=user,
        )
        return

    if action in ("consent_transborder_yes", "consent_transborder_no"):
        transborder_enabled = action == "consent_transborder_yes"
        database.db.set_user_transborder_consent(user_data["id"], transborder_enabled)
        if transborder_enabled:
            await utils.safe_edit_html(
                query.message,
                "<b>✅ Согласия сохранены.</b> ИИ-режим включен.\n\n"
                "Можно описать задачу в свободной форме, и я помогу сформировать следующий шаг.",
                action="consent_transborder_yes",
            )
        else:
            await utils.safe_edit_html(
                query.message,
                "<b>✅ Согласие на обработку ПД сохранено.</b>\n"
                "ИИ-режим отключен до вашего разрешения на трансграничную передачу.\n\n"
                "Можно пользоваться меню и оставить заявку на консультацию.",
                action="consent_transborder_no",
            )

        await utils.safe_reply_html(
            query.message,
            content.build_workspace_text(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
                emphasize_profile_choice=True,
            ),
            reply_markup=_workspace_markup_for(
                lead=database.db.get_local_lead_by_user_id(user_data["id"]),
                selected_profile=database.db.get_user_offer_profile(user_data["id"]),
            ),
            action="consent_workspace_after_transborder",
        )
        await process_pending_start_payload(
            message=query.message,
            context=context,
            user_data=user_data,
            user=user,
        )
        return

    await utils.safe_reply_text(query.message, "Неизвестное действие согласия. Попробуйте /start.", action="consent_unknown")


async def handle_documents_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для раздела документов/прав пользователя."""
    _ = context
    query = update.callback_query
    try:
        await utils.safe_answer_callback(query, action="documents_answer")
    except TelegramError as answer_error:
        logger.warning("Failed to answer documents callback: %s", answer_error)

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    action = query.data or ""

    if action == "doc_menu":
        await utils.safe_edit_html(
            query.message,
            _documents_panel_text(),
            reply_markup=_documents_panel_markup(),
            action="doc_menu",
        )
        return

    if action == "doc_privacy":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📄 Политика ПД", content.privacy_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_privacy",
        )
        return
    if action == "doc_transborder":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("🌍 Трансграничная передача", content.transborder_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_transborder",
        )
        return
    if action == "doc_user_agreement":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📜 Пользовательское соглашение", content.user_agreement_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_user_agreement",
        )
        return
    if action == "doc_ai_policy":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("🤖 Политика ИИ", content.ai_policy_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_ai_policy",
        )
        return
    if action == "doc_marketing_consent":
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📣 Согласие на рассылки", content.marketing_consent_text())),
            reply_markup=_documents_panel_markup(),
            action="doc_marketing_consent",
        )
        if user_data:
            database.db.set_user_marketing_consent(user_data["id"], True)
        return

    if not user_data:
        await utils.safe_edit_html(
            query.message,
            _documents_panel_text("⚠️ Ошибка", "Сначала выполните /start."),
            reply_markup=_documents_panel_markup(),
            action="doc_no_user",
        )
        return

    if action == "doc_consent_status":
        consent_state = database.db.get_user_consent_state(user_data["id"])
        is_admin = user.id == config.ADMIN_TELEGRAM_ID
        status_text = content.consent_status_text(consent_state) if is_admin else content.consent_user_status_text(consent_state)
        await utils.safe_edit_html(
            query.message,
            _clip_for_edit(_documents_panel_text("📑 Статус согласий", status_text)),
            reply_markup=_documents_panel_markup(),
            action="doc_consent_status",
        )
        return
    if action == "doc_export_data":
        payload = await admin_interface.admin_interface.export_user_data_async(user.id)
        await utils.safe_edit_text(
            query.message,
            _clip_for_edit(_documents_panel_text("📊 Экспорт данных", content.export_data_text(payload))),
            reply_markup=_documents_panel_markup(),
            action="doc_export_data",
        )
        return

    await utils.safe_edit_html(
        query.message,
        _documents_panel_text("⚠️ Неизвестное действие", "Используйте /documents."),
        reply_markup=_documents_panel_markup(),
        action="doc_unknown",
    )
