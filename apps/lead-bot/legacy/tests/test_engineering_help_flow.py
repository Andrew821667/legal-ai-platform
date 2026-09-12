"""Обращение в инженерную и гибридную практику из бота.

Раньше «🛠 Инженерная практика» была текстом с просьбой оставить контакт.
Теперь это обращение с практикой, и дальше оно идёт по общему циклу.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import intake_dialog
import intake_outreach
from handlers import engineering_help


def test_categories_match_core_keys() -> None:
    """Ключи категорий обязаны совпадать с PRACTICE_CATEGORIES ядра — проверка там."""
    assert set(engineering_help.ENGINEERING_CATEGORIES) == {
        "telegram_bot", "website", "miniapp", "internal_tool", "ai_module", "integration", "other",
    }
    assert set(engineering_help.HYBRID_CATEGORIES) == {
        "contracts_flow", "claims_flow", "compliance", "document_flow", "staff_consulting", "other",
    }


def test_start_buttons_sit_above_the_menu() -> None:
    from telegram import InlineKeyboardMarkup

    from telegram_ui import inline_button as InlineKeyboardButton

    base = InlineKeyboardMarkup([[InlineKeyboardButton("Услуги", callback_data="menu_services")]])
    rows = engineering_help.with_start_buttons(base).inline_keyboard
    assert [row[0].callback_data for row in rows] == [
        "eng_help_start:engineering",
        "eng_help_start:hybrid",
        "menu_services",
    ]


def test_category_markup_offers_every_category_once() -> None:
    values = [
        b.callback_data
        for row in engineering_help.category_markup("engineering").inline_keyboard
        for b in row
    ]
    assert values == [f"eng_cat:{k}" for k in engineering_help.ENGINEERING_CATEGORIES]


@pytest.mark.anyio
async def test_engineering_description_creates_an_intake_with_practice(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    replies: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        replies.append(text)

    def _create(payload, *, idempotency_key):
        captured["payload"] = payload
        return {"id": "11111111-1111-1111-1111-111111111111"}

    monkeypatch.setattr(engineering_help.utils, "safe_reply_text", _reply)
    monkeypatch.setattr(engineering_help.database.db, "create_new_local_lead", lambda user_id, payload: 77)
    monkeypatch.setattr(engineering_help.database.db, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(engineering_help.core_api_bridge, "create_legal_intake", _create)

    context = SimpleNamespace(
        user_data={
            engineering_help.MODE_KEY: "awaiting_description",
            engineering_help.PRACTICE_KEY: "engineering",
            engineering_help.CATEGORY_KEY: "integration",
            engineering_help.CLIENT_TYPE_KEY: "company",
        }
    )
    update = SimpleNamespace(effective_message=SimpleNamespace(message_id=55))
    user = SimpleNamespace(id=42, username="example_user", full_name="Иван Петров", first_name="Иван")

    handled = await engineering_help.maybe_handle_message(
        update=update,
        context=context,
        message_text="Заявки из бота сейчас руками переносим в CRM, хотим автоматически.",
        user=user,
        user_data={"id": 10, "telegram_id": 42},
    )

    assert handled is True
    payload = captured["payload"]
    assert payload["practice"] == "engineering"
    assert payload["category"] == "integration"
    assert payload["client_type"] == "company"
    assert payload["legal_area"] == "other"
    assert payload["contact"] == "@example_user"
    assert engineering_help.MODE_KEY not in context.user_data
    assert "передана команде" in replies[-1]


@pytest.mark.anyio
async def test_hybrid_description_names_both_teams(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    replies: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        replies.append(text)

    monkeypatch.setattr(engineering_help.utils, "safe_reply_text", _reply)
    monkeypatch.setattr(engineering_help.database.db, "create_new_local_lead", lambda user_id, payload: 78)
    monkeypatch.setattr(engineering_help.database.db, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        engineering_help.core_api_bridge,
        "create_legal_intake",
        lambda payload, *, idempotency_key: captured.setdefault("payload", payload) and {"id": "x"},
    )

    context = SimpleNamespace(
        user_data={
            engineering_help.MODE_KEY: "awaiting_description",
            engineering_help.PRACTICE_KEY: "hybrid",
            engineering_help.CATEGORY_KEY: "contracts_flow",
            engineering_help.CLIENT_TYPE_KEY: "company",
        }
    )
    handled = await engineering_help.maybe_handle_message(
        update=SimpleNamespace(effective_message=SimpleNamespace(message_id=56)),
        context=context,
        message_text="Согласование договоров идёт по почте неделями, хотим единый процесс.",
        user=SimpleNamespace(id=43, username=None, full_name="Анна", first_name="Анна"),
        user_data={"id": 11, "telegram_id": 43},
    )
    assert handled is True
    assert captured["payload"]["practice"] == "hybrid"
    assert "юристам и инженерам" in replies[-1]


@pytest.mark.anyio
async def test_short_description_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    replies: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        replies.append(text)

    monkeypatch.setattr(engineering_help.utils, "safe_reply_text", _reply)
    context = SimpleNamespace(user_data={engineering_help.MODE_KEY: "awaiting_description"})
    handled = await engineering_help.maybe_handle_message(
        update=SimpleNamespace(effective_message=SimpleNamespace(message_id=1)),
        context=context,
        message_text="бот",
        user=SimpleNamespace(id=1, username=None, full_name="А", first_name="А"),
        user_data={"id": 1},
    )
    assert handled is True
    assert "деталей" in replies[-1]
    assert context.user_data[engineering_help.MODE_KEY] == "awaiting_description"


def test_outside_the_flow_messages_are_not_intercepted() -> None:
    import asyncio

    context = SimpleNamespace(user_data={})
    handled = asyncio.run(
        engineering_help.maybe_handle_message(
            update=SimpleNamespace(effective_message=SimpleNamespace(message_id=1)),
            context=context,
            message_text="Просто вопрос",
            user=SimpleNamespace(id=1, username=None, full_name="А", first_name="А"),
            user_data={"id": 1},
        )
    )
    assert handled is False


# --- уточняющий диалог по практике ---------------------------------------


def test_dialog_key_is_the_practice_for_engineering_and_area_for_legal() -> None:
    assert intake_dialog.dialog_key({"practice": "engineering", "legal_area": "other"}) == "engineering"
    assert intake_dialog.dialog_key({"practice": "hybrid", "legal_area": "other"}) == "hybrid"
    assert intake_dialog.dialog_key({"practice": "legal", "legal_area": "contracts"}) == "contracts"
    assert intake_dialog.dialog_key({"legal_area": "disputes"}) == "disputes"


def test_practice_dialog_asks_about_process_not_law() -> None:
    questions = intake_dialog.questions_for("engineering")
    assert [q.key for q in questions] == ["process", "systems", "users"]
    assert intake_dialog.next_question("engineering", ["process"]).key == "systems"
    assert intake_dialog.next_question("engineering", ["process", "systems", "users"]) is None
    # Право не затронуто.
    assert intake_dialog.questions_for("contracts")[0].key == "stage"


def test_practice_texts_hand_off_to_the_team_not_the_lawyer() -> None:
    assert intake_dialog.build_handoff(documents_count=1, answered_count=3, area="engineering").startswith(
        "Всё передал команде."
    )
    assert "Юристы и инженеры" in intake_dialog.build_handoff(documents_count=0, answered_count=1, area="hybrid")
    assert intake_dialog.build_early_handoff("engineering").startswith("Конечно, передаю команде.")
    orientation = intake_dialog.build_orientation("engineering")
    assert "команда начала предметно" in orientation
    assert "область" not in orientation.lower()
    assert "техническое задание" in orientation
    assert "передам всё команде" in intake_dialog.build_document_request("engineering", nda_signed=False)
    # Право — как было.
    assert intake_dialog.build_handoff(documents_count=0, answered_count=0).startswith("Всё передал юристу.")


def test_outreach_for_practice_does_not_promise_a_lawyer() -> None:
    message = intake_outreach.build_outreach_message(
        {"practice": "engineering", "category": "telegram_bot", "name": "Иван", "client_type": "company"}
    )
    assert "инженерной задачи" in message
    assert "команда его уже смотрит" in message
    assert "юрист" not in message.lower()
    hybrid = intake_outreach.build_outreach_message({"practice": "hybrid", "name": "Анна"})
    assert "юристы и инженеры его уже смотрят" in hybrid
    legal = intake_outreach.build_outreach_message({"practice": "legal", "legal_area": "contracts", "name": "Иван"})
    assert "юрист его уже смотрит" in legal
