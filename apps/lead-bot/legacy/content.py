"""
Единый источник контента для legacy-бота.

Цель: убрать дубли текстов и контактов между prompts/handlers.
"""

from __future__ import annotations

from config import Config
from telegram_ui import normalize_button_text


config = Config()


CONTACTS = {
    "manager_name": "Андрей Попов",
    "telegram": "@AndrewPopov821667",
    "phone": "+7 (909) 233-09-09",
    "email": "a.popov.gv@gmail.com",
    "github": "github.com/Andrew821667",
}


MODULE_CATALOG = {
    "consultation_30m": "Консультация 30 минут по кейсу",
    "process_audit": "Диагностика процесса и roadmap внедрения",
    "lead_intake_pilot": "Пилот автоматизации входящих заявок",
    "contract_review_assist": "AI-помощник по договорной работе",
    "litigation_assist": "AI-помощник по судебным документам",
    "compliance_monitoring": "Комплаенс-мониторинг и контроль рисков",
    "legal_ops_outsource": "Юридический аутсорсинг с AI-поддержкой",
    "custom_integrations": "Кастомные интеграции (CRM/1C/ERP)",
}

CLIENT_PLATFORM = {
    "inhouse": {
        "title": "Инхаус-команда / юрдепартамент",
        "services": [
            "Intake и маршрутизация внутренних юридических запросов (SLA, приоритеты, контроль сроков).",
            "Договорной контур: предчек, redline-процессы, согласование с бизнесом.",
            "Контроль комплаенса и ПДн: чек-листы, триггеры рисков, регламентные напоминания.",
            "Внутренний AI-ассистент по базе знаний, шаблонам и типовым позициям команды.",
            "Legal Ops-аналитика: узкие места, метрики, roadmap автоматизации.",
        ],
        "pricing": [
            "Пилот (2-4 недели): от 150 000 ₽.",
            "Рабочий контур 1-2 процессов: от 300 000 ₽.",
            "Интеграции и масштабирование (CRM/1C/ERP): от 500 000 ₽.",
        ],
    },
    "law_firm": {
        "title": "Юрфирма / адвокатская практика",
        "services": [
            "Intake входящих обращений и первичная квалификация по практикам.",
            "Стандартизация клиентских документов и ускорение подготовки типовых комплектов.",
            "Контроль сроков по делам, задачам и точкам эскалации.",
            "AI-помощник по шаблонам, позициям и внутренним регламентам практики.",
            "Управляемая воронка заявок: от первого контакта до передачи в работу.",
        ],
        "pricing": [
            "Пилот intake + квалификация: от 120 000 ₽.",
            "Контур документов/дел и контроль сроков: от 250 000 ₽.",
            "Комплексная автоматизация практики: от 450 000 ₽.",
        ],
    },
    "business": {
        "title": "Собственник / руководитель бизнеса",
        "services": [
            "Единая точка входа в юридические задачи от бизнеса (без потерь и хаоса в коммуникациях).",
            "Быстрая оценка договорных рисков до передачи юристу.",
            "Типовые юридические процессы: шаблоны, согласование, напоминания и контроль этапов.",
            "Прозрачные статусы: что в работе, где узкое место, когда результат.",
            "Пошаговый формат внедрения без перегруза команды.",
        ],
        "pricing": [
            "Стартовый пилот на одной задаче: от 100 000 ₽.",
            "Рабочий контур на 1-2 направления: от 220 000 ₽.",
            "Сквозной контур с интеграциями: от 400 000 ₽.",
        ],
    },
    "universal": {
        "title": "Базовый профиль (уточняется)",
        "services": [
            "Диагностика текущего процесса и подбор реалистичного сценария автоматизации.",
            "Пилот intake/договоров/типовых процессов под вашу роль и объем.",
            "Дальнейшее масштабирование через legal ops и внутренние AI-инструменты.",
        ],
        "pricing": [
            "Пилотный сценарий: от 150 000 ₽.",
            "Рабочее решение с интеграциями: от 300 000 ₽.",
            "Комплексная автоматизация: от 500 000 ₽.",
        ],
    },
}


OFFER_PROFILE_LABELS = {
    "inhouse": "Инхаус-команда / юрдепартамент",
    "law_firm": "Юрфирма / адвокатская практика",
    "business": "Собственник / руководитель бизнеса",
    "universal": "Базовый профиль (уточняется)",
}


def _build_service_cards() -> list[str]:
    cards: list[str] = []
    index = 1
    for title in MODULE_CATALOG.values():
        cards.append(f"{index}) {title}")
        index += 1
    return cards


SERVICE_CARDS = _build_service_cards()
SERVICE_CATALOG_TEXT = "\n".join(f"• {item}" for item in SERVICE_CARDS)


def _detect_client_platform(lead: dict | None) -> str:
    if not lead:
        return "universal"
    haystack = " ".join(
        str(lead.get(field) or "").lower()
        for field in ("industry", "service_category", "specific_need", "pain_point", "company", "notes")
    )
    if any(token in haystack for token in ("юрфирм", "адвокат", "legal practice", "клиентск", "практик")):
        return "law_firm"
    if any(token in haystack for token in ("инхаус", "юрдеп", "корпорат", "комплаенс", "legal ops", "договор")):
        return "inhouse"
    if any(token in haystack for token in ("собствен", "директор", "ceo", "founder", "бизнес", "предприним")):
        return "business"
    return "universal"


def _platform_services_text(platform_key: str) -> str:
    platform = CLIENT_PLATFORM.get(platform_key) or CLIENT_PLATFORM["universal"]
    bullets = "\n".join(f"• {line}" for line in platform["services"])
    return (
        "🎯 НАПРАВЛЕНИЯ РАБОТЫ\n\n"
        f"Профиль клиента: {platform['title']}\n\n"
        "Формат оказания услуг на платформе:\n"
        f"{bullets}\n\n"
        "Если профиль определился неточно, используйте кнопку «🧩 Сменить профиль»."
    )


def _platform_prices_text(platform_key: str) -> str:
    platform = CLIENT_PLATFORM.get(platform_key) or CLIENT_PLATFORM["universal"]
    bullets = "\n".join(f"• {line}" for line in platform["pricing"])
    return (
        "💰 СТОИМОСТЬ И ФОРМАТЫ\n\n"
        f"Профиль клиента: {platform['title']}\n\n"
        "Ориентиры по стоимости:\n"
        f"{bullets}\n\n"
        "Точный расчет зависит от объема, интеграций и SLA. Для персонального расчета нажмите «📞 Консультация».\n"
        "Для просмотра цен в другом сценарии используйте кнопку «🧩 Сменить профиль»."
    )


def _resolve_client_platform(lead: dict | None, selected_profile: str | None) -> str:
    if selected_profile and selected_profile in CLIENT_PLATFORM:
        return selected_profile
    return _detect_client_platform(lead)


def offer_profile_panel_text(lead: dict | None = None, selected_profile: str | None = None) -> str:
    if selected_profile and selected_profile in OFFER_PROFILE_LABELS:
        current = OFFER_PROFILE_LABELS[selected_profile]
        mode = "ручной выбор"
    else:
        auto_key = _detect_client_platform(lead)
        current = OFFER_PROFILE_LABELS.get(auto_key, OFFER_PROFILE_LABELS["universal"])
        mode = "автоопределение"
    return (
        "🧩 СМЕНА ПРОФИЛЯ ПРЕДЛОЖЕНИЙ\n\n"
        "Вы можете переключать профиль и смотреть услуги/цены для разных ролей.\n\n"
        f"Текущий режим: {mode}\n"
        f"Активный профиль: {current}\n\n"
        "Выберите профиль кнопками ниже."
    )


def offer_profile_change_success_text(profile_key: str | None) -> str:
    if profile_key and profile_key in OFFER_PROFILE_LABELS:
        return (
            "✅ Профиль предложений обновлен.\n\n"
            f"Теперь услуги и цены показываю для: {OFFER_PROFILE_LABELS[profile_key]}.\n"
            "В любой момент можно вернуться в автоопределение."
        )
    return (
        "✅ Профиль переключен на автоопределение.\n\n"
        "Теперь услуги и цены снова подбираются автоматически по вашему контексту."
    )


def contact_lines(include_github: bool = False) -> str:
    lines = [
        f"📱 Telegram: {CONTACTS['telegram']}",
        f"📞 Телефон: {CONTACTS['phone']}",
        f"📧 Email: {CONTACTS['email']}",
    ]
    if include_github:
        lines.append(f"💻 GitHub: {CONTACTS['github']}")
    return "\n".join(lines)


def build_welcome_message(first_name: str) -> str:
    name = (first_name or "").strip() or "коллега"
    return (
        f"Здравствуйте, {name}.\n\n"
        "На связи ассистент Legal AI PRO и Андрея Попова.\n\n"
        "Помогу понять, как именно автоматизировать вашу юридическую функцию и связанные бизнес-процессы.\n\n"
        "Работаем с ключевыми направлениями:\n"
        "• входящие обращения и клиентский intake\n"
        "• договорная работа и согласование документов\n"
        "• претензионно-судебная работа и типовые юридические документы\n"
        "• комплаенс, ПДн и внутренний контроль\n"
        "• legal ops, база знаний и внутренние AI-ассистенты\n\n"
        "Разберем задачу, оценим риски и предложим реалистичный формат внедрения с понятным следующим шагом.\n\n"
        "Опишите кейс в 1-2 предложениях: где сейчас узкое место и какой результат нужен.\n\n"
        "Если вопрос нужно передать лично Андрею, нажмите «✉️ Личное обращение»."
    )


def build_business_welcome_message(first_name: str) -> str:
    return (
        f"{build_welcome_message(first_name)}\n\n"
        "Для быстрого старта используйте кнопки ниже: «📋 Услуги», «📞 Консультация», «📲 Оставить контакт»."
    )


HELP_MESSAGE = (
    "📖 ПОМОЩЬ\n\n"
    "Команды:\n"
    "/start - начать диалог\n"
    "/help - показать помощь\n"
    "/reset - очистить историю\n"
    "/menu - открыть меню\n\n"
    "/profile - мой профиль\n"
    "/documents - список документов\n\n"
    "Документы и управление данными:\n"
    "/privacy - политика обработки ПД\n"
    "/transborder_consent - условия трансграничной передачи\n"
    "/user_agreement - пользовательское соглашение\n"
    "/ai_policy - политика использования ИИ\n"
    "/marketing_consent - условия рассылок\n"
    "/consent_status - статус ваших согласий\n"
    "/export_data - экспорт ваших данных\n"
    "/correct_data <текст> - запрос на исправление данных\n"
    "/revoke_consent - отзыв согласия\n"
    "/delete_data - удалить персональные данные\n\n"
    "Можно просто написать вашу задачу в свободной форме."
)


WORKSPACE_TEXT = (
    "🧭 РАБОЧИЙ СТОЛ\n\n"
    "Здесь можно быстро:\n"
    "• посмотреть услуги и ориентиры по бюджету\n"
    "• выбрать сценарий автоматизации под ваш кейс\n"
    "• оставить контакт и сразу передать заявку команде\n"
    "• открыть профиль и документы\n"
    "• переключиться в режим личного обращения\n\n"
    "Выберите нужный раздел кнопками ниже."
)


MENU_HEADER_TEXT = WORKSPACE_TEXT


MENU_RESPONSES = {
    "menu_services": (
        "🎯 НАПРАВЛЕНИЯ РАБОТЫ:\n\n"
        f"{SERVICE_CATALOG_TEXT}\n\n"
        "Это наши действующие услуги. Подберем релевантный формат под ваш кейс."
    ),
    "menu_prices": (
        "💰 ОРИЕНТИРЫ ПО БЮДЖЕТУ:\n\n"
        "Точная стоимость зависит от объема документов, интеграций и глубины настройки.\n\n"
        "Обычно:\n"
        "• пилотный сценарий: от 150 000 ₽\n"
        "• рабочее решение с интеграциями: от 300 000 ₽\n"
        "• комплексная автоматизация: от 500 000 ₽\n\n"
        "Опишите текущий процесс, и я предложу реалистичный диапазон."
    ),
    "menu_help": (
        "❓ КАК Я ПОМОГАЮ:\n\n"
        "• отвечаю по направлениям и формату работ\n"
        "• уточняю контекст и помогаю сформулировать задачу\n"
        "• готовлю к консультации с командой\n\n"
        "Можно начать одной фразой: например, \"много времени уходит на согласование договоров\"."
    ),
    "menu_consultation": (
        "📞 КОНСУЛЬТАЦИЯ\n\n"
        "Оставьте номер телефона, и команда свяжется с вами в ближайшее рабочее время.\n"
        "Нажмите кнопку «📲 Оставить контакт» или отправьте номер в сообщении."
    ),
    "menu_leave_contact": (
        "📲 ОСТАВИТЬ КОНТАКТ\n\n"
        "Отправьте номер телефона одним сообщением в удобном формате.\n"
        "Примеры: +7 999 123-45-67 или 89991234567."
    ),
    "menu_profile": (
        "👤 ПРОФИЛЬ\n\n"
        "Показываю вашу карточку и контакты для связи. "
        "При необходимости сможете уточнить данные."
    ),
    "menu_documents": (
        "📚 ДОКУМЕНТЫ\n\n"
        "Открываю раздел с политиками, статусом согласий и управлением вашими данными."
    ),
    "menu_personal_request": (
        "✉️ ЛИЧНОЕ ОБРАЩЕНИЕ\n\n"
        "Этот режим нужен для личных сообщений Андрею Попову вне работы бота.\n"
        "После переключения бот перестанет отвечать, а вернуться можно будет кнопкой «↩️ Вернуться к боту»."
    ),
    "menu_dashboard": WORKSPACE_TEXT,
}


BUTTON_TO_MENU_KEY = {
    "🧭 Рабочий стол": "menu_dashboard",
    "📋 Меню услуг": "menu_dashboard",
    "📋 Услуги": "menu_services",
    "💰 Цены": "menu_prices",
    "❓ Помощь": "menu_help",
    "📞 Консультация": "menu_consultation",
    "📲 Оставить контакт": "menu_leave_contact",
    "📲 Контакт": "menu_leave_contact",
    "👤 Профиль": "menu_profile",
    "🧩 Сменить профиль": "menu_offer_profile",
    "📚 Документы": "menu_documents",
    "✉️ Личное обращение": "menu_personal_request",
}


def menu_response_by_key(
    key: str,
    lead: dict | None = None,
    selected_profile: str | None = None,
) -> str:
    if key == "menu_services":
        return _platform_services_text(_resolve_client_platform(lead, selected_profile))
    if key == "menu_prices":
        return _platform_prices_text(_resolve_client_platform(lead, selected_profile))
    if key == "menu_offer_profile":
        return offer_profile_panel_text(lead=lead, selected_profile=selected_profile)
    return MENU_RESPONSES.get(key, "Выберите пункт меню.")


def menu_response_by_button(
    button_text: str,
    lead: dict | None = None,
    selected_profile: str | None = None,
) -> str:
    normalized_text = normalize_button_text(button_text)
    key = BUTTON_TO_MENU_KEY.get(button_text)
    if not key:
        for button_key, menu_key in BUTTON_TO_MENU_KEY.items():
            if normalize_button_text(button_key) == normalized_text:
                key = menu_key
                break
    if not key:
        return "Выберите пункт меню."
    return menu_response_by_key(key, lead=lead, selected_profile=selected_profile)


LEAD_MAGNET_OFFER_TEXT = (
    "🎁 Полезные форматы на выбор:\n\n"
    "📞 Консультация 30 минут\n"
    "📄 Чек-лист «15 типовых ошибок в договорах»\n"
    "🎯 Демо-анализ вашего договора\n\n"
    "Выберите, что будет полезнее именно сейчас."
)

CONSULTATION_CTA_TEXT = (
    "Если хотите, можем перейти к следующему практическому шагу."
)

CONSULTATION_CTA_BUTTON_TEXT = "📞 Заказать консультацию"


LEAD_MAGNET_SELECTION_MESSAGES = {
    "consultation": (
        "Отличный выбор.\n\n"
        "Отправьте номер телефона, и команда согласует время консультации."
    ),
    "checklist": (
        "Отлично, отправим чек-лист.\n\n"
        "Укажите email, куда направить материал."
    ),
    "demo": (
        "Отлично, подготовим демо-анализ.\n\n"
        "Пришлите документ и укажите email для отправки результата."
    ),
}


LEAD_MAGNET_SENT_MESSAGES = {
    "consultation": (
        "✅ Спасибо, подтверждение отправлено.\n\n"
        "Команда свяжется с вами в течение рабочего дня."
    ),
    "checklist": (
        "✅ Готово, чек-лист отправлен.\n\n"
        "Проверьте почту, включая папку «Спам»."
    ),
    "demo": (
        "✅ Готово, инструкции отправлены.\n\n"
        "Если удобнее, можно оперативно связаться:\n"
        f"{contact_lines()}"
    ),
}


HANDOFF_ACK_TEXT = (
    "Принял запрос. Передаю диалог команде.\n\n"
    "Мы напишем вам в ближайшее рабочее время в Telegram."
)


DIRECT_CONTACTS_TEXT = (
    "Если нужно срочно, можно связаться напрямую:\n"
    f"{contact_lines()}"
)


BUSINESS_MENU_HINT_TEXT = (
    "💡 Для быстрого доступа используйте кнопки ниже.\n"
    "Если у вас личный вопрос к Андрею Попову, нажмите «✉️ Личное обращение».\n"
    "Для передачи контакта в один шаг нажмите «📲 Оставить контакт».\n"
    "Командой `/menu` рабочий стол можно открыть повторно."
)


REPEAT_LOOP_FALLBACK_TEXT = (
    "Похоже, мы зациклились на одном и том же вопросе.\n\n"
    "Передам диалог команде, чтобы вы получили точный ответ без задержек.\n\n"
    "Если срочно, используйте контакты:\n"
    f"{contact_lines()}"
)


CONSENT_STEP_1_TEXT = (
    "📋 Согласие на обработку ПД и трансграничную передачу\n\n"
    "Чтобы продолжить, нужно единое согласие:\n"
    "• имя и контакты для связи по вашему запросу\n"
    "• данные о задаче для подготовки консультации\n"
    "• хранение в защищенной базе до отзыва согласия\n"
    "• трансграничная передача сообщений в внешние LLM-сервисы для AI-режима\n\n"
    "Ваши права:\n"
    "• запросить экспорт данных\n"
    "• запросить исправление\n"
    "• отозвать согласие и удалить данные\n\n"
    "Нажимая кнопку ниже, вы подтверждаете это единое согласие."
)


CONSENT_TRANSBORDER_TEXT = (
    "🌍 Согласие на трансграничную передачу данных для ИИ\n\n"
    "Для AI-ответов сообщения отправляются в внешние LLM-сервисы.\n"
    "Перед отправкой мы не передаем ваши контактные данные как отдельные поля.\n\n"
    "Если не дать это согласие:\n"
    "• можно пользоваться меню и оставить заявку\n"
    "• AI-режим анализа кейса будет отключен\n\n"
    "Разрешаете использовать ИИ-режим с трансграничной передачей?"
)


TRANSBORDER_REQUIRED_TEXT = (
    "⚠️ Для AI-анализа вашего кейса нужно согласие на трансграничную передачу данных.\n\n"
    "Без него доступны: меню, консультация и ручная передача запроса команде."
)


CONSENT_DENIED_TEXT = (
    "Понял. Без согласия на обработку ПД и трансграничную передачу я не могу продолжить персональный сценарий.\n\n"
    "Когда будете готовы, отправьте /start."
)


CONSENT_REVOKED_TEXT = (
    "✅ Согласие отозвано.\n\n"
    "Персональные данные в анкете анонимизированы, история диалога удалена.\n"
    "Для повторного запуска отправьте /start."
)


def consent_status_text(consent: dict) -> str:
    consent_given = bool(consent.get("consent_given"))
    transborder = bool(consent.get("transborder_consent"))
    revoked = bool(consent.get("consent_revoked"))
    consent_date = consent.get("consent_date") or "—"
    transborder_date = consent.get("transborder_consent_date") or "—"
    revoked_date = consent.get("consent_revoked_at") or "—"
    return (
        "📑 Статус согласий\n\n"
        f"• Обработка ПД: {'✅' if consent_given else '❌'}\n"
        f"• Дата согласия: {consent_date}\n"
        f"• Трансграничная передача: {'✅' if transborder else '❌'}\n"
        f"• Дата трансграничного согласия: {transborder_date}\n"
        f"• Согласие отозвано: {'✅' if revoked else '❌'}\n"
        f"• Дата отзыва: {revoked_date}"
    )


def consent_user_status_text(consent: dict) -> str:
    consent_given = bool(consent.get("consent_given"))
    transborder = bool(consent.get("transborder_consent"))
    revoked = bool(consent.get("consent_revoked"))

    if revoked:
        return "⚠️ Согласия отозваны. Для повторного запуска отправьте /start."
    if consent_given and transborder:
        return "✅ Согласия на обработку ПД и трансграничную передачу уже даны."
    if consent_given:
        return "✅ Согласие на обработку ПД уже дано."
    return "❌ Согласия еще не даны."


def privacy_policy_text() -> str:
    return (
        "📄 Политика обработки персональных данных\n\n"
        "Оператор обрабатывает только данные, необходимые для связи и консультации.\n"
        "Подробная версия:\n"
        f"{config.PRIVACY_POLICY_URL}\n\n"
        f"Контакт по вопросам ПД: {config.PRIVACY_CONTACT_EMAIL}"
    )


def transborder_policy_text() -> str:
    return (
        "📄 Согласие на трансграничную передачу данных\n\n"
        "Нужно для работы ИИ-функций (LLM-сервисы).\n"
        "Подробная версия:\n"
        f"{config.TRANSBORDER_CONSENT_URL}"
    )


def documents_list_text() -> str:
    return (
        "📚 Документы и права пользователя\n\n"
        "Выберите документ кнопками ниже или используйте команды:\n"
        "/privacy\n"
        "/transborder_consent\n"
        "/user_agreement\n"
        "/ai_policy\n"
        "/marketing_consent\n\n"
        "Управление данными:\n"
        "/consent_status\n"
        "/export_data\n"
        "/correct_data <текст>\n"
        "/revoke_consent\n"
        "/delete_data"
    )


def user_agreement_text() -> str:
    return (
        "📄 Пользовательское соглашение\n\n"
        "Актуальная редакция:\n"
        f"{config.USER_AGREEMENT_URL}"
    )


def ai_policy_text() -> str:
    return (
        "📄 Политика использования ИИ\n\n"
        "Актуальная редакция:\n"
        f"{config.AI_POLICY_URL}"
    )


def marketing_consent_text() -> str:
    return (
        "📄 Согласие на информационные/маркетинговые рассылки\n\n"
        "Актуальная редакция:\n"
        f"{config.MARKETING_CONSENT_URL}"
    )


def export_data_text(payload: dict) -> str:
    user = payload.get("user") or {}
    lead = payload.get("lead") or {}
    consent = payload.get("consent") or {}
    return (
        "📊 Ваши данные в системе\n\n"
        "Профиль:\n"
        f"• Telegram ID: {user.get('telegram_id')}\n"
        f"• Username: @{user.get('username') or 'не указан'}\n"
        f"• Имя: {user.get('first_name') or 'не указано'}\n"
        f"• Фамилия: {user.get('last_name') or 'не указана'}\n\n"
        "Анкета лида:\n"
        f"• Имя: {lead.get('name') or 'не указано'}\n"
        f"• Email: {lead.get('email') or 'не указан'}\n"
        f"• Телефон: {lead.get('phone') or 'не указан'}\n"
        f"• Компания: {lead.get('company') or 'не указана'}\n\n"
        f"{consent_status_text(consent)}"
    )
