from __future__ import annotations

import content
from handlers.constants import build_workspace_inline_menu


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


def test_profile_and_documents_buttons_resolve_menu_keys() -> None:
    profile_response = content.menu_response_by_button("👤 Профиль")
    documents_response = content.menu_response_by_button("📚 Документы")
    assert "Профиль" in profile_response
    assert "Документы" in documents_response


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
    assert "Legal AI PRO" in first_touch
    assert "это ИИ-помощник по автоматизации юридических процессов" in first_touch
    assert "С чего удобно начать" in first_touch
    assert "Проверить договор" in first_touch


def test_menu_help_includes_channel_nurture_when_channel_available() -> None:
    response = content.menu_response_by_key("menu_help")
    assert "Можно не только нажимать кнопки" in response
    assert "как внедрять ИИ в юридические и бизнес-процессы" in response
    if content.public_channel_url():
        assert "канала Legal AI PRO" in response
    else:
        assert "канала Legal AI PRO" not in response


def test_services_menu_explicitly_allows_freeform_ai_chat() -> None:
    response = content.menu_response_by_key("menu_services", selected_profile="business")
    assert "Можно не только нажимать кнопки" in response
    assert "ИИ-помощник предложит следующий шаг" in response


def test_offer_profile_menu_explicitly_allows_freeform_ai_chat() -> None:
    response = content.menu_response_by_key("menu_offer_profile", selected_profile="business")
    assert "Можно не только нажимать кнопки" in response
    assert "ИИ-помощник предложит следующий шаг" in response


def test_welcome_message_is_result_oriented_and_contains_disclaimer() -> None:
    welcome = content.build_welcome_message("Андрей")
    assert "это ИИ-помощник по автоматизации юридических процессов" in welcome
    assert "внедрять ИИ в <b>юридические и бизнес-процессы</b>" in welcome
    assert "вопросы к юристам приходят хаотично" in welcome
    assert "Можно начать без специальных терминов" in welcome
    assert "информационный характер" in welcome
    assert "<b>" in welcome


def test_start_entry_text_is_clear_for_new_user() -> None:
    start_entry = content.build_start_entry_text("Андрей", selected_profile="law_firm")
    assert "Здравствуйте, Андрей." in start_entry
    assert "внедрять ИИ в <b>юридические и бизнес-процессы</b>" in start_entry
    assert "Сначала нажмите верхнюю кнопку" in start_entry
    assert "Сейчас активен:" in start_entry
    assert "Можно не ждать подходящей кнопки" in start_entry


def test_contract_module_text_is_clear_for_new_user() -> None:
    response = content.menu_response_by_key("menu_contract_ai")
    assert "Проверка договора" in response
    assert "это наш отдельный сервис для работы с договорами" in response
    assert "демонстрационный разбор договора" in response
