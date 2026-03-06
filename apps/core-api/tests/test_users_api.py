from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Event, Lead, LeadSource, LeadStatus, Scope, User
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
    idempotency_key = f"user-upsert-1-{uuid4().hex}"

    try:
        created = client.post(
            "/api/v1/users",
            headers={"X-API-Key": raw_key, "Idempotency-Key": idempotency_key},
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


def test_admin_user_data_operations_by_telegram_id() -> None:
    client = TestClient(app)
    admin_key_name = "pytest.users.admin.ops"
    admin_key = _create_api_key(Scope.admin, admin_key_name)
    telegram_user_id = 700000000 + (uuid4().int % 100000000)
    created_user_id = None

    db = SessionLocal()
    lead_ids: list = []
    try:
        # Create user via API so endpoint path mirrors runtime behavior.
        created = client.post(
            "/api/v1/users",
            headers={"X-API-Key": admin_key},
            json={
                "telegram_id": telegram_user_id,
                "username": "ops_user",
                "first_name": "Ops",
                "last_name": "User",
                "consent_given": True,
                "transborder_consent": True,
                "marketing_consent": True,
                "conversation_stage": "qualify",
                "cta_variant": "B",
                "cta_shown": True,
            },
        )
        assert created.status_code == 200
        created_user_id = created.json()["id"]

        # Create two leads directly to avoid upsert merge by telegram_user_id in /leads.
        lead_a = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=telegram_user_id,
            name="Lead A",
            contact="@lead_a",
            email="a@example.com",
            phone="+79000000001",
            status=LeadStatus.new,
        )
        lead_b = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=telegram_user_id,
            name="Lead B",
            contact="@lead_b",
            email="b@example.com",
            phone="+79000000002",
            status=LeadStatus.qualified,
        )
        db.add_all([lead_a, lead_b])
        db.flush()
        lead_ids = [lead_a.id, lead_b.id]

        db.add(
            Event(
                lead_id=lead_a.id,
                user_id=None,
                type="legacy.analytics",
                payload={"telegram_user_id": telegram_user_id},
            )
        )
        db.add(
            Event(
                lead_id=None,
                user_id=None,
                type="legacy.analytics",
                payload={"telegram_user_id": telegram_user_id, "legacy_user_id": 42},
            )
        )
        db.commit()

        # Add one event linked to user_id after user row exists.
        user_row = db.execute(select(User).where(User.telegram_id == telegram_user_id).limit(1)).scalar_one()
        db.add(
            Event(
                lead_id=None,
                user_id=user_row.id,
                type="legacy.analytics.user",
                payload={},
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        gdpr = client.post(
            f"/api/v1/users/by-telegram/{telegram_user_id}/gdpr-clear",
            headers={"X-API-Key": admin_key},
        )
        assert gdpr.status_code == 200
        gdpr_body = gdpr.json()
        assert gdpr_body["users_updated"] == 1
        assert gdpr_body["leads_anonymized"] == 2

        db = SessionLocal()
        try:
            user_row = db.execute(select(User).where(User.telegram_id == telegram_user_id).limit(1)).scalar_one()
            assert user_row.consent_given is False
            assert user_row.consent_revoked is True
            rows = list(db.execute(select(Lead).where(Lead.telegram_user_id == telegram_user_id)).scalars().all())
            assert len(rows) == 2
            assert all(item.email is None and item.phone is None and item.contact is None for item in rows)
        finally:
            db.close()

        reset = client.post(
            f"/api/v1/users/by-telegram/{telegram_user_id}/reset-new",
            headers={"X-API-Key": admin_key},
        )
        assert reset.status_code == 200
        reset_body = reset.json()
        assert reset_body["users_reset"] == 1
        assert reset_body["leads_deleted"] == 2
        assert reset_body["events_deleted"] >= 1

        db = SessionLocal()
        try:
            user_row = db.execute(select(User).where(User.telegram_id == telegram_user_id).limit(1)).scalar_one()
            assert user_row.consent_revoked is False
            assert user_row.conversation_stage == "discover"
            leads_after_reset = list(
                db.execute(select(Lead).where(Lead.telegram_user_id == telegram_user_id)).scalars().all()
            )
            assert leads_after_reset == []
        finally:
            db.close()

        # Create one new lead to verify full delete removes user + leads.
        db = SessionLocal()
        try:
            db.add(
                Lead(
                    source=LeadSource.telegram_bot,
                    telegram_user_id=telegram_user_id,
                    name="Lead C",
                    status=LeadStatus.new,
                )
            )
            db.commit()
        finally:
            db.close()

        deleted = client.delete(
            f"/api/v1/users/by-telegram/{telegram_user_id}",
            headers={"X-API-Key": admin_key},
        )
        assert deleted.status_code == 200
        deleted_body = deleted.json()
        assert deleted_body["users_deleted"] == 1
        assert deleted_body["leads_deleted"] == 1

        db = SessionLocal()
        try:
            user_row = db.execute(select(User).where(User.telegram_id == telegram_user_id).limit(1)).scalar_one_or_none()
            assert user_row is None
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            if created_user_id is not None:
                user_row = db.execute(select(User).where(User.telegram_id == telegram_user_id).limit(1)).scalar_one_or_none()
                db.execute(delete(Event).where(Event.lead_id.in_(lead_ids)))
                if user_row is not None:
                    db.execute(delete(Event).where(Event.user_id == user_row.id))
                db.execute(
                    text(
                        """
                        DELETE FROM events
                        WHERE (payload ->> 'telegram_user_id') = :tg_id
                           OR (payload ->> 'user_id') = :tg_id
                           OR (payload ->> 'telegram_id') = :tg_id
                        """
                    ),
                    {"tg_id": str(telegram_user_id)},
                )
                db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id))
                db.execute(delete(User).where(User.telegram_id == telegram_user_id))
                db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(admin_key_name)
