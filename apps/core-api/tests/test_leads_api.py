from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Lead, LeadSource, LeadStatus, Scope
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


def test_list_leads_and_summary() -> None:
    client = TestClient(app)
    api_key_name = "pytest.leads.read"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    created_ids = []

    db = SessionLocal()
    try:
        first = Lead(
            source=LeadSource.telegram_bot,
            legacy_lead_id=1001,
            telegram_user_id=111,
            name="Lead One",
            contact="@lead_one",
            status=LeadStatus.new,
            company="Alpha",
            email="one@example.com",
            phone="+70000000001",
            temperature="cold",
            service_category="contracts",
            specific_need="automation",
            pain_point="slow intake",
            budget="100k",
            urgency="high",
            industry="legal",
            conversation_stage="discover",
            cta_variant="A",
            cta_shown=True,
            lead_magnet_type="checklist",
            lead_magnet_delivered=True,
            notes="first",
        )
        second = Lead(
            source=LeadSource.telegram_bot,
            legacy_lead_id=1002,
            telegram_user_id=222,
            name="Lead Two",
            contact="@lead_two",
            status=LeadStatus.qualified,
            company="Beta",
            email="two@example.com",
            phone="+70000000002",
            temperature="warm",
            service_category="claims",
            specific_need="triage",
            pain_point="manual work",
            budget="200k",
            urgency="medium",
            industry="b2b",
            conversation_stage="qualify",
            cta_variant="B",
            cta_shown=False,
            lead_magnet_type="guide",
            lead_magnet_delivered=False,
            notes="second",
        )
        db.add_all([first, second])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        created_ids.extend([first.id, second.id])
    finally:
        db.close()

    try:
        listed = client.get(
            "/api/v1/leads?source_filter=telegram_bot&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert listed.status_code == 200
        payload = listed.json()
        ids = {row["id"] for row in payload}
        assert str(created_ids[0]) in ids
        assert str(created_ids[1]) in ids
        first_payload = next(row for row in payload if row["id"] == str(created_ids[0]))
        assert first_payload["company"] == "Alpha"
        assert first_payload["temperature"] == "cold"
        assert first_payload["lead_magnet_delivered"] is True

        filtered = client.get(
            "/api/v1/leads?status_filter=qualified&temperature_filter=warm&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert filtered.status_code == 200
        filtered_payload = filtered.json()
        assert any(row["id"] == str(created_ids[1]) for row in filtered_payload)
        assert all(row["status"] == "qualified" for row in filtered_payload)

        summary = client.get(
            "/api/v1/leads/stats/summary",
            headers={"X-API-Key": raw_key},
        )
        assert summary.status_code == 200
        summary_payload = summary.json()
        assert summary_payload["total_leads"] >= 2
        assert summary_payload["new_leads"] >= 1
        assert summary_payload["qualified_leads"] >= 1
        assert summary_payload["telegram_bot_leads"] >= 2
        assert summary_payload["warm_leads"] >= 1
        assert summary_payload["cold_leads"] >= 1
        assert summary_payload["stage_discover"] >= 1
        assert summary_payload["stage_qualify"] >= 1
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)


def test_upsert_uses_legacy_lead_id_to_keep_separate_leads() -> None:
    client = TestClient(app)
    api_key_name = "pytest.leads.legacy-id"
    raw_key = _create_api_key(Scope.bot, api_key_name)
    created_ids: list[str] = []
    first_key = f"legacy-2001-{uuid4().hex}"
    second_key = f"legacy-2002-{uuid4().hex}"

    try:
        first = client.post(
            "/api/v1/leads",
            headers={"X-API-Key": raw_key, "Idempotency-Key": first_key},
            json={
                "source": "telegram_bot",
                "legacy_lead_id": 2001,
                "telegram_user_id": 999,
                "name": "Same User First Lead",
                "status": "new",
                "temperature": "cold",
            },
        )
        assert first.status_code == 200
        created_ids.append(first.json()["id"])

        second = client.post(
            "/api/v1/leads",
            headers={"X-API-Key": raw_key, "Idempotency-Key": second_key},
            json={
                "source": "telegram_bot",
                "legacy_lead_id": 2002,
                "telegram_user_id": 999,
                "name": "Same User Second Lead",
                "status": "qualified",
                "temperature": "warm",
            },
        )
        assert second.status_code == 200
        created_ids.append(second.json()["id"])

        assert created_ids[0] != created_ids[1]

        listed = client.get(
            "/api/v1/leads?source_filter=telegram_bot&limit=10",
            headers={"X-API-Key": raw_key},
        )
        assert listed.status_code == 200
        payload = listed.json()
        same_user_rows = [row for row in payload if row["telegram_user_id"] == 999]
        assert len(same_user_rows) >= 2
        assert {row["legacy_lead_id"] for row in same_user_rows} >= {2001, 2002}
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.id.in_(created_ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
