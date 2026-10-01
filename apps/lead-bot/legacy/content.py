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


WEB_TRANSITION_VPN_ALERT = (
    "Вы переходите во внешний веб-адрес:\n{url}\n\n"
    "Перед открытием отключите VPN/прокси в Telegram. "
    "Иначе сайт может не открыться."
)


CONTACTS = {
    "manager_name": "Андрей Попов",
    "telegram": "@AndrewPopov821667",
    "phone": "+7 (909) 233-09-09",
    "email": "a.popov.gv@gmail.com",
    "github": "github.com/Andrew821667",
}

CHANNEL_BUTTON_TEXT = "📰 Канал AI Verdict"
CONTRACT_AI_BUTTON_TEXT = "🖥 Открыть модуль проверки договоров"

# Первые шаги с фиксированной ценой — те же, что на сайте
# (apps/web/lib/starter-offers.ts; совпадение сверяет тест). Раньше бот
# называл только проекты от 100–500 тыс. ₽, а сайт — консультацию за 4 900 ₽:
# клиент видел две разные компании.
STARTER_OFFERS = (
    ("legal", "Консультация юриста", "4 900 ₽", "до 60 минут онлайн и короткий письменный план"),
    ("legal", "Экспресс-проверка договора", "от 7 900 ₽", "один договор до 15 страниц, риски и правки"),
    ("legal", "Претензия или ответ на претензию", "от 9 900 ₽", "разбор документов и готовый документ"),
    (
        "engineering",
        "Диагностика автоматизации",
        "7 900 ₽",
        "технический план по одному процессу, засчитывается в бюджет проекта",
    ),
    ("engineering", "Прототип Telegram-бота или автоматизации", "от 39 000 ₽", "основной сценарий на реальной задаче"),
    ("engineering", "AI/RAG-интеграция или внутренний сервис", "от 79 000 ₽", "поиск по вашим данным, AI-функция или сервис"),
)

CONSULTATION_PRICE_TEXT = "4 900 ₽"
CONTRACT_REVIEW_PRICE_TEXT = "от 7 900 ₽"


def _starter_offers_block(practice: str) -> str:
    return "\n".join(
        f"• {title} — <b>{price}</b>: {note}" for kind, title, price, note in STARTER_OFFERS if kind == practice
    )


# Тот же список обычным текстом — для промпта ассистента.
STARTER_OFFERS_PLAIN = "\n".join(f"• {title} — {price}: {note}" for _, title, price, note in STARTER_OFFERS)

STARTER_OFFERS_TEXT = (
    "<b>Первые шаги — фиксированная цена</b>\n"
    "⚖️ Юридическая практика:\n"
    f"{_starter_offers_block('legal')}\n"
    "🛠 Инженерная практика:\n"
    f"{_starter_offers_block('engineering')}"
)

PLATFORM_PARTS_TEXT = (
    "• 🌐 сайт — продукты, услуги, методология и заявка на консультацию\n"
    "• 📄 Contract AI — проверка договоров, риски и рекомендации по правкам\n"
    "• 💬 ассистент — вопросы, демо, заявки и маршрут внедрения\n"
    "• ⚖️ юридическая практика — быстро передать правовую задачу юристу\n"
    "• 🛠 инженерная практика — разработка программных решений и интеграций\n"
    "• 📰 канал и reader-бот — новости права РФ, автоматизации и ИИ, персональная лента\n"
    "• 📱 Mini App — контент, инструменты, профиль и заявка внутри Telegram"
)

PRACTICES_TEXT = (
    "<b>Куда передать задачу</b>\n"
    "1. <b>Юридическая практика</b> — договоры, споры и другие правовые задачи\n"
    "2. <b>Инженерная практика</b> — боты, сайты, Mini App, программы, AI-модули и интеграции\n\n"
    "Автоматизацию юридической функции обе практики ведут вместе: юристы отвечают за правила и риски, инженеры — за систему.\n\n"
    "Запрос сразу направляется команде с нужной специализацией."
)

PLATFORM_CONTEXT_TEXT = (
    "В <b>AI Verdict</b> можно проверить договор, получить юридическую помощь, "
    "обсудить автоматизацию или отдельную разработку. Я сохраню контекст и передам запрос нужной команде."
)

RESET_MESSAGE = (
    "История диалога очищена. Начинаем заново.\n\n"
    "Вы снова в ассистенте платформы <b>AI Verdict</b>. Можно проверить договор, "
    "обсудить внедрение, открыть услуги или перейти в другие элементы платформы."
)


MODULE_CATALOG = {
    "consultation": "Консультация юриста — до 60 минут онлайн и письменный план, 4 900 ₽",
    "process_audit": "Диагностика процесса и план внедрения",
    "lead_intake_pilot": "Пилот по приему и разбору входящих обращений",
    "contract_review_assist": "ИИ-помощник для проверки договоров",
    "litigation_assist": "ИИ-помощник по судебным документам",
    "compliance_monitoring": "Контроль обязательных требований и рисков",
    "legal_ops_outsource": "Настройка и сопровождение юридических процессов с ИИ-поддержкой",
    "legal_help": "Юридическая практика: договоры, претензии, суды и другие правовые задачи",
    "custom_integrations": "Инженерная практика: боты, сайты, Mini App, программы, AI-модули, CRM/ERP/1C/ЭДО",
}

# Лестница цен на автоматизацию одна для всех профилей — та же, что на сайте
# (lib/faqData.ts) и в промпте ассистента. Раньше профиль, угаданный по словам,
# давал 100/220/400 или 120/250/450 тыс. — человек видел две разные компании.
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
            "Пилотный запуск на 2–4 недели: от 150 000 ₽.",
            "Рабочая система на 1–2 процессах: от 300 000 ₽.",
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
            "Пилотный запуск на 2–4 недели: от 150 000 ₽.",
            "Рабочая система на 1–2 процессах: от 300 000 ₽.",
            "Интеграции и масштабирование (CRM/1C/ERP): от 500 000 ₽.",
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
            "Пилотный запуск на 2–4 недели: от 150 000 ₽.",
            "Рабочая система на 1–2 процессах: от 300 000 ₽.",
            "Интеграции и масштабирование (CRM/1C/ERP): от 500 000 ₽.",
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
            "Пилотный запуск на 2–4 недели: от 150 000 ₽.",
            "Рабочая система на 1–2 процессах: от 300 000 ₽.",
            "Интеграции и масштабирование (CRM/1C/ERP): от 500 000 ₽.",
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
        "<b>рабочей системы на 1–2 процессах</b>.\n\n"
        "<b>Формат оказания услуг на платформе:</b>\n"
        f"{bullets}\n\n"
        "<b>Две базовые практики:</b>\n"
        "• юридическая практика для бизнеса, ИП и частных клиентов — задачу получает юрист\n"
        "• инженерная практика — бот, сайт, Mini App, внутренняя программа, AI-модуль, сервис или интеграция\n\n"
        "Если пока неясно, что подойдет именно вам, просто опишите задачу своими словами — "
        "я помогу сузить сценарий и предложу следующий шаг.\n\n"
        "Если профиль определился неточно, переключите верхнюю кнопку <b>«🎯 Профиль услуг»</b>."
    )


def _platform_prices_text(platform_key: str) -> str:
    platform = CLIENT_PLATFORM.get(platform_key) or CLIENT_PLATFORM["universal"]
    bullets = "\n".join(f"• {line}" for line in platform["pricing"])
    return (
        "<b>💰 Стоимость и форматы</b>\n\n"
        f"{STARTER_OFFERS_TEXT}\n\n"
        "<b>Автоматизация юридической функции</b> "
        f"(профиль: {_e(platform['title'])}):\n"
        f"{bullets}\n\n"
        "Проект считаем после диагностики: цена зависит от объема задач, интеграций и сроков. "
        "Записаться к юристу — кнопкой <b>«📞 Консультация»</b>.\n"
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
    direct_url = (config.CONTRACT_AI_SYSTEM_URL or "https://contract.ai-verdict.ru").strip()
    if not direct_url:
        return None
    if direct_url.startswith(("http://", "https://")):
        return direct_url
    return f"https://{direct_url.lstrip('/')}"


def web_url_by_key(key: str) -> str | None:
    urls = {
        "contract_ai": contract_ai_public_url(),
        "privacy": config.PRIVACY_POLICY_URL,
        "transborder": config.TRANSBORDER_CONSENT_URL,
        "user_agreement": config.USER_AGREEMENT_URL,
        "ai_policy": config.AI_POLICY_URL,
        "marketing_consent": config.MARKETING_CONSENT_URL,
    }
    value = (urls.get(key) or "").strip()
    return value or None


def web_transition_alert(url: str) -> str:
    return WEB_TRANSITION_VPN_ALERT.format(url=url)


def channel_nurture_text() -> str:
    if not public_channel_url():
        return ""
    return (
        "Если к консультации пока не готовы, можно начать с канала AI Verdict: "
        "там новости права РФ, автоматизации и ИИ с короткими практическими комментариями."
    )


def post_contact_channel_text() -> str:
    if not public_channel_url():
        return ""
    return (
        "Пока команда готовит ответ, можно подписаться на канал AI Verdict: "
        "там новости права РФ, автоматизации и ИИ с короткими комментариями."
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
        "• <i>«юристы тонут во входящих запросах»</i>\n"
        "• <i>«нужна юридическая помощь по спору»</i>\n"
        "• <i>«нужна инженерная разработка бота, сайта или внутренней программы»</i>"
    )


def with_assistant_chat_hint(text: str) -> str:
    hint = assistant_chat_hint_text()
    if hint in text:
        return text
    return f"{text}\n\n{hint}"


def contract_ai_entry_hint() -> str:
    if not contract_ai_public_url():
        return ""
    return "Открыть Contract AI и оставить заявку на демо-доступ — кнопкой ниже."


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
        f"{PLATFORM_CONTEXT_TEXT}\n\n"
        "Основное направление AI Verdict — <b>автоматизация юридических бизнес-процессов</b>: "
        "быстрее разбирать договоры, не терять юридические запросы и убирать "
        "ручную рутину без лишней сложности.\n\n"
        f"{PRACTICES_TEXT}\n\n"
        "<b>Что можно использовать:</b>\n"
        f"{PLATFORM_PARTS_TEXT}\n\n"
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
        f"{PLATFORM_CONTEXT_TEXT}\n\n"
        "Основное направление AI Verdict — <b>автоматизация юридических бизнес-процессов</b>: "
        "от проверки договоров и обработки запросов до пилотов и рабочих систем автоматизации.\n\n"
        f"{PRACTICES_TEXT}\n\n"
        "<b>Вам доступны все разделы платформы:</b>\n"
        f"{PLATFORM_PARTS_TEXT}\n\n"
        f"{profile_hint}"
        "<b>С чего удобно начать:</b>\n"
        "1. <b>🧪 Проверить договор</b> — если у вас уже есть документ\n"
        "2. <b>⚖️ Юридическая практика</b> — если правовую задачу нужно передать юристу\n"
        "3. <b>🛠 Инженерная практика</b> — если нужен бот, сайт, программа, AI-модуль или интеграция\n"
        "4. <b>📋 Услуги</b> и <b>💰 Цены</b> — если вы только знакомитесь с возможностями\n\n"
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
    f"{PLATFORM_CONTEXT_TEXT}\n\n"
    "<b>Основные элементы:</b>\n"
    f"{PLATFORM_PARTS_TEXT}\n\n"
    "Я помогаю выбрать маршрут: совместный проект по <b>автоматизации юридической функции</b>, "
    "юридическую помощь или инженерную разработку и интеграции.\n\n"
    "<b>Основные команды:</b>\n"
    "<code>/start</code> - начать диалог\n"
    "<code>/help</code> - показать помощь\n"
    "<code>/reset</code> - очистить историю\n"
    "<code>/menu</code> - открыть меню\n\n"
    "<code>/profile</code> - мой профиль\n"
    "<code>/documents</code> - список документов\n\n"
    "<b>Документы и управление данными:</b>\n"
    "<code>/privacy</code> - политика обработки ПД\n"
    "<code>/transborder_consent</code> - обезличивание данных перед сервисами ИИ\n"
    "<code>/user_agreement</code> - пользовательское соглашение\n"
    "<code>/ai_policy</code> - политика использования ИИ\n"
    "<code>/marketing_consent</code> - условия рассылок\n"
    "<code>/consent_status</code> - статус ваших согласий\n"
    "<code>/export_data</code> - экспорт ваших данных\n"
    "<code>/correct_data &lt;текст&gt;</code> - запрос на исправление данных\n"
    "<code>/revoke_consent</code> - отзыв согласия\n"
    "<code>/delete_data</code> - удалить персональные данные\n\n"
    "Можно просто написать вашу задачу в свободной форме.\n"
    "Например: <i>«хотим внедрить ИИ в согласование договоров»</i>, "
    "<i>«нужна юридическая помощь по спору»</i> или "
    "<i>«нужна инженерная разработка Telegram-бота»</i>.\n\n"
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
        "Здесь собраны основные разделы платформы: услуги, цены, ИИ-проверка договора, "
        "консультация, документы и переходы к связанным разделам.\n"
        "Можно пользоваться сайтом, Contract AI, ассистентом, каналом, reader-ботом "
        "и Mini App как одной системой.\n"
        "Если проще, можно вообще не идти по меню, а сразу написать задачу обычными словами.\n\n"
        "Если профиль определился неточно, переключите верхнюю кнопку «🎯 Профиль услуг».\n\n"
        f"<b>Сейчас активен:</b> {_e(active_profile_label)}\n"
        f"<b>Режим:</b> {_e(mode)}\n\n"
        "<b>Что можно сделать сейчас:</b>\n"
        "• посмотреть услуги и ориентиры по бюджету\n"
        "• открыть ИИ-проверку договора или описать задачу своими словами\n"
        "• передать правовую задачу юридической практике\n"
        "• передать разработку инженерной практике\n\n"
        "Для персональной заявки и ИИ-разбора я сначала попрошу согласие на обработку данных.\n\n"
        "Выберите нужный раздел кнопками ниже."
    )


WORKSPACE_TEXT = build_workspace_text()


MENU_HEADER_TEXT = WORKSPACE_TEXT


MENU_RESPONSES = {
    "menu_services": (
        "<b>🎯 Чем мы можем быть полезны</b>\n\n"
        f"{SERVICE_CATALOG_TEXT}\n\n"
        "Это основные форматы работы: от быстрых пилотов до рабочей системы на 1–2 процессах.\n"
        "Если пока неясно, что подойдет именно вам, просто опишите задачу своими словами — "
        "я помогу сузить сценарий и предложу следующий шаг."
    ),
    "menu_prices": (
        "<b>💰 Стоимость</b>\n\n"
        f"{STARTER_OFFERS_TEXT}\n\n"
        "<b>Автоматизация юридической функции:</b> пилот — от 150 000 ₽, рабочая система — "
        "от 300 000 ₽, интеграции и масштабирование — от 500 000 ₽. Проект считаем после диагностики.\n\n"
        "Если напишете, что именно нужно, подскажу подходящий первый шаг."
    ),
    "menu_help": (
        "<b>❓ Как я помогаю</b>\n\n"
        "• объясняю простыми словами, как внедрять ИИ в юридические и бизнес-процессы\n"
        "• передаю правовые задачи отдельной юридической практике\n"
        "• передаю разработку и интеграции отдельной инженерной практике\n"
        "• помогаю понять, какой формат вам подходит\n"
        "• собираю контекст перед консультацией с командой\n\n"
        "<b>Можно начать одной фразой, например:</b>\n"
        "«долго согласовываем договоры»\n"
        "«нужна помощь юриста по спору»\n"
        "«нужна инженерная разработка сайта или бота»\n"
        "«хотим внедрить ИИ в юридическую функцию»."
    ),
    "menu_custom_development": (
        "<b>🛠 Инженерная практика</b>\n\n"
        "Инженерная практика — одна из двух базовых практик AI Verdict. Вместе с юристами она "
        "автоматизирует юридическую функцию и интегрирует ее с действующими системами.\n\n"
        "Самостоятельно инженерная практика ведет разработку Telegram-ботов, сайтов, "
        "Mini App, личных кабинетов, внутренних программ, AI-модулей, сервисов и интеграций "
        "с CRM/ERP/1C/ЭДО, в том числе не связанных с юридической работой.\n\n"
        "Опишите задачу и текущий ручной процесс одной фразой — я помогу определить следующий шаг."
    ),
    "menu_consultation": (
        f"<b>📞 Консультация юриста — {CONSULTATION_PRICE_TEXT}</b>\n\n"
        "До 60 минут онлайн и короткий письменный план: что делать дальше, какие документы "
        "нужны и какие сроки проверить.\n\n"
        "• Оплатить на сайте — кнопка <b>«📅 Записаться к юристу»</b>: время выберете из открытого или согласуем с вами.\n"
        "• Или оставьте контакт — юрист напишет и согласует время.\n\n"
        "Задачу по автоматизации или разработке можно обсудить прямо здесь, в переписке. "
        "Разбор процесса с техническим планом — диагностика за 7 900 ₽, она засчитывается в бюджет проекта."
    ),
    "menu_contract_ai": (
        "<b>🧪 Проверка договора — в Contract AI</b>\n\n"
        "<b>Contract AI</b> — наш сервис анализа договоров с ИИ.\n\n"
        "<b>Что умеет:</b>\n"
        "• находит ключевые риски договора\n"
        "• проверяет на соответствие стандартам компании\n"
        "• предлагает правки\n"
        "• оценивает баланс прав и обязанностей сторон\n\n"
        "Доступ — персональный демо-доступ по заявке. Договоры загружают в Contract AI, "
        "в этот чат их присылать не нужно.\n\n"
        f"Нужен вывод юриста — экспресс-проверка договора {CONTRACT_REVIEW_PRICE_TEXT}."
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
    "🛠 Разработка": "menu_custom_development",
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
    if key in {"menu_help", "menu_custom_development", "menu_contract_ai", "menu_consultation", "menu_leave_contact", "menu_profile", "menu_documents"}:
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
    f"📞 Консультация юриста — {CONSULTATION_PRICE_TEXT}\n"
    "📄 Чек-лист «15 типовых ошибок в договорах»\n"
    "🧪 Автопроверка договора в Contract AI\n"
    "🧾 Образец отчёта по договору\n"
    "\nВыберите, что будет полезнее именно сейчас."
)

CONSULTATION_CTA_TEXT = (
    "<b>Если хотите, можем перейти к следующему практическому шагу.</b>"
)


# Чек-лист и образец отчёта бот присылает прямо в чат — почту не спрашиваем
# (решение владельца: писем клиентам нет). Тексты — HTML для Telegram. Проверить
# свой договор — в Contract AI, кнопкой; файлы договоров бот не принимает.
CHECKLIST_MESSAGE = (
    "📄 <b>Чек-лист: 15 типовых ошибок в договорах</b>\n"
    "Из практики наших юристов — что проверить до подписания.\n\n"
    "🔴 <b>Критично</b>\n"
    "1. Предмет не определён или описан неоднозначно — договор могут признать незаключённым "
    "(ст. 432 ГК РФ).\n"
    "2. Нет условий, которые закон называет существенными для этого вида договора.\n"
    "3. Нет цены там, где без неё договор не заключён: продажа и аренда недвижимости "
    "(ст. 555, 654 ГК РФ).\n"
    "4. Ответственность исключена за умышленное нарушение — такое условие ничтожно "
    "(п. 4 ст. 401 ГК РФ).\n"
    "5. Сроки размыты: «в разумный срок», «в кратчайшие сроки».\n\n"
    "⚠️ <b>Часто встречается</b>\n"
    "6. Нет порядка приёмки: чем подтверждается исполнение и в какой срок.\n"
    "7. Не прописано, как менять договор и можно ли менять условия в одностороннем порядке.\n"
    "8. Не прописан претензионный порядок: сроки, адреса, способ направления. По большинству "
    "денежных споров между организациями без претензии иск не примут (ч. 5 ст. 4 АПК РФ), "
    "а по умолчанию ответа ждут 30 дней.\n"
    "9. Ошибки в реквизитах сторон — сверяйте с ЕГРЮЛ и ЕГРИП.\n"
    "10. У подписанта нет полномочий — проверьте устав или доверенность.\n"
    "11. Не согласовано обеспечение: неустойка, залог, поручительство.\n"
    "12. Разделы противоречат друг другу — например, условия оплаты в разных пунктах.\n"
    "13. Форс-мажор описан слишком широко — «любые обстоятельства» не работают.\n"
    "14. Нет порядка расторжения и одностороннего отказа.\n"
    "15. Не учтены отраслевые требования: строительство, агро, финансы и др.\n\n"
    "💡 Contract AI проверяет договор по этим пунктам за несколько минут — загрузите его "
    "по кнопке ниже."
)

SAMPLE_REPORT_MESSAGE = (
    "🧾 <b>Образец отчёта Contract AI</b>\n"
    "Фрагмент проверки условного договора поставки — так выглядит отчёт по вашему документу.\n\n"
    "🔴 <b>Критично — п. 1.2</b> «Ассортимент и количество определяются заявками Покупателя»\n"
    "Риск: не описан порядок подачи и согласования заявок — по партиям договор могут признать "
    "незаключённым (п. 2 ст. 465 ГК РФ).\n"
    "Правка: добавить порядок заявок и спецификаций — форму, срок подтверждения, что считается "
    "согласием поставщика.\n\n"
    "🟠 <b>Важно — п. 6.2</b> неустойка Покупателя 0,5% в день без ограничения\n"
    "Риск: отвечает только одна сторона и без верхнего предела; суд может снизить неустойку "
    "(ст. 333 ГК РФ), но спор придётся вести.\n"
    "Правка: сделать ответственность взаимной и ограничить её, например 10% от суммы партии.\n\n"
    "🟡 <b>Желательно — п. 9.3</b> споры в суде по месту нахождения Поставщика\n"
    "Риск: для покупателя из другого региона это лишние расходы на процесс.\n"
    "Правка: суд по месту нахождения ответчика и срок ответа на претензию 10 дней.\n\n"
    "В полном отчёте — карта рисков по всем разделам, приоритеты и готовые формулировки правок.\n\n"
    "Проверьте свой договор в Contract AI — кнопка ниже."
)

DEMO_MESSAGE = (
    "🧪 <b>Автопроверка договора — в Contract AI</b>\n"
    "Contract AI показывает ключевые риски договора и что стоит поправить. "
    "Доступ — персональный демо-доступ по заявке: оставьте её по кнопке ниже.\n\n"
    f"Если нужен вывод юриста — экспресс-проверка договора {CONTRACT_REVIEW_PRICE_TEXT}."
)

# Что бот выдаёт сразу по кнопке, без следующего шага от человека. Договоры бот
# сам не принимает и не разбирает — для этого Contract AI (решение владельца).
INSTANT_MAGNETS = ("checklist", "sample_report", "demo")

LEAD_MAGNET_SELECTION_MESSAGES = {
    "consultation": (
        f"Консультация юриста — {CONSULTATION_PRICE_TEXT}, до 60 минут онлайн.\n\n"
        f"Оплатить можно на сайте: {config.CONSULTATION_BOOKING_URL} — время выберете из открытого или согласуем с вами.\n"
        "Или отправьте номер телефона — юрист напишет и согласует время."
    ),
    "checklist": CHECKLIST_MESSAGE,
    "demo": DEMO_MESSAGE,
    "sample_report": SAMPLE_REPORT_MESSAGE,
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
    "• реквизиты документа, удостоверяющего личность, — только при подписании NDA или договора\n"
    "• действия с данными: сбор, запись, систематизация, хранение, уточнение, использование, удаление\n"
    "• хранение в защищенной базе до отзыва согласия или истечения срока хранения\n\n"
    "<b>Важно:</b>\n"
    "• не присылайте без необходимости персональные данные третьих лиц и реквизиты документов\n"
    "• паспортные данные не передаются системам ИИ, веб-аналитике и рекламным системам\n"
    "• перед отправкой сервисам ИИ персональные данные обезличиваются — за рубеж они не передаются\n\n"
    "<b>Ваши права:</b>\n"
    "• запросить экспорт данных\n"
    "• запросить исправление\n"
    "• отозвать согласие и удалить данные\n\n"
    f"Подробная версия политики: {_e(config.PRIVACY_POLICY_URL)}\n\n"
    "Нажимая кнопку ниже, вы подтверждаете согласие на обработку ПД."
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
    revoked = bool(consent.get("consent_revoked"))
    consent_date = consent.get("consent_date") or "—"
    revoked_date = consent.get("consent_revoked_at") or "—"
    return (
        "<b>📑 Статус согласий</b>\n\n"
        f"• Обработка ПД: {'✅' if consent_given else '❌'}\n"
        f"• Дата согласия: {_e(consent_date)}\n"

        f"• Согласие отозвано: {'✅' if revoked else '❌'}\n"
        f"• Дата отзыва: {_e(revoked_date)}"
    )


def consent_user_status_text(consent: dict) -> str:
    consent_given = bool(consent.get("consent_given"))
    revoked = bool(consent.get("consent_revoked"))

    if revoked:
        return "⚠️ Согласия отозваны. Для повторного запуска отправьте /start."
    if consent_given:
        return "✅ Согласие на обработку ПД уже дано."
    return "❌ Согласия еще не даны."


def privacy_policy_text() -> str:
    return (
        "<b>📄 Политика обработки персональных данных</b>\n\n"
        f"Оператор: {_operator_identity_text()}\n"
        "Оператор обрабатывает только данные, необходимые для связи и консультации.\n"
        "<b>Подробная версия:</b> откройте веб-версию кнопкой под сообщением.\n\n"
        f"<b>Контакт по вопросам ПД:</b> {_e(config.PRIVACY_CONTACT_EMAIL)}"
    )


def transborder_policy_text() -> str:
    return (
        "<b>🛡 Обезличивание перед сервисами ИИ</b>\n\n"
        "Сервисы искусственного интеллекта получают только обезличенный текст: имена, телефоны, почта, "
        "номера документов, счетов и карт, адреса и даты рождения заменяются метками. "
        "Персональные данные за рубеж не передаются, отдельное согласие не нужно.\n"
        "<b>Подробная версия:</b> откройте веб-версию кнопкой под сообщением."
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
        "<b>Актуальная редакция:</b> откройте веб-версию кнопкой под сообщением."
    )


def ai_policy_text() -> str:
    return (
        "<b>📄 Политика использования ИИ</b>\n\n"
        "<b>Актуальная редакция:</b> откройте веб-версию кнопкой под сообщением."
    )


def marketing_consent_text(granted: bool | None = None) -> str:
    text = (
        "<b>📄 Согласие на информационные/маркетинговые рассылки</b>\n\n"
        "<b>Актуальная редакция:</b> откройте веб-версию кнопкой под сообщением."
    )
    if granted is None:
        return text
    status = (
        "✅ Сейчас согласие дано. Отозвать его можно в любой момент кнопкой ниже."
        if granted
        else "Сейчас согласия нет. Дать его можно только кнопкой «Согласен получать рассылки»."
    )
    return f"{text}\n\n{status}"


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
