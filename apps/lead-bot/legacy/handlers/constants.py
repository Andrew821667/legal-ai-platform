"""
Константы для handlers - меню кнопок и другие константы
"""
from telegram import KeyboardButton, InlineKeyboardButton

# Меню кнопок
MAIN_MENU = [
    [KeyboardButton("📋 Меню услуг"), KeyboardButton("📞 Консультация")],
    [KeyboardButton("👤 Мой профиль"), KeyboardButton("📚 Документы")],
    [KeyboardButton("✉️ Личное обращение"), KeyboardButton("🔄 Начать заново")],
]

# Админское меню (видно только админу)
ADMIN_MENU = [
    [KeyboardButton("📋 Меню услуг"), KeyboardButton("📞 Консультация")],
    [KeyboardButton("👤 Мой профиль"), KeyboardButton("📚 Документы")],
    [KeyboardButton("✉️ Личное обращение"), KeyboardButton("⚙️ Админ-панель")],
    [KeyboardButton("🔄 Начать заново")],
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
]

# Админ-панель inline кнопки
ADMIN_PANEL_MENU = [
    [InlineKeyboardButton("📊 Лиды и воронка", callback_data="admin_section_leads")],
    [InlineKeyboardButton("👥 Пользователи", callback_data="admin_section_users")],
    [InlineKeyboardButton("📥 Экспорт и логи", callback_data="admin_section_export")],
    [InlineKeyboardButton("🛡️ Безопасность", callback_data="admin_security")],
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
    [InlineKeyboardButton("🔎 Поиск / карточка по ID", callback_data="admin_users_lookup_help")],
    [InlineKeyboardButton("◀️ Назад в админ-панель", callback_data="admin_panel")],
]

ADMIN_LOOKUP_MENU = [
    [InlineKeyboardButton("🗂️ Карточка по ID", callback_data="admin_lookup_card_prompt")],
    [InlineKeyboardButton("💬 История диалога по ID", callback_data="admin_lookup_dialog_prompt")],
    [InlineKeyboardButton("✏️ Редактировать ПД", callback_data="admin_lookup_edit_prompt")],
    [InlineKeyboardButton("🗑️ Отозвать согласие по ID", callback_data="admin_lookup_revoke_prompt")],
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
