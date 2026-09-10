"""Выдача ссылки для автономного входа из /admin.

Кнопка и обработчик — тонкая обвязка вокруг lawyer_session_link.py: сам
формат токена и его проверка уже закрыты тестами там. Здесь важно другое:
без секрета кнопки нет вовсе, а с секретом сообщение уносит рабочую ссылку,
а не пустышку.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import handlers.admin_callbacks as admin_callbacks


@pytest.mark.anyio
async def test_sends_a_working_link_when_secret_is_set(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_callbacks.get_config(),
        "LAWYER_SESSION_SECRET",
        "test-secret",
        raising=False,
    )
    monkeypatch.setattr(
        admin_callbacks.get_config(),
        "LAWYER_WORKSPACE_URL",
        "https://ai-verdict.ru/lawyer",
        raising=False,
    )
    sent = []

    async def _reply(message, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(admin_callbacks.utils, "safe_reply_text", _reply)

    query = SimpleNamespace(from_user=SimpleNamespace(id=848510279), message=SimpleNamespace())
    await admin_callbacks._send_standalone_login_link(query, SimpleNamespace())

    assert len(sent) == 1
    assert "https://ai-verdict.ru/lawyer/login?token=848510279." in sent[0]
    assert "30 дней" in sent[0]


@pytest.mark.anyio
async def test_reports_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_callbacks.get_config(), "LAWYER_SESSION_SECRET", "", raising=False
    )
    sent = []

    async def _reply(message, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(admin_callbacks.utils, "safe_reply_text", _reply)

    query = SimpleNamespace(from_user=SimpleNamespace(id=848510279), message=SimpleNamespace())
    await admin_callbacks._send_standalone_login_link(query, SimpleNamespace())

    assert len(sent) == 1
    assert "не настроен" in sent[0]
    assert "http" not in sent[0]


def test_button_hidden_without_secret(monkeypatch) -> None:
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_SESSION_SECRET", "", raising=False)
    assert constants.standalone_login_button() is None


def test_button_present_with_secret(monkeypatch) -> None:
    import handlers.constants as constants

    monkeypatch.setattr(constants.get_config(), "LAWYER_SESSION_SECRET", "x", raising=False)
    button = constants.standalone_login_button()
    assert button is not None
    assert button.callback_data == "admin_lawyer_link"
