from __future__ import annotations

from types import SimpleNamespace

import pytest

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
        user_handlers,
        "_fetch_post_context",
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
    monkeypatch.setattr(user_handlers, "notify_admin_new_lead", _fake_notify)
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
