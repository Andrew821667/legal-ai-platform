from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    ConflictCheckStatus,
    Lead,
    LeadSource,
    LegalIntake,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


def _key(scope: Scope, name: str) -> str:
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=scope, name=name, is_active=True))
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw


def test_two_sided_agreement_flow(monkeypatch) -> None:
    from core_api.routers import service_agreements as api

    monkeypatch.setattr(
        api,
        "get_settings",
        lambda: SimpleNamespace(
            operator_name="Иванов Иван Иванович",
            operator_status="самозанятый",
            operator_inn="123456789012",
            operator_details="Москва, example@example.ru",
        ),
    )
    admin_name = f"pytest.agreement.admin.{uuid4().hex}"
    bot_name = f"pytest.agreement.bot.{uuid4().hex}"
    admin_key = _key(Scope.admin, admin_name)
    bot_key = _key(Scope.bot, bot_name)
    telegram_id = 8_000_000_000 + int(uuid4().hex[:6], 16)
    db = SessionLocal()
    try:
        lead = Lead(
            source=LeadSource.telegram_bot, telegram_user_id=telegram_id, name="Пётр Петров"
        )
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Нужно проверить договор поставки и подготовить замечания.",
            conflict_status=ConflictCheckStatus.clear,
        )
        db.add(intake)
        db.flush()
        db.add(
            NdaSignature(
                lead_id=lead.id,
                telegram_user_id=telegram_id,
                signer_full_name="Петров Пётр Петрович",
                signer_contact="client@example.ru",
                document_version="test-v1",
                document_hash="a" * 64,
                document_text="NDA",
            )
        )
        db.commit()
        intake_id = str(intake.id)
        lead_id = lead.id
    finally:
        db.close()

    client = TestClient(app)
    agreement_id = None
    try:
        body = {
            "intake_id": intake_id,
            "prepared_by_telegram_user_id": 42,
            "subject": "Правовой анализ договора поставки",
            "scope_text": "Изучить договор и подготовить письменные замечания",
            "exclusions_text": "Судебное представительство",
            "schedule_text": "Три рабочих дня после получения документов",
            "price_text": "15 000 рублей",
            "payment_terms": "100% до начала работы",
        }
        forbidden = client.post(
            "/api/v1/service-agreements",
            headers={"X-API-Key": bot_key},
            json=body,
        )
        assert forbidden.status_code == 403

        created = client.post(
            "/api/v1/service-agreements",
            headers={"X-API-Key": admin_key, "Idempotency-Key": f"agreement-{uuid4().hex}"},
            json=body,
        )
        assert created.status_code == 201
        agreement = created.json()
        agreement_id = agreement["id"]
        assert agreement["status"] == "draft"
        assert agreement["text"].startswith("ДОГОВОР ВОЗМЕЗДНОГО")

        hidden_drafts = client.get(
            f"/api/v1/service-agreements/by-telegram/{telegram_id}",
            headers={"X-API-Key": bot_key},
        )
        assert hidden_drafts.status_code == 200
        assert hidden_drafts.json() == []
        hidden_draft = client.get(
            f"/api/v1/service-agreements/{agreement_id}?telegram_user_id={telegram_id}",
            headers={"X-API-Key": bot_key},
        )
        assert hidden_draft.status_code == 404

        sent = client.post(
            f"/api/v1/service-agreements/{agreement_id}/sent",
            headers={"X-API-Key": admin_key},
            json={
                "chat_id": telegram_id,
                "message_id": 101,
                "telegram_user_id": 42,
                "callback_id": "admin-send-1",
            },
        )
        assert sent.status_code == 200
        assert sent.json()["status"] == "sent"
        visible = client.get(
            f"/api/v1/service-agreements/by-telegram/{telegram_id}",
            headers={"X-API-Key": bot_key},
        )
        assert [row["id"] for row in visible.json()] == [agreement_id]

        hidden = client.get(
            f"/api/v1/service-agreements/{agreement_id}",
            headers={"X-API-Key": bot_key},
        )
        assert hidden.status_code == 400
        wrong_client = client.get(
            f"/api/v1/service-agreements/{agreement_id}?telegram_user_id={telegram_id + 1}",
            headers={"X-API-Key": bot_key},
        )
        assert wrong_client.status_code == 403

        early_sign = client.post(
            f"/api/v1/service-agreements/{agreement_id}/sign",
            headers={"X-API-Key": bot_key},
            json={
                "telegram_user_id": telegram_id,
                "document_hash": agreement["hash"],
                "callback_id": "early-sign-1",
            },
        )
        assert early_sign.status_code == 409

        viewed = client.post(
            f"/api/v1/service-agreements/{agreement_id}/viewed",
            headers={"X-API-Key": bot_key},
            json={
                "telegram_user_id": telegram_id,
                "document_hash": agreement["hash"],
                "message_id": 102,
                "callback_id": "client-view-1",
            },
        )
        assert viewed.status_code == 200
        assert viewed.json()["status"] == "viewed"

        question = client.post(
            f"/api/v1/service-agreements/{agreement_id}/questions",
            headers={"X-API-Key": bot_key},
            json={"telegram_user_id": telegram_id, "text": "Можно оплатить двумя частями?"},
        )
        assert question.status_code == 201
        reply = client.post(
            f"/api/v1/service-agreements/{agreement_id}/replies",
            headers={"X-API-Key": admin_key},
            json={"telegram_user_id": 42, "text": "Да, подготовим новую редакцию."},
        )
        assert reply.status_code == 201
        messages = client.get(
            f"/api/v1/service-agreements/{agreement_id}/messages",
            headers={"X-API-Key": admin_key},
        )
        assert [row["role"] for row in messages.json()] == ["client", "lawyer"]
        assert messages.json()[0]["text"] == "Можно оплатить двумя частями?"

        signed = client.post(
            f"/api/v1/service-agreements/{agreement_id}/sign",
            headers={"X-API-Key": bot_key},
            json={
                "telegram_user_id": telegram_id,
                "telegram_username": "client",
                "document_hash": agreement["hash"],
                "callback_id": "callback-1",
            },
        )
        assert signed.status_code == 201
        assert signed.json()["status"] == "signed"
    finally:
        db = SessionLocal()
        try:
            if agreement_id:
                db.execute(
                    delete(ServiceAgreementMessage).where(
                        ServiceAgreementMessage.agreement_id == agreement_id
                    )
                )
                db.execute(delete(ServiceAgreement).where(ServiceAgreement.id == agreement_id))
            db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead_id))
            db.execute(delete(LegalIntake).where(LegalIntake.id == intake_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(ApiKey).where(ApiKey.name.in_([admin_name, bot_name])))
            db.commit()
            cache.invalidate()
        finally:
            db.close()
