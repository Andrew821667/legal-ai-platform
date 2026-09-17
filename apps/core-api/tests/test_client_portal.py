from __future__ import annotations

from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    IntakeDocument,
    Lead,
    LeadSource,
    LegalIntake,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


def _key(name: str) -> str:
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=Scope.bot, name=name, is_active=True))
        db.commit()
        cache.invalidate()
        return raw
    finally:
        db.close()


def _agreement(*, lead_id, intake_id, telegram_id: int, status: ServiceAgreementStatus):
    return ServiceAgreement(
        agreement_number=f"P-{uuid4().hex[:12]}",
        lead_id=lead_id,
        intake_id=intake_id,
        status=status,
        subject="Представительство по делу",
        scope_text="Подготовка позиции",
        exclusions_text="",
        schedule_text="По согласованному графику",
        price_text="30 000 руб.",
        amount_minor=3_000_000,
        payment_terms="Перевод по номеру телефона",
        operator_snapshot={},
        client_snapshot={"details_complete": True},
        document_text="Текст договора",
        document_version="v1",
        document_hash="a" * 64,
        client_telegram_user_id=telegram_id,
    )


def test_summary_isolates_client_data_and_hides_internal_fields() -> None:
    key_name = f"pytest.client-portal.{uuid4().hex}"
    key = _key(key_name)
    db = SessionLocal()
    try:
        first = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=71001,
            name="Первый клиент",
            contact="@first",
        )
        second = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=71002,
            name="Второй клиент",
            contact="@second",
        )
        db.add_all([first, second])
        db.flush()
        first_case = LegalIntake(
            lead_id=first.id,
            description="Задача первого клиента",
            internal_note="Служебная заметка",
        )
        second_case = LegalIntake(lead_id=second.id, description="Чужая задача")
        db.add_all([first_case, second_case])
        db.flush()
        db.add_all([
            IntakeDocument(
                intake_id=first_case.id,
                telegram_file_id="private-file-id",
                file_name="isk.pdf",
                nda_signed_at_upload=True,
            ),
            NdaSignature(
                lead_id=first.id,
                telegram_user_id=71001,
                signer_full_name="Первый Клиент",
                document_version="v1",
                document_hash="b" * 64,
                document_text="NDA",
                channel="miniapp",
            ),
        ])
        first_agreement = _agreement(
            lead_id=first.id,
            intake_id=first_case.id,
            telegram_id=71001,
            status=ServiceAgreementStatus.sent,
        )
        draft = _agreement(
            lead_id=first.id,
            intake_id=first_case.id,
            telegram_id=71001,
            status=ServiceAgreementStatus.draft,
        )
        foreign_agreement = _agreement(
            lead_id=second.id,
            intake_id=second_case.id,
            telegram_id=71002,
            status=ServiceAgreementStatus.sent,
        )
        db.add_all([first_agreement, draft, foreign_agreement])
        db.flush()
        db.add_all([
            ServiceAgreementMessage(
                agreement_id=first_agreement.id,
                role=ServiceAgreementMessageRole.client,
                telegram_user_id=71001,
                text="Вопрос по договору",
            ),
            WorkAct(
                act_number=f"A-{uuid4().hex[:12]}",
                agreement_id=first_agreement.id,
                lead_id=first.id,
                status=WorkActStatus.sent,
                description_text="Подготовлена позиция",
                amount_minor=3_000_000,
                document_text="Текст акта",
                document_hash="c" * 64,
                document_version="v1",
            ),
            WorkAct(
                act_number=f"A-{uuid4().hex[:12]}",
                agreement_id=foreign_agreement.id,
                lead_id=second.id,
                status=WorkActStatus.sent,
                description_text="Чужой акт",
                amount_minor=9_000_000,
                document_text="Чужой текст",
                document_hash="d" * 64,
                document_version="v1",
            ),
        ])
        db.commit()
        first_id = first.id
        second_id = second.id
    finally:
        db.close()

    try:
        response = TestClient(app).get(
            "/api/v1/client-portal/summary?telegram_user_id=71001",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["client"]["name"] == "Первый клиент"
        assert body["nda"]["signed"] is True
        assert [row["description"] for row in body["cases"]] == ["Задача первого клиента"]
        assert body["cases"][0]["documents"][0]["file_name"] == "isk.pdf"
        assert "telegram_file_id" not in body["cases"][0]["documents"][0]
        assert "internal_note" not in body["cases"][0]
        assert len(body["agreements"]) == 1
        assert body["agreements"][0]["messages"][0]["text"] == "Вопрос по договору"
        assert [row["description"] for row in body["acts"]] == ["Подготовлена позиция"]
        assert "Чужая задача" not in response.text
        assert "Чужой акт" not in response.text
        assert "private-file-id" not in response.text
        assert "Служебная заметка" not in response.text
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.lead_id.in_([first_id, second_id])))
            db.execute(delete(Lead).where(Lead.id.in_([first_id, second_id])))
            db.execute(delete(ApiKey).where(ApiKey.name == key_name))
            db.commit()
            cache.invalidate()
        finally:
            db.close()


def test_verify_returning_client_matches_contact_and_agreement_number() -> None:
    key_name = f"pytest.client-portal.verify.{uuid4().hex}"
    key = _key(key_name)
    db = SessionLocal()
    try:
        lead = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=72001,
            name="Постоянный клиент",
            phone="+7 909 233-09-09",
            email="client@example.test",
        )
        db.add(lead)
        db.flush()
        intake = LegalIntake(lead_id=lead.id, description="Дело клиента")
        db.add(intake)
        db.flush()
        agreement = _agreement(
            lead_id=lead.id,
            intake_id=intake.id,
            telegram_id=72001,
            status=ServiceAgreementStatus.sent,
        )
        agreement.agreement_number = "P-VERIFY-001"
        db.add(agreement)
        db.commit()
        lead_id = lead.id
    finally:
        db.close()

    try:
        client = TestClient(app)
        # Телефон в другом формате (без +, без разделителей) — должен совпасть
        # после нормализации до последних 10 цифр.
        ok = client.post(
            "/api/v1/client-portal/verify",
            headers={"X-API-Key": key},
            json={"contact": "89092330909", "agreement_number": "P-VERIFY-001"},
        )
        assert ok.status_code == 200
        assert ok.json() == {"verified": True, "telegram_user_id": 72001}

        wrong_number = client.post(
            "/api/v1/client-portal/verify",
            headers={"X-API-Key": key},
            json={"contact": "89092330909", "agreement_number": "P-DOES-NOT-EXIST"},
        )
        assert wrong_number.json() == {"verified": False}

        wrong_contact = client.post(
            "/api/v1/client-portal/verify",
            headers={"X-API-Key": key},
            json={"contact": "+79990000000", "agreement_number": "P-VERIFY-001"},
        )
        assert wrong_contact.json() == {"verified": False}

        by_email = client.post(
            "/api/v1/client-portal/verify",
            headers={"X-API-Key": key},
            json={"contact": "Client@Example.TEST", "agreement_number": "P-VERIFY-001"},
        )
        assert by_email.json() == {"verified": True, "telegram_user_id": 72001}
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(ApiKey).where(ApiKey.name == key_name))
            db.commit()
            cache.invalidate()
        finally:
            db.close()


def test_verify_returning_client_rejects_agreement_without_telegram_link() -> None:
    key_name = f"pytest.client-portal.verify.no-tg.{uuid4().hex}"
    key = _key(key_name)
    db = SessionLocal()
    try:
        lead = Lead(source=LeadSource.website_form, name="Заявка с сайта", phone="+79001234567")
        db.add(lead)
        db.flush()
        intake = LegalIntake(lead_id=lead.id, description="Дело без телеграма")
        db.add(intake)
        db.flush()
        agreement = _agreement(
            lead_id=lead.id, intake_id=intake.id, telegram_id=0, status=ServiceAgreementStatus.sent
        )
        agreement.agreement_number = "P-NO-TG-001"
        agreement.client_telegram_user_id = None
        db.add(agreement)
        db.commit()
        lead_id = lead.id
    finally:
        db.close()

    try:
        response = TestClient(app).post(
            "/api/v1/client-portal/verify",
            headers={"X-API-Key": key},
            json={"contact": "+79001234567", "agreement_number": "P-NO-TG-001"},
        )
        assert response.json() == {"verified": False}
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
            db.execute(delete(ApiKey).where(ApiKey.name == key_name))
            db.commit()
            cache.invalidate()
        finally:
            db.close()


def test_summary_rejects_non_positive_telegram_id() -> None:
    key_name = f"pytest.client-portal.invalid.{uuid4().hex}"
    key = _key(key_name)
    try:
        response = TestClient(app).get(
            "/api/v1/client-portal/summary?telegram_user_id=0",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ApiKey).where(ApiKey.name == key_name))
            db.commit()
            cache.invalidate()
        finally:
            db.close()
