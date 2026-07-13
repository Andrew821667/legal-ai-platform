from __future__ import annotations

from types import SimpleNamespace

import pytest
from handlers import callback_flows


@pytest.mark.anyio
async def test_pdn_consent_creates_profile_and_edits_single_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    edited: list[tuple[str, object | None]] = []
    replied: list[str] = []
    granted: list[int] = []

    async def _fake_answer(query, **kwargs) -> None:
        return None

    async def _fake_edit(message, text, **kwargs) -> None:
        edited.append((text, kwargs.get("reply_markup")))

    async def _fake_reply(message, text, **kwargs) -> None:
        replied.append(text)

    async def _fake_process(**kwargs) -> None:
        return None

    monkeypatch.setattr(callback_flows.utils, "safe_answer_callback", _fake_answer)
    monkeypatch.setattr(callback_flows.utils, "safe_edit_html", _fake_edit)
    monkeypatch.setattr(callback_flows.utils, "safe_reply_html", _fake_reply)
    monkeypatch.setattr(callback_flows, "process_pending_start_payload", _fake_process)
    monkeypatch.setattr(callback_flows.database.db, "get_user_by_telegram_id", lambda telegram_id: None)
    monkeypatch.setattr(callback_flows.database.db, "create_or_update_user", lambda **kwargs: 7)
    monkeypatch.setattr(
        callback_flows.database.db,
        "get_user_by_id",
        lambda user_id: {"id": user_id, "telegram_id": 42},
    )
    monkeypatch.setattr(callback_flows.database.db, "grant_user_consent", granted.append)
    monkeypatch.setattr(callback_flows.database.db, "get_local_lead_by_user_id", lambda user_id: None)
    monkeypatch.setattr(callback_flows.database.db, "get_user_offer_profile", lambda user_id: None)

    query = SimpleNamespace(
        data="consent_pdn_yes",
        from_user=SimpleNamespace(
            id=42,
            username="user",
            first_name="Андрей",
            last_name=None,
        ),
        message=SimpleNamespace(),
    )
    update = SimpleNamespace(callback_query=query)

    await callback_flows.handle_consent_callback(update, SimpleNamespace(user_data={}))

    assert granted == [7]
    assert len(edited) == 1
    assert "Согласие" in edited[0][0]
    assert edited[0][1] is not None
    assert replied == []
