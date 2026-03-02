from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Scope, User
from core_api.security import generate_api_key, hash_api_key


def _create_api_key(scope: Scope, name: str) -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_hash=hash_api_key(raw_key),
                scope=scope,
                name=name,
                is_active=True,
            )
        )
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw_key


def _delete_api_key_by_name(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(ApiKey).where(ApiKey.name == name))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_upsert_and_list_users() -> None:
    client = TestClient(app)
    api_key_name = "pytest.users.read"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    created_ids: list[str] = []

    try:
        created = client.post(
            "/api/v1/users",
            headers={"X-API-Key": raw_key, "Idempotency-Key": "user-upsert-1"},
            json={
                "telegram_id": 555001111,
                "username": "core_user",
                "first_name": "Core",
                "last_name": "User",
                "consent_given": True,
                "transborder_consent": True,
                "conversation_stage": "discover",
                "cta_variant": "A",
                "cta_shown": True,
            },
        )
        assert created.status_code == 200
        created_payload = created.json()
        created_ids.append(created_payload["id"])
        assert created_payload["telegram_id"] == 555001111
        assert created_payload["username"] == "core_user"
        assert created_payload["consent_given"] is True

        listed = client.get(
            "/api/v1/users?telegram_id=555001111&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert listed.status_code == 200
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["telegram_id"] == 555001111

        without_consent = client.get(
            "/api/v1/users?without_consent=true&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert without_consent.status_code == 200
    finally:
        db = SessionLocal()
        try:
            if created_ids:
                db.execute(delete(User).where(User.id.in_(created_ids)))
                db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
