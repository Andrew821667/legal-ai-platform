"""
Handlers: helpers
"""
from __future__ import annotations

import logging
import smtplib
import sqlite3
import time
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes
import database
import ai_brain
import lead_qualifier
import admin_interface
from config import Config
config = Config()
import utils
import email_sender
import security
import prompts
import content
from core_api_bridge import core_api_bridge
from handlers.constants import *

logger = logging.getLogger(__name__)


def extract_email(text: str) -> str:
    """Извлекает email из текста"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


async def send_message_gradually(update: Update, text: str):
    """
    Отправляет сообщение постепенно, создавая эффект печатания как в ChatGPT

    Args:
        update: Telegram update
        text: Текст для отправки
    """
    import asyncio
    import re

    # Показываем индикатор печатания
    await update.message.chat.send_action(action="typing")

    # Разбиваем текст на предложения (по точкам, вопр/воскл знакам, переносам строк)
    sentences = re.split(r'([.!?]\s+|\n)', text)

    full_message = ""
    sent_message = None
    last_update_time = 0

    for i, part in enumerate(sentences):
        if not part.strip():
            continue

        # Добавляем часть к сообщению
        full_message += part

        # Показываем typing перед добавлением каждого предложения
        await update.message.chat.send_action(action="typing")

        # Задержка для имитации печатания (0.8-1.2 секунды)
        # Длиннее для предложений, короче для переносов строк
        if part.strip() in ['.', '!', '?', '\n']:
            delay = 0.3
        else:
            delay = min(len(part) / 50, 1.5)  # от длины текста, но не больше 1.5 сек

        await asyncio.sleep(delay)

        # Обновляем сообщение каждые несколько частей или когда достаточно текста
        current_time = i
        should_update = (current_time - last_update_time >= 2) or (len(full_message) - len(str(sent_message.text if sent_message else "")) > 30)

        if sent_message is None:
            # Первая отправка - когда накопилось хотя бы немного текста
            if len(full_message.strip()) > 20:
                sent_message = await update.message.reply_text(full_message)
                last_update_time = current_time
        else:
            # Обновляем существующее сообщение
            if should_update or i == len(sentences) - 1:  # Обновляем или в конце
                try:
                    await sent_message.edit_text(full_message)
                    last_update_time = current_time
                except TelegramError:
                    # Если ошибка редактирования - пропускаем
                    pass

    # Финальное обновление - убеждаемся что весь текст отправлен
    if sent_message:
        try:
            await sent_message.edit_text(text)
        except TelegramError:
            pass
    else:
        # Если вообще не отправили (очень короткий текст)
        await update.message.reply_text(text)



async def send_lead_magnet_email(update: Update, user_data: dict, lead: dict, email: str):
    """Отправляет email с lead magnet"""
    try:
        magnet_type = lead.get('lead_magnet_type')
        if magnet_type == "demo_analysis":
            magnet_type = "demo"
            database.db.create_or_update_lead(user_data["id"], {"lead_magnet_type": "demo"})
        user_name = lead.get('name') or user_data.get('first_name')

        # Показываем индикатор печатания
        await update.message.chat.send_action(action="typing")

        # Отправляем email в зависимости от типа
        success = False
        if magnet_type == 'consultation':
            success = email_sender.email_sender.send_consultation_confirmation(email, user_name)
        elif magnet_type == 'checklist':
            success = email_sender.email_sender.send_checklist(email, user_name)
        elif magnet_type == 'demo':
            success = email_sender.email_sender.send_demo_request_confirmation(email, user_name)

        if success:
            # Обновляем email в lead если его там нет
            if not lead.get('email'):
                database.db.create_or_update_lead(user_data['id'], {'email': email})

            # Отмечаем lead magnet как доставленный
            lead_qualifier.lead_qualifier.mark_lead_magnet_delivered(lead['id'])

            # Подтверждение пользователю
            base_message = content.LEAD_MAGNET_SENT_MESSAGES.get(magnet_type, "✅ Спасибо! Письмо отправлено.")
            await update.message.reply_text(f"{base_message}\n\nКонтакт для отправки: {email}")
            logger.info("Lead magnet %s sent to %s", magnet_type, utils.mask_email(email))
        else:
            # Ошибка отправки
            await update.message.reply_text(
                "Произошла ошибка при отправке email.\n\n"
                f"{content.DIRECT_CONTACTS_TEXT}"
            )
            logger.error("Failed to send lead magnet %s to %s", magnet_type, utils.mask_email(email))

    except (smtplib.SMTPException, sqlite3.Error, TelegramError, KeyError, OSError) as e:
        logger.error(f"Error in send_lead_magnet_email: {e}")
        await update.message.reply_text(
            "Произошла ошибка.\n\n"
            f"{content.DIRECT_CONTACTS_TEXT}"
        )



async def notify_admin_new_lead(context, lead_id: int, lead_data: dict, user_data: dict, is_update: bool = False):
    """
    Отправка уведомления админу о лиде
    is_update: True если это обновление существующего лида (клиент вернулся с новой инфой)
    """
    try:
        # Получаем информацию о лиде
        legacy_lead = database.db.get_lead_by_id(lead_id)
        if not legacy_lead:
            return

        # Формируем сообщение для админа
        # ИСПРАВЛЕНИЕ: проверяем оба поля - 'temperature' и 'lead_temperature'
        temperature = (
            legacy_lead.get('temperature')
            or lead_data.get('temperature')
            or lead_data.get('lead_temperature', 'cold')
        )

        user_row = database.db.get_user_by_id(user_data.get("id")) if user_data.get("id") else None
        bridge_user_data = {
            "telegram_id": user_data.get("telegram_id") or (user_row or {}).get("telegram_id"),
            "username": user_data.get("username") or (user_row or {}).get("username"),
            "first_name": user_data.get("first_name") or (user_row or {}).get("first_name"),
        }
        if core_api_bridge.enabled:
            core_lead_id = core_api_bridge.sync_lead(legacy_lead, bridge_user_data)
            if core_lead_id and legacy_lead.get("core_lead_id") != core_lead_id:
                database.db.set_core_lead_id(lead_id, core_lead_id)
                legacy_lead["core_lead_id"] = core_lead_id
            if core_lead_id:
                core_api_bridge.track_event(
                    event_type="legacy_lead_notified",
                    payload={
                        "legacy_lead_id": lead_id,
                        "is_update": is_update,
                        "temperature": temperature,
                        "service_category": legacy_lead.get("service_category"),
                        "specific_need": legacy_lead.get("specific_need"),
                    },
                    idempotency_key=f"legacy-lead-notified-{lead_id}-{int(is_update)}",
                    core_lead_id=core_lead_id,
                )
        core_snapshot = admin_interface.admin_interface.get_lead_snapshot_by_legacy_id(lead_id) or {}
        lead = {**legacy_lead, **core_snapshot}
        logger.info(
            "Lead %s notification: temperature=%s (from lead_data: %s)",
            lead_id,
            temperature,
            lead_data.get('temperature') or lead_data.get('lead_temperature'),
        )
        
        temperature_emoji = {
            'hot': '🔥',
            'warm': '♨️',
            'cold': '❄️'
        }.get(temperature, '❓')

        # Получаем telegram username
        username = user_data.get('username')
        username_str = f"@{username}" if username else "нет"
        telegram_id = user_data.get('telegram_id') or user_data.get('id')

        # ЗАГОЛОВОК: НОВЫЙ ИЛИ ОБНОВЛЕНИЕ
        header = f"{temperature_emoji} 🔄 ОБНОВЛЕНИЕ ЛИДА!\n\n" if is_update else f"{temperature_emoji} НОВЫЙ ЛИД!\n\n"
        
        notification_message = (
            header +
            f"👤 Имя: {lead.get('name') or 'Не указано'}\n"
            f"📱 Telegram: {username_str} (ID: {telegram_id})\n"
            f"🏢 Компания: {lead.get('company') or 'Не указана'}\n"
            f"📧 Email: {lead.get('email') or 'Не указан'}\n"
            f"📞 Телефон: {lead.get('phone') or 'Не указан'}\n\n"
        )
        
        # Добавляем СПЕЦИАЛИЗАЦИЮ (новое!)
        if lead.get('service_category') or lead.get('specific_need') or lead.get('industry'):
            notification_message += "🎯 Специализация:\n"
            
            if lead.get('service_category'):
                notification_message += f"• Направление: {lead.get('service_category')}\n"
            
            if lead.get('specific_need'):
                notification_message += f"• Потребность: {lead.get('specific_need')}\n"
            
            if lead.get('industry'):
                notification_message += f"• Отрасль: {lead.get('industry')}\n"
            
            notification_message += "\n"
        
        # Остальные детали - ТОЛЬКО ЕСЛИ ЕСТЬ ДАННЫЕ
        details = []
        if lead.get('team_size'):
            details.append(f"• Юристов: {lead.get('team_size')}")
        if lead.get('contracts_per_month'):
            details.append(f"• Договоров/мес: {lead.get('contracts_per_month')}")
        if lead.get('budget'):
            details.append(f"• Бюджет: {lead.get('budget')}")
        if lead.get('urgency'):
            urgency_emoji = {'high': '🔥', 'medium': '⏱️', 'low': '🐌'}.get(lead.get('urgency'), '')
            details.append(f"• Срочность: {urgency_emoji} {lead.get('urgency')}")
        
        if details:
            notification_message += "📊 Детали:\n" + "\n".join(details) + "\n\n"
        
        # Боль и температура
        if lead.get('pain_point'):
            notification_message += f"💭 Боль: {lead.get('pain_point')}\n\n"
        
        notification_message += f"🌡️ Температура: {temperature.upper()}"

        # Отправляем в Telegram с retry и fallback в личный чат админа.
        targets = []
        if config.LEADS_CHAT_ID and config.LEADS_CHAT_ID != config.ADMIN_TELEGRAM_ID:
            targets.append(config.LEADS_CHAT_ID)
        targets.append(config.ADMIN_TELEGRAM_ID)

        sent_any = False
        for target_chat_id in targets:
            try:
                await utils.telegram_call_with_retry(
                    lambda target_chat_id=target_chat_id: context.bot.send_message(
                        chat_id=target_chat_id,
                        text=notification_message,
                    ),
                    action=f"lead_notification_{target_chat_id}",
                    max_retries=3,
                    base_delay=1.0,
                )
                sent_any = True
                logger.info(f"Lead notification sent to chat {target_chat_id} for lead {lead_id}")
            except TelegramError as send_error:
                logger.warning(f"Failed to send lead notification to chat {target_chat_id}: {send_error}")

        if sent_any:
            try:
                database.db.create_notification(
                    lead_id,
                    "new_lead_update" if is_update else "new_lead",
                    notification_message,
                )
            except Exception as notification_log_error:
                logger.warning(
                    "Failed to persist admin notification for lead %s: %s",
                    lead_id,
                    notification_log_error,
                )
            # Помечаем что уведомление отправлено
            database.db.mark_lead_notification_sent(lead_id)
        else:
            logger.error(f"Lead notification was not delivered to any target for lead {lead_id}")

        # Отправляем на email (если настроен SMTP)
        if config.SMTP_USER and config.SMTP_PASSWORD:
            try:
                email_subject = f"[Legal AI Bot] Новый лид: {lead.get('name') or user_data.get('first_name')}"
                email_body = notification_message

                email_sender.email_sender.send_email(
                    to_email=config.SMTP_USER,  # Админу на почту
                    subject=email_subject,
                    body=email_body
                )

                logger.info(f"Email notification sent to admin about lead {lead_id}")
            except (smtplib.SMTPException, OSError) as e:
                logger.error(f"Error sending email notification: {e}")

    except (sqlite3.Error, TelegramError, KeyError, AttributeError) as e:
        logger.error(f"Error in notify_admin_new_lead: {e}")
