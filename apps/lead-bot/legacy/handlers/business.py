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
from config import Config
config = Config()
import utils
import email_sender
import security
import prompts
import content
import funnel
from handlers.constants import *
from handlers.helpers import notify_admin_new_lead, extract_email

logger = logging.getLogger(__name__)
PHONE_RE = re.compile(r"(?:\+7|8|7)[\s\-()]*(?:\d[\s\-()]*){10,11}")


def _schedule_business_typing(context: ContextTypes.DEFAULT_TYPE, message, user_id: int) -> None:
    """Неблокирующий typing-индикатор для бизнес-диалогов."""

    async def _send_typing() -> None:
        try:
            await asyncio.wait_for(
                context.bot.send_chat_action(
                    chat_id=message.chat.id,
                    action="typing",
                    business_connection_id=message.business_connection_id,
                ),
                timeout=1.5,
            )
            logger.info(f"[Business] Typing indicator sent for user {user_id}")
        except Exception as error:
            logger.debug(f"[Business] Typing indicator skipped for user {user_id}: {error}")

    asyncio.create_task(_send_typing())


def _extract_phone_candidate(text: str) -> str | None:
    match = PHONE_RE.search(text or "")
    if not match:
        return None
    return match.group(0)


def _persist_fasttrack_contact(user_db_id: int, first_name: str, text: str) -> None:
    payload = {}
    email = extract_email(text)
    if email:
        payload["email"] = email

    phone = _extract_phone_candidate(text)
    if phone and utils.validate_phone(phone):
        payload["phone"] = utils.format_phone(phone)

    if payload:
        payload.setdefault("name", first_name)
        database.db.create_or_update_lead(user_db_id, payload)


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
        is_admin = user_id == config.ADMIN_TELEGRAM_ID
        allow_lead_processing = (not is_admin) or config.ALLOW_ADMIN_TEST_LEADS
        
        # Обработка команды /start для бизнес-чата
        if text == "/start":
            welcome_message = content.build_welcome_message(message.from_user.first_name)
            
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
                text=content.MENU_HEADER_TEXT,
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
                database.db.reset_user_funnel_state(user_data['id'])
            
            await context.bot.send_message(
                chat_id=message.chat.id,
                text="История диалога очищена. Начнем сначала!\n\nЧем могу помочь вам сегодня?",
                business_connection_id=message.business_connection_id
            )
            return

        # Явный handoff-запрос
        if ai_brain.ai_brain.check_handoff_trigger(text):
            if allow_lead_processing:
                _persist_fasttrack_contact(user, message.from_user.first_name, text)
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.HANDOFF_ACK_TEXT,
                business_connection_id=message.business_connection_id
            )

            lead = database.db.get_lead_by_user_id(user)
            if not lead:
                lead_id = database.db.create_or_update_lead(user, {'name': message.from_user.first_name})
            else:
                lead_id = lead['id']

            funnel_state = database.db.get_user_funnel_state(user)
            previous_stage = funnel_state.get('conversation_stage') or 'discover'
            cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user)

            database.db.update_user_funnel_state(
                user,
                conversation_stage='handoff',
                cta_variant=cta_variant
            )
            database.db.update_lead_funnel_state(
                user,
                conversation_stage='handoff',
                cta_variant=cta_variant
            )

            if previous_stage != 'handoff':
                try:
                    database.db.track_event(
                        user,
                        "stage_changed",
                        payload={"from": previous_stage, "to": "handoff"},
                        lead_id=lead_id
                    )
                except Exception as analytics_error:
                    logger.warning(f"[Business] Failed to track handoff stage change: {analytics_error}")

            lead_payload = database.db.get_lead_by_id(lead_id) or {}
            await notify_admin_new_lead(
                context=context,
                lead_id=lead_id,
                lead_data=lead_payload,
                user_data={
                    "id": user,
                    "telegram_id": user_id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                },
                is_update=bool(lead),
            )

            try:
                database.db.track_event(
                    user,
                    "handoff_done",
                    payload={"source": "business_trigger", "cta_variant": cta_variant},
                    lead_id=lead_id
                )
            except Exception as analytics_error:
                logger.warning(f"[Business] Failed to track handoff_done: {analytics_error}")
            return

        if allow_lead_processing and funnel.should_fast_track_handoff(text, database.db.get_lead_by_user_id(user)):
            database.db.add_message(user, 'user', text)
            _persist_fasttrack_contact(user, message.from_user.first_name, text)
            await context.bot.send_message(
                chat_id=message.chat.id,
                text=content.HANDOFF_ACK_TEXT,
                business_connection_id=message.business_connection_id,
            )
            lead = database.db.get_lead_by_user_id(user)
            if not lead:
                lead_id = database.db.create_or_update_lead(user, {'name': message.from_user.first_name})
            else:
                lead_id = lead['id']

            funnel_state = database.db.get_user_funnel_state(user)
            cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user)
            previous_stage = funnel_state.get('conversation_stage') or 'discover'
            database.db.update_user_funnel_state(user, conversation_stage='handoff', cta_variant=cta_variant)
            database.db.update_lead_funnel_state(user, conversation_stage='handoff', cta_variant=cta_variant)
            if previous_stage != 'handoff':
                try:
                    database.db.track_event(
                        user,
                        "stage_changed",
                        payload={"from": previous_stage, "to": "handoff"},
                        lead_id=lead_id,
                    )
                except Exception as analytics_error:
                    logger.warning(f"[Business] Failed to track fasttrack stage change: {analytics_error}")

            lead_payload = database.db.get_lead_by_id(lead_id) or {}
            await notify_admin_new_lead(
                context=context,
                lead_id=lead_id,
                lead_data=lead_payload,
                user_data={
                    "id": user,
                    "telegram_id": user_id,
                    "username": message.from_user.username,
                    "first_name": message.from_user.first_name,
                },
                is_update=bool(lead),
            )
            try:
                database.db.track_event(
                    user,
                    "handoff_done",
                    payload={"source": "business_fasttrack", "cta_variant": cta_variant},
                    lead_id=lead_id,
                )
            except Exception as analytics_error:
                logger.warning(f"[Business] Failed to track business_fasttrack handoff_done: {analytics_error}")
            return

        # Pending lead-magnet в business flow: принимаем email и подтверждаем отправку.
        lead = database.db.get_lead_by_user_id(user)
        if lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered"):
            magnet_type = lead.get("lead_magnet_type")
            if magnet_type == "demo_analysis":
                magnet_type = "demo"
                database.db.create_or_update_lead(user, {"lead_magnet_type": "demo"})
                lead = database.db.get_lead_by_user_id(user)

            email = extract_email(text) if text else None
            if email:
                user_name = lead.get("name") or message.from_user.first_name
                success = False
                if magnet_type == "consultation":
                    success = email_sender.email_sender.send_consultation_confirmation(email, user_name)
                elif magnet_type == "checklist":
                    success = email_sender.email_sender.send_checklist(email, user_name)
                elif magnet_type == "demo":
                    success = email_sender.email_sender.send_demo_request_confirmation(email, user_name)

                if success:
                    if not lead.get("email"):
                        database.db.create_or_update_lead(user, {"email": email})
                    lead_qualifier.lead_qualifier.mark_lead_magnet_delivered(lead["id"])
                    base_message = content.LEAD_MAGNET_SENT_MESSAGES.get(magnet_type, "✅ Спасибо! Письмо отправлено.")
                    await context.bot.send_message(
                        chat_id=message.chat.id,
                        text=f"{base_message}\n\nКонтакт для отправки: {email}",
                        business_connection_id=message.business_connection_id,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=message.chat.id,
                        text=f"Произошла ошибка при отправке email.\n\n{content.DIRECT_CONTACTS_TEXT}",
                        business_connection_id=message.business_connection_id,
                    )
                return

            if magnet_type == "demo" and (getattr(message, "document", None) or getattr(message, "photo", None)):
                file_marker = "photo"
                if getattr(message, "document", None):
                    file_marker = f"document:{message.document.file_name or message.document.file_id}"
                existing_notes = (lead.get("notes") or "").strip()
                notes = f"{existing_notes}\nДокумент для демо: {file_marker}".strip()
                database.db.create_or_update_lead(user, {"notes": notes})
                await context.bot.send_message(
                    chat_id=message.chat.id,
                    text="Документ получил. Теперь укажите email, и команда отправит дальнейшие шаги.",
                    business_connection_id=message.business_connection_id,
                )
                return

        if not text:
            logger.warning(f"[Business] Skipping non-text message update: {update.update_id}")
            return

        funnel_state = database.db.get_user_funnel_state(user)
        current_stage = funnel_state.get('conversation_stage') or 'discover'
        cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user)
        cta_shown = bool(funnel_state.get('cta_shown'))
        if not funnel_state.get('cta_variant'):
            database.db.update_user_funnel_state(user, cta_variant=cta_variant)
        
        # Сохраняем сообщение пользователя
        database.db.add_message(user, 'user', text)
        
        # Получаем историю диалога
        conversation_history = database.db.get_conversation_history(user)
        
        # ПРОВЕРКА: если это первое сообщение клиента - показываем кнопки меню
        # (в бизнес-чатах клиент не видит /start, начинает сразу с вопроса)
        is_first_message = len(conversation_history) <= 1  # Только его первое сообщение
        show_menu_buttons = is_first_message

        lead_snapshot = database.db.get_lead_by_user_id(user) if allow_lead_processing else None
        lead_id = lead_snapshot["id"] if lead_snapshot else None
        merged_lead_data = dict(lead_snapshot or {})
        response_stage = current_stage

        # Стадию ответа считаем без дополнительного pre-LLM шага,
        # чтобы пользователь не ждал лишний запрос к модели.
        if allow_lead_processing:
            response_stage = funnel.infer_stage(
                previous_stage=current_stage,
                user_message=text,
                lead_data=merged_lead_data,
            )

        # Получаем ответ от AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        _schedule_business_typing(context, message, user_id)

        # Собираем ответ от OpenAI и постепенно обновляем сообщение
        start_generation = time.time()
        preview_enabled = config.STREAMING_PREVIEW
        funnel_context = funnel.build_stage_context(response_stage, cta_variant, cta_shown)
        async for chunk in ai_brain.ai_brain.generate_response_stream(
            conversation_history,
            funnel_context=funnel_context
        ):
            full_response += chunk
            chunk_buffer += chunk

            # Обновляем сообщение когда накопилось достаточно новых символов
            # ИЛИ прошло достаточно времени (для избежания rate limit)
            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 3.5) or  # Каждые 150 символов И минимум 3.5 сек (было 2)
                (len(chunk_buffer) > 300 and current_time - last_update_time >= 5.0)  # Или каждые 5 секунд при 300+ символах (было 3)
            )

            if preview_enabled and should_update:
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
        full_response = funnel.enforce_leadgen_response(
            response_text=full_response,
            stage=response_stage,
            user_message=text,
            cta_shown=cta_shown,
            cta_variant=cta_variant,
            lead_data=merged_lead_data,
        )

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

        # Аналитика: показ CTA (A/B)
        if not cta_shown and funnel.is_cta_shown(full_response, cta_variant):
            database.db.update_user_funnel_state(
                user,
                cta_variant=cta_variant,
                cta_shown=True
            )
            database.db.update_lead_funnel_state(
                user,
                cta_variant=cta_variant,
                cta_shown=True
            )
            try:
                database.db.track_event(
                    user,
                    "cta_shown",
                    payload={"variant": cta_variant, "stage": response_stage, "source": "assistant_response"},
                )
            except Exception as analytics_error:
                logger.warning(f"[Business] Failed to track cta_shown: {analytics_error}")
            cta_shown = True
        
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
                    text=content.BUSINESS_MENU_HINT_TEXT,
                    reply_markup=reply_markup,
                    business_connection_id=message.business_connection_id,
                )
                logger.info(f"[Business] Menu buttons sent to user {user_id}")
            except Exception as e:
                logger.warning(f"[Business] Failed to send menu buttons: {e}")
        
        # Фиксируем stage сразу, чтобы следующий апдейт не ждал LLM-экстракцию.
        if allow_lead_processing:
            if lead_id:
                database.db.update_lead_last_message_time(user)

            next_stage = response_stage
            database.db.update_user_funnel_state(
                user,
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )
            database.db.update_lead_funnel_state(
                user,
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )

            if next_stage != current_stage:
                try:
                    database.db.track_event(
                        user,
                        "stage_changed",
                        payload={"from": current_stage, "to": next_stage},
                        lead_id=lead_id,
                    )
                except Exception as analytics_error:
                    logger.warning(f"[Business] Failed to track stage_changed: {analytics_error}")

            cta_was_shown = cta_shown
            conversation_snapshot = list(conversation_history)

            async def _post_response_lead_processing() -> None:
                try:
                    extracted = await ai_brain.ai_brain.extract_lead_data_async(conversation_snapshot)
                    if not extracted:
                        return

                    processed_lead_id = lead_qualifier.lead_qualifier.process_lead_data(user, extracted)
                    if processed_lead_id:
                        temperature = extracted.get("temperature") or extracted.get("lead_temperature", "cold")
                        should_notify = (
                            temperature in ["hot", "warm"]
                            or (
                                extracted.get("name")
                                and (extracted.get("email") or extracted.get("phone"))
                                and extracted.get("pain_point")
                            )
                        )
                        logger.info(
                            f"[Business] Lead {processed_lead_id}: "
                            f"temperature={temperature}, should_notify={should_notify}"
                        )
                        database.db.update_lead_last_message_time(user)

                        if should_notify:
                            await notify_admin_new_lead(
                                context,
                                processed_lead_id,
                                extracted,
                                {"id": user, "telegram_id": user_id},
                            )

                    existing_lead = database.db.get_lead_by_user_id(user)
                    lead_magnet_already_selected = bool(existing_lead and existing_lead.get("lead_magnet_type"))
                    if (
                        not lead_magnet_already_selected
                        and not cta_was_shown
                        and ai_brain.ai_brain.should_offer_lead_magnet(extracted)
                    ):
                        reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
                        await context.bot.send_message(
                            chat_id=message.chat.id,
                            text=content.LEAD_MAGNET_OFFER_TEXT,
                            reply_markup=reply_markup,
                            business_connection_id=message.business_connection_id,
                        )

                        database.db.update_user_funnel_state(
                            user,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        database.db.update_lead_funnel_state(
                            user,
                            cta_variant=cta_variant,
                            cta_shown=True,
                        )
                        try:
                            database.db.track_event(
                                user,
                                "cta_shown",
                                payload={"variant": cta_variant, "stage": next_stage, "source": "lead_magnet_offer"},
                                lead_id=processed_lead_id,
                            )
                        except Exception as analytics_error:
                            logger.warning(f"[Business] Failed to track lead magnet CTA show: {analytics_error}")
                except Exception as background_error:
                    logger.warning(f"[Business] Background lead processing failed for user {user_id}: {background_error}")

            asyncio.create_task(_post_response_lead_processing())

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
