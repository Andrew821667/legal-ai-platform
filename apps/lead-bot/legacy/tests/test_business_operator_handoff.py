from types import SimpleNamespace

import pytest

from handlers import business


@pytest.mark.asyncio
async def test_operator_personal_handoff_switches_chat_without_creating_lead(monkeypatch):
    """Личное обращение — это не лид: оператор сам увидел сообщение, заводить
    лид и слать «новый лид» себе же незачем (см. Current.md, кейс Виктории:
    личные фразы попадали в фоновый квалификатор воронки как ответы лида)."""
    captured = {"chat_mode": [], "events": []}

    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 41)
    monkeypatch.setattr(business.database.db, "set_chat_mode", lambda chat_id, mode: captured["chat_mode"].append((chat_id, mode)))
    monkeypatch.setattr(
        business.database.db,
        "track_event",
        lambda user_id, event_type, payload=None, lead_id=None: captured["events"].append((user_id, event_type, payload, lead_id)),
    )

    def _fail(*args, **kwargs):
        raise AssertionError("personal_request не должен трогать лиды/CRM")

    monkeypatch.setattr(business.database.db, "create_or_update_lead", _fail)
    monkeypatch.setattr(business.database.db, "get_lead_by_user_id", _fail)
    monkeypatch.setattr(business.database.db, "update_lead_last_message_time", _fail)
    monkeypatch.setattr(business.database.db, "get_user_funnel_state", _fail)
    monkeypatch.setattr(business.database.db, "update_user_funnel_state", _fail)
    monkeypatch.setattr(business.database.db, "update_lead_funnel_state", _fail)

    async def _fail_notify(**kwargs):
        raise AssertionError("личное обращение не должно уведомлять «о новом лиде»")

    monkeypatch.setattr(business, "notify_admin_new_lead", _fail_notify)

    sent = []

    async def _fake_send_message(**kwargs):
        sent.append(kwargs)

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

    assert lead_id is None
    assert captured["chat_mode"] == [(555001, "personal")]
    assert len(captured["events"]) == 1
    user_id, event_type, payload, tracked_lead_id = captured["events"][0]
    assert (user_id, event_type, tracked_lead_id) == (41, "personal_handoff_requested", None)
    assert payload["note"] == "нужно лично подключиться"
    assert len(sent) == 1 and "личного обращения" in sent[0]["text"].lower()


@pytest.mark.asyncio
async def test_operator_consultation_handoff_still_creates_lead(monkeypatch):
    """Ветка консультации не должна пострадать от выделения personal_request."""
    monkeypatch.setattr(business.database.db, "create_or_update_user", lambda **kwargs: 41)
    monkeypatch.setattr(business.database.db, "get_lead_by_user_id", lambda user_id: {})
    monkeypatch.setattr(business.database.db, "update_lead_last_message_time", lambda user_id: None)
    monkeypatch.setattr(business.database.db, "create_or_update_lead", lambda user_id, payload: 77)
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

    notified = []

    async def _fake_notify_admin_new_lead(**kwargs):
        notified.append(kwargs)

    monkeypatch.setattr(business, "notify_admin_new_lead", _fake_notify_admin_new_lead)

    async def _fake_send_message(**kwargs):
        return None

    context = SimpleNamespace(bot=SimpleNamespace(send_message=_fake_send_message), user_data={})
    message = SimpleNamespace(
        chat=SimpleNamespace(id=555002, username="client_user2", first_name="Client2", last_name=None),
        business_connection_id="bc-1",
    )
    operator = SimpleNamespace(id=999001, full_name="Andrew Operator", first_name="Andrew")

    lead_id = await business.handle_business_operator_handoff(
        context=context,
        message=message,
        operator_user=operator,
        trigger="command",
        mode="consultation",
        note_text="нужна консультация по договору",
    )

    assert lead_id == 77
    assert len(notified) == 1
