"""Сохранение ответов клиента и присланных им документов.

Это материалы обращения: они должны переживать перезапуск бота и попадать в
карточку к юристу целиком.
"""

from __future__ import annotations

from uuid import uuid4

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    IntakeClarification,
    IntakeDocument,
    Lead,
    LegalIntake,
    NdaSignature,
    Scope,
)
from core_api.nda_document import NDA_VERSION
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, select


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
        db.execute(delete(IntakeClarification).where(IntakeClarification.intake_id.in_(intake_ids)))
        db.execute(delete(IntakeDocument).where(IntakeDocument.intake_id.in_(intake_ids)))
        if lead_ids:
            db.execute(delete(NdaSignature).where(NdaSignature.lead_id.in_(lead_ids)))
        db.execute(delete(LegalIntake).where(LegalIntake.id.in_(intake_ids)))
        if lead_ids:
            db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(api_key_names)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _create_intake(client: TestClient, bot_key: str) -> str:
    response = client.post(
        "/api/v1/legal-intakes",
        headers={"X-API-Key": bot_key, "Idempotency-Key": f"dialog-{uuid4().hex}"},
        json={
            "source": "telegram_bot",
            "telegram_user_id": 5150,
            "name": "Пётр Иванов",
            "contact": "@petr",
            "client_type": "individual",
            "legal_area": "employment",
            "description": "Уволили без объяснения причин, приказ не выдали.",
            "urgency": "urgent",
            "consent_accepted": True,
            "consent_version": "pytest-v1",
            "consent_at": "2026-09-04T10:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_clarifications_and_documents_reach_the_case_file() -> None:
    client = TestClient(app)
    names = ["pytest.dialog.bot", "pytest.dialog.admin"]
    bot_key = _create_api_key(Scope.bot, names[0])
    admin_key = _create_api_key(Scope.admin, names[1])
    intake_ids: list[str] = []

    try:
        intake_id = _create_intake(client, bot_key)
        intake_ids.append(intake_id)

        answer = client.post(
            f"/api/v1/legal-intakes/{intake_id}/clarifications",
            headers={"X-API-Key": bot_key},
            json={
                "question_key": "side",
                "question_text": "Вы обращаетесь как работник или как работодатель?",
                "answer_text": "Как работник",
            },
        )
        assert answer.status_code == 200, answer.text

        document = client.post(
            f"/api/v1/legal-intakes/{intake_id}/documents",
            headers={"X-API-Key": bot_key},
            json={
                "telegram_file_id": "FILE-1",
                "file_name": "приказ.pdf",
                "file_size": 2048,
                "mime_type": "application/pdf",
                "nda_signed_at_upload": False,
            },
        )
        assert document.status_code == 200, document.text

        dialog = client.get(
            f"/api/v1/legal-intakes/{intake_id}/dialog",
            headers={"X-API-Key": admin_key},
        )
        assert dialog.status_code == 200
        body = dialog.json()
        assert len(body["clarifications"]) == 1
        assert body["clarifications"][0]["answer_text"] == "Как работник"
        assert len(body["documents"]) == 1
        # Отметка о соглашении на момент передачи — юрист должен видеть,
        # в каких условиях документ был получен.
        assert body["documents"][0]["nda_signed_at_upload"] is False

        # Обращение, по которому пошли ответы, перестаёт быть просто принятым.
        card = client.get(
            f"/api/v1/legal-intakes/{intake_id}", headers={"X-API-Key": admin_key}
        )
        assert card.json()["status"] == "needs_clarification"
    finally:
        _cleanup(names, intake_ids)


def test_corrected_answer_replaces_the_previous_one() -> None:
    """Человек поправил себя — в карточке остаётся последний ответ, а не оба."""
    client = TestClient(app)
    names = ["pytest.dialog-fix.bot", "pytest.dialog-fix.admin"]
    bot_key = _create_api_key(Scope.bot, names[0])
    admin_key = _create_api_key(Scope.admin, names[1])
    intake_ids: list[str] = []

    try:
        intake_id = _create_intake(client, bot_key)
        intake_ids.append(intake_id)

        for answer in ("Как работодатель", "Извините, как работник"):
            response = client.post(
                f"/api/v1/legal-intakes/{intake_id}/clarifications",
                headers={"X-API-Key": bot_key},
                json={
                    "question_key": "side",
                    "question_text": "Вы обращаетесь как работник или как работодатель?",
                    "answer_text": answer,
                },
            )
            assert response.status_code == 200, response.text

        dialog = client.get(
            f"/api/v1/legal-intakes/{intake_id}/dialog", headers={"X-API-Key": admin_key}
        ).json()
        assert len(dialog["clarifications"]) == 1
        assert dialog["clarifications"][0]["answer_text"] == "Извините, как работник"
    finally:
        _cleanup(names, intake_ids)


def test_incomplete_clarification_is_rejected() -> None:
    client = TestClient(app)
    names = ["pytest.dialog-bad.bot"]
    bot_key = _create_api_key(Scope.bot, names[0])
    intake_ids: list[str] = []

    try:
        intake_id = _create_intake(client, bot_key)
        intake_ids.append(intake_id)
        response = client.post(
            f"/api/v1/legal-intakes/{intake_id}/clarifications",
            headers={"X-API-Key": bot_key},
            json={"question_key": "side", "question_text": "Вопрос", "answer_text": "   "},
        )
        assert response.status_code == 422
    finally:
        _cleanup(names, intake_ids)


def test_dialog_for_unknown_intake_is_not_found() -> None:
    client = TestClient(app)
    names = ["pytest.dialog-404.admin"]
    admin_key = _create_api_key(Scope.admin, names[0])
    try:
        response = client.get(
            f"/api/v1/legal-intakes/{uuid4()}/dialog", headers={"X-API-Key": admin_key}
        )
        assert response.status_code == 404
    finally:
        _cleanup(names, [])


def test_signature_is_refused_when_the_document_changed() -> None:
    """Подпись под редакцией, которой человек не видел, не фиксируется.

    Записать текущий хеш было бы хуже, чем отказать: в базе осталась бы
    достоверная на вид запись о подписании документа, которого подписант не
    читал.
    """
    client = TestClient(app)
    names = ["pytest.nda-hash.bot"]
    bot_key = _create_api_key(Scope.bot, names[0])
    intake_ids: list[str] = []

    try:
        intake_id = _create_intake(client, bot_key)
        intake_ids.append(intake_id)
        lead_id = client.get(
            f"/api/v1/legal-intakes/{intake_id}/dialog", headers={"X-API-Key": bot_key}
        )
        assert lead_id.status_code == 200

        db = SessionLocal()
        try:
            lead_uuid = db.execute(
                select(LegalIntake.lead_id).where(LegalIntake.id == intake_id)
            ).scalar_one()
        finally:
            db.close()

        stale = client.post(
            "/api/v1/nda/sign",
            headers={"X-API-Key": bot_key},
            json={"lead_id": str(lead_uuid), "document_hash": "0" * 64},
        )
        assert stale.status_code == 409

        document = client.get("/api/v1/nda/document", headers={"X-API-Key": bot_key}).json()
        fresh = client.post(
            "/api/v1/nda/sign",
            headers={"X-API-Key": bot_key},
            json={"lead_id": str(lead_uuid), "document_hash": document["hash"]},
        )
        assert fresh.status_code == 201, fresh.text
        assert fresh.json()["signed"] is True
        assert fresh.json()["version"] == NDA_VERSION
    finally:
        _cleanup(names, intake_ids)
