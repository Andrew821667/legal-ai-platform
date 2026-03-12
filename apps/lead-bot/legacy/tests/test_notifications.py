from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import helpers, user_ai_response


@pytest.mark.anyio
async def test_consultation_cta_uses_safe_reply_html(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        user_ai_response.funnel,
        "should_show_consultation_button",
        lambda response_stage, cta_shown: True,
    )

    async def _fake_reply_html(message, text, **kwargs):
        captured["text"] = text
        captured["reply_markup"] = kwargs.get("reply_markup")
        captured["action"] = kwargs.get("action")
        return SimpleNamespace()

    monkeypatch.setattr(user_ai_response.utils, "safe_reply_html", _fake_reply_html)

    shown = await user_ai_response._maybe_send_consultation_cta(
        original_message=SimpleNamespace(),
        response_stage="qualify",
        cta_shown=False,
    )

    assert shown is True
    assert captured["text"] == user_ai_response.content.CONSULTATION_CTA_TEXT
    assert captured["reply_markup"] is not None
    assert captured["action"] == "consultation_cta"


@pytest.mark.anyio
async def test_notify_admin_new_lead_skips_same_origin_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_targets: list[int] = []
    marked: list[int] = []

    monkeypatch.setattr(
        helpers.database.db,
        "get_lead_by_id",
        lambda lead_id: {
            "id": lead_id,
            "temperature": "cold",
            "pain_point": "Ничего не понял",
            "phone": "+79092330909",
        },
    )
    monkeypatch.setattr(helpers.database.db, "get_user_by_id", lambda user_id: None)
    monkeypatch.setattr(helpers.database.db, "create_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(helpers.database.db, "mark_lead_notification_sent", lambda lead_id: marked.append(lead_id))
    monkeypatch.setattr(
        helpers.admin_interface.admin_interface,
        "get_lead_snapshot_by_legacy_id",
        lambda lead_id: {},
    )
    monkeypatch.setattr(helpers.core_api_bridge, "enabled", False)
    monkeypatch.setattr(helpers.config, "LEADS_CHAT_ID", None)
    monkeypatch.setattr(helpers.config, "ADMIN_TELEGRAM_ID", 321681061)
    monkeypatch.setattr(helpers.config, "SMTP_USER", "")
    monkeypatch.setattr(helpers.config, "SMTP_PASSWORD", "")

    class _FakeBot:
        async def send_message(self, chat_id, text):
            sent_targets.append(chat_id)
            return SimpleNamespace()

    context = SimpleNamespace(bot=_FakeBot())

    await helpers.notify_admin_new_lead(
        context=context,
        lead_id=7,
        lead_data={"temperature": "cold", "pain_point": "Ничего не понял", "phone": "+79092330909"},
        user_data={
            "id": 1,
            "telegram_id": 321681061,
            "username": "LegalAI_Popov_Andrew",
            "first_name": "Andrew",
        },
    )

    assert sent_targets == []
    assert marked == [7]


@pytest.mark.anyio
async def test_notify_admin_new_lead_requires_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_targets: list[int] = []
    marked: list[int] = []

    monkeypatch.setattr(
        helpers.database.db,
        "get_lead_by_id",
        lambda lead_id: {"id": lead_id, "temperature": "cold", "pain_point": "Ничего не понял"},
    )
    monkeypatch.setattr(helpers.database.db, "get_user_by_id", lambda user_id: None)
    monkeypatch.setattr(helpers.database.db, "create_notification", lambda *args, **kwargs: None)
    monkeypatch.setattr(helpers.database.db, "mark_lead_notification_sent", lambda lead_id: marked.append(lead_id))
    monkeypatch.setattr(
        helpers.admin_interface.admin_interface,
        "get_lead_snapshot_by_legacy_id",
        lambda lead_id: {},
    )
    monkeypatch.setattr(helpers.core_api_bridge, "enabled", False)
    monkeypatch.setattr(helpers.config, "LEADS_CHAT_ID", 777777)
    monkeypatch.setattr(helpers.config, "ADMIN_TELEGRAM_ID", 888888)
    monkeypatch.setattr(helpers.config, "SMTP_USER", "")
    monkeypatch.setattr(helpers.config, "SMTP_PASSWORD", "")

    class _FakeBot:
        async def send_message(self, chat_id, text):
            sent_targets.append(chat_id)
            return SimpleNamespace()

    context = SimpleNamespace(bot=_FakeBot())

    await helpers.notify_admin_new_lead(
        context=context,
        lead_id=8,
        lead_data={"temperature": "cold", "pain_point": "Ничего не понял"},
        user_data={
            "id": 1,
            "telegram_id": 321681061,
            "username": "LegalAI_Popov_Andrew",
            "first_name": "Andrew",
        },
    )

    assert sent_targets == []
    assert marked == []
