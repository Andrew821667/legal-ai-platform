from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Event, Lead, LeadSource, LeadStatus, Scope
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


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


def test_pending_notification_queue_is_core_owned_and_source_filtered() -> None:
    client = TestClient(app)
    name = f"pytest.leads.pending.{uuid4().hex}"
    key = _create_api_key(Scope.bot, name)
    db = SessionLocal()
    try:
        telegram = Lead(
            source=LeadSource.telegram_bot,
            legacy_lead_id=91_001,
            telegram_user_id=91_001,
            name="Telegram lead",
            contact="@pending",
            temperature="warm",
            pain_point="Нужна автоматизация",
            last_message_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            notification_sent=False,
        )
        website = Lead(
            source=LeadSource.website_form,
            name="Website lead",
            contact="site@example.com",
            temperature="hot",
            pain_point="Нужна консультация",
            last_message_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            notification_sent=False,
        )
        db.add_all([telegram, website])
        db.commit()
        db.refresh(telegram)
        db.refresh(website)
        ids = [telegram.id, website.id]
    finally:
        db.close()

    try:
        queued = client.get(
            "/api/v1/leads/notifications/pending?idle_minutes=5&source_filter=telegram_bot",
            headers={"X-API-Key": key},
        )
        assert queued.status_code == 200
        got = {row["id"] for row in queued.json()}
        assert str(ids[0]) in got and str(ids[1]) not in got

        marked = client.post(
            f"/api/v1/leads/{ids[0]}/notification-sent",
            headers={"X-API-Key": key},
            json={},
        )
        assert marked.status_code == 200
        assert marked.json()["notification_sent"] is True
        assert marked.json()["notification_sent_at"] is not None
        assert str(ids[0]) not in {
            row["id"]
            for row in client.get(
                "/api/v1/leads/notifications/pending?idle_minutes=5&source_filter=telegram_bot",
                headers={"X-API-Key": key},
            ).json()
        }
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.id.in_(ids)))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(name)


def test_delete_lead_detaches_events() -> None:
    client = TestClient(app)
    api_key_name = "pytest.leads.delete-detach"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    lead_id = None
    event_id = None

    db = SessionLocal()
    try:
        lead = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=555001,
            name="Delete With Event",
            status=LeadStatus.new,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id

        event = Event(lead_id=lead.id, user_id=None, type="pytest.lead.delete", payload={"kind": "test"})
        db.add(event)
        db.commit()
        db.refresh(event)
        event_id = event.id
    finally:
        db.close()

    try:
        response = client.delete(f"/api/v1/leads/{lead_id}", headers={"X-API-Key": raw_key})
        assert response.status_code == 204

        db = SessionLocal()
        try:
            deleted_lead = db.get(Lead, lead_id)
            assert deleted_lead is None

            detached_event = db.get(Event, event_id)
            assert detached_event is not None
            assert detached_event.lead_id is None
        finally:
            db.close()
    finally:
        if event_id is not None:
            db = SessionLocal()
            try:
                db.execute(delete(Event).where(Event.id == event_id))
                db.commit()
            finally:
                db.close()
        _delete_api_key_by_name(api_key_name)


def test_bot_handoff_reaches_the_lawyer_even_without_message_time() -> None:
    """Клиент дошёл до «передачи юристу» одними кнопками: last_message_at пуст,
    температура не тёплая — раньше он не попадал ни в уведомления, ни в задачи."""
    from core_api.models import LegalIntake, LegalIntakeStatus

    client = TestClient(app)
    name = f"pytest.leads.handoff.{uuid4().hex}"
    bot = _create_api_key(Scope.bot, name)
    admin = _create_api_key(Scope.admin, f"{name}.admin")
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        def handoff(**extra) -> Lead:
            values = dict(
                source=LeadSource.telegram_bot, telegram_user_id=9_900_000_000 + int(uuid4().hex[:5], 16),
                name="Передан юристу", contact="@handoff", temperature="cold", conversation_stage="handoff",
                notification_sent=False, created_at=now - timedelta(hours=2), last_activity_at=now - timedelta(hours=2),
            )
            values.update(extra)
            row = Lead(**values)
            db.add(row)
            return row

        fresh = handoff()
        stale = handoff(created_at=now - timedelta(days=40), last_activity_at=now - timedelta(days=40))
        with_intake = handoff()
        db.flush()
        db.add(LegalIntake(lead_id=with_intake.id, description="Обращение уже есть.", status=LegalIntakeStatus.accepted))
        db.commit()
        ids = {"fresh": str(fresh.id), "stale": str(stale.id), "with_intake": str(with_intake.id)}
    finally:
        db.close()

    try:
        pending = {
            row["id"]
            for row in client.get(
                "/api/v1/leads/notifications/pending?idle_minutes=5&limit=100", headers={"X-API-Key": bot}
            ).json()
        }
        assert ids["fresh"] in pending
        # Старше месяца — не уведомление, а задача в «Сегодня».
        assert ids["stale"] not in pending

        today = client.get("/api/v1/lawyer/today", headers={"X-API-Key": admin}).json()
        section = next(s for s in today["sections"] if s["key"] == "bot_handoff")
        shown = {item["lead_id"] for item in section["items"]}
        assert {ids["fresh"], ids["stale"]} <= shown
        assert ids["with_intake"] not in shown
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(LegalIntake).where(LegalIntake.lead_id.in_(list(ids.values()))))
            db.execute(delete(Lead).where(Lead.id.in_(list(ids.values()))))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(name)
        _delete_api_key_by_name(f"{name}.admin")
