from __future__ import annotations

from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import ApiKey, Lead, LegalIntake, Scope
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select


def _create_api_key(scope: Scope, name: str) -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw_key), scope=scope, name=name, is_active=True))
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw_key


def _cleanup(api_key_names: list[str], intake_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        lead_ids = db.execute(
            select(LegalIntake.lead_id).where(LegalIntake.id.in_(intake_ids))
        ).scalars().all()
        db.execute(delete(LegalIntake).where(LegalIntake.id.in_(intake_ids)))
        if lead_ids:
            db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(api_key_names)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_create_list_update_and_idempotency() -> None:
    client = TestClient(app)
    bot_name = "pytest.legal-intake.bot"
    admin_name = "pytest.legal-intake.admin"
    bot_key = _create_api_key(Scope.bot, bot_name)
    admin_key = _create_api_key(Scope.admin, admin_name)
    idempotency_key = f"legal-intake-{uuid4().hex}"
    intake_ids: list[str] = []
    payload = {
        "source": "website_form",
        "name": "Иван Петров",
        "contact": "+7 900 000-00-00",
        "company": "Пример",
        "client_type": "company",
        "legal_area": "disputes",
        "description": "Нужно оценить перспективы спора и ближайший процессуальный срок.",
        "urgency": "urgent",
        "deadline": "до пятницы",
        "region": "Москва",
        "source_context": "/legal-help/business",
        "consent_accepted": True,
        "consent_version": "pytest-v1",
        "consent_at": "2026-07-16T10:00:00Z",
    }

    try:
        first = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": bot_key, "Idempotency-Key": idempotency_key},
            json=payload,
        )
        assert first.status_code == 201
        intake_ids.append(first.json()["id"])
        assert first.json()["status"] == "received"
        assert first.json()["lead_contact"] == payload["contact"]
        assert first.json()["legal_area"] == "disputes"

        repeated = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": bot_key, "Idempotency-Key": idempotency_key},
            json=payload,
        )
        assert repeated.status_code == 201
        assert repeated.json()["id"] == intake_ids[0]

        db = SessionLocal()
        try:
            count = db.execute(
                select(func.count()).select_from(LegalIntake).where(LegalIntake.id == intake_ids[0])
            ).scalar_one()
            assert count == 1
        finally:
            db.close()

        bot_list = client.get("/api/v1/legal-intakes", headers={"X-API-Key": bot_key})
        assert bot_list.status_code == 403

        admin_list = client.get(
            "/api/v1/legal-intakes?status_filter=received",
            headers={"X-API-Key": admin_key},
        )
        assert admin_list.status_code == 200
        assert any(row["id"] == intake_ids[0] for row in admin_list.json())

        updated = client.patch(
            f"/api/v1/legal-intakes/{intake_ids[0]}",
            headers={"X-API-Key": admin_key},
            json={
                "status": "conflict_check",
                "conflict_status": "clear",
                "assigned_to": "Андрей",
                "internal_note": "Связаться сегодня",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "conflict_check"
        assert updated.json()["conflict_status"] == "clear"
        assert updated.json()["assigned_to"] == "Андрей"
    finally:
        _cleanup([bot_name, admin_name], intake_ids)


def test_requires_explicit_consent() -> None:
    client = TestClient(app)
    key_name = "pytest.legal-intake.consent"
    bot_key = _create_api_key(Scope.bot, key_name)
    try:
        response = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": bot_key},
            json={
                "source": "telegram_bot",
                "contact": "@example_user",
                "description": "Достаточно длинное описание юридической задачи для проверки.",
                "consent_accepted": False,
                "consent_version": "pytest-v1",
                "consent_at": "2026-07-16T10:00:00Z",
            },
        )
        assert response.status_code == 422
    finally:
        _cleanup([key_name], [])
