"""Вход из кабинета по конкретному делу: /start case_<id> и сообщение юристу."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import case_messages, start_payloads

INTAKE_ID = "11111111-1111-1111-1111-111111111111"
LEAD_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def replies(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        sent.append(text)

    monkeypatch.setattr(case_messages.utils, "safe_reply_text", _reply)
    return sent


@pytest.fixture
def admin_messages(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    sent: list[dict] = []

    async def _send(bot, action="send_message", **kwargs) -> None:
        sent.append(kwargs)

    monkeypatch.setattr(case_messages.utils, "safe_send_message", _send)
    monkeypatch.setattr(case_messages.config, "ADMIN_TELEGRAM_ID", 777)
    return sent


@pytest.fixture
def summary(monkeypatch: pytest.MonkeyPatch) -> dict:
    data = {
        "client": {"lead_id": LEAD_ID, "name": "Иван"},
        "cases": [
            {
                "id": INTAKE_ID,
                "practice": "legal",
                "legal_area": "employment",
                "category": None,
                "status": "accepted",
                "created_at": "2026-09-10T12:00:00+00:00",
            }
        ],
    }
    monkeypatch.setattr(case_messages.core_api_bridge, "client_portal_summary", lambda telegram_user_id: data)
    return data


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=42, username="client", first_name="Иван")


def _update(text: str) -> SimpleNamespace:
    return SimpleNamespace(effective_user=_user(), effective_message=SimpleNamespace(text=text))


@pytest.mark.asyncio
async def test_start_opens_own_case_and_remembers_it(replies, summary) -> None:
    context = SimpleNamespace(user_data={start_payloads.PENDING_START_PAYLOAD_KEY: f"case_{INTAKE_ID}"}, bot=None)

    handled = await start_payloads.process_pending_start_payload(
        message=object(), context=context, user_data={"id": 1}, user=_user()
    )

    assert handled is True
    assert replies == [
        "📁 Дело: Трудовые отношения от 10.09.2026 · в работе.\n\n"
        "Напишите, что хотите передать юристу по этому делу, — сообщение "
        "уйдёт ему с пометкой дела, и он ответит вам здесь."
    ]
    assert context.user_data[case_messages.CASE_CONTEXT_KEY]["intake_id"] == INTAKE_ID
    assert context.user_data[case_messages.CASE_CONTEXT_KEY]["lead_id"] == LEAD_ID


@pytest.mark.asyncio
async def test_start_with_foreign_case_does_not_open_it(replies, summary) -> None:
    """Идентификатор из ссылки можно подделать: чужое дело не открывается."""
    context = SimpleNamespace(user_data={start_payloads.PENDING_START_PAYLOAD_KEY: "case_99999999-9999-9999-9999-999999999999"})

    handled = await start_payloads.process_pending_start_payload(
        message=object(), context=context, user_data={"id": 1}, user=_user()
    )

    assert handled is True
    assert case_messages.CASE_CONTEXT_KEY not in context.user_data
    assert replies and replies[0].startswith("Не нашёл это дело")


@pytest.mark.asyncio
async def test_message_goes_to_case_card_and_to_lawyer(monkeypatch, replies, admin_messages) -> None:
    recorded: list[dict] = []

    def _record(intake_id, **kwargs) -> bool:
        recorded.append({"intake_id": intake_id, **kwargs})
        return True

    monkeypatch.setattr(case_messages.core_api_bridge, "record_clarification", _record)
    context = SimpleNamespace(
        user_data={
            case_messages.CASE_CONTEXT_KEY: {
                "intake_id": INTAKE_ID,
                "lead_id": LEAD_ID,
                "title": "Трудовые отношения",
                "until": 10**12,
            }
        },
        bot=object(),
    )

    handled = await case_messages.maybe_handle_case_message(
        update=_update("Работодатель прислал ответ на претензию"),
        context=context,
        original_message=object(),
        message_text="Работодатель прислал ответ на претензию",
        user=_user(),
        user_data={"first_name": "Иван", "last_name": "Петров", "username": "client"},
    )

    assert handled is True
    assert recorded[0]["intake_id"] == INTAKE_ID
    assert recorded[0]["question_text"] == "Сообщение клиента по делу"
    assert recorded[0]["answer_text"] == "Работодатель прислал ответ на претензию"
    assert recorded[0]["question_key"].startswith("client_message:")
    assert admin_messages[0]["chat_id"] == 777
    assert "«Трудовые отношения»" in admin_messages[0]["text"]
    assert "Иван Петров (@client)" in admin_messages[0]["text"]
    assert "Работодатель прислал ответ на претензию" in admin_messages[0]["text"]
    assert replies == ["Передал юристу по делу «Трудовые отношения». Ответ придёт сюда же."]
    # Контекст остаётся: следующее сообщение того же разговора — тоже по делу.
    assert case_messages.CASE_CONTEXT_KEY in context.user_data


@pytest.mark.asyncio
async def test_expired_case_context_is_ignored(replies) -> None:
    context = SimpleNamespace(
        user_data={case_messages.CASE_CONTEXT_KEY: {"intake_id": INTAKE_ID, "until": 1}},
        bot=object(),
    )

    handled = await case_messages.maybe_handle_case_message(
        update=_update("привет"),
        context=context,
        original_message=object(),
        message_text="привет",
        user=_user(),
        user_data={},
    )

    assert handled is False
    assert case_messages.CASE_CONTEXT_KEY not in context.user_data
    assert replies == []


@pytest.mark.asyncio
async def test_core_and_lawyer_both_unreachable_is_reported_to_client(monkeypatch, replies, admin_messages) -> None:
    monkeypatch.setattr(case_messages.core_api_bridge, "record_clarification", lambda *a, **k: False)

    async def _fail(bot, action="send_message", **kwargs) -> None:
        raise RuntimeError("network")

    monkeypatch.setattr(case_messages.utils, "safe_send_message", _fail)
    context = SimpleNamespace(
        user_data={case_messages.CASE_CONTEXT_KEY: {"intake_id": INTAKE_ID, "title": "Спор", "until": 10**12}},
        bot=object(),
    )

    handled = await case_messages.maybe_handle_case_message(
        update=_update("текст"),
        context=context,
        original_message=object(),
        message_text="текст",
        user=_user(),
        user_data={},
    )

    assert handled is True
    assert replies[0].startswith("Не получилось передать сообщение")


def test_case_title_follows_practice() -> None:
    assert case_messages.case_title({"practice": "legal", "legal_area": "real_estate"}) == "Недвижимость"
    assert case_messages.case_title({"practice": "engineering", "category": "telegram_bot"}) == "Telegram-бот"
    assert case_messages.case_title({"practice": "hybrid", "category": "compliance"}) == "Комплаенс"
    assert case_messages.case_title({"practice": "legal", "legal_area": "unknown"}) == "Требует уточнения"
