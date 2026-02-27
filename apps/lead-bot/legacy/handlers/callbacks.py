"""
Handlers: callbacks
"""
import logging
import os
import shutil
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
import content
import funnel
from handlers.constants import *

logger = logging.getLogger(__name__)


def _backup_and_truncate_log(log_file: str) -> str | None:
    """
    Создает backup лог-файла и очищает текущий файл без rename.
    Так FileHandler продолжает писать в тот же inode.
    """
    if not os.path.exists(log_file):
        return None

    backup_file = f"{log_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(log_file, backup_file)
    with open(log_file, "w", encoding="utf-8"):
        pass
    return backup_file


async def handle_business_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик inline кнопок меню для бизнес-чатов
    """
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        response_text = content.menu_response_by_key(callback_data)
        
        # Проверяем есть ли business_connection_id
        if query.message and hasattr(query.message, 'business_connection_id') and query.message.business_connection_id:
            # Бизнес-чат
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=response_text,
                business_connection_id=query.message.business_connection_id
            )
        else:
            # Обычный чат
            await query.edit_message_text(text=response_text)
            
    except Exception as e:
        logger.error(f"Error in handle_business_menu_callback: {e}")



async def handle_lead_magnet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора lead magnet"""
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)

    if not user_data:
        await query.message.reply_text("Ошибка. Попробуйте /start")
        return

    magnet_type = query.data.replace("magnet_", "")
    if magnet_type == "demo_analysis":
        magnet_type = "demo"

    # Сохраняем выбор lead magnet
    lead = database.db.get_lead_by_user_id(user_data['id'])
    if not lead:
        lead_id = database.db.create_or_update_lead(
            user_data["id"],
            {"name": user.first_name, "lead_magnet_type": magnet_type, "lead_magnet_delivered": False},
        )
        lead = database.db.get_lead_by_id(lead_id)
    else:
        lead_qualifier.lead_qualifier.update_lead_magnet(lead["id"], magnet_type)
        lead_id = lead["id"]

    # Уведомляем админа
    admin_interface.admin_interface.send_admin_notification(
        context.bot,
        lead_id,
        "lead_magnet_requested",
        f"Запрошен: {magnet_type}",
    )

    funnel_state = database.db.get_user_funnel_state(user_data['id'])
    cta_variant = funnel_state.get('cta_variant') or funnel.choose_cta_variant(user_data['id'])
    current_stage = funnel_state.get('conversation_stage') or 'discover'
    target_stage = 'handoff' if magnet_type == 'consultation' else 'propose'
    next_stage = funnel.advance_stage(current_stage, target_stage)

    database.db.update_user_funnel_state(
        user_data['id'],
        conversation_stage=next_stage,
        cta_variant=cta_variant,
        cta_shown=True,
    )
    database.db.update_lead_funnel_state(
        user_data['id'],
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
            user_data['id'],
            "cta_clicked",
            payload={
                "variant": cta_variant,
                "magnet_type": magnet_type,
                "from_stage": current_stage,
                "to_stage": next_stage,
            },
            lead_id=lead_id
        )
        if next_stage != current_stage:
            database.db.track_event(
                user_data['id'],
                "stage_changed",
                payload={"from": current_stage, "to": next_stage, "reason": "cta_clicked"},
                lead_id=lead_id
            )
    except Exception as analytics_error:
        logger.warning(f"Failed to track CTA click analytics: {analytics_error}")

    selection_text = content.LEAD_MAGNET_SELECTION_MESSAGES.get(magnet_type, "Спасибо!")
    if query.message and hasattr(query.message, "business_connection_id") and query.message.business_connection_id:
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=selection_text,
            business_connection_id=query.message.business_connection_id,
        )
    else:
        await query.message.reply_text(selection_text)



async def handle_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для согласий на ПД и трансграничную передачу."""
    query = update.callback_query
    await query.answer()

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
        await query.message.reply_text("Ошибка инициализации профиля. Нажмите /start еще раз.")
        return

    action = query.data or ""

    if action == "consent_doc_privacy":
        await query.message.reply_text(content.privacy_policy_text())
        return

    if action == "consent_doc_transborder":
        await query.message.reply_text(content.transborder_policy_text())
        return

    if action == "consent_pdn_no":
        await query.message.edit_text(content.CONSENT_DENIED_TEXT)
        return

    if action == "consent_pdn_yes":
        database.db.grant_user_consent(user_data["id"])
        database.db.set_user_transborder_consent(user_data["id"], True)
        await query.message.edit_text(
            "✅ Согласие на обработку ПД и трансграничную передачу сохранено.\n\n"
            "AI-режим включен. Можно описать задачу в свободной форме."
        )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            welcome_message += "\n\n⚙️ Доступна админ-панель!"
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await query.message.reply_text(welcome_message, reply_markup=reply_markup)
        return

    if action in ("consent_transborder_yes", "consent_transborder_no"):
        transborder_enabled = action == "consent_transborder_yes"
        database.db.set_user_transborder_consent(user_data["id"], transborder_enabled)
        if transborder_enabled:
            await query.message.edit_text(
                "✅ Согласия сохранены. AI-режим включен.\n\n"
                "Можно описать задачу в свободной форме, и я помогу сформировать следующий шаг."
            )
        else:
            await query.message.edit_text(
                "✅ Согласие на обработку ПД сохранено.\n"
                "ИИ-режим отключен до вашего разрешения на трансграничную передачу.\n\n"
                "Можно пользоваться меню и оставить заявку на консультацию."
            )

        welcome_message = content.build_welcome_message(user.first_name)
        if user.id == config.ADMIN_TELEGRAM_ID:
            welcome_message += "\n\n⚙️ Доступна админ-панель!"
            reply_markup = ReplyKeyboardMarkup(ADMIN_MENU, resize_keyboard=True)
        else:
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await query.message.reply_text(welcome_message, reply_markup=reply_markup)
        return

    await query.message.reply_text("Неизвестное действие согласия. Попробуйте /start.")


async def handle_documents_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback для раздела документов/прав пользователя."""
    _ = context
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_data = database.db.get_user_by_telegram_id(user.id)
    action = query.data or ""

    if action == "doc_privacy":
        await query.message.reply_text(content.privacy_policy_text())
        return
    if action == "doc_transborder":
        await query.message.reply_text(content.transborder_policy_text())
        return
    if action == "doc_user_agreement":
        await query.message.reply_text(content.user_agreement_text())
        return
    if action == "doc_ai_policy":
        await query.message.reply_text(content.ai_policy_text())
        return
    if action == "doc_marketing_consent":
        if user_data:
            database.db.set_user_marketing_consent(user_data["id"], True)
        await query.message.reply_text(content.marketing_consent_text())
        return

    if not user_data:
        await query.message.reply_text("Сначала выполните /start.")
        return

    if action == "doc_consent_status":
        consent_state = database.db.get_user_consent_state(user_data["id"])
        await query.message.reply_text(content.consent_status_text(consent_state))
        return
    if action == "doc_export_data":
        payload = database.db.export_user_data(user_data["id"])
        await query.message.reply_text(content.export_data_text(payload))
        return

    await query.message.reply_text("Неизвестное действие. Используйте /documents.")


def _format_users_for_admin(title: str, users: list[dict]) -> str:
    if not users:
        return f"{title}\n\nПользователи не найдены."

    lines = [title, ""]
    for user in users:
        consent = "✅" if user.get("consent_given") else "❌"
        revoked = "🗑️" if user.get("consent_revoked") else "—"
        username = f"@{user.get('username')}" if user.get("username") else "без username"
        lines.append(
            f"ID: {user.get('telegram_id')} | {username}\n"
            f"Имя: {user.get('first_name') or '—'} {user.get('last_name') or ''}\n"
            f"Согласие ПД: {consent} | Отзыв: {revoked}\n"
            f"Последняя активность: {user.get('last_interaction') or user.get('created_at') or '—'}\n"
        )
    return "\n".join(lines).strip()


async def handle_admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback кнопок админ-панели"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    # Проверка что это админ
    if user.id != config.ADMIN_TELEGRAM_ID:
        await query.message.reply_text("У вас нет доступа к этой функции")
        return

    action = query.data

    try:
        if action == "admin_section_leads":
            leads_section_message = (
                "📊 РАЗДЕЛ: ЛИДЫ И ВОРОНКА\n\n"
                "Выберите срез для просмотра:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_LEADS_MENU)
            await query.message.edit_text(leads_section_message, reply_markup=reply_markup)

        elif action == "admin_section_users":
            users_section_message = (
                "👥 РАЗДЕЛ: ПОЛЬЗОВАТЕЛИ\n\n"
                "Выберите действие:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_USERS_MENU)
            await query.message.edit_text(users_section_message, reply_markup=reply_markup)

        elif action == "admin_section_export":
            export_section_message = (
                "📥 РАЗДЕЛ: ЭКСПОРТ И ЛОГИ\n\n"
                "Выберите действие:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_EXPORT_MENU)
            await query.message.edit_text(export_section_message, reply_markup=reply_markup)

        elif action == "admin_section_commands":
            await query.message.reply_text(
                "🧭 КОМАНДЫ И ПОИСК\n\n"
                "Поиск/карточка пользователя:\n"
                "/pdn_user <telegram_id>\n"
                "/view_conversation <telegram_id>\n\n"
                "Редактирование ПД:\n"
                "/edit_pdn <telegram_id> <field> <value>\n"
                "/revoke_user_consent <telegram_id>\n\n"
                "Поля:\n"
                "user: first_name, last_name, username\n"
                "lead: name, email, phone, company"
            )

        elif action == "admin_users_recent":
            users = database.db.get_recent_users(limit=20)
            await query.message.reply_text(
                _format_users_for_admin("🕒 ПОСЛЕДНИЕ ПОЛЬЗОВАТЕЛИ (20)", users),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
            )

        elif action == "admin_users_no_consent":
            users = database.db.get_users_without_consent(limit=20)
            await query.message.reply_text(
                _format_users_for_admin("⚠️ ПОЛЬЗОВАТЕЛИ БЕЗ СОГЛАСИЯ ПД (20)", users),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
            )

        elif action == "admin_users_revoked":
            users = database.db.get_users_with_revoked_consent(limit=20)
            await query.message.reply_text(
                _format_users_for_admin("🗑️ ОТОЗВАЛИ СОГЛАСИЕ (20)", users),
                reply_markup=InlineKeyboardMarkup(ADMIN_USERS_MENU),
            )

        elif action == "admin_users_lookup_help":
            await query.message.reply_text(
                "🔎 Поиск пользователя по ID\n\n"
                "Используйте команды:\n"
                "/pdn_user <telegram_id>\n"
                "/view_conversation <telegram_id>\n"
                "/edit_pdn <telegram_id> <field> <value>"
            )

        elif action == "admin_stats":
            # Общая статистика
            stats_message = admin_interface.admin_interface.format_statistics(30)
            await query.message.reply_text(stats_message)
        
        elif action == "admin_funnel_report":
            # Воронка + A/B отчет
            report_message = admin_interface.admin_interface.format_funnel_report(30)
            await query.message.reply_text(report_message)
        
        elif action == "admin_funnel_export_csv":
            # Экспорт funnel-отчета в CSV
            csv_data = admin_interface.admin_interface.export_funnel_report_csv(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.csv"
            await query.message.reply_document(
                document=csv_data.encode('utf-8'),
                filename=filename,
                caption="📥 Funnel report (CSV)"
            )
        
        elif action == "admin_funnel_export_md":
            # Экспорт funnel-отчета в Markdown
            md_data = admin_interface.admin_interface.export_funnel_report_markdown(30)
            filename = f"funnel_report_{datetime.now().strftime('%Y%m%d')}.md"
            await query.message.reply_document(
                document=md_data.encode('utf-8'),
                filename=filename,
                caption="📝 Funnel report (Markdown)"
            )

        elif action == "admin_security":
            # Статистика безопасности
            stats = security.security_manager.get_stats()

            # Форматируем время начала статистики
            stats_since = stats['stats_start_time'].strftime("%d.%m.%Y %H:%M")

            stats_message = (
                "🛡️ СТАТИСТИКА БЕЗОПАСНОСТИ\n\n"
                f"📅 Статистика с: {stats_since}\n\n"
                f"📊 Токены:\n"
                f"• Использовано сегодня: {stats['total_tokens_today']:,}\n"
                f"• Дневной бюджет: {stats['daily_budget']:,}\n"
                f"• Осталось: {stats['budget_remaining']:,}\n"
                f"• Использовано: {stats['budget_percentage']:.1f}%\n\n"
                f"🚫 Безопасность:\n"
                f"• Заблокированных пользователей: {stats['blacklisted_users']}\n"
                f"• Подозрительных пользователей: {stats['suspicious_users']}\n\n"
                f"⚙️ Лимиты:\n"
                f"• Сообщений в минуту: {security.security_manager.RATE_LIMITS['messages_per_minute']}\n"
                f"• Сообщений в час: {security.security_manager.RATE_LIMITS['messages_per_hour']}\n"
                f"• Сообщений в день: {security.security_manager.RATE_LIMITS['messages_per_day']}\n"
                f"• Cooldown: {security.security_manager.COOLDOWN_SECONDS} сек\n"
                f"• Макс длина сообщения: {security.security_manager.MAX_MESSAGE_LENGTH} символов"
            )
            await query.message.reply_text(stats_message)

        elif action == "admin_leads":
            # Список всех лидов
            leads_message = admin_interface.admin_interface.format_leads_list(limit=20)
            await query.message.reply_text(leads_message)

        elif action == "admin_hot_leads":
            # Только горячие лиды
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='hot', limit=10)
            await query.message.reply_text(leads_message)

        elif action == "admin_warm_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='warm', limit=10)
            await query.message.reply_text(leads_message)

        elif action == "admin_cold_leads":
            leads_message = admin_interface.admin_interface.format_leads_list(temperature='cold', limit=10)
            await query.message.reply_text(leads_message)

        elif action == "admin_logs":
            # Последние строки логов отправляем файлом, чтобы не упираться в Markdown/лимиты.
            import subprocess
            result = subprocess.run(['tail', '-50', config.LOG_FILE], capture_output=True, text=True)
            logs = result.stdout
            if not logs.strip():
                await query.message.reply_text("📋 Логи пусты.")
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await query.message.reply_document(
                    document=logs.encode("utf-8"),
                    filename=f"lead_bot_logs_tail_{timestamp}.txt",
                    caption="📋 Последние 50 строк логов",
                )

        elif action == "admin_export":
            # Экспорт лидов в CSV
            csv_data = admin_interface.admin_interface.export_leads_to_csv()

            if csv_data:
                await query.message.reply_document(
                    document=csv_data.encode('utf-8') if isinstance(csv_data, str) else csv_data,
                    filename=f'leads_export_{datetime.now().strftime("%Y%m%d")}.csv',
                    caption="📥 Экспорт лидов"
                )
            else:
                await query.message.reply_text("Ошибка при экспорте данных")

        elif action == "admin_cleanup":
            # Меню очистки данных
            cleanup_message = (
                "🗑️ ОЧИСТКА ДАННЫХ\n\n"
                "⚠️ ВНИМАНИЕ: Данные будут удалены безвозвратно!\n\n"
                "Выберите что очистить:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_CLEANUP_MENU)
            await query.message.edit_text(cleanup_message, reply_markup=reply_markup)

        elif action == "admin_commands":
            await query.message.reply_text(
                "🧭 ДОСТУПНЫЕ АДМИН-КОМАНДЫ\n\n"
                "/stats — общая статистика\n"
                "/leads [hot|warm|cold] — список лидов\n"
                "/export — выгрузка лидов в CSV\n"
                "/view_conversation <telegram_id> — история диалога\n"
                "/security_stats — статистика безопасности\n"
                "/blacklist <telegram_id> [причина] — блокировка пользователя\n"
                "/unblacklist <telegram_id> — снять блокировку\n"
                "/pdn_user <telegram_id> — карточка ПД и согласий\n"
                "/edit_pdn <telegram_id> <field> <value> — правка ПД\n"
                "/revoke_user_consent <telegram_id> — отзыв согласия + очистка\n\n"
                "Эти функции работают и доступны даже если не вынесены отдельной кнопкой."
            )

        elif action == "admin_panel":
            # Вернуться в главное меню админ-панели
            admin_panel_message = (
                "⚙️ АДМИН-ПАНЕЛЬ\n\n"
                "Выберите действие:"
            )
            reply_markup = InlineKeyboardMarkup(ADMIN_PANEL_MENU)
            await query.message.edit_text(admin_panel_message, reply_markup=reply_markup)

        elif action == "admin_close":
            # Закрыть админ-панель
            await query.message.edit_text("⚙️ Админ-панель закрыта")

    except Exception as e:
        logger.error(f"Error in handle_admin_panel_callback: {e}")
        await query.message.reply_text(f"Ошибка: {str(e)}")



async def handle_cleanup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик cleanup операций"""
    query = update.callback_query
    await query.answer()

    user = query.from_user

    # Проверка что это админ
    if user.id != config.ADMIN_TELEGRAM_ID:
        await query.message.reply_text("У вас нет доступа к этой функции")
        return

    action = query.data

    try:
        if action == "cleanup_conversations":
            # Очистка всех диалогов
            conn = database.db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM conversations")
                conn.commit()
                count = cursor.rowcount

                await query.message.reply_text(f"✅ Удалено {count} сообщений из диалогов")
                logger.info(f"Admin {user.id} cleared {count} conversations")
            finally:
                conn.close()

        elif action == "cleanup_leads":
            # Очистка всех лидов
            conn = database.db.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM leads")
                conn.commit()
                count = cursor.rowcount

                await query.message.reply_text(f"✅ Удалено {count} лидов")
                logger.info(f"Admin {user.id} cleared {count} leads")
            finally:
                conn.close()

        elif action == "cleanup_logs":
            # Очистка логов без rename, чтобы FileHandler не потерял текущий файл.
            backup_file = _backup_and_truncate_log(config.LOG_FILE)
            if backup_file:
                await query.message.reply_text(f"✅ Логи очищены\nBackup: {backup_file}")
                logger.info(f"Admin {user.id} cleared logs, backup: {backup_file}")
            else:
                await query.message.reply_text("Файл логов не найден")

        elif action == "cleanup_security":
            # Сброс счетчиков безопасности
            security.security_manager.message_timestamps.clear()
            security.security_manager.token_usage.clear()
            security.security_manager.cooldowns.clear()
            security.security_manager.suspicious_users.clear()
            security.security_manager.blacklist.clear()
            security.security_manager.total_tokens_today = 0
            security.security_manager.reset_stats_time()

            new_time = security.security_manager.stats_start_time.strftime("%d.%m.%Y %H:%M")
            await query.message.reply_text(f"✅ Счетчики безопасности сброшены\n📅 Статистика теперь с: {new_time}")
            logger.info(f"Admin {user.id} reset security counters")

        elif action == "cleanup_all":
            # Очистка всего
            conn = database.db.get_connection()
            cursor = conn.cursor()

            try:
                # Диалоги
                cursor.execute("DELETE FROM conversations")
                conv_count = cursor.rowcount

                # Лиды
                cursor.execute("DELETE FROM leads")
                leads_count = cursor.rowcount

                # Уведомления
                cursor.execute("DELETE FROM admin_notifications")
                notif_count = cursor.rowcount

                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
            finally:
                conn.close()

            # Логи
            backup_file = _backup_and_truncate_log(config.LOG_FILE)

            # Безопасность
            security.security_manager.message_timestamps.clear()
            security.security_manager.token_usage.clear()
            security.security_manager.cooldowns.clear()
            security.security_manager.suspicious_users.clear()
            security.security_manager.blacklist.clear()
            security.security_manager.total_tokens_today = 0

            result_message = (
                "✅ ВСЕ ДАННЫЕ ОЧИЩЕНЫ\n\n"
                f"🗑️ Диалоги: {conv_count}\n"
                f"🗑️ Лиды: {leads_count}\n"
                f"🗑️ Уведомления: {notif_count}\n"
                f"🗑️ Логи: {'очищены (backup создан)' if backup_file else 'файл не найден'}\n"
                f"🗑️ Счетчики безопасности: сброшены"
            )

            await query.message.reply_text(result_message)
            logger.warning(f"Admin {user.id} cleared ALL data")

    except Exception as e:
        logger.error(f"Error in handle_cleanup_callback: {e}")
        await query.message.reply_text(f"Ошибка: {str(e)}")
