from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import start_payloads
from handlers import user as user_handlers


class _DummyMessage:
    pass


@pytest.mark.anyio
async def test_process_pending_start_payload_creates_new_lead(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _DummyMessage()
    context = SimpleNamespace(user_data={"pending_start_payload": "readerq_11111111-1111-1111-1111-111111111111"})
    user_data = {"id": 77}
    user = SimpleNamespace(first_name="Andrew")

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        start_payloads,
        "fetch_post_context",
        lambda post_id: {"title": "Пилот automation", "source_url": "https://example.com/news"},
    )

    def _fake_create_new_lead(local_user_id: int, payload: dict) -> int:
        captured["create_new_lead"] = {"user_id": local_user_id, "payload": payload}
        return 456

    def _fake_track_event(local_user_id: int, event_type: str, payload: dict | None = None, lead_id: int | None = None) -> None:
        captured["track_event"] = {
            "user_id": local_user_id,
            "event_type": event_type,
            "payload": payload or {},
            "lead_id": lead_id,
        }

    async def _fake_notify(context_obj, lead_id: int, lead_payload: dict, user_row: dict, is_update: bool = False) -> None:
        captured["notify"] = {
            "lead_id": lead_id,
            "lead_payload": lead_payload,
            "user_id": user_row.get("id"),
            "is_update": is_update,
        }

    async def _fake_reply(message_obj, text: str, **kwargs) -> None:
        captured["reply"] = {"text": text, "kwargs": kwargs}

    monkeypatch.setattr(user_handlers.database.db, "create_new_lead", _fake_create_new_lead)
    monkeypatch.setattr(user_handlers.database.db, "track_event", _fake_track_event)
    monkeypatch.setattr(start_payloads, "notify_admin_new_lead", _fake_notify)
    monkeypatch.setattr(user_handlers.utils, "safe_reply_text", _fake_reply)

    processed = await user_handlers.process_pending_start_payload(
        message=message,
        context=context,
        user_data=user_data,
        user=user,
    )

    assert processed is True
    assert context.user_data.get("pending_start_payload") is None
    assert captured["create_new_lead"]
    assert captured["track_event"]
    assert captured["notify"]
    assert captured["reply"]

    lead_payload = captured["create_new_lead"]["payload"]  # type: ignore[index]
    assert lead_payload["service_category"] == "ai_legal_consulting"
    assert "post_id=11111111-1111-1111-1111-111111111111" in lead_payload["notes"]

    reply_text = captured["reply"]["text"]  # type: ignore[index]
    assert "заявка создана" in reply_text.lower()


@pytest.mark.anyio
async def test_process_pending_start_payload_ignores_unknown_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    message = _DummyMessage()
    context = SimpleNamespace(user_data={"pending_start_payload": "unknown_payload"})
    user_data = {"id": 1}
    user = SimpleNamespace(first_name="User")

    called = {"create_new_lead": False}

    def _fake_create_new_lead(*args, **kwargs):
        called["create_new_lead"] = True
        return 1

    monkeypatch.setattr(user_handlers.database.db, "create_new_lead", _fake_create_new_lead)

    processed = await user_handlers.process_pending_start_payload(
        message=message,
        context=context,
        user_data=user_data,
        user=user,
    )

    assert processed is False
    assert called["create_new_lead"] is False
    assert context.user_data.get("pending_start_payload") is None


@pytest.mark.anyio
async def test_channel_post_button_opens_the_assistant_with_post_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Кнопка «Ассистент AI Verdict» под постом: разговор с умным ассистентом,
    а не приём заявки к юристу. Заявки и уведомления юристу на клик нет."""
    context = SimpleNamespace(user_data={"pending_start_payload": "chq_22222222-2222-2222-2222-222222222222"})
    captured: dict[str, object] = {"leads": 0, "notices": 0, "history": []}

    monkeypatch.setattr(
        start_payloads,
        "fetch_post_context",
        lambda post_id: {"title": "Суд и ИИ", "text": "<b>Суды</b> начали применять ИИ &amp; проверять доказательства.", "rubric": "Право"},
    )

    def _no_lead(*args, **kwargs):
        captured["leads"] += 1  # type: ignore[operator]
        return 1

    monkeypatch.setattr(user_handlers.database.db, "create_new_lead", _no_lead)
    monkeypatch.setattr(
        user_handlers.database.db,
        "track_event",
        lambda local_user_id, event_type, payload=None, lead_id=None: captured.update(event=event_type, event_payload=payload),
    )
    monkeypatch.setattr(
        user_handlers.database.db,
        "add_message",
        lambda local_user_id, role, text: captured["history"].append((role, text)),  # type: ignore[union-attr]
    )

    async def _notify(*args, **kwargs) -> None:
        captured["notices"] += 1  # type: ignore[operator]

    async def _fake_reply(message_obj, text: str, **kwargs) -> None:
        captured["reply"] = text

    monkeypatch.setattr(start_payloads, "notify_admin_new_lead", _notify)
    monkeypatch.setattr(user_handlers.utils, "safe_reply_text", _fake_reply)

    processed = await user_handlers.process_pending_start_payload(
        message=_DummyMessage(), context=context, user_data={"id": 77}, user=SimpleNamespace(first_name="")
    )

    assert processed is True
    assert captured["leads"] == 0 and captured["notices"] == 0
    reply = captured["reply"]
    assert "Ассистент AI Verdict" in reply and "«Суд и ИИ»" in reply  # type: ignore[operator]
    assert "заявка создана" not in reply  # type: ignore[operator]
    assert captured["event"] == "channel_post_start"
    assert captured["event_payload"]["post_id"] == "22222222-2222-2222-2222-222222222222"  # type: ignore[index]
    assert captured["history"] == [("assistant", reply)]

    block = start_payloads.channel_post_context_block(context.user_data)
    assert "Суд и ИИ" in block and "Суды начали применять ИИ & проверять" in block
    assert "<b>" not in block
    # Через сутки пост уже не подмешивается в ответы.
    stale = context.user_data[start_payloads.CHANNEL_POST_CONTEXT_KEY]["at"] + 25 * 3600
    assert start_payloads.channel_post_context_block(context.user_data, now=stale) == ""
