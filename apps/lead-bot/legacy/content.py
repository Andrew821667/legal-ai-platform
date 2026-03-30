"""
Единый источник контента для legacy-бота.

Цель: убрать дубли текстов и контактов между prompts/handlers.
"""

from __future__ import annotations

from html import escape

from config import get_config
from telegram_ui import normalize_button_text


config = get_config()


def _e(value: object) -> str:
    return escape(str(value or ""))


CONTACTS = {
    "manager_name": "Андрей Попов",
    "telegram": "@AndrewPopov821667",
    "phone": "+7 (909) 233-09-09",
    "email": "a.popov.gv@gmail.com",
    "github": "github.com/Andrew821667",
}

CHANNEL_BUTTON_TEXT = "📰 Канал Legal AI PRO"
CONTRACT_AI_BUTTON_TEXT = "🖥 Открыть модуль проверки договоров"


MODULE_CATALOG = {
    "consultation_30m": "Консультация 30 минут по кейсу",
    "process_audit": "Диагностика процесса и план внедрения",
    "lead_intake_pilot": "Пилот по приему и разбору входящих обращений",
    "contract_review_assist": "ИИ-помощник для проверки договоров",
    "litigation_assist": "ИИ-помощник по судебным документам",
    "compliance_monitoring": "Контроль обязательных требований и рисков",
    "legal_ops_outsource": "Настройка и сопровождение юридических процессов с ИИ-поддержкой",
    "custom_integrations": "Кастомные интеграции (CRM/1C/ERP)",
}

CLIENT_PLATFORM = {
    "inhouse": {
        "title": "Юридический отдел компании",
        "services": [
            "Прием и распределение внутренних юридических запросов: приоритеты, очереди и контроль сроков.",
            "Проверка договоров до согласования: быстрый первичный разбор, правки и комментарии для бизнеса.",
            "Контроль обязательных требований и ПДн: чек-листы, сигналы рисков и регламентные напоминания.",
            "Внутренний ИИ-помощник по базе знаний, шаблонам и типовым позициям команды.",
            "Аналитика юридического процесса: узкие места, метрики и план автоматизации.",
        ],
        "pricing": [
            "Пилотный запуск на 2-4 недели: от 150 000 ₽.",
            "Рабочий контур 1-2 процессов: от 300 000 ₽.",
            "Интеграции и масштабирование (CRM/1C/ERP): от 500 000 ₽.",
        ],
    },
    "law_firm": {
        "title": "Юрфирма или адвокатская практика",
        "services": [
            "Прием входящих обращений и первичная квалификация по практикам.",
            "Стандартизация клиентских документов и ускорение подготовки типовых комплектов.",
            "Контроль сроков по делам, задачам и точкам эскалации.",
            "ИИ-помощник по шаблонам, позициям и внутренним регламентам практики.",
            "Управляемая воронка заявок: от первого контакта до передачи в работу.",
        ],
        "pricing": [
            "Пилотный запуск приема и квалификации обращений: от 120 000 ₽.",
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
        "title": "Общий профиль (уточняется)",
        "services": [
            "Диагностика текущего процесса и подбор реалистичного сценария автоматизации.",
            "Пилотный запуск для входящих запросов, договоров или типовых процессов под вашу роль и объем.",
            "Дальнейшее масштабирование через организацию юридической работы и внутренние ИИ-инструменты.",
        ],
        "pricing": [
            "Пилотный сценарий: от 150 000 ₽.",
            "Рабочее решение с интеграциями: от 300 000 ₽.",
            "Комплексная автоматизация: от 500 000 ₽.",
        ],
    },
}


OFFER_PROFILE_LABELS = {
    "inhouse": "Юридический отдел компании",
    "law_firm": "Юрфирма или адвокатская практика",
    "business": "Собственник / руководитель бизнеса",
    "universal": "Общий профиль (уточняется)",
}

OFFER_PROFILE_SHORT_LABELS = {
    "inhouse": "Юр. отдел",
    "law_firm": "Юрфирма",
    "business": "Бизнес",
    "universal": "Общий",
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
        "<b>🎯 Направления работы</b>\n\n"
        f"<b>Профиль клиента:</b> {_e(platform['title'])}\n\n"
        "Здесь показываю практические форматы работы: от <b>быстрых пилотов</b> до "
        "<b>рабочего контура автоматизации</b>.\n\n"
        "<b>Формат оказания услуг на платформе:</b>\n"
        f"{bullets}\n\n"
        "Если пока неясно, что подойдет именно вам, просто опишите задачу своими словами — "
        "я помогу сузить сценарий и предложу следующий шаг.\n\n"
        "Если профиль определился неточно, переключите верхнюю кнопку <b>«🎯 Профиль услуг»</b>."
    )


def _platform_prices_text(platform_key: str) -> str:
    platform = CLIENT_PLATFORM.get(platform_key) or CLIENT_PLATFORM["universal"]
    bullets = "\n".join(f"• {line}" for line in platform["pricing"])
    return (
        "<b>💰 Стоимость и форматы</b>\n\n"
        f"<b>Профиль клиента:</b> {_e(platform['title'])}\n\n"
        "<b>Ориентиры по стоимости:</b>\n"
        f"{bullets}\n\n"
        "Точный расчет зависит от объема задач, интеграций и требуемой скорости работы. "
        "Для персонального расчета нажмите <b>«📞 Консультация»</b>.\n"
        "Для просмотра цен в другом сценарии переключите верхнюю кнопку <b>«🎯 Профиль услуг»</b>."
    )


def _resolve_client_platform(lead: dict | None, selected_profile: str | None) -> str:
    if selected_profile and selected_profile in CLIENT_PLATFORM:
        return selected_profile
    return _detect_client_platform(lead)


def _active_offer_profile_state(lead: dict | None = None, selected_profile: str | None = None) -> tuple[str, str, str]:
    if selected_profile and selected_profile in OFFER_PROFILE_LABELS:
        return selected_profile, OFFER_PROFILE_LABELS[selected_profile], "ручной выбор"
    auto_key = _detect_client_platform(lead)
    return auto_key, OFFER_PROFILE_LABELS.get(auto_key, OFFER_PROFILE_LABELS["universal"]), "автоопределение"


def offer_profile_cta_label(lead: dict | None = None, selected_profile: str | None = None) -> str:
    profile_key, _, mode = _active_offer_profile_state(lead=lead, selected_profile=selected_profile)
    short_label = OFFER_PROFILE_SHORT_LABELS.get(profile_key, OFFER_PROFILE_SHORT_LABELS["universal"])
    suffix = "вручную" if mode == "ручной выбор" else "авто"
    return f"🎯 Профиль услуг: {short_label} ({suffix})"


def offer_profile_panel_text(lead: dict | None = None, selected_profile: str | None = None) -> str:
    _, current, mode = _active_offer_profile_state(lead=lead, selected_profile=selected_profile)
    return (
        "<b>🧩 Смена профиля предложений</b>\n\n"
        "Сначала выберите профиль услуг. От него зависят направления, ориентиры по бюджету и сценарий консультации.\n\n"
        f"<b>Текущий режим:</b> {_e(mode)}\n"
        f"<b>Активный профиль:</b> {_e(current)}\n\n"
        "Если услуги или цены выглядят нерелевантно, начните именно с этого экрана.\n\n"
        "Выберите профиль кнопками ниже."
    )


def offer_profile_change_success_text(profile_key: str | None) -> str:
    if profile_key and profile_key in OFFER_PROFILE_LABELS:
        return (
            "<b>✅ Профиль предложений обновлен.</b>\n\n"
            f"Теперь услуги и цены показываю для: <b>{_e(OFFER_PROFILE_LABELS[profile_key])}</b>.\n"
            "В любой момент можно вернуться в автоопределение."
        )
    return (
        "<b>✅ Профиль переключен на автоопределение.</b>\n\n"
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


def public_channel_url() -> str | None:
    direct_url = (config.TELEGRAM_CHANNEL_URL or "").strip()
    if direct_url:
        if direct_url.startswith(("http://", "https://")):
            return direct_url
        return f"https://{direct_url.lstrip('/')}"

    username = (config.TELEGRAM_CHANNEL_USERNAME or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}"
    return None


def contract_ai_public_url() -> str | None:
    direct_url = (config.CONTRACT_AI_SYSTEM_URL or "").strip()
    if not direct_url:
        return None
    if direct_url.startswith(("http://", "https://")):
        return direct_url
    return f"https://{direct_url.lstrip('/')}"


def channel_nurture_text() -> str:
    if not public_channel_url():
        return ""
    return (
        "Если к консультации пока не готовы, можно начать с канала Legal AI PRO: "
        "там короткие практические разборы по автоматизации юридической работы, договорам и внедрению ИИ."
    )


def post_contact_channel_text() -> str:
    if not public_channel_url():
        return ""
    return (
        "Пока команда готовит ответ, можно подписаться на канал Legal AI PRO: "
        "там регулярные разборы, кейсы внедрения и полезные сигналы рынка."
    )


def with_channel_nurture(text: str, *, after_contact: bool = False) -> str:
    extra = post_contact_channel_text() if after_contact else channel_nurture_text()
    if not extra:
        return text
    return f"{text}\n\n{extra}"


def assistant_chat_hint_text() -> str:
    return (
        "💬 <b>Необязательно ждать подходящую кнопку — можно просто написать задачу боту.</b>\n"
        "<i>Например:</i>\n"
        "• <i>«хотим внедрить ИИ в договорную работу»</i>\n"
        "• <i>«юристы тонут во входящих запросах»</i>"
    )


def with_assistant_chat_hint(text: str) -> str:
    hint = assistant_chat_hint_text()
    if hint in text:
        return text
    return f"{text}\n\n{hint}"


def contract_ai_entry_hint() -> str:
    if not contract_ai_public_url():
        return ""
    return "Если доступ уже согласован, можно сразу открыть внешний модуль кнопкой ниже."


def legal_disclaimer_short_text() -> str:
    return (
        "<i>Важно: ответы бота носят информационный характер "
        "и не заменяют персональную юридическую консультацию.</i>"
    )


def _operator_identity_text() -> str:
    parts = [config.OPERATOR_NAME]
    if config.OPERATOR_INN:
        parts.append(f"ИНН {config.OPERATOR_INN}")
    if config.OPERATOR_DETAILS:
        parts.append(config.OPERATOR_DETAILS)
    return _e(", ".join(part for part in parts if part))


def pdn_consent_required_text(action_label: str | None = None) -> str:
    action_prefix = (
        f"Чтобы перейти к «{_e(action_label)}», нужно согласие на обработку персональных данных."
        if action_label
        else "Чтобы продолжить персональный сценарий, нужно согласие на обработку персональных данных."
    )
    return (
        f"⚠️ <b>{action_prefix}</b>\n\n"
        "Без согласия можно смотреть меню, услуги, цены и документы.\n"
        "После подтверждения станут доступны <b>передача контакта</b>, <b>получение материалов</b> и <b>персональная заявка</b>."
    )


def build_welcome_message(first_name: str) -> str:
    name = _e((first_name or "").strip() or "коллега")
    return (
        f"<b>Здравствуйте, {name}.</b>\n\n"
        "<b>Legal AI PRO</b> — это ИИ-помощник по автоматизации юридических процессов.\n"
        "Мы помогаем внедрять ИИ в <b>юридические и бизнес-процессы</b>: "
        "быстрее разбирать договоры, не терять юридические запросы и убирать "
        "ручную рутину без лишней сложности.\n\n"
        "<b>Когда это особенно полезно:</b>\n"
        "• договоры долго согласуются\n"
        "• вопросы к юристам приходят хаотично\n"
        "• много ручной переписки и повторяющихся действий\n"
        "• нужен понятный первый шаг, а не большой проект «сразу на все»\n\n"
        "Можно начать без специальных терминов: посмотреть услуги, цены, "
        "проверку договора или просто описать задачу обычными словами.\n\n"
        f"{assistant_chat_hint_text()}\n\n"
        f"{legal_disclaimer_short_text()}"
    )


def build_start_entry_text(
    first_name: str | None = None,
    *,
    lead: dict | None = None,
    selected_profile: str | None = None,
    emphasize_profile_choice: bool = True,
) -> str:
    name = _e((first_name or "").strip() or "коллега")
    _, active_profile_label, mode = _active_offer_profile_state(lead=lead, selected_profile=selected_profile)
    profile_hint = ""
    if emphasize_profile_choice:
        profile_hint = (
            "👉 <b>Сначала нажмите верхнюю кнопку «🎯 Профиль услуг».</b>\n"
            "Так я быстрее покажу подходящие услуги, цены и следующий шаг именно под вашу роль.\n\n"
        )
    return (
        f"<b>Здравствуйте, {name}.</b>\n\n"
        "<b>Legal AI PRO</b> — это ИИ-помощник по автоматизации юридических процессов.\n"
        "Мы помогаем внедрять ИИ в <b>юридические и бизнес-процессы</b>: "
        "от проверки договоров и обработки запросов до пилотов и рабочих контуров автоматизации.\n\n"
        f"{profile_hint}"
        "<b>С чего удобно начать:</b>\n"
        "1. <b>🧪 Проверить договор</b> — если у вас уже есть документ\n"
        "2. <b>📞 Консультация</b> — если нужно обсудить задачу с человеком\n"
        "3. <b>📋 Услуги</b> и <b>💰 Цены</b> — если вы только знакомитесь с возможностями\n\n"
        f"<b>Сейчас активен:</b> {_e(active_profile_label)}\n"
        f"<b>Режим:</b> {_e(mode)}\n\n"
        "Меню и документы доступны сразу. Для персональной заявки, контакта и ИИ-разбора "
        "я сначала попрошу согласие на обработку данных.\n\n"
        f"{assistant_chat_hint_text()}\n\n"
        f"{legal_disclaimer_short_text()}"
    )


def build_business_welcome_message(first_name: str) -> str:
    return (
        f"{build_welcome_message(first_name)}\n\n"
        "<b>Для быстрого старта:</b>\n"
        "• <b>🧪 Проверить договор</b> — если уже есть документ\n"
        "• <b>📞 Консультация</b> — если нужно обсудить задачу\n"
        "• <b>📲 Оставить контакт</b> — если хотите, чтобы команда вернулась к вам"
    )


HELP_MESSAGE = (
    "<b>📖 Помощь</b>\n\n"
    "Я помогаю разобраться, <b>где именно ИИ даст эффект в юридической и бизнес-работе</b>, "
    "и подсказываю следующий шаг без сложных терминов.\n\n"
    "<b>Основные команды:</b>\n"
    "<code>/start</code> - начать диалог\n"
    "<code>/help</code> - показать помощь\n"
    "<code>/reset</code> - очистить историю\n"
    "<code>/menu</code> - открыть меню\n\n"
    "<code>/profile</code> - мой профиль\n"
    "<code>/documents</code> - список документов\n\n"
    "<b>Документы и управление данными:</b>\n"
    "<code>/privacy</code> - политика обработки ПД\n"
    "<code>/transborder_consent</code> - условия трансграничной передачи\n"
    "<code>/user_agreement</code> - пользовательское соглашение\n"
    "<code>/ai_policy</code> - политика использования ИИ\n"
    "<code>/marketing_consent</code> - условия рассылок\n"
    "<code>/consent_status</code> - статус ваших согласий\n"
    "<code>/export_data</code> - экспорт ваших данных\n"
    "<code>/correct_data &lt;текст&gt;</code> - запрос на исправление данных\n"
    "<code>/revoke_consent</code> - отзыв согласия\n"
    "<code>/delete_data</code> - удалить персональные данные\n\n"
    "Можно просто написать вашу задачу в свободной форме.\n"
    "Например: <i>«хотим внедрить ИИ в согласование договоров»</i> или "
    "<i>«у нас юристы тонут во входящих запросах»</i>.\n\n"
    f"{legal_disclaimer_short_text()}"
)


def build_workspace_text(
    lead: dict | None = None,
    selected_profile: str | None = None,
    emphasize_profile_choice: bool = False,
    include_context_intro: bool = False,
    first_name: str | None = None,
) -> str:
    if include_context_intro:
        return build_start_entry_text(
            first_name=first_name,
            lead=lead,
            selected_profile=selected_profile,
            emphasize_profile_choice=emphasize_profile_choice,
        )

    _, active_profile_label, mode = _active_offer_profile_state(lead=lead, selected_profile=selected_profile)
    intro_parts: list[str] = []
    if emphasize_profile_choice:
        intro_parts.append(
            "👉 <b>Начните с верхней кнопки «🎯 Профиль услуг».</b>\n"
            "Так я быстрее покажу подходящие услуги, цены и маршрут консультации."
        )
    intro = "\n\n".join(intro_parts)
    if intro:
        intro = f"{intro}\n\n"
    return (
        "<b>🧭 Рабочий стол</b>\n\n"
        f"{intro}"
        "Здесь собраны основные разделы: услуги, цены, ИИ-проверка договора, консультация и документы.\n"
        "Если проще, можно вообще не идти по меню, а сразу написать задачу обычными словами.\n\n"
        "Если профиль определился неточно, переключите верхнюю кнопку «🎯 Профиль услуг».\n\n"
        f"<b>Сейчас активен:</b> {_e(active_profile_label)}\n"
        f"<b>Режим:</b> {_e(mode)}\n\n"
        "<b>Что можно сделать сейчас:</b>\n"
        "• посмотреть услуги и ориентиры по бюджету\n"
        "• открыть ИИ-проверку договора или описать задачу своими словами\n"
        "• запросить консультацию, оставить контакт или обсудить внедрение ИИ\n\n"
        "Для персональной заявки и ИИ-разбора я сначала попрошу согласие на обработку данных.\n\n"
        "Выберите нужный раздел кнопками ниже."
    )


WORKSPACE_TEXT = build_workspace_text()


MENU_HEADER_TEXT = WORKSPACE_TEXT


MENU_RESPONSES = {
    "menu_services": (
        "<b>🎯 Чем мы можем быть полезны</b>\n\n"
        f"{SERVICE_CATALOG_TEXT}\n\n"
        "Это основные форматы работы: от быстрых пилотов до рабочего контура автоматизации.\n"
        "Если пока неясно, что подойдет именно вам, просто опишите задачу своими словами — "
        "я помогу сузить сценарий и предложу следующий шаг."
    ),
    "menu_prices": (
        "<b>💰 Ориентиры по бюджету</b>\n\n"
        "Точная стоимость зависит от объема задач, количества документов, интеграций и глубины настройки.\n\n"
        "<b>Обычно:</b>\n"
        "• пилотный сценарий: от 150 000 ₽\n"
        "• рабочее решение с интеграциями: от 300 000 ₽\n"
        "• комплексная автоматизация: от 500 000 ₽\n\n"
        "Если напишете, что именно нужно ускорить или упростить, я предложу более точный диапазон."
    ),
    "menu_help": (
        "<b>❓ Как я помогаю</b>\n\n"
        "• объясняю простыми словами, как внедрять ИИ в юридические и бизнес-процессы\n"
        "• помогаю понять, какой формат вам подходит\n"
        "• собираю контекст перед консультацией с командой\n\n"
        "<b>Можно начать одной фразой, например:</b>\n"
        "«долго согласовываем договоры»\n"
        "«теряются юридические запросы»\n"
        "«нужен порядок в юридической работе»\n"
        "«хотим внедрить ИИ в юридическую функцию»."
    ),
    "menu_consultation": (
        "<b>📞 Консультация</b>\n\n"
        "Этот маршрут подходит, если хотите обсудить задачу с человеком, сверить приоритеты "
        "и понять, с чего лучше начать внедрение.\n\n"
        "Оставьте номер телефона, и команда свяжется с вами в ближайшее рабочее время.\n"
        "Нажмите кнопку <b>«📲 Оставить контакт»</b> или отправьте номер в сообщении."
    ),
    "menu_contract_ai": (
        "<b>🧪 Проверка договора</b>\n\n"
        "<b>Contract_AI_System</b> — сервис AI-анализа договоров.\n\n"
        "<b>Что умеет:</b>\n"
        "• полный анализ рисков договора за минуты\n"
        "• проверка на соответствие стандартам компании\n"
        "• рекомендации по правкам\n"
        "• оценка баланса прав и обязанностей сторон\n\n"
        "Отправьте файл договора (PDF, DOCX, DOC, TXT) прямо сюда — "
        "и получите краткий отчёт с ключевыми рисками и рекомендациями."
    ),
    "menu_leave_contact": (
        "<b>📲 Оставить контакт</b>\n\n"
        "Отправьте номер телефона одним сообщением в удобном формате.\n"
        "Примеры: +7 999 123-45-67 или 89991234567."
    ),
    "menu_profile": (
        "<b>👤 Профиль</b>\n\n"
        "Показываю вашу карточку и контакты для связи. "
        "При необходимости сможете уточнить данные."
    ),
    "menu_documents": (
        "<b>📚 Документы</b>\n\n"
        "Открываю раздел с политиками, статусом согласий и управлением вашими данными."
    ),
    "menu_personal_request": (
        "<b>✉️ Личное обращение</b>\n\n"
        "Этот режим нужен для личных сообщений Андрею Попову вне работы бота.\n"
        "После переключения бот перестанет отвечать, а вернуться можно будет кнопкой <b>«↩️ Вернуться к боту»</b>."
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
    "🧪 Проверить договор": "menu_contract_ai",
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
        return with_channel_nurture(with_assistant_chat_hint(_platform_services_text(_resolve_client_platform(lead, selected_profile))))
    if key == "menu_prices":
        return with_channel_nurture(with_assistant_chat_hint(_platform_prices_text(_resolve_client_platform(lead, selected_profile))))
    if key == "menu_offer_profile":
        return with_assistant_chat_hint(offer_profile_panel_text(lead=lead, selected_profile=selected_profile))
    if key == "menu_dashboard":
        return build_workspace_text(lead=lead, selected_profile=selected_profile)
    response = MENU_RESPONSES.get(key, "Выберите пункт меню.")
    if key in {"menu_help", "menu_contract_ai", "menu_consultation", "menu_leave_contact", "menu_profile", "menu_documents"}:
        response = with_assistant_chat_hint(response)
    if key in {"menu_help", "menu_contract_ai"}:
        if key == "menu_contract_ai":
            hint = contract_ai_entry_hint()
            if hint:
                response = f"{response}\n\n{hint}"
        return with_channel_nurture(response)
    return response


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
    "<b>🎁 Полезные первые шаги</b>\n\n"
    "📞 Консультация 30 минут\n"
    "📄 Чек-лист «15 типовых ошибок в договорах»\n"
    "🎯 Демонстрационный разбор вашего договора\n"
    "🧾 Пример отчета по договору\n\n"
    "Выберите, что будет полезнее именно сейчас."
)

CONSULTATION_CTA_TEXT = (
    "<b>Если хотите, можем перейти к следующему практическому шагу.</b>"
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
        "Отлично, подготовим демонстрационный разбор.\n\n"
        "Пришлите документ и укажите email для отправки результата."
    ),
    "sample_report": (
        "Отлично, отправим пример отчета по договору.\n\n"
        "Укажите email, куда направить материал."
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
    "sample_report": (
        "✅ Готово, пример отчета отправлен.\n\n"
        "Проверьте почту, включая папку «Спам»."
    ),
}


HANDOFF_ACK_TEXT = (
    "<b>Принял запрос.</b> Передаю диалог команде.\n\n"
    "Мы напишем вам в ближайшее рабочее время в Telegram."
)


DIRECT_CONTACTS_TEXT = (
    "<b>Если нужно срочно, можно связаться напрямую:</b>\n"
    f"{contact_lines()}"
)


BUSINESS_MENU_HINT_TEXT = (
    "💡 Для быстрого доступа используйте кнопки ниже.\n"
    "Если у вас личный вопрос к Андрею Попову, нажмите «✉️ Личное обращение».\n"
    "Для передачи контакта в один шаг нажмите «📲 Оставить контакт».\n"
    "Командой `/menu` рабочий стол можно открыть повторно."
)


REPEAT_LOOP_FALLBACK_TEXT = (
    "<b>Похоже, мы зациклились на одном и том же вопросе.</b>\n\n"
    "Передам диалог команде, чтобы вы получили точный ответ без задержек.\n\n"
    "<b>Если срочно, используйте контакты:</b>\n"
    f"{contact_lines()}"
)


CONSENT_STEP_1_TEXT = (
    "<b>📋 Согласие на обработку персональных данных</b>\n\n"
    f"Оператор: {_operator_identity_text()}\n\n"
    "<b>Для персональной заявки и связи по вашему запросу нужно согласие на обработку ПД:</b>\n"
    "• имя и контакты для связи\n"
    "• данные о задаче для подготовки консультации\n"
    "• действия с данными: сбор, запись, систематизация, хранение, уточнение, использование, удаление\n"
    "• хранение в защищенной базе до отзыва согласия или истечения срока хранения\n\n"
    "<b>Важно:</b>\n"
    "• не присылайте без необходимости персональные данные третьих лиц и реквизиты документов\n"
    "• для ИИ-анализа действует отдельное согласие на трансграничную передачу\n\n"
    "<b>Ваши права:</b>\n"
    "• запросить экспорт данных\n"
    "• запросить исправление\n"
    "• отозвать согласие и удалить данные\n\n"
    f"Подробная версия политики: {_e(config.PRIVACY_POLICY_URL)}\n\n"
    "Нажимая кнопку ниже, вы подтверждаете согласие на обработку ПД."
)


CONSENT_TRANSBORDER_TEXT = (
    "<b>🌍 Согласие на трансграничную передачу данных для ИИ</b>\n\n"
    "Для ИИ-ответов сообщения отправляются во внешние сервисы искусственного интеллекта "
    "(например, OpenAI-совместимые провайдеры).\n"
    "Перед отправкой мы не передаем ваши контактные данные как отдельные поля.\n\n"
    "<b>Если не дать это согласие:</b>\n"
    "• можно пользоваться меню и оставить заявку\n"
    "• ИИ-режим анализа кейса будет отключен\n\n"
    "Разрешаете использовать ИИ-режим с трансграничной передачей?"
)


TRANSBORDER_REQUIRED_TEXT = (
    "⚠️ <b>Для ИИ-анализа вашего кейса нужно согласие на трансграничную передачу данных.</b>\n\n"
    "Без него доступны: меню, консультация и ручная передача запроса команде."
)


CONSENT_DENIED_TEXT = (
    "<b>Понял.</b> Без согласия на обработку ПД я не смогу оформить персональную заявку или связать вас с командой.\n\n"
    "Меню, услуги, цены и документы по-прежнему доступны. Когда будете готовы, нажмите /start или кнопку согласия."
)


CONSENT_REVOKED_TEXT = (
    "<b>✅ Согласие отозвано.</b>\n\n"
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
        "<b>📑 Статус согласий</b>\n\n"
        f"• Обработка ПД: {'✅' if consent_given else '❌'}\n"
        f"• Дата согласия: {_e(consent_date)}\n"
        f"• Трансграничная передача: {'✅' if transborder else '❌'}\n"
        f"• Дата трансграничного согласия: {_e(transborder_date)}\n"
        f"• Согласие отозвано: {'✅' if revoked else '❌'}\n"
        f"• Дата отзыва: {_e(revoked_date)}"
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
        return "✅ Согласие на обработку ПД уже дано. ИИ-режим включится после отдельного согласия на трансграничную передачу."
    return "❌ Согласия еще не даны."


def privacy_policy_text() -> str:
    return (
        "<b>📄 Политика обработки персональных данных</b>\n\n"
        f"Оператор: {_operator_identity_text()}\n"
        "Оператор обрабатывает только данные, необходимые для связи и консультации.\n"
        "<b>Подробная версия:</b>\n"
        f"{_e(config.PRIVACY_POLICY_URL)}\n\n"
        f"<b>Контакт по вопросам ПД:</b> {_e(config.PRIVACY_CONTACT_EMAIL)}"
    )


def transborder_policy_text() -> str:
    return (
        "<b>📄 Согласие на трансграничную передачу данных</b>\n\n"
        "Нужно для работы ИИ-функций на базе внешних сервисов искусственного интеллекта.\n"
        "<b>Подробная версия:</b>\n"
        f"{_e(config.TRANSBORDER_CONSENT_URL)}"
    )


def documents_list_text() -> str:
    return (
        "<b>📚 Документы и права пользователя</b>\n\n"
        "<b>Выберите документ кнопками ниже или используйте команды:</b>\n"
        "<code>/privacy</code>\n"
        "<code>/transborder_consent</code>\n"
        "<code>/user_agreement</code>\n"
        "<code>/ai_policy</code>\n"
        "<code>/marketing_consent</code>\n\n"
        "<b>Управление данными:</b>\n"
        "<code>/consent_status</code>\n"
        "<code>/export_data</code>\n"
        "<code>/correct_data &lt;текст&gt;</code>\n"
        "<code>/revoke_consent</code>\n"
        "<code>/delete_data</code>"
    )


def user_agreement_text() -> str:
    return (
        "<b>📄 Пользовательское соглашение</b>\n\n"
        "<b>Актуальная редакция:</b>\n"
        f"{_e(config.USER_AGREEMENT_URL)}"
    )


def ai_policy_text() -> str:
    return (
        "<b>📄 Политика использования ИИ</b>\n\n"
        "<b>Актуальная редакция:</b>\n"
        f"{_e(config.AI_POLICY_URL)}"
    )


def marketing_consent_text() -> str:
    return (
        "<b>📄 Согласие на информационные/маркетинговые рассылки</b>\n\n"
        "<b>Актуальная редакция:</b>\n"
        f"{_e(config.MARKETING_CONSENT_URL)}"
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
