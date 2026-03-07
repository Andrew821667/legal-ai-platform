from __future__ import annotations

import content
from handlers.constants import WORKSPACE_INLINE_MENU


def test_workspace_button_maps_to_dashboard() -> None:
    response = content.menu_response_by_button("🧭 Рабочий стол")
    assert "РАБОЧИЙ СТОЛ" in response


def test_workspace_inline_menu_contains_profile_and_documents() -> None:
    callback_values = [
        button.callback_data
        for row in WORKSPACE_INLINE_MENU
        for button in row
    ]
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
