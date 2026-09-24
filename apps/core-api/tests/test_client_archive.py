"""Архив клиентов.

Главное, что здесь закрепляется: архив прячет клиента отовсюду, но ничего
не теряет; удалить совсем можно только из архива, и удаляется всё, что
относится к этой карточке, — но не записи другого клиента с тем же Telegram.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    AuditLog,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
    WorkAct,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select


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


def _agreement(lead_id, intake_id, **kwargs) -> ServiceAgreement:
    values = dict(
        agreement_number=f"AV-TEST-{uuid4().hex[:8].upper()}",
        lead_id=lead_id,
        intake_id=intake_id,
        subject="Сопровождение сделки",
        scope_text="Проверка документов",
        exclusions_text="",
        schedule_text="",
        price_text="100 000 ₽",
        amount_minor=10_000_000,
        payment_terms="",
        operator_snapshot={},
        client_snapshot={},
        document_text="текст",
        document_version="v1",
        document_hash="h" * 64,
        status=ServiceAgreementStatus.signed,
        signed_at=datetime.now(timezone.utc),
    )
    values.update(kwargs)
    return ServiceAgreement(**values)


def _seed(telegram_id: int, name: str = "Тестовый клиент") -> dict:
    """Клиент с NDA, обращением, подписанным договором, допсоглашением, актом и вопросом."""
    db = SessionLocal()
    try:
        lead = Lead(name=name, contact="@test", telegram_user_id=telegram_id, source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        db.add(
            NdaSignature(
                lead_id=lead.id,
                telegram_user_id=telegram_id,
                signer_full_name=name,
                document_version="v1",
                document_hash="n" * 64,
            )
        )
        intake = LegalIntake(
            lead_id=lead.id,
            description="Тестовое обращение для проверки архива.",
            status=LegalIntakeStatus.accepted,
        )
        db.add(intake)
        db.flush()
        main = _agreement(lead.id, intake.id)
        db.add(main)
        db.flush()
        db.add(
            _agreement(
                lead.id,
                intake.id,
                agreement_number=f"{main.agreement_number}-DS1",
                parent_agreement_id=main.id,
                status=ServiceAgreementStatus.sent,
                signed_at=None,
            )
        )
        db.add(
            WorkAct(
                act_number=f"AC-TEST-{uuid4().hex[:6].upper()}",
                agreement_id=main.id,
                lead_id=lead.id,
                description_text="Проверены документы.",
                amount_minor=5_000_000,
            )
        )
        db.add(
            ServiceAgreementMessage(
                agreement_id=main.id,
                role=ServiceAgreementMessageRole.client,
                telegram_user_id=telegram_id,
                text="Вопрос клиента без ответа",
            )
        )
        db.add(
            AuditLog(
                actor_type="api_key",
                actor_id="pytest",
                action="service_agreement.sign",
                target_type="service_agreement",
                target_id=main.id,
                details={},
            )
        )
        db.commit()
        return {"lead_id": str(lead.id), "intake_id": str(intake.id), "agreement_id": str(main.id)}
    finally:
        db.close()


def _cleanup(names: list[str], lead_ids: list[str]) -> None:
    db = SessionLocal()
    try:
        for lead_id in lead_ids:
            ids = db.scalars(select(ServiceAgreement.id).where(ServiceAgreement.lead_id == lead_id)).all()
            if ids:
                db.execute(delete(WorkAct).where(WorkAct.agreement_id.in_(ids)))
                db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
                db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(ids)))
            db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead_id))
            db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(names)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_archive_hides_the_client_everywhere_and_restore_brings_it_back() -> None:
    client = TestClient(app)
    name = f"pytest.archive.{uuid4().hex}"
    key = _key(Scope.admin, name)
    seeded = _seed(9_100_000_000 + int(uuid4().hex[:5], 16))
    headers = {"X-API-Key": key}
    try:
        before = client.get("/api/v1/lawyer/finance", headers=headers).json()
        archived = client.post(f"/api/v1/lawyer/clients/{seeded['lead_id']}/archive", headers=headers)
        assert archived.status_code == 200, archived.text
        assert archived.json()["archived_at"]

        rows = client.get("/api/v1/lawyer/clients?limit=200", headers=headers).json()
        assert all(row["lead_id"] != seeded["lead_id"] for row in rows)
        today = client.get("/api/v1/lawyer/today", headers=headers).json()
        mentioned = {item.get("lead_id") for section in today["sections"] for item in section["items"]}
        assert seeded["lead_id"] not in mentioned
        after = client.get("/api/v1/lawyer/finance", headers=headers).json()
        assert all(row["lead_id"] != seeded["lead_id"] for row in after["agreements"])
        assert after["signed_total"]["minor"] == before["signed_total"]["minor"] - 10_000_000

        archive = client.get("/api/v1/lawyer/archive", headers=headers).json()
        row = next(item for item in archive if item["lead_id"] == seeded["lead_id"])
        # Перед удалением видно, что пропадёт вместе с клиентом.
        assert row["intakes"] == 1
        assert row["agreements"] == 1
        assert row["signed_agreements"] == 1
        assert row["acts"] == 1
        assert row["nda_signed"] is True

        card = client.get(f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers=headers).json()
        assert card["archived_at"]

        restored = client.post(f"/api/v1/lawyer/clients/{seeded['lead_id']}/restore", headers=headers)
        assert restored.status_code == 200
        rows = client.get("/api/v1/lawyer/clients?limit=200", headers=headers).json()
        assert any(row["lead_id"] == seeded["lead_id"] for row in rows)
    finally:
        _cleanup([name], [seeded["lead_id"]])


def test_purge_only_from_archive_and_only_this_card() -> None:
    client = TestClient(app)
    name = f"pytest.archive.purge.{uuid4().hex}"
    key = _key(Scope.admin, name)
    headers = {"X-API-Key": key}
    telegram_id = 9_200_000_000 + int(uuid4().hex[:5], 16)
    doomed = _seed(telegram_id, "Удаляемый")
    # Тот же человек в Telegram, другая карточка — её записи не трогаем.
    kept = _seed(telegram_id, "Остающийся")
    try:
        refused = client.delete(f"/api/v1/lawyer/clients/{doomed['lead_id']}", headers=headers)
        assert refused.status_code == 409

        client.post(f"/api/v1/lawyer/clients/{doomed['lead_id']}/archive", headers=headers)
        purged = client.delete(f"/api/v1/lawyer/clients/{doomed['lead_id']}", headers=headers)
        assert purged.status_code == 200, purged.text
        assert purged.json()["deleted"]["signed_agreements"] == 1

        db = SessionLocal()
        try:
            assert db.get(Lead, doomed["lead_id"]) is None
            assert db.get(LegalIntake, doomed["intake_id"]) is None
            assert db.get(ServiceAgreement, doomed["agreement_id"]) is None
            # Допсоглашение уходит вместе с договором.
            assert db.scalar(
                select(func.count(ServiceAgreement.id)).where(
                    ServiceAgreement.parent_agreement_id == doomed["agreement_id"]
                )
            ) == 0
            assert db.scalar(select(func.count(NdaSignature.id)).where(NdaSignature.lead_id == doomed["lead_id"])) == 0
            assert db.scalar(
                select(func.count(AuditLog.id)).where(AuditLog.target_id == doomed["agreement_id"])
            ) == 0
            # В журнале — одна запись об удалении, без имени и контактов.
            trail = db.execute(
                select(AuditLog).where(AuditLog.target_id == doomed["lead_id"], AuditLog.action == "lead.purge")
            ).scalar_one()
            assert "Удаляемый" not in str(trail.details)

            assert db.get(Lead, kept["lead_id"]) is not None
            assert db.get(ServiceAgreement, kept["agreement_id"]) is not None
            assert db.scalar(select(func.count(NdaSignature.id)).where(NdaSignature.lead_id == kept["lead_id"])) == 1
        finally:
            db.close()
    finally:
        _cleanup([name], [doomed["lead_id"], kept["lead_id"]])


def test_client_who_writes_again_comes_back_from_the_archive() -> None:
    client = TestClient(app)
    admin_name = f"pytest.archive.back.{uuid4().hex}"
    bot_name = f"pytest.archive.back.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    telegram_id = 9_300_000_000 + int(uuid4().hex[:5], 16)
    seeded = _seed(telegram_id)
    try:
        client.post(f"/api/v1/lawyer/clients/{seeded['lead_id']}/archive", headers={"X-API-Key": admin})
        created = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": bot},
            json={
                "source": "telegram_bot",
                "telegram_user_id": telegram_id,
                "name": "Тестовый клиент",
                "contact": "@test",
                "client_type": "individual",
                "legal_area": "disputes",
                "description": "Новый вопрос после архива — клиент вернулся сам.",
                "urgency": "normal",
                "consent_accepted": True,
                "consent_version": "pytest-v1",
                "consent_at": "2026-09-24T10:00:00Z",
            },
        )
        assert created.status_code == 201, created.text
        assert created.json()["lead_id"] == seeded["lead_id"]
        rows = client.get("/api/v1/lawyer/clients?limit=200", headers={"X-API-Key": admin}).json()
        assert any(row["lead_id"] == seeded["lead_id"] for row in rows)
    finally:
        _cleanup([admin_name, bot_name], [seeded["lead_id"]])
