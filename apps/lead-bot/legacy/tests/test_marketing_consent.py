"""Согласие на рассылки — только по явной кнопке (ч. 1 ст. 18 38-ФЗ).

Раньше /marketing_consent и кнопка «Согласие на рассылки» сами записывали
marketing_consent=True, хотя человек лишь открыл текст."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from handlers import callback_flows, user_commands


def _env(monkeypatch: pytest.MonkeyPatch, module, granted: bool) -> dict:
    state = {"granted": granted, "set_calls": [], "texts": []}

    async def _capture(message, text, **kwargs):
        state["texts"].append((text, kwargs.get("reply_markup")))

    async def _answer(*args, **kwargs):
        return None

    def _set(user_id, value):
        state["set_calls"].append(value)
        state["granted"] = value

    monkeypatch.setattr(module.utils, "safe_reply_html", _capture)
    monkeypatch.setattr(module.utils, "safe_edit_html", _capture)
    monkeypatch.setattr(module.utils, "safe_answer_callback", _answer)
    monkeypatch.setattr(module.database.db, "get_local_user_by_telegram_id", lambda tg: {"id": 7})
    monkeypatch.setattr(module.database.db, "get_user_by_telegram_id", lambda tg: {"id": 7})
    monkeypatch.setattr(module.database.db, "get_user_consent_state", lambda uid: {"marketing_consent": state["granted"]})
    monkeypatch.setattr(module.database.db, "set_user_marketing_consent", _set)
    return state


def _buttons(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


@pytest.mark.anyio
async def test_command_shows_text_without_granting(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _env(monkeypatch, user_commands, granted=False)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=5), message=SimpleNamespace())

    await user_commands.marketing_consent_command(update, SimpleNamespace())

    assert state["set_calls"] == []
    assert "doc_marketing_yes" in _buttons(state["texts"][0][1])


def _query(data: str):
    return SimpleNamespace(
        callback_query=SimpleNamespace(data=data, from_user=SimpleNamespace(id=5), message=SimpleNamespace())
    )


@pytest.mark.anyio
async def test_viewing_from_documents_does_not_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _env(monkeypatch, callback_flows, granted=False)

    await callback_flows.handle_documents_callback(_query("doc_marketing_consent"), SimpleNamespace())

    assert state["set_calls"] == []


@pytest.mark.anyio
async def test_explicit_buttons_grant_and_revoke(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _env(monkeypatch, callback_flows, granted=False)

    await callback_flows.handle_documents_callback(_query("doc_marketing_yes"), SimpleNamespace())
    assert state["set_calls"] == [True]
    assert "doc_marketing_no" in _buttons(state["texts"][-1][1])

    await callback_flows.handle_documents_callback(_query("doc_marketing_no"), SimpleNamespace())
    assert state["set_calls"] == [True, False]
    assert "doc_marketing_yes" in _buttons(state["texts"][-1][1])
