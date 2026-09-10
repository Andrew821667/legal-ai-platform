"""
Константы для handlers - меню кнопок и другие константы
"""
from telegram import InlineKeyboardMarkup, WebAppInfo

from config import get_config
from telegram_ui import inline_button as InlineKeyboardButton
from telegram_ui import reply_button as KeyboardButton

# Меню кнопок.
#
# Текстовая кнопка оставлена запасным вариантом: build_client_reply_menu ниже
# заменяет её на web_app-кнопку мини-аппа, если адрес настроен (а он настроен
# по умолчанию). Пустой CLIENT_MINIAPP_URL — единственный случай, когда эти
# списки используются как есть.
MAIN_MENU = [
    [KeyboardButton("🧭 Рабочий стол")],
]

# Админское меню (видно только админу)
ADMIN_MENU = [
    [KeyboardButton("🧭 Рабочий стол")],
]

DEFAULT_PROFILE_CTA_LABEL = "🎯 Профиль услуг: выбрать и проверить"


def contract_ai_menu_url() -> str:
    return "open_web:contract_ai"


def build_workspace_inline_menu(
    profile_cta_label: str = DEFAULT_PROFILE_CTA_LABEL,
    *,
    is_admin: bool = False,
):
    """Кнопки рабочего стола.

    Админу первой строкой добавляется вход в панель. Раньше попасть туда можно
    было, только зная про команду /admin: панель существовала, но на экране её
    не было.
    """
    admin_row = (
        [[InlineKeyboardButton("🛠 Админ-панель", callback_data="admin_panel")]]
        if is_admin
        else []
    )
    return admin_row + [
        [InlineKeyboardButton(profile_cta_label, callback_data="menu_offer_profile")],
        [InlineKeyboardButton("⚖️ Юридическая практика", callback_data="legal_help_start")],
        # Рядом с юридической практикой: соглашение подписывают в связи с
        # делом, и искать его будут здесь. На стартовом экране кнопки нет —
        # там человеку ещё нечего подписывать.
        [InlineKeyboardButton("🔒 Подписать NDA", callback_data="nda:open")],
        [InlineKeyboardButton("🛠 Инженерная практика", callback_data="menu_custom_development")],
        [
            InlineKeyboardButton("📋 Услуги", callback_data="menu_services"),
            InlineKeyboardButton("💰 Цены", callback_data="menu_prices"),
        ],
        [
            InlineKeyboardButton("🧪 Проверить договор", callback_data=contract_ai_menu_url()),
            InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
        ],
        [
            InlineKeyboardButton("📲 Оставить контакт", callback_data="menu_leave_contact"),
            InlineKeyboardButton("✉️ Личное обращение", callback_data="menu_personal_request"),
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
            InlineKeyboardButton("📚 Документы", callback_data="menu_documents"),
        ],
        [
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
        ],
    ]


def build_start_inline_menu(profile_cta_label: str = DEFAULT_PROFILE_CTA_LABEL):
    return [
        [InlineKeyboardButton(profile_cta_label, callback_data="menu_offer_profile")],
        [InlineKeyboardButton("⚖️ Юридическая практика", callback_data="legal_help_start")],
        [InlineKeyboardButton("🛠 Инженерная практика", callback_data="menu_custom_development")],
        [
            InlineKeyboardButton("🧪 Проверить договор", callback_data=contract_ai_menu_url()),
            InlineKeyboardButton("📞 Консультация", callback_data="menu_consultation"),
        ],
        [
            InlineKeyboardButton("📋 Услуги", callback_data="menu_services"),
            InlineKeyboardButton("💰 Цены", callback_data="menu_prices"),
        ],
        [
            InlineKeyboardButton("📲 Оставить контакт", callback_data="menu_leave_contact"),
            InlineKeyboardButton("❓ Помощь", callback_data="menu_help"),
        ],
        [
            InlineKeyboardButton("📚 Документы", callback_data="menu_documents"),
        ],
    ]


def build_quick_nav_menu(profile_cta_label: str = DEFAULT_PROFILE_CTA_LABEL):
    return [
        [InlineKeyboardButton(profile_cta_label, callback_data="menu_offer_profile")],
        [InlineKeyboardButton("⚖️ Юридическая практика", callback_data="legal_help_start")],
        [InlineKeyboardButton("🛠 Инженерная практика", callback_data="menu_custom_development")],
        [
            InlineKeyboardButton("🧭 Рабочий стол", callback_data="menu_dashboard"),
            InlineKeyboardButton("🧪 Проверить договор", callback_data=contract_ai_menu_url()),
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
            InlineKeyboardButton("📚 Документы", callback_data="menu_documents"),
        ],
    ]


WORKSPACE_INLINE_MENU = build_workspace_inline_menu()
START_INLINE_MENU = build_start_inline_menu()

QUICK_NAV_MENU = build_quick_nav_menu()


def append_inline_url_row(
    markup: InlineKeyboardMarkup,
    text: str,
    url: str | None,
    *,
    prepend: bool = False,
) -> InlineKeyboardMarkup:
    if not url:
        return markup
    rows = [list(row) for row in markup.inline_keyboard]
    if any(any(getattr(button, "url", None) == url for button in row) for row in rows):
        return markup
    link_row = [InlineKeyboardButton(text, url=url)]
    updated_rows = [link_row, *rows] if prepend else [*rows, link_row]
    return InlineKeyboardMarkup(updated_rows)

LEAD_MAGNET_MENU = [
    [InlineKeyboardButton("📞 Консультация 30 мин", callback_data="magnet_consultation")],
    [InlineKeyboardButton("📄 Чек-лист по договорам", callback_data="magnet_checklist")],
    [InlineKeyboardButton("🎯 Демо-анализ договора", callback_data="magnet_demo")],
    [InlineKeyboardButton("🧾 Образец AI-отчета", callback_data="magnet_sample_report")],
]

CONSENT_PDN_MENU = [
    [InlineKeyboardButton("✅ Даю согласие на обработку ПД", callback_data="consent_pdn_yes")],
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
    [InlineKeyboardButton("🔒 Соглашение о конфиденциальности", callback_data="nda:open")],
    [InlineKeyboardButton("📄 Договоры с юридической практикой", callback_data="sa_c:list")],
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
def lawyer_workspace_button():
    """Кнопка входа в рабочее место юриста для inline-меню.

    Возвращает None, если адрес не задан: кнопка, ведущая в никуда, хуже её
    отсутствия.
    """
    url = getattr(get_config(), "LAWYER_WORKSPACE_URL", "")
    if not url:
        return None
    return InlineKeyboardButton("🗂 Рабочее место", web_app=WebAppInfo(url=url))


def client_miniapp_button():
    """Кнопка мини-аппа для постоянной клавиатуры.

    Раньше "🧭 Рабочий стол" была обычной текстовой кнопкой: нажатие слало
    сообщение, а роутер по тексту открывал inline-меню. Мини-апп открывается
    сразу, без прохождения через отправку и разбор текста, — тот же выигрыш,
    что дала web_app-кнопка рабочего места юриста.

    Запасной вариант — старая текстовая кнопка: этот ряд клавиатуры не может
    остаться пустым, в отличие от необязательных кнопок вроде рабочего места
    юриста или перехода в бота дел.
    """
    url = getattr(get_config(), "CLIENT_MINIAPP_URL", "")
    if not url:
        return KeyboardButton("🧭 Рабочий стол")
    return KeyboardButton("📱 Мини-апп", web_app=WebAppInfo(url=url))


def build_client_reply_menu():
    """Постоянная клавиатура клиента."""
    return [[client_miniapp_button()]]


def build_admin_reply_menu():
    """Постоянная клавиатура владельца — то, что видно под полем ввода всегда.

    Рабочее место — на отдельной строке: у одиночной кнопки в reply-клавиатуре
    Telegram растягивает её на всю ширину ряда, и это ровно то, что делает
    ежедневный экран заметным, не отбирая при этом угловую кнопку меню у
    списка команд.
    """
    rows = [[client_miniapp_button()]]
    url = getattr(get_config(), "LAWYER_WORKSPACE_URL", "")
    if url:
        rows.append([KeyboardButton("🗂 Рабочее место", web_app=WebAppInfo(url=url))])
    return rows


def case_management_button():
    """Кнопка перехода в бота учёта судебных дел.

    Дела и клиентская переписка живут в разных системах: здесь — обращения и
    договоры, там — заседания и сроки. Пока это не один продукт, кнопка хотя
    бы убирает необходимость держать в голове, куда переключаться.

    Возвращает None, если адрес не задан, — кнопка, ведущая в никуда, хуже её
    отсутствия. По умолчанию не задан: имя того бота не было известно на
    момент, когда писался этот код.
    """
    username = getattr(get_config(), "CASE_MANAGEMENT_BOT_USERNAME", "")
    if not username:
        return None
    return InlineKeyboardButton(
        "📅 Судебные дела", url=f"https://t.me/{username}"
    )


def standalone_login_button():
    """Кнопка выдачи ссылки для входа в рабочее место вне Telegram.

    Сама ссылка на кнопке не помещается: токен подписывается временем клика,
    а не временем сборки меню, — обрабатывается отдельным callback'ом.
    Возвращает None, если секрет не задан: выдавать ссылку, которую сервер не
    сможет проверить, хуже её отсутствия.
    """
    if not getattr(get_config(), "LAWYER_SESSION_SECRET", ""):
        return None
    return InlineKeyboardButton("🔗 Ссылка для Safari", callback_data="admin_lawyer_link")


def build_admin_panel_menu():
    """Меню админ-панели. Рабочее место идёт первым: это ежедневный экран."""
    rows = []
    workspace = lawyer_workspace_button()
    if workspace is not None:
        rows.append([workspace])
    rows += ADMIN_PANEL_MENU[:-1]
    case_management = case_management_button()
    if case_management is not None:
        rows.append([case_management])
    login_link = standalone_login_button()
    if login_link is not None:
        rows.append([login_link])
    rows.append(ADMIN_PANEL_MENU[-1])
    return rows


ADMIN_PANEL_MENU = [
    [InlineKeyboardButton("⚖️ Юридические обращения и договоры", callback_data="sa_a:menu")],
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
