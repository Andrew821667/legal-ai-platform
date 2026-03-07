"""
Константы для handlers - меню кнопок и другие константы
"""
from telegram_ui import inline_button as InlineKeyboardButton
from telegram_ui import reply_button as KeyboardButton

# Меню кнопок
MAIN_MENU = [
    [KeyboardButton("🧭 Рабочий стол")],
]

# Админское меню (видно только админу)
ADMIN_MENU = [
    [KeyboardButton("🧭 Рабочий стол")],
]

WORKSPACE_INLINE_MENU = [
    [
        InlineKeyboardButton("📋 Услуги", callback_data="menu_services"),
        InlineKeyboardButton("💰 Цены", callback_data="menu_prices"),
    ],
    [
        InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
        InlineKeyboardButton("📲 Оставить контакт", callback_data="menu_leave_contact"),
    ],
    [
        InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        InlineKeyboardButton("📚 Документы", callback_data="menu_documents"),
    ],
    [
        InlineKeyboardButton("✉️ Личное обращение", callback_data="menu_personal_request"),
        InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
    ],
]

QUICK_NAV_MENU = [
    [
        InlineKeyboardButton("🧭 Рабочий стол", callback_data="menu_dashboard"),
        InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
    ],
    [
        InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        InlineKeyboardButton("📚 Документы", callback_data="menu_documents"),
    ],
]

LEAD_MAGNET_MENU = [
    [InlineKeyboardButton("📞 Консультация 30 мин", callback_data="magnet_consultation")],
    [InlineKeyboardButton("📄 Чек-лист по договорам", callback_data="magnet_checklist")],
    [InlineKeyboardButton("🎯 Демо-анализ договора", callback_data="magnet_demo")]
]

CONSENT_PDN_MENU = [
    [InlineKeyboardButton("✅ Даю согласие (ПД + трансграничная)", callback_data="consent_pdn_yes")],
    [InlineKeyboardButton("❌ Отказаться", callback_data="consent_pdn_no")],
    [InlineKeyboardButton("📄 Политика ПД", callback_data="consent_doc_privacy")],
]

CONSENT_TRANSBORDER_MENU = [
    [InlineKeyboardButton("✅ Согласен на трансграничную передачу", callback_data="consent_transborder_yes")],
    [InlineKeyboardButton("❌ Отказаться от ИИ-режима", callback_data="consent_transborder_no")],
    [InlineKeyboardButton("📄 Условия трансграничной передачи", callback_data="consent_doc_transborder")],
]

CONSULTATION_CTA_MENU = [
    [InlineKeyboardButton("📞 Заказать консультацию", callback_data="magnet_consultation")],
]

PERSONAL_MODE_RETURN_MENU = [
    [InlineKeyboardButton("↩️ Вернуться к боту", callback_data="menu_return_to_bot")],
]

DOCUMENTS_MENU = [
    [
        InlineKeyboardButton("📄 Политика ПД", callback_data="doc_privacy"),
        InlineKeyboardButton("🌍 Трансграничная передача", callback_data="doc_transborder"),
    ],
    [
        InlineKeyboardButton("📜 Пользовательское соглашение", callback_data="doc_user_agreement"),
        InlineKeyboardButton("🤖 Политика ИИ", callback_data="doc_ai_policy"),
    ],
    [InlineKeyboardButton("📣 Согласие на рассылки", callback_data="doc_marketing_consent")],
    [
        InlineKeyboardButton("📑 Статус согласий", callback_data="doc_consent_status"),
        InlineKeyboardButton("📊 Экспорт данных", callback_data="doc_export_data"),
    ],
    [
        InlineKeyboardButton("🧭 Рабочий стол", callback_data="menu_dashboard"),
        InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
    ],
    [
        InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
    ],
]

# Админ-панель inline кнопки
ADMIN_PANEL_MENU = [
    [InlineKeyboardButton("📊 Лиды и воронка", callback_data="admin_section_leads")],
    [InlineKeyboardButton("👥 Пользователи", callback_data="admin_section_users")],
    [InlineKeyboardButton("📥 Экспорт и логи", callback_data="admin_section_export")],
    [InlineKeyboardButton("🛡️ Безопасность", callback_data="admin_section_security")],
    [InlineKeyboardButton("🧭 Команды и поиск", callback_data="admin_section_commands")],
    [InlineKeyboardButton("🗑️ Очистка данных", callback_data="admin_cleanup")],
    [InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")]
]

ADMIN_LEADS_MENU = [
    [InlineKeyboardButton("📊 Общая статистика", callback_data="admin_stats")],
    [InlineKeyboardButton("📈 Воронка и A/B", callback_data="admin_funnel_report")],
    [
        InlineKeyboardButton("👥 Все лиды", callback_data="admin_leads"),
        InlineKeyboardButton("🔥 Горячие", callback_data="admin_hot_leads"),
    ],
    [
        InlineKeyboardButton("♨️ Теплые", callback_data="admin_warm_leads"),
        InlineKeyboardButton("❄️ Холодные", callback_data="admin_cold_leads"),
    ],
    [InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")],
]

ADMIN_USERS_MENU = [
    [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users_list")],
    [InlineKeyboardButton("🕒 Последние пользователи", callback_data="admin_users_recent")],
    [InlineKeyboardButton("⚠️ Без согласия ПД", callback_data="admin_users_no_consent")],
    [InlineKeyboardButton("🗑️ Отозвали согласие", callback_data="admin_users_revoked")],
    [InlineKeyboardButton("♻️ Сделать как новый (ID)", callback_data="admin_lookup_reset_new_prompt")],
    [InlineKeyboardButton("🧨 Полностью удалить (ID)", callback_data="admin_lookup_delete_prompt")],
    [InlineKeyboardButton("🔎 Поиск / карточка по ID", callback_data="admin_users_lookup_help")],
    [InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")],
]

ADMIN_LOOKUP_MENU = [
    [InlineKeyboardButton("🗂️ Карточка по ID", callback_data="admin_lookup_card_prompt")],
    [InlineKeyboardButton("💬 История диалога по ID", callback_data="admin_lookup_dialog_prompt")],
    [InlineKeyboardButton("✏️ Редактировать ПД", callback_data="admin_lookup_edit_prompt")],
    [InlineKeyboardButton("🗑️ Отозвать согласие по ID", callback_data="admin_lookup_revoke_prompt")],
    [InlineKeyboardButton("♻️ Сделать как новый по ID", callback_data="admin_lookup_reset_new_prompt")],
    [InlineKeyboardButton("🧨 Полностью удалить по ID", callback_data="admin_lookup_delete_prompt")],
    [InlineKeyboardButton("👥 Открыть список пользователей", callback_data="admin_users_list")],
    [InlineKeyboardButton("◀️ Назад в раздел пользователей", callback_data="admin_section_users")],
]

ADMIN_EDIT_FIELD_MENU = [
    [
        InlineKeyboardButton("👤 Имя профиля", callback_data="admin_lookup_edit_field_first_name"),
        InlineKeyboardButton("👤 Фамилия профиля", callback_data="admin_lookup_edit_field_last_name"),
    ],
    [InlineKeyboardButton("🔖 Username", callback_data="admin_lookup_edit_field_username")],
    [
        InlineKeyboardButton("📝 Имя в заявке", callback_data="admin_lookup_edit_field_name"),
        InlineKeyboardButton("✉️ Email", callback_data="admin_lookup_edit_field_email"),
    ],
    [
        InlineKeyboardButton("📞 Телефон", callback_data="admin_lookup_edit_field_phone"),
        InlineKeyboardButton("🏢 Компания", callback_data="admin_lookup_edit_field_company"),
    ],
    [InlineKeyboardButton("◀️ Назад в поиск", callback_data="admin_users_lookup_help")],
]

ADMIN_EXPORT_MENU = [
    [InlineKeyboardButton("📥 Экспорт лидов (CSV)", callback_data="admin_export")],
    [InlineKeyboardButton("📥 Воронка CSV", callback_data="admin_funnel_export_csv")],
    [InlineKeyboardButton("📝 Воронка Markdown", callback_data="admin_funnel_export_md")],
    [InlineKeyboardButton("📋 Логи (последние)", callback_data="admin_logs")],
    [InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")],
]

ADMIN_SECURITY_MENU = [
    [InlineKeyboardButton("📊 Статистика безопасности", callback_data="admin_security_stats")],
    [InlineKeyboardButton("📋 Черный список", callback_data="admin_blacklist_list")],
    [InlineKeyboardButton("🚫 Блокировать по ID", callback_data="admin_blacklist_add_prompt")],
    [InlineKeyboardButton("✅ Разблокировать по ID", callback_data="admin_blacklist_remove_prompt")],
    [InlineKeyboardButton("⚙️ Runtime-настройки", callback_data="admin_runtime_settings")],
    [InlineKeyboardButton("🧹 Сбросить счетчики безопасности", callback_data="admin_security_reset")],
    [InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")],
]

ADMIN_RUNTIME_MENU = [
    [
        InlineKeyboardButton("🟢 Мягкий пресет", callback_data="admin_runtime_preset_soft"),
        InlineKeyboardButton("🟡 Стандарт", callback_data="admin_runtime_preset_standard"),
    ],
    [InlineKeyboardButton("🔴 Строгий пресет", callback_data="admin_runtime_preset_strict")],
    [
        InlineKeyboardButton("🎬 Streaming on/off", callback_data="admin_runtime_toggle_streaming"),
        InlineKeyboardButton("🧪 Тест-лиды on/off", callback_data="admin_runtime_toggle_admin_test"),
    ],
    [
        InlineKeyboardButton("🕒 Timeout 15s", callback_data="admin_runtime_timeout_15"),
        InlineKeyboardButton("🕒 Timeout 25s", callback_data="admin_runtime_timeout_25"),
        InlineKeyboardButton("🕒 Timeout 40s", callback_data="admin_runtime_timeout_40"),
    ],
    [
        InlineKeyboardButton("⏱ Idle 3m", callback_data="admin_runtime_idle_3"),
        InlineKeyboardButton("⏱ Idle 5m", callback_data="admin_runtime_idle_5"),
        InlineKeyboardButton("⏱ Idle 10m", callback_data="admin_runtime_idle_10"),
    ],
    [
        InlineKeyboardButton("📦 Batch 10", callback_data="admin_runtime_batch_10"),
        InlineKeyboardButton("📦 Batch 20", callback_data="admin_runtime_batch_20"),
        InlineKeyboardButton("📦 Batch 50", callback_data="admin_runtime_batch_50"),
    ],
    [InlineKeyboardButton("◀️ Назад в безопасность", callback_data="admin_section_security")],
]

# Меню очистки данных
ADMIN_CLEANUP_MENU = [
    [InlineKeyboardButton("🗑️ Очистить диалоги", callback_data="cleanup_conversations")],
    [InlineKeyboardButton("🗑️ Очистить лиды", callback_data="cleanup_leads")],
    [InlineKeyboardButton("🗑️ Очистить логи", callback_data="cleanup_logs")],
    [InlineKeyboardButton("🗑️ Сбросить счетчики безопасности", callback_data="cleanup_security")],
    [InlineKeyboardButton("⚠️ ОЧИСТИТЬ ВСЁ", callback_data="cleanup_all")],
    [InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]
]

# Служебные ключи user_data для business-сценария контакта.
BUSINESS_AWAITING_CONTACT_KEY = "business_awaiting_contact"
BUSINESS_AWAITING_CONTACT_SOURCE_KEY = "business_awaiting_contact_source"
BUSINESS_PENDING_CONTACT_KEY = "business_pending_contact"
