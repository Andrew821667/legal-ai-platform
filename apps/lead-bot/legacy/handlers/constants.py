"""
Константы для handlers - меню кнопок и другие константы
"""
from telegram import KeyboardButton, InlineKeyboardButton

# Меню кнопок
MAIN_MENU = [
    [KeyboardButton("📋 Услуги"), KeyboardButton("💰 Цены")],
    [KeyboardButton("📞 Консультация"), KeyboardButton("❓ Помощь")],
    [KeyboardButton("🔄 Начать заново")]
]

# Админское меню (видно только админу)
ADMIN_MENU = [
    [KeyboardButton("📋 Услуги"), KeyboardButton("💰 Цены")],
    [KeyboardButton("📞 Консультация"), KeyboardButton("❓ Помощь")],
    [KeyboardButton("⚙️ Админ-панель"), KeyboardButton("🔄 Начать заново")]
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

# Админ-панель inline кнопки
ADMIN_PANEL_MENU = [
    [InlineKeyboardButton("📊 Общая статистика", callback_data="admin_stats")],
    [InlineKeyboardButton("📈 Воронка и A/B", callback_data="admin_funnel_report")],
    [InlineKeyboardButton("📥 Воронка CSV", callback_data="admin_funnel_export_csv")],
    [InlineKeyboardButton("📝 Воронка Markdown", callback_data="admin_funnel_export_md")],
    [InlineKeyboardButton("🛡️ Безопасность", callback_data="admin_security")],
    [
        InlineKeyboardButton("👥 Все лиды", callback_data="admin_leads"),
        InlineKeyboardButton("🔥 Горячие", callback_data="admin_hot_leads"),
    ],
    [
        InlineKeyboardButton("♨️ Теплые", callback_data="admin_warm_leads"),
        InlineKeyboardButton("❄️ Холодные", callback_data="admin_cold_leads"),
    ],
    [InlineKeyboardButton("📋 Логи (последние)", callback_data="admin_logs")],
    [InlineKeyboardButton("📥 Экспорт данных", callback_data="admin_export")],
    [InlineKeyboardButton("🧭 Команды админа", callback_data="admin_commands")],
    [InlineKeyboardButton("🗑️ Очистка данных", callback_data="admin_cleanup")],
    [InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")]
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
