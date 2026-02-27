"""
Handlers: user
"""
import logging
import time
import re
import asyncio
from typing import Optional, Dict
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
import content
import funnel
from handlers.constants import *
from handlers.helpers import extract_email, send_lead_magnet_email

logger = logging.getLogger(__name__)

# Import admin panel function (avoid at module level due to potential circular import)
def get_show_admin_panel():
    from handlers.admin import show_admin_panel
    return show_admin_panel


def _pdn_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_PDN_MENU)


def _transborder_consent_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(CONSENT_TRANSBORDER_MENU)


def _is_pdn_consent_granted(consent_state: Dict) -> bool:
    return bool(consent_state.get("consent_given")) and not bool(consent_state.get("consent_revoked"))


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

        # Для пользователей (кроме админа) сначала обязателен сбор согласия на ПД.
        if user.id != config.ADMIN_TELEGRAM_ID:
            consent_state = database.db.get_user_consent_state(user_id)
            if not _is_pdn_consent_granted(consent_state):
                await update.message.reply_text(
                    content.CONSENT_STEP_1_TEXT,
                    reply_markup=_pdn_consent_markup(),
                )
                return

        # Приветственное сообщение
        welcome_message = content.build_welcome_message(user.first_name)

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
    await update.message.reply_text(content.HELP_MESSAGE)



async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /privacy - политика обработки ПД."""
    _ = context
    await update.message.reply_text(content.privacy_policy_text())


async def user_agreement_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /user_agreement - пользовательское соглашение."""
    _ = context
    await update.message.reply_text(content.user_agreement_text())


async def ai_policy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai_policy - политика использования ИИ."""
    _ = context
    await update.message.reply_text(content.ai_policy_text())


async def marketing_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /marketing_consent - условия рассылок."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if user_data:
        database.db.set_user_marketing_consent(user_data["id"], True)
    await update.message.reply_text(content.marketing_consent_text())


async def transborder_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transborder_consent - условия и управление согласием."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return
    consent_state = database.db.get_user_consent_state(user_data["id"])
    message = content.transborder_policy_text()
    if bool(consent_state.get("transborder_consent")):
        await update.message.reply_text(f"{message}\n\nСтатус: ✅ согласие активно.")
        return
    await update.message.reply_text(
        f"{message}\n\nСтатус: ❌ согласие не дано.",
        reply_markup=_transborder_consent_markup(),
    )


async def consent_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /consent_status - текущий статус согласий пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return
    consent_state = database.db.get_user_consent_state(user_data["id"])
    await update.message.reply_text(content.consent_status_text(consent_state))


async def export_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /export_data - выгрузка данных пользователя."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return
    payload = database.db.export_user_data(user_data["id"])
    if not payload:
        await update.message.reply_text("Данные пользователя не найдены.")
        return
    await update.message.reply_text(content.export_data_text(payload))


async def revoke_consent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /revoke_consent - отзыв согласий и удаление ПД."""
    _ = context
    user = update.effective_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    if not user_data:
        await update.message.reply_text("Сначала выполните /start.")
        return

    result = database.db.revoke_user_consent_and_delete_data(user_data["id"])
    await update.message.reply_text(
        f"{content.CONSENT_REVOKED_TEXT}\n\n"
        f"Изменено профилей: {result.get('users_updated', 0)}\n"
        f"Анонимизировано анкет: {result.get('leads_anonymized', 0)}\n"
        f"Удалено сообщений диалога: {result.get('messages_deleted', 0)}"
    )


async def delete_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /delete_data - алиас для /revoke_consent."""
    await revoke_consent_command(update, context)


async def correct_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /correct_data - запрос на исправление данных пользователем."""
    user = update.effective_user
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text(
            "Использование:\n"
            "/correct_data <что исправить>\n\n"
            "Пример:\n"
            "/correct_data Исправьте email на example@mail.ru"
        )
        return

    admin_text = (
        "📝 Запрос на исправление данных\n\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username or '—'}\n"
        f"Имя: {user.first_name or '—'}\n\n"
        f"Запрос:\n{text}"
    )

    try:
        await context.bot.send_message(chat_id=config.ADMIN_TELEGRAM_ID, text=admin_text)
    except Exception as e:
        logger.warning(f"Failed to notify admin about correct_data request: {e}")

    await update.message.reply_text("✅ Запрос на исправление данных отправлен команде.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /reset"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if user_data:
            # Очищаем историю диалога
            database.db.clear_conversation_history(user_data['id'])
            database.db.reset_user_funnel_state(user_data['id'])
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
                content.MENU_HEADER_TEXT,
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



def _normalize_magnet_type(value: Optional[str]) -> str:
    if value == "demo_analysis":
        return "demo"
    return value or ""


async def _handle_non_text_input(
    update: Update,
    user_data: Dict,
    lead: Optional[Dict],
) -> bool:
    """
    Обрабатывает non-text сообщения в сценарии lead magnet.
    Возвращает True, если сообщение обработано и основной flow продолжать не нужно.
    """
    message = update.effective_message
    if not message:
        return True

    if not lead or not lead.get("lead_magnet_type") or lead.get("lead_magnet_delivered"):
        logger.warning(f"Skipping non-text message update type: {update.update_id}")
        return True

    magnet_type = _normalize_magnet_type(lead.get("lead_magnet_type"))
    if magnet_type != lead.get("lead_magnet_type"):
        database.db.create_or_update_lead(user_data["id"], {"lead_magnet_type": magnet_type})
        lead = database.db.get_lead_by_user_id(user_data["id"])

    caption_text = message.caption or ""
    email = extract_email(caption_text)
    if email:
        await send_lead_magnet_email(update, user_data, lead, email)
        return True

    if magnet_type == "demo" and (message.document or message.photo):
        file_marker = "photo"
        if message.document:
            file_marker = f"document:{message.document.file_name or message.document.file_id}"

        existing_notes = (lead.get("notes") or "").strip()
        notes = f"{existing_notes}\nДокумент для демо: {file_marker}".strip()
        database.db.create_or_update_lead(user_data["id"], {"notes": notes})
        await message.reply_text(
            "Документ получил. Теперь укажите email, и мы отправим подтверждение и дальнейшие шаги."
        )
        return True

    await message.reply_text(
        "Чтобы продолжить, отправьте email в текстовом сообщении.\n"
        "Для демо-анализа можно приложить документ с подписью, где указан email."
    )
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пользовательских сообщений."""
    try:
        user = update.effective_user
        original_message = update.effective_message
        if not user or not original_message:
            return

        message_text = original_message.text or ""
        logger.info(f"Message from user {user.id}: {(message_text or '[non-text]')[:50]}")

        # Получаем или создаем пользователя
        user_data = database.db.get_user_by_telegram_id(user.id)
        if not user_data:
            database.db.create_or_update_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            user_data = database.db.get_user_by_telegram_id(user.id)
            if not user_data:
                return

        lead = database.db.get_lead_by_user_id(user_data["id"])
        consent_state = database.db.get_user_consent_state(user_data["id"])
        has_pdn_consent = _is_pdn_consent_granted(consent_state)
        has_transborder_consent = bool(consent_state.get("transborder_consent"))

        if user.id != config.ADMIN_TELEGRAM_ID and not has_pdn_consent:
            await original_message.reply_text(
                content.CONSENT_STEP_1_TEXT,
                reply_markup=_pdn_consent_markup(),
            )
            return

        # В non-text ветке поддерживаем сценарий демо (документ + email).
        if not message_text:
            await _handle_non_text_input(update, user_data, lead)
            return

        # 🛡️ ПРОВЕРКА БЕЗОПАСНОСТИ (только для текстовых сообщений)
        is_allowed, block_reason = security.security_manager.check_all_security(user.id, message_text)
        if not is_allowed:
            logger.warning(f"Security check failed for user {user.id}: {block_reason}")
            await original_message.reply_text(block_reason)
            return

        # Проверяем есть ли pending lead magnet и email в сообщении
        if lead and lead.get("lead_magnet_type") and not lead.get("lead_magnet_delivered"):
            normalized = _normalize_magnet_type(lead.get("lead_magnet_type"))
            if normalized != lead.get("lead_magnet_type"):
                database.db.create_or_update_lead(user_data["id"], {"lead_magnet_type": normalized})
                lead = database.db.get_lead_by_user_id(user_data["id"])

            email = extract_email(message_text)
            if email:
                await send_lead_magnet_email(update, user_data, lead, email)
                return

        # Состояние воронки + A/B CTA
        funnel_state = database.db.get_user_funnel_state(user_data["id"])
        current_stage = funnel_state.get("conversation_stage") or "discover"
        cta_variant = funnel_state.get("cta_variant") or funnel.choose_cta_variant(user_data["id"])
        cta_shown = bool(funnel_state.get("cta_shown"))
        if not funnel_state.get("cta_variant"):
            database.db.update_user_funnel_state(user_data["id"], cta_variant=cta_variant)

        # Обработка кнопок меню
        if message_text in ["📋 Услуги", "💰 Цены", "📞 Консультация", "❓ Помощь"]:
            await handle_menu_button(update, context, message_text)
            return

        # Обработка команды /menu (на случай если CommandHandler не сработал)
        if message_text.strip().lower() in ["/menu", "menu", "/меню", "меню"]:
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
                await original_message.reply_text("У вас нет доступа к этой функции")
            return

        # Проверяем триггеры передачи админу
        if ai_brain.ai_brain.check_handoff_trigger(message_text):
            await handle_handoff_request(update, context)
            return

        if user.id != config.ADMIN_TELEGRAM_ID and not has_transborder_consent:
            await original_message.reply_text(
                content.TRANSBORDER_REQUIRED_TEXT,
                reply_markup=_transborder_consent_markup(),
            )
            return

        # ПРОВЕРКА: если клиент повторяет одно и то же сообщение 3+ раза
        # И прошло более 30 минут с начала диалога - завершаем разговор
        conversation_history = database.db.get_conversation_history(user_data["id"])
        if conversation_history:
            user_messages = [msg for msg in conversation_history if msg["role"] == "user"]
            if len(user_messages) >= 3:
                last_three = [msg.get("content", msg.get("message", "")).strip().lower() for msg in user_messages[-3:]]
                if len(set(last_three)) == 1:
                    import datetime

                    first_message_time = datetime.datetime.fromisoformat(conversation_history[0]["timestamp"])
                    current_time = datetime.datetime.now()
                    time_elapsed = (current_time - first_message_time).total_seconds() / 60
                    if time_elapsed > 30:
                        await original_message.reply_text(content.REPEAT_LOOP_FALLBACK_TEXT)
                        return

        # Сохраняем сообщение пользователя
        database.db.add_message(user_data["id"], "user", message_text)

        # Получаем историю диалога (включая текущее сообщение)
        conversation_history = database.db.get_conversation_history(user_data["id"])
        lead_id = lead["id"] if lead else None
        lead_data = None
        merged_lead_data = dict(lead or {})
        response_stage = current_stage

        # Готовим стадию ДО генерации ответа, чтобы убрать лаг на 1 шаг.
        if user.id != config.ADMIN_TELEGRAM_ID:
            lead_data = ai_brain.ai_brain.extract_lead_data(conversation_history)
            if lead_data:
                merged_lead_data.update({k: v for k, v in lead_data.items() if v is not None})

            response_stage = funnel.infer_stage(
                previous_stage=current_stage,
                user_message=message_text,
                lead_data=merged_lead_data,
            )

        # Генерируем ответ через AI с постепенным streaming (как в GPT)
        full_response = ""
        sent_message = None
        chunk_buffer = ""
        last_update_length = 0
        last_update_time = 0

        try:
            await original_message.chat.send_action(action="typing")
            logger.info(f"Typing indicator sent for user {user_data['telegram_id']}")
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

        start_generation = time.time()
        funnel_context = funnel.build_stage_context(response_stage, cta_variant, cta_shown)
        async for chunk in ai_brain.ai_brain.generate_response_stream(
            conversation_history,
            funnel_context=funnel_context,
        ):
            full_response += chunk
            chunk_buffer += chunk

            current_time = time.time()
            should_update = (
                (len(full_response) - last_update_length >= 150 and current_time - last_update_time >= 2.0)
                or (len(chunk_buffer) > 300 and current_time - last_update_time >= 3.0)
            )

            if should_update:
                if sent_message is None:
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
                    try:
                        await sent_message.edit_text(full_response)
                        last_update_length = len(full_response)
                        last_update_time = current_time
                        chunk_buffer = ""
                        logger.debug(f"Message updated: {len(full_response)} chars")
                    except Exception as e:
                        logger.debug(f"Skipped update (rate limit): {e}")

        generation_time = time.time() - start_generation
        logger.info(f"Response generated in {generation_time:.2f}s ({len(full_response)} chars)")
        full_response = funnel.enforce_leadgen_response(
            response_text=full_response,
            stage=response_stage,
            user_message=message_text,
            cta_shown=cta_shown,
            cta_variant=cta_variant,
            lead_data=merged_lead_data,
        )

        if len(full_response) > 4096:
            logger.warning(f"Response too long ({len(full_response)} chars), splitting into parts")
            parts = utils.split_long_message(full_response, max_length=4000)

            if sent_message:
                try:
                    await sent_message.delete()
                except Exception:
                    pass

            for i, part in enumerate(parts):
                part_msg = f"[Часть {i+1}/{len(parts)}]\n\n{part}" if len(parts) > 1 else part
                await original_message.reply_text(part_msg)
                if i < len(parts) - 1:
                    await original_message.chat.send_action(action="typing")
                    await asyncio.sleep(0.5)
        else:
            if sent_message:
                try:
                    await sent_message.edit_text(full_response)
                    logger.debug("Final message update sent")
                except Exception:
                    pass
            else:
                await original_message.reply_text(full_response)

        database.db.add_message(user_data["id"], "assistant", full_response)

        # Аналитика: показ CTA (A/B) внутри ответа ассистента
        if not cta_shown and funnel.is_cta_shown(full_response, cta_variant):
            database.db.update_user_funnel_state(
                user_data["id"],
                cta_variant=cta_variant,
                cta_shown=True,
            )
            database.db.update_lead_funnel_state(
                user_data["id"],
                cta_variant=cta_variant,
                cta_shown=True,
            )
            cta_shown = True
            try:
                database.db.track_event(
                    user_data["id"],
                    "cta_shown",
                    payload={"variant": cta_variant, "stage": response_stage, "source": "assistant_response"},
                    lead_id=lead_id,
                )
            except Exception as analytics_error:
                logger.warning(f"Failed to track cta_shown event: {analytics_error}")

        # 🛡️ УЧЕТ ИСПОЛЬЗОВАННЫХ ТОКЕНОВ
        user_tokens = security.security_manager.estimate_tokens(message_text)
        assistant_tokens = security.security_manager.estimate_tokens(full_response)
        system_tokens = security.security_manager.estimate_tokens(prompts.SYSTEM_PROMPT)
        total_tokens = user_tokens + assistant_tokens + system_tokens
        security.security_manager.add_tokens_used(total_tokens)
        logger.debug(
            f"Tokens used: user={user_tokens}, assistant={assistant_tokens}, "
            f"system={system_tokens}, total={total_tokens}"
        )

        # Извлекаем/сохраняем данные лида (только если это НЕ админ)
        if user.id != config.ADMIN_TELEGRAM_ID:
            if lead_data:
                lead_id = lead_qualifier.lead_qualifier.process_lead_data(user_data["id"], lead_data)
                if lead_id:
                    logger.info(f"Lead {lead_id} updated, waiting for conversation to finish before notifying admin")

            if lead_id:
                database.db.update_lead_last_message_time(user_data["id"])

            next_stage = response_stage
            database.db.update_user_funnel_state(
                user_data["id"],
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )
            database.db.update_lead_funnel_state(
                user_data["id"],
                conversation_stage=next_stage,
                cta_variant=cta_variant,
            )

            if next_stage != current_stage:
                try:
                    database.db.track_event(
                        user_data["id"],
                        "stage_changed",
                        payload={"from": current_stage, "to": next_stage},
                        lead_id=lead_id,
                    )
                except Exception as analytics_error:
                    logger.warning(f"Failed to track stage_changed event: {analytics_error}")

            # Авто-оффер lead magnet в user-flow (как в business-flow).
            lead_after = database.db.get_lead_by_user_id(user_data["id"])
            lead_magnet_already_selected = bool(lead_after and lead_after.get("lead_magnet_type"))
            if (
                lead_data
                and not lead_magnet_already_selected
                and not cta_shown
                and ai_brain.ai_brain.should_offer_lead_magnet(lead_data)
            ):
                await offer_lead_magnet(update, context)
                database.db.update_user_funnel_state(
                    user_data["id"],
                    cta_variant=cta_variant,
                    cta_shown=True,
                )
                database.db.update_lead_funnel_state(
                    user_data["id"],
                    cta_variant=cta_variant,
                    cta_shown=True,
                )
                try:
                    database.db.track_event(
                        user_data["id"],
                        "cta_shown",
                        payload={"variant": cta_variant, "stage": next_stage, "source": "lead_magnet_offer"},
                        lead_id=lead_id,
                    )
                except Exception as analytics_error:
                    logger.warning(f"Failed to track lead magnet CTA show: {analytics_error}")

    except Exception as e:
        if "Peer_id_invalid" not in str(e):
            logger.error(f"Error in handle_message: {e}")



async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    """Обработчик кнопок меню"""
    _ = context
    response = content.menu_response_by_button(button_text)
    await update.message.reply_text(response)



async def offer_lead_magnet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предложение lead magnet"""
    _ = context
    reply_markup = InlineKeyboardMarkup(LEAD_MAGNET_MENU)
    await update.message.reply_text(content.LEAD_MAGNET_OFFER_TEXT, reply_markup=reply_markup)



async def handle_handoff_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    source: str = "trigger",
):
    """Обработка запроса на передачу админу"""
    try:
        user = update.effective_user
        user_data = database.db.get_user_by_telegram_id(user.id)

        if not user_data:
            await update.message.reply_text("Ошибка. Попробуйте /start")
            return

        # Уведомляем пользователя
        await update.message.reply_text(content.HANDOFF_ACK_TEXT)

        # Создаем или обновляем лид
        lead = database.db.get_lead_by_user_id(user_data['id'])
        if not lead:
            lead_id = database.db.create_or_update_lead(user_data['id'], {
                'name': user.first_name
            })
        else:
            lead_id = lead['id']

        funnel_state = database.db.get_user_funnel_state(user_data['id'])
        previous_stage = funnel_state.get('conversation_stage') or 'discover'
        cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user_data['id'])

        database.db.update_user_funnel_state(
            user_data['id'],
            conversation_stage='handoff',
            cta_variant=cta_variant
        )
        database.db.update_lead_funnel_state(
            user_data['id'],
            conversation_stage='handoff',
            cta_variant=cta_variant
        )

        if previous_stage != 'handoff':
            try:
                database.db.track_event(
                    user_data['id'],
                    "stage_changed",
                    payload={"from": previous_stage, "to": "handoff"},
                    lead_id=lead_id
                )
            except Exception as analytics_error:
                logger.warning(f"Failed to track handoff stage change: {analytics_error}")

        # Уведомляем админа
        last_message = update.message.text[:100] if update.message and update.message.text else "n/a"
        admin_interface.admin_interface.send_admin_notification(
            context.bot,
            lead_id,
            'handoff_request',
            f"Последнее сообщение: {last_message}"
        )

        try:
            database.db.track_event(
                user_data['id'],
                "handoff_done",
                payload={"source": source, "cta_variant": cta_variant},
                lead_id=lead_id
            )
        except Exception as analytics_error:
            logger.warning(f"Failed to track handoff_done event: {analytics_error}")

        logger.info(f"Handoff request from user {user.id}")

    except Exception as e:
        logger.error(f"Error in handle_handoff_request: {e}")
