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

    def fake_post(url: str, data: dict[str, Any], timeout: int) -> _Response:
        calls.append({"url": url, "data": data, "timeout": timeout})
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
            "notes": "source_channel=miniapp\noffer=consultation",
            "utm_source": "miniapp",
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
        assert "Новая заявка" in text
        assert "Sample Name" in text
        assert "miniapp" in text  # source_channel hint in notes
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
