"""Реквизиты документа подписанта — в базе только зашифрованными."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from core_api import pii
from core_api.db import SessionLocal
from core_api.models import Lead, LeadSource, NdaPersonalDataConsent


def test_roundtrip_and_prefix() -> None:
    token = pii.encrypt("4500 123456, выдан ОВД 01.01.2010")
    assert token.startswith("enc:v1:")
    assert "123456" not in token
    assert pii.decrypt(token) == "4500 123456, выдан ОВД 01.01.2010"
    assert pii.encrypt(token) == token  # повторное шифрование не наслаивается
    assert pii.decrypt(None) is None and pii.encrypt(None) is None


def test_legacy_plaintext_is_read_as_is() -> None:
    """Строка, записанная до шифрования, читается, пока миграция её не дошифровала."""
    assert pii.decrypt("4500 123456") == "4500 123456"
    assert not pii.is_encrypted("4500 123456")


def test_without_key_write_fails_and_read_of_legacy_still_works(monkeypatch) -> None:
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    pii.reset_key_cache()
    try:
        with pytest.raises(pii.PiiKeyMissingError):
            pii.encrypt("4500 123456")
        assert pii.decrypt("4500 123456") == "4500 123456"
        with pytest.raises(pii.PiiKeyMissingError):
            pii.decrypt("enc:v1:gAAAAA")
    finally:
        pii.reset_key_cache()


def test_wrong_key_is_reported_not_returned(monkeypatch) -> None:
    token = pii.encrypt("4500 123456")
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "Zz9v1mQ7pL2kN4rT6yU8wA0sD3fG5hJ7cV9bX1nM4qE=")
    pii.reset_key_cache()
    try:
        with pytest.raises(pii.PiiKeyMissingError):
            pii.decrypt(token)
    finally:
        pii.reset_key_cache()


def test_column_stores_only_the_token() -> None:
    """В самой базе — токен; ORM отдаёт открытый текст только тому, кто читает столбец."""
    assert os.getenv("PII_ENCRYPTION_KEY")
    db = SessionLocal()
    try:
        lead = Lead(name="pytest pii", contact="@pii", source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        consent = NdaPersonalDataConsent(
            lead_id=lead.id,
            telegram_user_id=1,
            signer_full_name="Тест Тестов",
            signer_contact="test@example.ru",
            signer_identity_document="4500 123456, выдан ОВД",
            document_version="test",
            document_hash="a" * 64,
            document_text="согласие",
            channel="test",
        )
        db.add(consent)
        db.commit()
        raw = db.execute(
            text("SELECT signer_identity_document FROM nda_personal_data_consents WHERE id = :id"),
            {"id": consent.id},
        ).scalar_one()
        assert raw.startswith("enc:v1:")
        assert "123456" not in raw
        db.expire_all()
        assert db.get(NdaPersonalDataConsent, consent.id).signer_identity_document == "4500 123456, выдан ОВД"
    finally:
        db.rollback()
        db.execute(text("DELETE FROM nda_personal_data_consents WHERE signer_full_name = 'Тест Тестов'"))
        db.execute(text("DELETE FROM leads WHERE name = 'pytest pii'"))
        db.commit()
        db.close()


def test_migration_reencrypts_legacy_rows() -> None:
    """Миграция 0032 дошифровывает то, что записано открытым текстом."""
    import importlib.util
    import pathlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from core_api.db import engine

    db = SessionLocal()
    try:
        lead = Lead(name="pytest pii legacy", contact="@pii2", source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        row_id = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO nda_personal_data_consents (id, lead_id, accepted_at, telegram_user_id, signer_full_name, "
                "signer_contact, signer_identity_document, document_version, document_hash, document_text, channel) "
                "VALUES (:id, :lead_id, now(), 1, 'Старый', 'old@example.ru', '4500 000000 открыто', 'v', :hash, 't', 'test')"
            ),
            {"id": row_id, "lead_id": lead.id, "hash": "b" * 64},
        )
        db.commit()
    finally:
        db.close()

    # Схема в тестах создана ORM, а не alembic, поэтому саму ревизию
    # вызываем напрямую — тем же кодом, что пойдёт на проде.
    path = pathlib.Path(__file__).resolve().parents[1] / "alembic/versions/20260915_0032_encrypt_identity_documents.py"
    spec = importlib.util.spec_from_file_location("m0032", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        raw = conn.execute(
            text("SELECT signer_identity_document FROM nda_personal_data_consents WHERE id = :id"), {"id": row_id}
        ).scalar_one()
    assert raw.startswith("enc:v1:")
    assert pii.decrypt(raw) == "4500 000000 открыто"

    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM nda_personal_data_consents WHERE id = :id"), {"id": row_id})
        db.execute(text("DELETE FROM leads WHERE name = 'pytest pii legacy'"))
        db.commit()
    finally:
        db.close()
