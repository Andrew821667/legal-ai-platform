"""
Handlers: callbacks
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


async def handle_business_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик inline кнопок меню для бизнес-чатов
    """
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        menu_responses = {
            "menu_services": (
                "🎯 НАШИ УСЛУГИ:\n\n"
                "1️⃣ AI для договорной работы (от 150K₽)\n"
                "2️⃣ AI для судебной работы (от 200K₽)\n"
                "3️⃣ M&A и корпоративное право (от 300K₽)\n"
                "4️⃣ Земельное право (от 250K₽)\n"
                "5️⃣ Комплаенс и риск-менеджмент (от 200K₽)\n"
                "6️⃣ Аналитические системы (от 150K₽)\n"
                "7️⃣ Юридический аутсорсинг + AI (от 100K₽/мес)\n"
                "8️⃣ Кастомная разработка под ключ (от 300K₽)\n\n"
                "Какое направление интересует подробнее?"
            ),
            "menu_prices": (
                "💰 ЦЕНООБРАЗОВАНИЕ:\n\n"
                "Стоимость зависит от:\n"
                "• Объема автоматизации\n"
                "• Интеграций с вашими системами\n"
                "• Обучения на ваших данных\n\n"
                "Примерные цены:\n"
                "📌 Базовое решение: от 150K₽\n"
                "📌 Полная автоматизация: от 300K₽\n"
                "📌 Корпоративное решение: от 500K₽\n\n"
                "Для точной оценки опишите вашу задачу!"
            ),
            "menu_consultation": (
                "📞 БЕСПЛАТНАЯ КОНСУЛЬТАЦИЯ:\n\n"
                "Наша команда может провести бесплатную консультацию (30 минут), на которой:\n"
                "• Разберет вашу ситуацию\n"
                "• Предложит варианты решений\n"
                "• Оценит сроки и стоимость\n\n"
                "Для записи на консультацию укажите ваш email или телефон."
            ),
            "menu_help": (
                "📖 ПОМОЩЬ:\n\n"
                "Вы можете:\n"
                "• Задавать вопросы о услугах\n"
                "• Описать вашу ситуацию\n"
                "• Запросить консультацию\n\n"
                "Я работаю 24/7 и всегда рад помочь!"
            )
        }
        
        response_text = menu_responses.get(callback_data, "Выберите пункт меню")
        
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

    messages = {
        "consultation": (
            "Отлично! Наша команда свяжется с вами для согласования времени консультации.\n\n"
            "Укажите ваш email или телефон для связи:"
        ),
        "checklist": (
            "Отлично! Чек-лист \"15 типовых ошибок в договорах\" будет отправлен вам на email.\n\n"
            "Укажите ваш email:"
        ),
        "demo": (
            "Отлично! Для демо-анализа вашего договора:\n\n"
            "1. Отправьте мне договор (файл или фото)\n"
            "2. Укажите ваш email\n\n"
            "Анализ будет готов в течение 24 часов."
        )
    }

    # Сохраняем выбор lead magnet
    lead = database.db.get_lead_by_user_id(user_data['id'])
    if lead:
        lead_qualifier.lead_qualifier.update_lead_magnet(lead['id'], magnet_type)

        # Уведомляем админа
        admin_interface.admin_interface.send_admin_notification(
            context.bot,
            lead['id'],
            'lead_magnet_requested',
            f"Запрошен: {magnet_type}"
        )

    await query.message.reply_text(messages.get(magnet_type, "Спасибо!"))



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
        if action == "admin_stats":
            # Общая статистика
            stats_message = admin_interface.admin_interface.format_statistics(30)
            await query.message.reply_text(stats_message)

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

        elif action == "admin_logs":
            # Последние строки логов
            import subprocess
            result = subprocess.run(['tail', '-50', config.LOG_FILE], capture_output=True, text=True)
            logs = result.stdout

            # Добавляем цветные индикаторы для ошибок и предупреждений
            formatted_lines = []
            for line in logs.split('\n'):
                if ' - ERROR - ' in line:
                    formatted_lines.append(f"🔴 {line}")  # Красный индикатор для ошибок
                elif ' - WARNING - ' in line:
                    formatted_lines.append(f"⚠️ {line}")  # Желтый индикатор для предупреждений
                else:
                    formatted_lines.append(line)

            formatted_logs = '\n'.join(formatted_lines)

            if len(formatted_logs) > 4000:
                formatted_logs = formatted_logs[-4000:]  # Telegram limit

            await query.message.reply_text(f"📋 ПОСЛЕДНИЕ ЛОГИ:\n\n```\n{formatted_logs}\n```", parse_mode="Markdown")

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
            # Очистка логов
            import os
            if os.path.exists(config.LOG_FILE):
                # Создаем backup
                backup_file = f"{config.LOG_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(config.LOG_FILE, backup_file)
                # Создаем новый пустой файл
                open(config.LOG_FILE, 'w').close()
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
            import os
            if os.path.exists(config.LOG_FILE):
                backup_file = f"{config.LOG_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                os.rename(config.LOG_FILE, backup_file)
                open(config.LOG_FILE, 'w').close()

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
                f"🗑️ Логи: очищены (backup создан)\n"
                f"🗑️ Счетчики безопасности: сброшены"
            )

            await query.message.reply_text(result_message)
            logger.warning(f"Admin {user.id} cleared ALL data")

    except Exception as e:
        logger.error(f"Error in handle_cleanup_callback: {e}")
        await query.message.reply_text(f"Ошибка: {str(e)}")



