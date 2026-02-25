"""
Handlers: business
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


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка подключения/отключения Business аккаунта"""
    try:
        if update.business_connection:
            connection = update.business_connection
            if connection.is_enabled:
                logger.info(f"✅ Business connection enabled: {connection.id} for user {connection.user_chat_id}")
                await context.bot.send_message(
                    chat_id=connection.user_chat_id,
                    text="✅ Бот успешно подключен к вашему Telegram Business аккаунту!\n\n"
                         "Теперь я буду автоматически отвечать на сообщения ваших клиентов."
                )
            else:
                logger.info(f"❌ Business connection disabled: {connection.id}")
    except Exception as e:
        logger.error(f"Error in handle_business_connection: {e}", exc_info=True)



async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений через Business аккаунт"""
    try:
        if not update.business_message:
            return
            
        message = update.business_message
        user_id = message.from_user.id
        text = message.text or ""
        
        logger.info(f"📨 Business message from {user_id}: {text}")
        
        # Получаем пользователя
        user = database.db.create_or_update_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Обработка команды /start для бизнес-чата
        if text == "/start":
            welcome_message = (
                f"Здравствуйте, {message.from_user.first_name}! 👋\n\n"
                "Я AI-ассистент команды юристов-практиков с опытом более 20 лет, "
                "которые САМИ РАЗРАБАТЫВАЮТ программное обеспечение для автоматизации юридической работы.\n\n"
                "Могу помочь вам:\n"
                "• Рассказать о наших услугах по разработке AI-решений\n"
                "• Подобрать решение под ваши задачи\n"
                "• Ответить на вопросы о технологиях\n\n"
                "Чем могу помочь вам сегодня?"
            )
            
            # Для бизнес-чатов используем InlineKeyboard (ReplyKeyboard не поддерживается)
            keyboard = [
                [InlineKeyboardButton("📋 Услуги", callback_data="menu_services")],
                [InlineKeyboardButton("💰 Цены", callback_data="menu_prices")],
                [InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation")],
                [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=welcome_message,
                reply_markup=reply_markup,
                business_connection_id=message.business_connection_id
            )
            return
        
        # Обработка кнопок меню для бизнес-чата (удалено - используем callback)
        # Inline кнопки обрабатываются через callback_query
        
        # Обработка команды /menu для бизнес-чата
        if text.strip().lower() in ['/menu', 'menu', '/меню', 'меню']:
            keyboard = [
                [InlineKeyboardButton("📋 Услуги", callback_data="menu_services")],
                [InlineKeyboardButton("💰 Цены", callback_data="menu_prices")],
                [InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation")],
                [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="📋 МЕНЮ УСЛУГ:\n\nВыберите интересующую тему:",
                reply_markup=reply_markup,
                business_connection_id=message.business_connection_id
            )
            logger.info(f"[Business] Menu shown to user {user_id}")
            return
        
        # Обработка команды сброса
        if text == "🔄 Начать заново":
            user_data = database.db.get_user_by_telegram_id(user_id)
            if user_data:
                database.db.clear_conversation_history(user_data['id'])
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="История диалога очищена. Начнем сначала!\n\nЧем могу помочь вам сегодня?",
                business_connection_id=message.business_connection_id
            )
            return
        
        # Сохраняем сообщение пользователя
        database.db.add_message(user, 'user', text)
        
        # Получаем историю диалога
        conversation_history = database.db.get_conversation_history(user)
        
        # ПРОВЕРКА: если это первое сообщение клиента - показываем кнопки меню
        # (в бизнес-чатах клиент не видит /start, начинает сразу с вопроса)
        is_first_message = len(conversation_history) <= 1  # Только его первое сообщение
        show_menu_buttons = is_first_message

        # Получаем ответ от AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        # Показываем typing в начале
        try:
            await context.bot.send_chat_action(
                chat_id=message.chat.id,
                action="typing",
                business_connection_id=message.business_connection_id
            )
            logger.info(f"[Business] Typing indicator sent for user {user_id}")
        except Exception as e:
            logger.warning(f"[Business] Failed to send typing indicator: {e}")

        # Собираем ответ от OpenAI и постепенно обновляем сообщение
        start_generation = time.time()
        async for chunk in ai_brain.ai_brain.generate_response_stream(conversation_history):
            full_response += chunk
            chunk_buffer += chunk

            # Обновляем сообщение когда накопилось достаточно новых символов
            # ИЛИ прошло достаточно времени (для избежания rate limit)
            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 3.5) or  # Каждые 150 символов И минимум 3.5 сек (было 2)
                (len(chunk_buffer) > 300 and current_time - last_update_time >= 5.0)  # Или каждые 5 секунд при 300+ символах (было 3)
            )

            if should_update:
                if sent_message is None:
                    # Первая отправка - когда накопилось хотя бы 100 символов (снижаем частоту обновлений)
                    if len(full_response.strip()) >= 100:
                        try:
                            sent_message = await context.bot.send_message(
                                chat_id=message.chat.id,
                                text=full_response,
                                business_connection_id=message.business_connection_id
                            )
                            last_update_length = len(full_response)
                            last_update_time = current_time
                            chunk_buffer = ""
                            logger.debug(f"[Business] Initial message sent: {len(full_response)} chars")
                        except Exception as e:
                            logger.warning(f"[Business] Failed to send initial message: {e}")
                else:
                    # Обновляем существующее сообщение
                    try:
                        await context.bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=full_response,
                            business_connection_id=message.business_connection_id
                        )
                        last_update_length = len(full_response)
                        last_update_time = current_time
                        chunk_buffer = ""
                        logger.debug(f"[Business] Message updated: {len(full_response)} chars")
                    except Exception as e:
                        # Telegram rate limit - просто пропускаем это обновление
                        logger.debug(f"[Business] Skipped update (rate limit): {e}")
                        pass

        # Финальное обновление с полным текстом
        generation_time = time.time() - start_generation
        logger.info(f"[Business] Response generated in {generation_time:.2f}s ({len(full_response)} chars)")

        # Проверяем нужно ли разбить на части (лимит Telegram 4096 символов)
        if len(full_response) > 4096:
            logger.warning(f"[Business] Response too long ({len(full_response)} chars), splitting into parts")
            # Разбиваем на части
            parts = utils.split_long_message(full_response, max_length=4000)
            
            # Удаляем первое сообщение если оно было отправлено
            if sent_message:
                try:
                    await context.bot.delete_message(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id
                    )
                except Exception:
                    pass
            
            # Отправляем по частям
            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=part_msg,
                    business_connection_id=message.business_connection_id
                )
                # Небольшая задержка между частями
                if i < len(parts) - 1:
                    await context.bot.send_chat_action(
                        chat_id=message.chat.id,
                        action="typing",
                        business_connection_id=message.business_connection_id
                    )
                    await asyncio.sleep(0.5)
        else:
            # Обычное обновление для коротких сообщений
            if sent_message:
                try:
                    await context.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        text=full_response,
                        business_connection_id=message.business_connection_id
                    )
                    logger.debug("[Business] Final message update sent")
                except Exception:
                    pass
            else:
                # Если текст был слишком коротким для постепенного вывода
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=full_response,
                    business_connection_id=message.business_connection_id
                )

        # Сохраняем ответ
        database.db.add_message(user, 'assistant', full_response)
        
        # ОТПРАВЛЯЕМ КНОПКИ МЕНЮ ОТДЕЛЬНЫМ СООБЩЕНИЕМ при первом сообщении
        if show_menu_buttons:
            keyboard = [
                [InlineKeyboardButton("📋 Услуги", callback_data="menu_services")],
                [InlineKeyboardButton("💰 Цены", callback_data="menu_prices")],
                [InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation")],
                [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        "💡 **Полезная информация:**\n\n"
                        "Для быстрого доступа к информации используйте кнопки ниже 👇\n\n"
                        "Также вы всегда можете написать `/menu` чтобы вызвать это меню снова."
                    ),
                    reply_markup=reply_markup,
                    business_connection_id=message.business_connection_id,
                    parse_mode='Markdown'
                )
                logger.info(f"[Business] Menu buttons sent to user {user_id}")
            except Exception as e:
                logger.warning(f"[Business] Failed to send menu buttons: {e}")
        
        # Извлекаем и сохраняем лид данные (аналогично handle_message)
        if user_id != config.ADMIN_TELEGRAM_ID:
            lead_data = ai_brain.ai_brain.extract_lead_data(conversation_history)
            
            if lead_data:
                # Обрабатываем данные лида
                lead_id = lead_qualifier.lead_qualifier.process_lead_data(user, lead_data)
                
                if lead_id:
                    # Уведомляем админа о новом лиде
                    # ИСПРАВЛЕНИЕ: AI возвращает 'lead_temperature', приводим к 'temperature'
                    temperature = lead_data.get('temperature') or lead_data.get('lead_temperature', 'cold')
                    
                    should_notify = (
                        temperature in ['hot', 'warm'] or
                        (lead_data.get('name') and
                         (lead_data.get('email') or lead_data.get('phone')) and
                         lead_data.get('pain_point'))
                    )
                    
                    logger.info(f"[Business] Lead {lead_id}: temperature={temperature}, should_notify={should_notify}")
                    
                    if should_notify:
                        await notify_admin_new_lead(context, lead_id, lead_data, {"id": user, "telegram_id": user_id})
                
                # Проверяем нужно ли предложить lead magnet
                existing_lead = database.db.get_lead_by_user_id(user)
                lead_magnet_already_offered = existing_lead and existing_lead.get('lead_magnet_type') is not None
                
                if not lead_magnet_already_offered and ai_brain.ai_brain.should_offer_lead_magnet(lead_data):
                    # Формируем сообщение с lead magnet кнопками
                    lead_magnet_msg = "🎁 Чтобы помочь вам лучше, я подготовил специальные материалы:\n\n"
                    reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
                    await context.bot.send_message(
                        chat_id=message.chat.id,
                        text=lead_magnet_msg,
                        reply_markup=reply_markup,
                        business_connection_id=message.business_connection_id
                    )

        logger.info(f"✅ [Business] Response sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error in handle_business_message: {e}", exc_info=True)
        try:
            if update.business_message:
                await context.bot.send_message(
                    chat_id=update.business_message.chat.id,
                    text="❌ Произошла ошибка. Попробуйте позже.",
                    business_connection_id=update.business_message.business_connection_id
                )
        except:
            pass


