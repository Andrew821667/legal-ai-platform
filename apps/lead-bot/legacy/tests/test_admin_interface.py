import os
import tempfile

import pytest

import admin_interface
from database import Database


@pytest.fixture
def test_db():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path)
    yield db
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_get_user_snapshot_prefers_core_lead(test_db, monkeypatch):
    user_id = test_db.create_or_update_user(
        telegram_id=555000111,
        username="snapshot_user",
        first_name="Snapshot",
        last_name="Tester",
    )
    test_db.create_or_update_lead(
        user_id,
        {
            "name": "Legacy Lead",
            "email": "legacy@example.com",
            "company": "Legacy Co",
            "temperature": "cold",
        },
    )
    test_db.grant_user_consent(user_id)
    test_db.set_user_transborder_consent(user_id, True)

    interface = admin_interface.AdminInterface(test_db)

    monkeypatch.setattr(
        interface,
        "_core_get_json",
        lambda path, params=None: [
            {
                "id": "core-1",
                "created_at": "2026-03-02T10:00:00Z",
                "updated_at": "2026-03-02T11:00:00Z",
                "name": "Core Lead",
                "company": "Core Co",
                "email": "core@example.com",
                "phone": "+79990001122",
                "temperature": "hot",
                "status": "qualified",
                "service_category": "contracts",
                "specific_need": "review",
                "pain_point": "slow team",
                "budget": "300k",
                "urgency": "high",
                "industry": "legal",
                "conversation_stage": "qualify",
                "cta_variant": "A",
                "cta_shown": True,
                "lead_magnet_type": "checklist",
                "lead_magnet_delivered": True,
            }
        ]
        if path == "/api/v1/leads" and params and params.get("telegram_user_id") == 555000111
        else None,
    )

    snapshot = interface.get_user_snapshot(555000111)

    assert snapshot is not None
    assert snapshot["user"]["telegram_id"] == 555000111
    assert snapshot["lead"]["name"] == "Core Lead"
    assert snapshot["lead"]["company"] == "Core Co"
    assert snapshot["lead"]["temperature"] == "hot"
    assert bool(snapshot["consent"]["consent_given"]) is True
    assert bool(snapshot["consent"]["transborder_consent"]) is True


def test_get_lead_snapshot_by_legacy_id_prefers_core(test_db, monkeypatch):
    user_id = test_db.create_or_update_user(
        telegram_id=555000222,
        username="legacy_id_user",
        first_name="LegacyId",
    )
    lead_id = test_db.create_or_update_lead(
        user_id,
        {
            "name": "Legacy Lead",
            "company": "Legacy Company",
            "temperature": "cold",
        },
    )

    interface = admin_interface.AdminInterface(test_db)

    monkeypatch.setattr(
        interface,
        "_core_get_json",
        lambda path, params=None: [
            {
                "id": "core-legacy-id",
                "created_at": "2026-03-02T10:00:00Z",
                "updated_at": "2026-03-02T11:00:00Z",
                "name": "Core Lead by Legacy ID",
                "company": "Core Company",
                "email": "core-id@example.com",
                "phone": "+79990002233",
                "temperature": "warm",
                "status": "qualified",
                "service_category": "claims",
                "specific_need": "routing",
                "pain_point": "manual triage",
                "budget": "500k",
                "urgency": "high",
                "industry": "services",
                "conversation_stage": "diagnose",
                "cta_variant": "B",
                "cta_shown": True,
                "lead_magnet_type": "playbook",
                "lead_magnet_delivered": False,
            }
        ]
        if path == "/api/v1/leads" and params and params.get("legacy_lead_id") == lead_id
        else None,
    )

    lead = interface.get_lead_snapshot_by_legacy_id(lead_id)

    assert lead["name"] == "Core Lead by Legacy ID"
    assert lead["company"] == "Core Company"
    assert lead["temperature"] == "warm"


def test_get_user_by_telegram_id_prefers_core_fields(test_db, monkeypatch):
    test_db.create_or_update_user(
        telegram_id=555000333,
        username="local_username",
        first_name="Local",
        last_name="User",
    )

    interface = admin_interface.AdminInterface(test_db)

    monkeypatch.setattr(
        interface,
        "_core_get_json",
        lambda path, params=None: [
            {
                "telegram_id": 555000333,
                "username": "core_username",
                "first_name": "Core",
                "last_name": "User",
                "consent_given": True,
                "consent_date": "2026-03-02T10:00:00Z",
                "consent_revoked": False,
                "consent_revoked_at": None,
                "transborder_consent": True,
                "transborder_consent_date": "2026-03-02T10:01:00Z",
                "marketing_consent": False,
                "marketing_consent_date": None,
                "conversation_stage": "discover",
                "cta_variant": "A",
                "cta_shown": True,
                "cta_shown_at": "2026-03-02T10:02:00Z",
                "created_at": "2026-03-02T09:00:00Z",
                "last_interaction": "2026-03-02T10:05:00Z",
            }
        ]
        if path == "/api/v1/users" and params and params.get("telegram_id") == 555000333
        else None,
    )

    user = interface.get_user_by_telegram_id(555000333)

    assert user is not None
    assert user["telegram_id"] == 555000333
    assert user["username"] == "core_username"
    assert user["first_name"] == "Core"
    assert bool(user["consent_given"]) is True
    assert bool(user["transborder_consent"]) is True


def test_get_recent_users_and_total_prefers_core(test_db, monkeypatch):
    interface = admin_interface.AdminInterface(test_db)

    def _fake_core(path, params=None):
        if path == "/api/v1/users" and params == {"limit": 2, "offset": 2}:
            return [
                {
                    "telegram_id": 555700001,
                    "username": "core_u1",
                    "first_name": "Core",
                    "last_name": "One",
                },
                {
                    "telegram_id": 555700002,
                    "username": "core_u2",
                    "first_name": "Core",
                    "last_name": "Two",
                },
            ]
        if path == "/api/v1/users/count":
            return {"total": 42}
        return None

    monkeypatch.setattr(interface, "_core_get_json", _fake_core)

    users = interface.get_recent_users(limit=2, offset=2)
    total = interface.get_total_users_count()

    assert len(users) == 2
    assert users[0]["telegram_id"] == 555700001
    assert users[1]["username"] == "core_u2"
    assert total == 42


def test_format_leads_list_supports_offset(test_db):
    interface = admin_interface.AdminInterface(test_db)

    user_a = test_db.create_or_update_user(telegram_id=555800001, username="l1", first_name="L1")
    user_b = test_db.create_or_update_user(telegram_id=555800002, username="l2", first_name="L2")
    user_c = test_db.create_or_update_user(telegram_id=555800003, username="l3", first_name="L3")
    test_db.create_or_update_lead(user_a, {"name": "Lead 1", "temperature": "cold", "company": "A"})
    test_db.create_or_update_lead(user_b, {"name": "Lead 2", "temperature": "warm", "company": "B"})
    test_db.create_or_update_lead(user_c, {"name": "Lead 3", "temperature": "hot", "company": "C"})

    text = interface.format_leads_list(limit=2, offset=1)

    assert "Позиция с #2" in text
    assert "2." in text
    assert "3." in text
