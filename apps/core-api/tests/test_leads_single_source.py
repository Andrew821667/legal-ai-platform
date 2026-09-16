"""Лиды только в ядре: номер выдаёт ядро, upsert умеет частичное обновление.

До этого лид из Telegram жил в SQLite бота, а ядро было зеркалом с номером
из SQLite. Теперь бот пишет и читает только здесь, и ядро должно уметь то,
что раньше делал SQLite: выдать номер, обновить одно поле, не сливать двух
людей в одного и не заводить второго при переносе.
"""

from __future__ import annotations

from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Lead, LeadSource, Scope
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, text


def _key(name: str) -> str:
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=Scope.bot, name=name, is_active=True))
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw


def _cleanup(name: str, telegram_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(Lead).where(Lead.telegram_user_id.in_(telegram_ids)))
        db.execute(delete(ApiKey).where(ApiKey.name == name))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _post(client: TestClient, key: str, body: dict) -> dict:
    response = client.post(
        "/api/v1/leads",
        headers={"X-API-Key": key, "Idempotency-Key": f"pytest-{uuid4().hex}"},
        json=body,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_core_assigns_lead_number_for_telegram_leads_only() -> None:
    client = TestClient(app)
    name = "pytest.leads.seq"
    key = _key(name)
    try:
        first = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501001, "name": "Первый"})
        second = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501002, "name": "Второй"})
        site = _post(client, key, {"source": "website_form", "contact": "seq@example.ru", "name": "С сайта"})
        assert isinstance(first["legacy_lead_id"], int)
        assert second["legacy_lead_id"] > first["legacy_lead_id"]
        assert site["legacy_lead_id"] is None
    finally:
        _cleanup(name, [501001, 501002])
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.contact == "seq@example.ru"))
            db.commit()
        finally:
            db.close()


def test_partial_update_keeps_fields_that_were_not_sent() -> None:
    """Бот обновляет по одному полю; умолчания схемы не затирают живые значения."""
    client = TestClient(app)
    name = "pytest.leads.partial"
    key = _key(name)
    try:
        created = _post(
            client,
            key,
            {
                "source": "telegram_bot",
                "telegram_user_id": 501010,
                "name": "Клиент",
                "status": "qualified",
                "cta_shown": True,
                "lead_magnet_delivered": True,
                "temperature": "hot",
                "team_size": "6-20",
                "contracts_per_month": "10-50",
            },
        )
        touched = _post(
            client,
            key,
            {
                "source": "telegram_bot",
                "legacy_lead_id": created["legacy_lead_id"],
                "last_message_at": "2026-09-16T10:00:00+00:00",
            },
        )
        assert touched["id"] == created["id"]
        assert touched["status"] == "qualified"
        assert touched["cta_shown"] is True
        assert touched["lead_magnet_delivered"] is True
        assert touched["temperature"] == "hot"
        assert touched["team_size"] == "6-20"
        assert touched["contracts_per_month"] == "10-50"
        from datetime import datetime

        assert datetime.fromisoformat(touched["last_message_at"]).timestamp() == datetime.fromisoformat(
            "2026-09-16T10:00:00+00:00"
        ).timestamp()
    finally:
        _cleanup(name, [501010])


def test_force_new_and_latest_lead_of_account() -> None:
    """force_new заводит второго; обычный upsert по аккаунту обновляет последнего."""
    client = TestClient(app)
    name = "pytest.leads.force-new"
    key = _key(name)
    try:
        first = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501020, "name": "Первое дело"})
        second = _post(
            client,
            key,
            {"source": "telegram_bot", "telegram_user_id": 501020, "name": "Второе дело", "force_new": True},
        )
        assert second["id"] != first["id"]
        assert second["legacy_lead_id"] != first["legacy_lead_id"]

        updated = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501020, "temperature": "hot"})
        assert updated["id"] == second["id"]
        assert updated["temperature"] == "hot"
    finally:
        _cleanup(name, [501020])


def test_update_only_does_not_create() -> None:
    client = TestClient(app)
    name = "pytest.leads.update-only"
    key = _key(name)
    try:
        response = client.post(
            "/api/v1/leads",
            headers={"X-API-Key": key},
            json={"source": "telegram_bot", "telegram_user_id": 501030, "update_only": True, "temperature": "hot"},
        )
        assert response.status_code == 404
        db = SessionLocal()
        try:
            assert db.scalar(text("SELECT count(*) FROM leads WHERE telegram_user_id = 501030")) == 0
        finally:
            db.close()
    finally:
        _cleanup(name, [501030])


def test_claim_unlinked_adopts_the_lead_created_by_an_intake() -> None:
    """Перенос из SQLite: лид аккаунта без номера получает номер, второго не появляется."""
    client = TestClient(app)
    name = "pytest.leads.claim"
    key = _key(name)
    db = SessionLocal()
    try:
        # Лид, заведённый обращением: без номера (до этой ревизии ядро номера не выдавало).
        row = Lead(source=LeadSource.telegram_bot, telegram_user_id=501040, name="Из обращения", contact="@claim")
        db.add(row)
        db.flush()
        row.legacy_lead_id = None
        db.commit()
        unlinked_id = str(row.id)
    finally:
        db.close()
    try:
        claimed = _post(
            client,
            key,
            {
                "source": "telegram_bot",
                "telegram_user_id": 501040,
                "legacy_lead_id": 777001,
                "claim_unlinked": True,
                "temperature": "warm",
            },
        )
        assert claimed["id"] == unlinked_id
        assert claimed["legacy_lead_id"] == 777001
        assert claimed["name"] == "Из обращения"

        again = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501040, "legacy_lead_id": 777001})
        assert again["id"] == unlinked_id
    finally:
        _cleanup(name, [501040])


def test_legacy_sequence_moves_forward_only() -> None:
    client = TestClient(app)
    name = "pytest.leads.handover"
    key = _key(name)
    try:
        before = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501050, "name": "До"})
        floor = before["legacy_lead_id"] + 1000
        moved = client.post("/api/v1/leads/legacy-sequence", headers={"X-API-Key": key}, json={"min_next": floor})
        assert moved.status_code == 200, moved.text
        assert moved.json()["next_legacy_lead_id"] == floor

        after = _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501051, "name": "После"})
        assert after["legacy_lead_id"] == floor

        # Назад счётчик не двигается.
        back = client.post("/api/v1/leads/legacy-sequence", headers={"X-API-Key": key}, json={"min_next": 5})
        assert back.json()["next_legacy_lead_id"] == floor + 1
    finally:
        _cleanup(name, [501050, 501051])


def test_list_leads_offset() -> None:
    client = TestClient(app)
    name = "pytest.leads.offset"
    key = _key(name)
    try:
        for index in range(3):
            _post(client, key, {"source": "telegram_bot", "telegram_user_id": 501060 + index, "name": f"Смещение {index}"})
        page = client.get(
            "/api/v1/leads?source_filter=telegram_bot&limit=1&offset=1",
            headers={"X-API-Key": key},
        ).json()
        assert len(page) == 1
        full = client.get("/api/v1/leads?source_filter=telegram_bot&limit=3", headers={"X-API-Key": key}).json()
        assert page[0]["id"] == full[1]["id"]
    finally:
        _cleanup(name, [501060, 501061, 501062])
