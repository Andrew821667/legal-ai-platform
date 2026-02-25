"""
Handlers: helpers
"""
import logging
import time
import re
import asyncio
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
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
                except Exception as e:
                    # Если ошибка редактирования - пропускаем
                    pass

    # Финальное обновление - убеждаемся что весь текст отправлен
    if sent_message:
        try:
            await sent_message.edit_text(text)
        except Exception:
            pass
    else:
        # Если вообще не отправили (очень короткий текст)
        await update.message.reply_text(text)



async def send_lead_magnet_email(update: Update, user_data: dict, lead: dict, email: str):
    """Отправляет email с lead magnet"""
    try:
        magnet_type = lead.get('lead_magnet_type')
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
            messages = {
                'consultation': (
                    f"✅ Отлично! Подтверждение консультации отправлено на {email}\n\n"
                    "Наша команда свяжется с вами в ближайшее время для согласования времени.\n\n"
                    "Если есть еще вопросы - спрашивайте, я на связи!"
                ),
                'checklist': (
                    f"✅ Отлично! Чек-лист отправлен на {email}\n\n"
                    "Проверьте почту (иногда письма попадают в спам).\n\n"
                    "Если хотите обсудить автоматизацию - готов ответить на вопросы!"
                ),
                'demo': (
                    f"✅ Отлично! Инструкции отправлены на {email}\n\n"
                    "Теперь вы можете отправить нам ваш договор для демо-анализа:\n"
                    "📱 Telegram: @AndrewPopov821667\n"
                    "📧 Email: a.popov.gv@gmail.com"
                )
            }

            await update.message.reply_text(messages.get(magnet_type, "✅ Спасибо! Письмо отправлено."))
            logger.info(f"Lead magnet {magnet_type} sent to {email}")
        else:
            # Ошибка отправки
            await update.message.reply_text(
                "Произошла ошибка при отправке email. Пожалуйста, свяжитесь с нами напрямую:\n\n"
                "📧 a.popov.gv@gmail.com\n"
                "📱 @AndrewPopov821667\n"
                "📞 +7 (909) 233-09-09"
            )
            logger.error(f"Failed to send lead magnet {magnet_type} to {email}")

    except Exception as e:
        logger.error(f"Error in send_lead_magnet_email: {e}")
        await update.message.reply_text(
            "Произошла ошибка. Пожалуйста, свяжитесь с нами напрямую:\n"
            "📧 a.popov.gv@gmail.com"
        )



async def notify_admin_new_lead(context, lead_id: int, lead_data: dict, user_data: dict, is_update: bool = False):
    """
    Отправка уведомления админу о лиде
    is_update: True если это обновление существующего лида (клиент вернулся с новой инфой)
    """
    try:
        # Получаем информацию о лиде
        lead = database.db.get_lead_by_id(lead_id)
        if not lead:
            return

        # Формируем сообщение для админа
        # ИСПРАВЛЕНИЕ: проверяем оба поля - 'temperature' и 'lead_temperature'
        temperature = lead.get('temperature') or lead_data.get('temperature') or lead_data.get('lead_temperature', 'cold')
        logger.info(f"Lead {lead_id} notification: temperature={temperature} (from lead_data: {lead_data.get('temperature') or lead_data.get('lead_temperature')})")
        
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

        # Отправляем в Telegram
        # Если задан LEADS_CHAT_ID - отправляем в отдельный чат, иначе напрямую админу
        target_chat_id = config.LEADS_CHAT_ID if config.LEADS_CHAT_ID else config.ADMIN_TELEGRAM_ID

        await context.bot.send_message(
            chat_id=target_chat_id,
            text=notification_message
        )

        # Помечаем что уведомление отправлено
        database.db.mark_lead_notification_sent(lead_id)

        logger.info(f"Lead notification sent to chat {target_chat_id} for lead {lead_id}")

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
            except Exception as e:
                logger.error(f"Error sending email notification: {e}")

    except Exception as e:
        logger.error(f"Error in notify_admin_new_lead: {e}")



