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

        counted = client.get(
            "/api/v1/users/count?telegram_id=555001111",
            headers={"X-API-Key": raw_key},
        )
        assert counted.status_code == 200
        assert counted.json()["total"] >= 1
    finally:
        db = SessionLocal()
        try:
            if created_ids:
                db.execute(delete(User).where(User.id.in_(created_ids)))
                db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_upsert_and_list_user_with_large_telegram_id() -> None:
    client = TestClient(app)
    api_key_name = "pytest.users.large-telegram-id"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    telegram_id = 5_690_579_174
    created_id: str | None = None

    try:
        created = client.post(
            "/api/v1/users",
            headers={"X-API-Key": raw_key},
            json={
                "telegram_id": telegram_id,
                "username": "large_tg_user",
                "first_name": "Large",
                "last_name": "Telegram",
            },
        )
        assert created.status_code == 200
        created_payload = created.json()
        created_id = created_payload["id"]
        assert created_payload["telegram_id"] == telegram_id

        listed = client.get(
            f"/api/v1/users?telegram_id={telegram_id}&limit=1",
            headers={"X-API-Key": raw_key},
        )
        assert listed.status_code == 200
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["telegram_id"] == telegram_id
    finally:
        db = SessionLocal()
        try:
            if created_id:
                db.execute(delete(User).where(User.id == created_id))
            else:
                db.execute(delete(User).where(User.telegram_id == telegram_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_upsert_user_does_not_reset_omitted_consents() -> None:
    client = TestClient(app)
    api_key_name = "pytest.users.preserve-consent"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    telegram_id = 6_000_000_000 + (uuid4().int % 100_000_000)
    created_id: str | None = None

    try:
        created = client.post(
            "/api/v1/users",
            headers={"X-API-Key": raw_key},
            json={
                "telegram_id": telegram_id,
                "consent_given": True,
                "transborder_consent": True,
                "marketing_consent": True,
            },
        )
        assert created.status_code == 200
        created_id = created.json()["id"]

        updated = client.post(
            "/api/v1/users",
            headers={"X-API-Key": raw_key},
            json={"telegram_id": telegram_id, "name": "Updated name"},
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["id"] == created_id
        assert payload["name"] == "Updated name"
        assert payload["consent_given"] is True
        assert payload["transborder_consent"] is True
        assert payload["marketing_consent"] is True
    finally:
        db = SessionLocal()
        try:
            if created_id:
                db.execute(delete(User).where(User.id == created_id))
            else:
                db.execute(delete(User).where(User.telegram_id == telegram_id))
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
            # Обращения без договора обезличены целиком и отвязаны от Telegram.
            rows = list(db.execute(select(Lead).where(Lead.id.in_(lead_ids))).scalars().all())
            assert len(rows) == 2
            assert all(item.anonymized_at is not None and item.telegram_user_id is None for item in rows)
            assert all(item.email is None and item.phone is None and item.notes is None for item in rows)
            assert not any("Lead" in (item.name or "") for item in rows)
            events = list(db.execute(select(Event).where(Event.lead_id == lead_ids[0])).scalars().all())
            assert all(event.payload == {} for event in events)
        finally:
            db.close()

        reset = client.post(
            f"/api/v1/users/by-telegram/{telegram_user_id}/reset-new",
            headers={"X-API-Key": admin_key},
        )
        assert reset.status_code == 200
        reset_body = reset.json()
        assert reset_body["users_reset"] == 1
        # Обезличенные обращения к Telegram больше не привязаны — сбрасывать нечего.
        assert reset_body["leads_deleted"] == 0
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
                db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
                db.execute(delete(Lead).where(Lead.telegram_user_id == telegram_user_id))
                db.execute(delete(User).where(User.telegram_id == telegram_user_id))
                db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(admin_key_name)


def test_gdpr_clear_keeps_lead_with_contract_work() -> None:
    """Отзыв согласия не обезличивает обращение с договорной работой:
    основание обработки — договор и закон; бот сообщает об этом прямо."""
    from core_api.models import ContractJob, ContractJobStatus, InputMode, UserRole

    client = TestClient(app)
    admin_key_name = f"pytest.users.admin.gdpr.{uuid4().hex[:6]}"
    admin_key = _create_api_key(Scope.admin, admin_key_name)
    telegram_user_id = 990_000_000 + int(uuid4().int % 1_000_000)
    db = SessionLocal()
    try:
        db.add(User(telegram_id=telegram_user_id, username="gdpr_work", consent_given=True, role=UserRole.user))
        free = Lead(source=LeadSource.telegram_bot, telegram_user_id=telegram_user_id, name="Без договора",
                    contact="@free", status=LeadStatus.new)
        worked = Lead(source=LeadSource.telegram_bot, telegram_user_id=telegram_user_id, name="С договором",
                      contact="@worked", status=LeadStatus.qualified)
        db.add_all([free, worked])
        db.flush()
        db.add(ContractJob(lead_id=worked.id, status=ContractJobStatus.new, input_mode=InputMode.text_only,
                           document_text="договор"))
        db.commit()
        free_id, worked_id = free.id, worked.id
    finally:
        db.close()

    try:
        response = client.post(
            f"/api/v1/users/by-telegram/{telegram_user_id}/gdpr-clear",
            headers={"X-API-Key": admin_key},
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["leads_anonymized"], body["leads_kept"]) == (1, 1)

        db = SessionLocal()
        try:
            free_row = db.get(Lead, free_id)
            worked_row = db.get(Lead, worked_id)
            assert free_row.anonymized_at is not None and free_row.contact != "@free"
            assert worked_row.anonymized_at is None and worked_row.contact == "@worked"
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ContractJob).where(ContractJob.lead_id.in_([free_id, worked_id])))
            db.execute(delete(Lead).where(Lead.id.in_([free_id, worked_id])))
            db.execute(delete(User).where(User.telegram_id == telegram_user_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(admin_key_name)
