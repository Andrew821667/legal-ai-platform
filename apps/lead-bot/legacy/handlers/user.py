"""
Handlers: user
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

# Import admin panel function (avoid at module level due to potential circular import)
def get_show_admin_panel():
    from handlers.admin import show_admin_panel
    return show_admin_panel


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        logger.info(f"User {user.id} started bot")

        # Создаем или обновляем пользователя в БД
        user_id = database.db.create_or_update_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Приветственное сообщение
        welcome_message = (
            f"Здравствуйте, {user.first_name}! 👋\n\n"
            "Я AI-ассистент команды юристов-практиков с опытом более 20 лет, "
            "которые САМИ РАЗРАБАТЫВАЮТ программное обеспечение для автоматизации юридической работы.\n\n"
            "Могу помочь вам:\n"
            "• Рассказать о наших услугах по разработке AI-решений\n"
            "• Подобрать решение под ваши задачи\n"
            "• Ответить на вопросы о технологиях\n\n"
            "Чем могу помочь вам сегодня?"
        )

        # Админу показываем расширенное меню с кнопкой админ-панели
        if user.id == config.ADMIN_TELEGRAM_ID:
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
            welcome_message += "\n\n⚙️ Доступна админ-панель!"
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте еще раз.")



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📖 ПОМОЩЬ\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/reset - Начать диалог заново\n\n"
        "Вы можете:\n"
        "• Задавать вопросы о услугах\n"
        "• Описать вашу ситуацию\n"
        "• Запросить консультацию\n\n"
        "Я работаю 24/7 и всегда рад помочь!"
    )

    await update.message.reply_text(help_text)



async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if user_data:
            # Очищаем историю диалога
            database.db.clear_conversation_history(user_data['id'])
            logger.info(f"Conversation reset for user {user.id}")

            await update.message.reply_text(
                "История диалога очищена. Начнем сначала!\n\n"
                "Чем могу помочь вам сегодня?"
            )
        else:
            await start_command(update, context)

    except Exception as e:
        logger.error(f"Error in reset_command: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте /start")



async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu - показывает меню услуг"""
    try:
        keyboard = [
            [InlineKeyboardButton("📋 Услуги", callback_data="menu_services")],
            [InlineKeyboardButton("💰 Цены", callback_data="menu_prices")],
            [InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation")],
            [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Используем effective_message вместо message (может быть None)
        message = update.effective_message
        if message:
            await message.reply_text(
                "📋 МЕНЮ УСЛУГ:\n\nВыберите интересующую тему:",
                reply_markup=reply_markup
            )
            logger.info(f"Menu shown to user {update.effective_user.id}")
        
    except Exception as e:
        logger.error(f"Error in menu_command: {e}")
        try:
            if update.effective_message:
                await update.effective_message.reply_text("Произошла ошибка. Попробуйте /start")
        except:
            pass



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        user = update.effective_user
        message_text = update.effective_message.text

        # 🛡️ ЗАЩИТА: проверяем что это текстовое сообщение
        if not update.effective_message or not update.effective_message.text:
            logger.warning(f"Skipping non-text message update type: {update.update_id}")
            return

        logger.info(f"Message from user {user.id}: {message_text[:50]}")

        # 🛡️ ПРОВЕРКА БЕЗОПАСНОСТИ
        is_allowed, block_reason = security.security_manager.check_all_security(user.id, message_text)
        if not is_allowed:
            logger.warning(f"Security check failed for user {user.id}: {block_reason}")
            await update.effective_message.reply_text(block_reason)
            return

        # Получаем или создаем пользователя
        user_data = database.db.get_user_by_telegram_id(user.id)
        if not user_data:
            user_id = database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            user_data = database.db.get_user_by_telegram_id(user.id)

        # Проверяем есть ли pending lead magnet и email в сообщении
        lead = database.db.get_lead_by_user_id(user_data['id'])
        if lead and lead.get('lead_magnet_type') and not lead.get('lead_magnet_delivered'):
            email = extract_email(message_text)
            if email:
                await send_lead_magnet_email(update, user_data, lead, email)
                return

        # Обработка кнопок меню
        if message_text in ["📋 Услуги", "💰 Цены", "📞 Консультация", "❓ Помощь"]:
            await handle_menu_button(update, context, message_text)
            return
        
        # Обработка команды /menu (на случай если CommandHandler не сработал)
        if message_text.strip().lower() in ['/menu', 'menu', '/меню', 'меню']:
            await menu_command(update, context)
            return

        if message_text == "🔄 Начать заново":
            await reset_command(update, context)
            return

        # Админ-панель (только для админа)
        if message_text == "⚙️ Админ-панель":
            if user.id == config.ADMIN_TELEGRAM_ID:
                show_admin_panel_func = get_show_admin_panel()
                await show_admin_panel_func(update, context)
            else:
                await update.effective_message.reply_text("У вас нет доступа к этой функции")
            return

        # Проверяем триггеры передачи админу
        if ai_brain.ai_brain.check_handoff_trigger(message_text):
            await handle_handoff_request(update, context)
            return
        
        # ПРОВЕРКА: если клиент повторяет одно и то же сообщение 3+ раза
        # И прошло более 30 минут с начала диалога - завершаем разговор
        conversation_history = database.db.get_conversation_history(user_data['id'])
        
        if len(conversation_history) > 0:
            # Получаем последние сообщения пользователя
            user_messages = [msg for msg in conversation_history if msg['role'] == 'user']
            
            # Проверяем повторы последних 3-х сообщений
            if len(user_messages) >= 3:
                last_three = [msg.get('content', msg.get('message', '')).strip().lower() for msg in user_messages[-3:]]
                
                # Если все 3 последних сообщения одинаковые
                if len(set(last_three)) == 1:
                    # Проверяем прошло ли 30 минут с начала диалога
                    import datetime
                    first_message_time = datetime.datetime.fromisoformat(conversation_history[0]['timestamp'])
                    current_time = datetime.datetime.now()
                    time_elapsed = (current_time - first_message_time).total_seconds() / 60  # в минутах
                    
                    if time_elapsed > 30:
                        await update.effective_message.reply_text(
                            "Похоже, у нас возникли трудности с пониманием.\n\n"
                            "Предлагаю связаться напрямую с нашей командой:\n"
                            "📧 a.popov.gv@gmail.com\n"
                            "📱 @AndrewPopov821667\n"
                            "📞 +7 (909) 233-09-09"
                        )
                        return

        # Сохраняем сообщение пользователя
        database.db.add_message(user_data['id'], 'user', message_text)

        # Получаем историю диалога
        conversation_history = database.db.get_conversation_history(user_data['id'])

        # Генерируем ответ через AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0
        original_message = update.effective_message

        # Показываем typing индикатор в начале
        try:
            await original_message.chat.send_action(action="typing")
            logger.info(f"Typing indicator sent for user {user_data['telegram_id']}")
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

        # Собираем ответ от OpenAI и постепенно обновляем сообщение
        start_generation = time.time()
        async for chunk in ai_brain.ai_brain.generate_response_stream(conversation_history):
            full_response += chunk
            chunk_buffer += chunk

            # Обновляем сообщение когда накопилось достаточно новых символов
            # ИЛИ прошло достаточно времени (для избежания rate limit)
            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 2.0) or  # Каждые 150 символов И минимум 2 сек
                (len(chunk_buffer) > 300 and current_time - last_update_time >= 3.0)  # Или каждые 3 секунды при 300+ символах
            )

            if should_update:
                if sent_message is None:
                    # Первая отправка - когда накопилось хотя бы 100 символов (снижаем частоту обновлений)
                    if len(full_response.strip()) >= 100:
                        try:
                            sent_message = await original_message.reply_text(full_response)
                            last_update_length = len(full_response)
                            last_update_time = current_time
                            chunk_buffer = ""
                            logger.debug(f"Initial message sent: {len(full_response)} chars")
                        except Exception as e:
                            logger.warning(f"Failed to send initial message: {e}")
                else:
                    # Обновляем существующее сообщение
                    try:
                        await sent_message.edit_text(full_response)
                        last_update_length = len(full_response)
                        last_update_time = current_time
                        chunk_buffer = ""
                        logger.debug(f"Message updated: {len(full_response)} chars")
                    except Exception as e:
                        # Telegram rate limit - просто пропускаем это обновление
                        logger.debug(f"Skipped update (rate limit): {e}")
                        pass

        # Финальное обновление с полным текстом
        generation_time = time.time() - start_generation
        logger.info(f"Response generated in {generation_time:.2f}s ({len(full_response)} chars)")

        # Проверяем нужно ли разбить на части (лимит Telegram 4096 символов)
        if len(full_response) > 4096:
            logger.warning(f"Response too long ({len(full_response)} chars), splitting into parts")
            # Разбиваем на части
            parts = utils.split_long_message(full_response, max_length=4000)  # Оставляем запас
            
            # Удаляем первое сообщение если оно было отправлено
            if sent_message:
                try:
                    await sent_message.delete()
                except Exception:
                    pass
            
            # Отправляем по частям
            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                await original_message.reply_text(part_msg)
                # Небольшая задержка между частями
                if i < len(parts) - 1:
                    await original_message.chat.send_action(action="typing")
                    await asyncio.sleep(0.5)
        else:
            # Обычное обновление для коротких сообщений
            if sent_message:
                try:
                    await sent_message.edit_text(full_response)
                    logger.debug("Final message update sent")
                except Exception:
                    pass
            else:
                # Если текст был слишком коротким для постепенного вывода
                await original_message.reply_text(full_response)

        # Сохраняем ответ ассистента
        database.db.add_message(user_data['id'], 'assistant', full_response)

        # 🛡️ УЧЕТ ИСПОЛЬЗОВАННЫХ ТОКЕНОВ
        # Оцениваем токены: user message + assistant response + system prompt
        user_tokens = security.security_manager.estimate_tokens(message_text)
        assistant_tokens = security.security_manager.estimate_tokens(full_response)
        system_tokens = security.security_manager.estimate_tokens(prompts.SYSTEM_PROMPT)
        total_tokens = user_tokens + assistant_tokens + system_tokens
        security.security_manager.add_tokens_used(total_tokens)
        logger.debug(f"Tokens used: user={user_tokens}, assistant={assistant_tokens}, system={system_tokens}, total={total_tokens}")

        # Извлекаем данные лида из диалога (ТОЛЬКО если это НЕ админ!)
        # Админские сообщения НЕ должны создавать лиды
        if user.id != config.ADMIN_TELEGRAM_ID:
            lead_data = ai_brain.ai_brain.extract_lead_data(conversation_history)

            if lead_data:
                # Обрабатываем данные лида
                lead_id = lead_qualifier.lead_qualifier.process_lead_data(user_data['id'], lead_data)

                if lead_id:
                    # ОБНОВЛЯЕМ ВРЕМЯ ПОСЛЕДНЕГО СООБЩЕНИЯ
                    database.db.update_lead_last_message_time(user_data['id'])
                    
                    # НЕ ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ СРАЗУ!
                    # Уведомление отправится автоматически через 5 минут без новых сообщений
                    # (см. check_pending_leads_job)
                    
                    logger.info(f"Lead {lead_id} updated, waiting for conversation to finish before notifying admin")

    except Exception as e:
        # Пропускаем Peer_id_invalid - нормально для бизнес-сообщений
        if "Peer_id_invalid" not in str(e):
            logger.error(f"Error in handle_message: {e}")
            # НЕ пытаемся отправлять ошибки - может быть None или уже отправлено



async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    """Обработчик кнопок меню"""
    responses = {
        "📋 Услуги": (
            "УСЛУГИ ПО АВТОМАТИЗАЦИИ ЮРРАБОТЫ:\n\n"
            "1️⃣ Договорная работа (от 150.000₽)\n"
            "   • Анализ договоров через AI за 5-10 минут\n"
            "   • Генерация договоров\n"
            "   • Экономия 60-80% времени\n\n"
            "2️⃣ Судебная работа (от 200.000₽)\n"
            "   • Анализ судебной практики\n"
            "   • Генерация процессуальных документов\n\n"
            "3️⃣ Корпоративное право и M&A (от 300.000₽)\n"
            "   • Автоматизация Due Diligence\n\n"
            "4️⃣ Земельное право (от 250.000₽)\n\n"
            "5️⃣ Комплаенс (от 200.000₽)\n\n"
            "6️⃣ Аналитика и отчетность (от 150.000₽)\n\n"
            "7️⃣ Кастомные решения (от 300.000₽)\n\n"
            "8️⃣ Юридический аутсорсинг + AI (от 100.000₽/мес)\n\n"
            "Какое направление вас интересует?"
        ),
        "💰 Цены": (
            "СТОИМОСТЬ УСЛУГ:\n\n"
            "Цены зависят от сложности задачи и объема работ.\n\n"
            "Примерные диапазоны:\n"
            "• Договорная работа: от 150.000₽\n"
            "• Судебная работа: от 200.000₽\n"
            "• M&A и корпоративное: от 300.000₽\n"
            "• Кастомные решения: от 300.000₽\n"
            "• Аутсорсинг: от 100.000₽/мес\n\n"
            "ROI внедрения: обычно 5-6 месяцев\n"
            "Экономия для компании с 5 юристами: 2-3 млн руб/год\n\n"
            "Расскажите о вашей ситуации, и я подберу оптимальное решение!"
        ),
        "📞 Консультация": (
            "БЕСПЛАТНАЯ КОНСУЛЬТАЦИЯ:\n\n"
            "Наша команда может провести бесплатную консультацию (30 минут), на которой:\n"
            "• Разберет вашу ситуацию\n"
            "• Предложит варианты решений\n"
            "• Оценит сроки и стоимость\n\n"
            "Для записи на консультацию укажите ваш email или телефон."
        ),
        "❓ Помощь": (
            "КАК Я МОГУ ПОМОЧЬ:\n\n"
            "1. Отвечаю на вопросы о услугах\n"
            "2. Подбираю решения под ваши задачи\n"
            "3. Объясняю как работают технологии\n"
            "4. Записываю на консультацию с нашей командой\n\n"
            "Просто опишите вашу ситуацию или задайте вопрос!"
        )
    }

    response = responses.get(button_text, "Выберите пункт меню")
    await update.message.reply_text(response)



async def offer_lead_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предложение lead magnet"""
    message = (
        "🎁 ВЫБЕРИТЕ ПОДАРОК:\n\n"
        "Я могу предложить вам на выбор:\n\n"
        "📞 Бесплатную консультацию (30 мин с нашей командой)\n"
        "📄 Чек-лист \"15 типовых ошибок в договорах\"\n"
        "🎯 Демо-анализ вашего договора\n\n"
        "Что вас интересует?"
    )

    reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
    await update.message.reply_text(message, reply_markup=reply_markup)



async def handle_handoff_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка запроса на передачу админу"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if not user_data:
            await update.message.reply_text("Ошибка. Попробуйте /start")
            return

        # Уведомляем пользователя
        await update.message.reply_text(
            "Понял, сейчас передам ваш запрос нашей команде.\n\n"
            "Мы свяжемся с вами в ближайшее время:\n"
            "📞 +7 (909) 233-09-09\n"
            "📧 a.popov.gv@gmail.com\n\n"
            "Если есть еще вопросы - спрашивайте, я на связи!"
        )

        # Создаем или обновляем лид
        lead = database.db.get_lead_by_user_id(user_data['id'])
        if not lead:
            lead_id = database.db.create_or_update_lead(user_data['id'], {
                'name': user.first_name
            })
        else:
            lead_id = lead['id']

        # Уведомляем админа
        admin_interface.admin_interface.send_admin_notification(
            context.bot,
            lead_id,
            'handoff_request',
            f"Последнее сообщение: {update.message.text[:100]}"
        )

        logger.info(f"Handoff request from user {user.id}")

    except Exception as e:
        logger.error(f"Error in handle_handoff_request: {e}")



