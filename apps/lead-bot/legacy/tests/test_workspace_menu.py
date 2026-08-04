from __future__ import annotations

import content
import prompts
from handlers.constants import build_workspace_inline_menu
from handlers.markup import web_open_markup, web_url_markup


def test_workspace_button_maps_to_dashboard() -> None:
    response = content.menu_response_by_button("🧭 Рабочий стол", selected_profile="business")
    assert "Рабочий стол" in response
    assert "Собственник / руководитель бизнеса" in response


def test_workspace_inline_menu_contains_profile_and_documents() -> None:
    workspace_menu = build_workspace_inline_menu(content.offer_profile_cta_label(selected_profile="inhouse"))
    callback_values = [
        button.callback_data
        for row in workspace_menu
        for button in row
    ]
    assert workspace_menu[0][0].callback_data == "menu_offer_profile"
    assert workspace_menu[0][0].text.startswith("🎯 Профиль услуг:")
    assert "menu_profile" in callback_values
    assert "menu_offer_profile" in callback_values
    assert "menu_documents" in callback_values
    assert "open_web:contract_ai" in callback_values
    assert "legal_help_start" in callback_values
    assert "menu_custom_development" in callback_values


def test_profile_and_documents_buttons_resolve_menu_keys() -> None:
    profile_response = content.menu_response_by_button("👤 Профиль")
    documents_response = content.menu_response_by_button("📚 Документы")
    assert "Профиль" in profile_response
    assert "Документы" in documents_response


def test_document_web_markups_keep_back_to_documents() -> None:
    open_markup = web_open_markup("privacy")
    url_markup = web_url_markup("privacy", "https://ai-verdict.ru/privacy")

    assert open_markup.inline_keyboard[0][0].callback_data == "open_web:privacy"
    assert open_markup.inline_keyboard[1][0].callback_data == "doc_menu"
    assert url_markup.inline_keyboard[0][0].url == "https://ai-verdict.ru/privacy"
    assert url_markup.inline_keyboard[1][0].callback_data == "doc_menu"


def test_offer_profile_button_and_override() -> None:
    selector_response = content.menu_response_by_button("🧩 Сменить профиль")
    business_services = content.menu_response_by_key("menu_services", selected_profile="business")
    assert "Смена профиля" in selector_response
    assert "Собственник / руководитель бизнеса" in business_services


def test_offer_profile_cta_label_mentions_mode() -> None:
    manual_label = content.offer_profile_cta_label(selected_profile="law_firm")
    auto_label = content.offer_profile_cta_label()
    assert "Юрфирма" in manual_label
    assert "(вручную)" in manual_label
    assert "(авто)" in auto_label


def test_offer_profile_labels_are_clear_for_new_user() -> None:
    selector_response = content.offer_profile_panel_text(selected_profile="inhouse")
    workspace_text = content.build_workspace_text(selected_profile="inhouse")
    assert "Юридический отдел компании" in selector_response
    assert "Юридический отдел компании" in workspace_text


def test_workspace_onboarding_text_emphasizes_profile_choice() -> None:
    onboarding_text = content.build_workspace_text(selected_profile="business", emphasize_profile_choice=True)
    regular_text = content.build_workspace_text(selected_profile="business")
    assert "Начните с верхней кнопки «🎯 Профиль услуг»." in onboarding_text
    assert "Так я быстрее покажу подходящие услуги, цены" in onboarding_text
    assert "Начните с верхней кнопки «🎯 Профиль услуг»." not in regular_text


def test_workspace_first_touch_text_explains_platform_for_new_user() -> None:
    first_touch = content.build_workspace_text(
        first_name="Андрей",
        selected_profile="business",
        emphasize_profile_choice=True,
        include_context_intro=True,
    )
    assert "AI Verdict" in first_touch
    assert "это единая платформа для юридической AI-работы" in first_touch
    assert "а не отдельный бот" in first_touch
    assert "Contract AI" in first_touch
    assert "reader-бот" in first_touch
    assert "Mini App" in first_touch
    assert "С чего удобно начать" in first_touch
    assert "Проверить договор" in first_touch


def test_menu_help_includes_channel_nurture_when_channel_available() -> None:
    response = content.menu_response_by_key("menu_help")
    assert "Необязательно ждать подходящую кнопку" in response
    assert "💬 <b>" in response
    assert "хотим внедрить ИИ в договорную работу" in response
    assert "как внедрять ИИ в юридические и бизнес-процессы" in response
    if content.public_channel_url():
        assert "канала AI Verdict" in response
    else:
        assert "канала AI Verdict" not in response


def test_services_menu_explicitly_allows_freeform_ai_chat() -> None:
    response = content.menu_response_by_key("menu_services", selected_profile="business")
    assert "быстрых пилотов" in response
    assert "рабочего контура автоматизации" in response
    assert "Необязательно ждать подходящую кнопку" in response
    assert "юристы тонут во входящих запросах" in response


def test_offer_profile_menu_explicitly_allows_freeform_ai_chat() -> None:
    response = content.menu_response_by_key("menu_offer_profile", selected_profile="business")
    assert "Необязательно ждать подходящую кнопку" in response
    assert "хотим внедрить ИИ в договорную работу" in response


def test_welcome_message_is_result_oriented_and_contains_disclaimer() -> None:
    welcome = content.build_welcome_message("Андрей")
    assert "это единая платформа для юридической AI-работы" in welcome
    assert "а не отдельный бот" in welcome
    assert "внедрять ИИ в <b>юридические бизнес-процессы</b>" in welcome
    assert "три специализированных направления" in welcome
    assert "Contract AI" in welcome
    assert "reader-бот" in welcome
    assert "Mini App" in welcome
    assert "вопросы к юристам приходят хаотично" in welcome
    assert "Можно начать без специальных терминов" in welcome
    assert "💬 <b>Необязательно ждать подходящую кнопку" in welcome
    assert "информационный характер" in welcome
    assert "<b>" in welcome


def test_start_entry_text_is_clear_for_new_user() -> None:
    start_entry = content.build_start_entry_text("Андрей", selected_profile="law_firm")
    assert "Здравствуйте, Андрей." in start_entry
    assert "внедрять ИИ в <b>юридические бизнес-процессы</b>" in start_entry
    assert "Вам доступен весь контур платформы" in start_entry
    assert "Contract AI" in start_entry
    assert "reader-бот" in start_entry
    assert "Mini App" in start_entry
    assert "Сначала нажмите верхнюю кнопку" in start_entry
    assert "Юридическая практика" in start_entry
    assert "три специализированных направления" in start_entry
    assert "Инженерная практика" in start_entry
    assert "🛠 Инженерная практика" in start_entry
    assert "Сейчас активен:" in start_entry
    assert "💬 <b>Необязательно ждать подходящую кнопку" in start_entry


def test_help_message_keeps_platform_context() -> None:
    assert "это единая платформа для юридической AI-работы" in content.HELP_MESSAGE
    assert "а не отдельный бот" in content.HELP_MESSAGE
    assert "Contract AI" in content.HELP_MESSAGE
    assert "reader-бот" in content.HELP_MESSAGE
    assert "Mini App" in content.HELP_MESSAGE
    assert "юридическую практику" in content.HELP_MESSAGE
    assert "инженерная разработка Telegram-бота" in content.HELP_MESSAGE


def test_services_cover_legal_help_and_development_for_other_goals() -> None:
    services = content.menu_response_by_key("menu_services", selected_profile="business")
    development = content.menu_response_by_key("menu_custom_development")

    assert "юридическая практика для бизнеса, ИП и частных клиентов" in services
    assert "инженерная практика" in services
    assert "Основное направление AI Verdict" in development
    assert "Отдельная инженерная практика" in development
    assert "CRM/ERP/1C/ЭДО" in development


def test_system_prompt_forbids_denial_of_expanded_services() -> None:
    assert "Отдельная юридическая практика" in prompts.SYSTEM_PROMPT
    assert "может быть не связана с юридической автоматизацией" in prompts.SYSTEM_PROMPT
    assert "Никогда не утверждай" in prompts.SYSTEM_PROMPT
    assert "для любых задач" in prompts.SYSTEM_PROMPT


def test_reset_message_returns_user_to_platform_assistant() -> None:
    assert "ассистенте платформы <b>AI Verdict</b>" in content.RESET_MESSAGE
    assert "другие элементы платформы" in content.RESET_MESSAGE


def test_workspace_text_links_platform_elements() -> None:
    workspace = content.build_workspace_text()
    assert "основные разделы платформы" in workspace
    assert "Contract AI" in workspace
    assert "Mini App как одной системой" in workspace


def test_contract_module_text_is_clear_for_new_user() -> None:
    response = content.menu_response_by_key("menu_contract_ai")
    assert "Проверка договора" in response
    assert "сервис AI-анализа договоров" in response
    assert "полный анализ рисков договора за минуты" in response
    assert "краткий отчёт с ключевыми рисками и рекомендациями" in response


def test_consultation_text_explains_value_of_handoff() -> None:
    response = content.menu_response_by_key("menu_consultation")
    assert "обсудить задачу с человеком" in response
    assert "с чего лучше начать внедрение" in response
