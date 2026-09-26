"""Обезличивание по сроку хранения (152-ФЗ).

Закрепляется: архивный клиент без договора обезличивается через год,
любой клиент без договора — через три года без активности; клиент с
договором и недавно архивный — нет; NDA и согласие живут три года с
подписания, потом теряют данные подписанта, но не хеш; учётная запись
удаляется, только если других дел у почты нет; повторный проход ничего
не меняет; журнал — без персональных данных.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from core_api import anonymization
from core_api.config import get_settings
from core_api.db import SessionLocal
from core_api.models import (
    AuditLog,
    Scope,
    ClientAccount,
    ClientNotice,
    Event,
    IntakeClarification,
    IntakeDocument,
    Lead,
    LeadSource,
    LegalIntake,
    LegalIntakeStatus,
    NdaPersonalDataConsent,
    NdaSignature,
    TelegramDelivery,
)
from sqlalchemy import delete, select, text

from test_client_archive import _agreement
from test_practice import _cleanup

NOW = datetime.now(timezone.utc)
YEAR_AGO = NOW - timedelta(days=400)
LONG_AGO = NOW - timedelta(days=4 * 365)


def _lead(db, *, archived_at=None, when=NOW, email=None, telegram=True) -> Lead:
    email = email or f"anon-{uuid4().hex[:8]}@example.com"
    lead = Lead(
        name="Иван Персональный",
        contact=email,
        email=email,
        phone="+7 900 123-45-67",
        company="ООО Тайна",
        telegram_user_id=(9_400_000_000 + int(uuid4().hex[:5], 16)) if telegram else None,
        source=LeadSource.website_form,
        notes="Личное",
        pain_point="Развод и раздел имущества",
        archived_at=archived_at,
        created_at=when,
        last_activity_at=when,
    )
    db.add(lead)
    db.flush()
    return lead


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch):
    # По умолчанию выключено (необратимо) — в тестах включаем явно.
    monkeypatch.setenv("ANONYMIZE_ENABLED", "true")
    get_settings.cache_clear()
    db = SessionLocal()
    try:
        old = _lead(db, archived_at=YEAR_AGO, when=LONG_AGO - timedelta(days=10))
        intake = LegalIntake(lead_id=old.id, description="Жена ушла к соседу, делим квартиру.",
                             status=LegalIntakeStatus.closed, deadline="к пятнице", region="Москва",
                             internal_note="Клиент нервный")
        db.add(intake)
        db.flush()
        db.add_all([
            IntakeClarification(intake_id=intake.id, question_key="q1", question_text="Дети есть?", answer_text="Двое"),
            IntakeDocument(intake_id=intake.id, telegram_file_id="file-secret", file_name="паспорт.jpg"),
            TelegramDelivery(kind="agreement_reply", chat_id=str(old.telegram_user_id), text="Иван, добрый день",
                             status="sent", lead_id=old.id),
            Event(lead_id=old.id, type="lead.created", payload={"name": "Иван Персональный"}),
            ClientAccount(email=old.email, yandex_id=f"ya-{uuid4().hex[:6]}"),
            NdaSignature(lead_id=old.id, signer_full_name="Иванов Иван (давний)", document_version="v0",
                         document_hash="f" * 64, signed_at=LONG_AGO),
            NdaPersonalDataConsent(lead_id=old.id, signer_full_name="Иванов Иван", signer_contact="+7 900",
                                   signer_identity_document="4510 123456", document_version="c1",
                                   document_hash="d" * 64, document_text="Я, Иванов Иван, согласен…",
                                   accepted_at=LONG_AGO),
        ])
        # Архивный год назад, NDA подписан год назад: клиент обезличен, NDA ещё доказательство.
        fresh_nda = _lead(db, archived_at=YEAR_AGO, when=YEAR_AGO)
        db.add(NdaSignature(lead_id=fresh_nda.id, telegram_user_id=fresh_nda.telegram_user_id,
                            signer_full_name="Петров Пётр", signer_contact="+7 901", document_version="v1",
                            document_hash="e" * 64, signed_at=YEAR_AGO))
        with_agreement = _lead(db, archived_at=YEAR_AGO)
        db.add(_agreement(with_agreement.id, None))
        recent = _lead(db, archived_at=NOW - timedelta(days=100))
        silent = _lead(db, when=LONG_AGO)  # не в архиве, но 4 года без активности
        # Вторая живая заявка на ту же почту, что и у silent: учётную запись не трогать.
        sibling = _lead(db, email=silent.email)
        db.add(ClientAccount(email=silent.email, yandex_id=f"ya-{uuid4().hex[:6]}"))
        db.commit()
        ids = {key: lead.id for key, lead in
               (("old", old), ("fresh_nda", fresh_nda), ("with_agreement", with_agreement), ("recent", recent),
                ("silent", silent), ("sibling", sibling))}
        ids["intake"] = intake.id
        emails = {"old": old.email, "silent": silent.email}
    finally:
        db.close()
    yield {"ids": ids, "emails": emails}
    db = SessionLocal()
    try:
        db.execute(delete(ClientNotice).where(ClientNotice.event_key.like("anonymize:%")))
        db.execute(delete(AuditLog).where(AuditLog.action == "lead.anonymize"))
        db.execute(delete(TelegramDelivery).where(TelegramDelivery.lead_id.in_(list(ids.values()))))
        db.execute(delete(Event).where(Event.lead_id.in_(list(ids.values()))))
        db.execute(delete(NdaPersonalDataConsent).where(NdaPersonalDataConsent.lead_id == ids["old"]))
        db.execute(delete(ClientAccount).where(ClientAccount.email.in_(list(emails.values()))))
        db.commit()
    finally:
        db.close()
    for key in ("old", "fresh_nda", "with_agreement", "recent", "silent", "sibling"):
        _cleanup([], ids[key])
    get_settings.cache_clear()


def test_due_clients_are_anonymized_and_others_are_not(world) -> None:
    ids = world["ids"]
    result = anonymization.run(limit=10_000)
    assert result["leads"] >= 2

    db = SessionLocal()
    try:
        old = db.get(Lead, ids["old"])
        assert old.anonymized_at is not None
        assert (old.name, old.contact, old.email, old.phone, old.company, old.telegram_user_id, old.pain_point) == (
            anonymization.ANON_NAME, anonymization.PLACEHOLDER, None, None, None, None, None)
        # Источник и даты остаются — на них держатся воронка и итоги.
        assert old.source == LeadSource.website_form and old.archived_at is not None

        intake = db.get(LegalIntake, ids["intake"])
        assert intake.description == "[обезличено]" and intake.region is None and intake.internal_note is None
        assert db.scalar(select(IntakeClarification).where(IntakeClarification.intake_id == ids["intake"])) is None
        assert db.scalar(select(IntakeDocument).where(IntakeDocument.intake_id == ids["intake"])) is None
        delivery = db.scalar(select(TelegramDelivery).where(TelegramDelivery.lead_id == ids["old"]))
        assert delivery.text == "[обезличено]" and delivery.chat_id == "обезличено"
        assert db.scalar(select(Event.payload).where(Event.lead_id == ids["old"])) == {}
        assert db.scalar(select(ClientAccount).where(ClientAccount.email == world["emails"]["old"])) is None

        # NDA годовой давности — ещё доказательство; четырёхлетний — без подписанта, но с хешем.
        assert db.get(Lead, ids["fresh_nda"]).anonymized_at is not None
        fresh = db.scalar(select(NdaSignature).where(NdaSignature.lead_id == ids["fresh_nda"]))
        assert fresh.signer_full_name == "Петров Пётр" and fresh.telegram_user_id is not None
        stale = db.scalar(select(NdaSignature).where(NdaSignature.lead_id == ids["old"]))
        assert stale.signer_full_name is None and stale.document_hash == "f" * 64
        consent = db.scalar(select(NdaPersonalDataConsent).where(NdaPersonalDataConsent.lead_id == ids["old"]))
        assert consent.signer_identity_document == "обезличено" and consent.document_hash == "d" * 64
        # Заглушка лежит строкой, мимо шифрования: проходу не нужен ключ.
        raw = db.execute(text("SELECT signer_identity_document FROM nda_personal_data_consents WHERE lead_id = :id"),
                         {"id": ids["old"]}).scalar()
        assert raw == "обезличено"

        silent = db.get(Lead, ids["silent"])
        assert silent.anonymized_at is not None
        # У почты есть другое живое дело — учётную запись не трогаем.
        assert db.scalar(select(ClientAccount).where(ClientAccount.email == world["emails"]["silent"])) is not None

        for key in ("with_agreement", "recent", "sibling"):
            assert db.get(Lead, ids[key]).anonymized_at is None, key
        recent = db.get(Lead, ids["recent"])
        planned = anonymization.planned_date(db, recent)
        assert planned is not None and abs((planned - (recent.archived_at + timedelta(days=365))).total_seconds()) < 1
        assert anonymization.planned_date(db, db.get(Lead, ids["with_agreement"])) is None

        audit = db.scalar(select(AuditLog).where(AuditLog.action == "lead.anonymize", AuditLog.target_id == ids["old"]))
        assert audit.details["clarifications"] == 1 and audit.details["documents"] == 1
        assert "Иван" not in str(audit.details)
        notice = db.scalar(select(ClientNotice.text).where(ClientNotice.event_key.like("anonymize:%")))
        assert "152-ФЗ" in notice and "Иван" not in notice
    finally:
        db.close()

    # Повторный проход уже обезличенных не трогает: ни второй записи в журнале.
    anonymization.run(limit=10_000)
    db = SessionLocal()
    try:
        assert ids["old"] not in anonymization.due_leads(db, NOW, limit=10_000)
        runs = db.scalars(select(AuditLog).where(AuditLog.action == "lead.anonymize", AuditLog.target_id == ids["old"]))
        assert len(list(runs)) == 1
    finally:
        db.close()


def test_switched_off_does_nothing(world, monkeypatch) -> None:
    monkeypatch.setenv("ANONYMIZE_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert anonymization.run(limit=10_000) == {"enabled": False}
        db = SessionLocal()
        try:
            assert db.get(Lead, world["ids"]["old"]).anonymized_at is None
        finally:
            db.close()
    finally:
        get_settings.cache_clear()


def test_preview_counts_without_names_and_digest_asks_to_switch_on(world, monkeypatch) -> None:
    from core_api import weekly_digest
    from core_api.main import app
    from fastapi.testclient import TestClient

    from test_practice import _key

    monkeypatch.setenv("ANONYMIZE_ENABLED", "false")
    get_settings.cache_clear()
    name = f"pytest.anon.preview.{uuid4().hex}"
    try:
        response = TestClient(app).get("/api/v1/lawyer/anonymization", headers={"X-API-Key": _key(Scope.admin, name)})
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is False and body["due_leads"] >= 3
        assert "Иван" not in response.text
        db = SessionLocal()
        try:
            assert "включите ANONYMIZE_ENABLED" in weekly_digest.build(db, NOW)
            assert db.get(Lead, world["ids"]["old"]).anonymized_at is None
        finally:
            db.close()
    finally:
        _cleanup([name], None)
