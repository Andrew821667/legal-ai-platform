from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Lead, Scope
from core_api.security import generate_api_key, hash_api_key
from core_api import lead_notifications


@pytest.fixture
def api_key() -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_hash=hash_api_key(raw_key),
                scope=Scope.bot,
                name="pytest.lead_notify",
                is_active=True,
            )
        )
        db.commit()
        cache.invalidate()
        yield raw_key
    finally:
        db.execute(delete(ApiKey).where(ApiKey.name == "pytest.lead_notify"))
        db.commit()
        cache.invalidate()
        db.close()


@pytest.fixture
def notify_config(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        get_settings().__class__,
        "model_config",
        get_settings().__class__.model_config,
    )
    get_settings.cache_clear()
    monkeypatch.setenv("LEAD_NOTIFY_BOT_TOKEN", "test-token")
    monkeypatch.setenv("LEAD_NOTIFY_CHAT_ID", "999")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_telegram(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []

    class _Response:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, data: dict[str, Any], timeout: int, proxies=None) -> _Response:
        calls.append({"url": url, "data": data, "timeout": timeout, "proxies": proxies})
        return _Response()

    monkeypatch.setattr(lead_notifications.requests, "post", fake_post)
    return calls


def _cleanup_lead(lead_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.commit()
    finally:
        db.close()


def test_new_website_lead_triggers_notification(
    api_key: str,
    notify_config: None,
    fake_telegram: list[dict[str, Any]],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "website_form",
            "name": "Sample Name",
            "contact": f"+7900{uuid.uuid4().hex[:7]}",
            "notes": "offer=consultation",
            "utm_source": "site",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    lead_id = uuid.UUID(body["id"])

    try:
        assert len(fake_telegram) == 1
        call = fake_telegram[0]
        assert call["url"].endswith("/bottest-token/sendMessage")
        assert call["data"]["chat_id"] == "999"
        text = call["data"]["text"]
        assert "Новая заявка с сайта" in text  # website_form header
        # Уведомление идёт через Telegram (серверы за рубежом): без имени и
        # контакта — они в рабочем месте.
        assert "Sample Name" not in text
        assert "+7900" not in text
        assert "Имя и контакт — в рабочем месте" in text
        assert "Консультация юриста" in text  # localized offer
        # Should not leak technical/admin internals to the manager.
        assert "ip_hash" not in text
        assert "ua_hash" not in text
        assert "/admin/leads/" not in text
        assert str(lead_id) not in text  # UUID hidden
    finally:
        _cleanup_lead(lead_id)


def test_new_miniapp_lead_triggers_notification(
    api_key: str,
    notify_config: None,
    fake_telegram: list[dict[str, Any]],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "miniapp_form",
            "name": "MiniApp User",
            "contact": f"+7900{uuid.uuid4().hex[:7]}",
            "notes": "offer=consultation\ntelegram_verified=1",
            "utm_source": "miniapp",
            "utm_medium": "telegram",
        },
    )
    assert response.status_code == 200, response.text
    lead_id = uuid.UUID(response.json()["id"])

    try:
        assert len(fake_telegram) == 1
        text = fake_telegram[0]["data"]["text"]
        assert "Mini App" in text  # source label for miniapp_form
        assert "MiniApp User" not in text  # имя — только в рабочем месте
        assert "Telegram ID" not in text
        assert "telegram_verified" not in text  # internal flag hidden
    finally:
        _cleanup_lead(lead_id)


def test_telegram_bot_lead_does_not_notify(
    api_key: str,
    notify_config: None,
    fake_telegram: list[dict[str, Any]],
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "telegram_bot",
            "telegram_user_id": int(uuid.uuid4().int % 10_000_000),
            "name": "TG User",
            "contact": "@tg_user_sample",
        },
    )
    assert response.status_code == 200
    lead_id = uuid.UUID(response.json()["id"])

    try:
        assert fake_telegram == []
    finally:
        _cleanup_lead(lead_id)


def test_update_existing_lead_does_not_notify(
    api_key: str,
    notify_config: None,
    fake_telegram: list[dict[str, Any]],
) -> None:
    client = TestClient(app)
    contact = f"+7900{uuid.uuid4().hex[:7]}"

    first = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "website_form",
            "name": "First",
            "contact": contact,
        },
    )
    assert first.status_code == 200
    lead_id = uuid.UUID(first.json()["id"])
    assert len(fake_telegram) == 1

    second = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "website_form",
            "name": "Updated",
            "contact": contact,
        },
    )
    assert second.status_code == 200
    assert uuid.UUID(second.json()["id"]) == lead_id

    try:
        assert len(fake_telegram) == 1  # no second notification
    finally:
        _cleanup_lead(lead_id)


def test_no_notification_when_not_configured(
    api_key: str,
    fake_telegram: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LEAD_NOTIFY_BOT_TOKEN", raising=False)
    monkeypatch.delenv("LEAD_NOTIFY_CHAT_ID", raising=False)
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": api_key},
        json={
            "source": "website_form",
            "name": "No Notify",
            "contact": f"+7900{uuid.uuid4().hex[:7]}",
        },
    )
    assert response.status_code == 200
    lead_id = uuid.UUID(response.json()["id"])

    try:
        assert fake_telegram == []
    finally:
        _cleanup_lead(lead_id)
        get_settings.cache_clear()


def test_telegram_goes_through_the_configured_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Напрямую api.telegram.org с прод-хоста не открывается — только через прокси."""
    seen: list[Any] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"ok": True, "result": {"message_id": 7}}

    def fake_post(url: str, data: dict[str, Any], timeout: int, proxies=None) -> _Response:
        seen.append(proxies)
        return _Response()

    monkeypatch.setattr(lead_notifications.requests, "post", fake_post)
    monkeypatch.setenv("LEGAL_AI_HTTPS_PROXY", "http://192.168.64.1:10811")
    get_settings.cache_clear()
    try:
        result = lead_notifications._post_telegram_message("token", "1", "текст")
    finally:
        get_settings.cache_clear()
    assert result == {"message_id": 7}
    assert seen == [{"https": "http://192.168.64.1:10811", "http": "http://192.168.64.1:10811"}]


def test_without_proxy_telegram_is_called_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"ok": True, "result": {}}

    def fake_post(url: str, data: dict[str, Any], timeout: int, proxies=None) -> _Response:
        seen.append(proxies)
        return _Response()

    monkeypatch.setattr(lead_notifications.requests, "post", fake_post)
    monkeypatch.setenv("LEGAL_AI_HTTPS_PROXY", "")
    get_settings.cache_clear()
    try:
        lead_notifications._post_telegram_message("token", "1", "текст")
    finally:
        get_settings.cache_clear()
    assert seen == [None]


def test_legal_intake_notice_carries_no_personal_data(
    api_key: str,
    notify_config: None,
    fake_telegram: list[dict[str, Any]],
) -> None:
    """Уведомление юристу о юридическом обращении идёт через Telegram (серверы за
    рубежом): ни имени, ни контакта, ни телефона и почты из описания в нём нет."""
    from test_practice import _cleanup

    client = TestClient(app)
    contact = f"intake-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/legal-intakes",
        headers={"X-API-Key": api_key},
        json={
            "source": "website_form",
            "name": "Аркадий Соколов",
            "contact": contact,
            "description": "Аркадий Соколов, звоните +7 916 123-45-67 или пишите arkady@example.ru: спор по аренде.",
            "consent_accepted": True,
            "consent_version": "test",
            "consent_at": "2026-10-01T00:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    lead_id = response.json()["lead_id"]
    try:
        texts = [call["data"]["text"] for call in fake_telegram]
        assert texts, "уведомление не отправлено"
        text = texts[-1]
        assert "Имя, организация и контакт — в рабочем месте" in text
        for leaked in ("Аркадий", "Соколов", contact, "+7 916", "arkady@example.ru"):
            assert leaked not in text, leaked
        assert "спор по аренде" in text  # суть обращения юрист видит
    finally:
        _cleanup([], lead_id)


def test_telegram_safe_masks_known_names_and_contacts() -> None:
    text = lead_notifications.telegram_safe(
        "Ольга Петрова, ООО Ромашка: +7 999 123-45-67, olga@example.ru", ("Ольга Петрова", "ООО Ромашка")
    )
    assert "Петрова" not in text and "+7 999" not in text and "olga@example.ru" not in text
