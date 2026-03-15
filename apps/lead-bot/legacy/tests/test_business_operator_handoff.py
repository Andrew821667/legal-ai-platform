from types import SimpleNamespace

import pytest

from handlers import business


@pytest.mark.asyncio
async def test_operator_personal_handoff_switches_chat_to_personal(monkeypatch):
    captured = {"chat_mode": []}

    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 41)
    monkeypatch.setattr(business.database.db, "set_chat_mode", lambda chat_id, mode: captured["chat_mode"].append((chat_id, mode)))
    monkeypatch.setattr(business.database.db, "get_lead_by_user_id", lambda user_id: {})
    monkeypatch.setattr(business.database.db, "update_lead_last_message_time", lambda user_id: None)
    monkeypatch.setattr(
        business.database.db,
        "create_or_update_lead",
        lambda user_id, payload: 77,
    )
    monkeypatch.setattr(
        business.database.db,
        "get_user_funnel_state",
        lambda user_id: {"conversation_stage": "discover", "cta_variant": "a"},
    )
    monkeypatch.setattr(business.database.db, "update_user_funnel_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(business.database.db, "update_lead_funnel_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(business.database.db, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(business.database.db, "get_lead_by_id", lambda lead_id: {"id": lead_id})
    monkeypatch.setattr(business.funnel, "choose_cta_variant", lambda user_id: "a")

    async def _fake_notify_admin_new_lead(**kwargs):
        return None

    monkeypatch.setattr(business, "notify_admin_new_lead", _fake_notify_admin_new_lead)

    async def _fake_send_message(**kwargs):
        return None

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})
    message = SimpleNamespace(
        chat=SimpleNamespace(id=555001, username="client_user", first_name="Client", last_name=None),
        business_connection_id="bc-1",
    )
    operator = SimpleNamespace(id=999001, full_name="Andrew Operator", first_name="Andrew")

    lead_id = await business.handle_business_operator_handoff(
        context=context,
        message=message,
        operator_user=operator,
        trigger="command",
        mode="personal_request",
        note_text="нужно лично подключиться",
    )

    assert lead_id == 77
    assert captured["chat_mode"] == [(555001, "personal")]
