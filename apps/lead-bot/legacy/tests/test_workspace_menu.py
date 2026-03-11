from __future__ import annotations

import content
from handlers.constants import build_workspace_inline_menu


def test_workspace_button_maps_to_dashboard() -> None:
    response = content.menu_response_by_button("🧭 Рабочий стол", selected_profile="business")
    assert "РАБОЧИЙ СТОЛ" in response
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
    assert "ПРОФИЛЬ" in profile_response
    assert "ДОКУМЕНТЫ" in documents_response


def test_offer_profile_button_and_override() -> None:
    selector_response = content.menu_response_by_button("🧩 Сменить профиль")
    business_services = content.menu_response_by_key("menu_services", selected_profile="business")
    assert "СМЕНА ПРОФИЛЯ" in selector_response
    assert "Собственник / руководитель бизнеса" in business_services


def test_offer_profile_cta_label_mentions_mode() -> None:
    manual_label = content.offer_profile_cta_label(selected_profile="law_firm")
    auto_label = content.offer_profile_cta_label()
    assert "Юрфирма" in manual_label
    assert "(вручную)" in manual_label
    assert "(авто)" in auto_label


def test_workspace_onboarding_text_emphasizes_profile_choice() -> None:
    onboarding_text = content.build_workspace_text(selected_profile="business", emphasize_profile_choice=True)
    regular_text = content.build_workspace_text(selected_profile="business")
    assert "👉 Начните с верхней кнопки «🎯 Профиль услуг»." in onboarding_text
    assert "Так я быстрее покажу именно те услуги и цены" in onboarding_text
    assert "👉 Начните с верхней кнопки «🎯 Профиль услуг»." not in regular_text
