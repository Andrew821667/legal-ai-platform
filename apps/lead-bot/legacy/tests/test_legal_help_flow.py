from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import legal_help


def test_legal_help_client_type_markup() -> None:
    values = [
        button.callback_data
        for row in legal_help.legal_help_client_type_markup().inline_keyboard
        for button in row
    ]
    assert values == [
        "legal_client:company",
        "legal_client:entrepreneur",
        "legal_client:individual",
        "legal_client:unknown",
    ]


@pytest.mark.anyio
async def test_legal_help_message_uses_dedicated_core_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    replies: list[str] = []

    async def _reply(message, text, **kwargs) -> None:
        replies.append(text)

    def _create(payload, *, idempotency_key):
        captured["payload"] = payload
        captured["idempotency_key"] = idempotency_key
        return {"id": "11111111-1111-1111-1111-111111111111", "lead_id": "22222222-2222-2222-2222-222222222222"}

    def _record_intake_lead(user_id, core_lead_id, lead_data):
        captured["lead_user_id"] = user_id
        captured["core_lead_id"] = core_lead_id
        captured["lead_data"] = lead_data
        return 77

    monkeypatch.setattr(legal_help.utils, "safe_reply_text", _reply)
    monkeypatch.setattr(legal_help.database.db, "record_intake_lead", _record_intake_lead)
    monkeypatch.setattr(legal_help.database.db, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(legal_help.core_api_bridge, "create_legal_intake", _create)

    context = SimpleNamespace(
        user_data={
            legal_help.LEGAL_HELP_MODE_KEY: "awaiting_description",
            legal_help.LEGAL_HELP_CLIENT_TYPE_KEY: "company",
        }
    )
    message = SimpleNamespace(message_id=55)
    update = SimpleNamespace(effective_message=message)
    user = SimpleNamespace(
        id=42,
        username="example_user",
        full_name="Иван Петров",
        first_name="Иван",
    )

    handled = await legal_help.maybe_handle_legal_help_message(
        update=update,
        context=context,
        message_text="Нужно проверить перспективы судебного спора и определить ближайший срок.",
        user=user,
        user_data={"id": 10, "telegram_id": 42},
    )

    assert handled is True
    assert captured["payload"]["legal_area"] == "other"
    assert captured["payload"]["client_type"] == "company"
    assert captured["payload"]["consent_accepted"] is True
    assert captured["payload"]["contact"] == "@example_user"
    # Лид заводит обращение; бот дописывает в него свою квалификацию.
    assert captured["lead_user_id"] == 10
    assert captured["core_lead_id"] == "22222222-2222-2222-2222-222222222222"
    assert captured["lead_data"]["temperature"] == "warm"
    assert captured["lead_data"]["cta_variant"] == "legal_help"
    assert context.user_data.get(legal_help.LEGAL_HELP_MODE_KEY) is None
    assert "передано юристу" in replies[-1]


@pytest.mark.anyio
async def test_legal_help_keeps_local_fallback_and_notifies_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    notifications: list[dict] = []

    async def _reply(message, text, **kwargs) -> None:
        return None

    async def _send_message(**kwargs) -> None:
        notifications.append(kwargs)

    monkeypatch.setattr(legal_help.utils, "safe_reply_text", _reply)
    # Ядро не подтвердило обращение: лид всё же заводится отдельно (номер 88),
    # а владелец получает текст обращения, чтобы разобрать его вручную.
    monkeypatch.setattr(legal_help.database.db, "record_intake_lead", lambda user_id, core_lead_id, payload: 88)
    monkeypatch.setattr(legal_help.database.db, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(legal_help.core_api_bridge, "create_legal_intake", lambda *args, **kwargs: None)

    context = SimpleNamespace(
        user_data={
            legal_help.LEGAL_HELP_MODE_KEY: "awaiting_description",
            legal_help.LEGAL_HELP_CLIENT_TYPE_KEY: "individual",
        },
        bot=SimpleNamespace(send_message=_send_message),
    )
    update = SimpleNamespace(effective_message=SimpleNamespace(message_id=56))
    user = SimpleNamespace(id=43, username=None, full_name="Анна Иванова", first_name="Анна")

    handled = await legal_help.maybe_handle_legal_help_message(
        update=update,
        context=context,
        message_text="Нужно оценить наследственный спор и понять порядок дальнейших действий.",
        user=user,
        user_data={"id": 11, "telegram_id": 43},
    )

    assert handled is True
    assert len(notifications) == 1
    assert "НЕ ДОШЛО ДО ЯДРА" in notifications[0]["text"]
    assert "tg:43" in notifications[0]["text"]
    assert "Лид: 88" in notifications[0]["text"]
