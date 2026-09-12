"""Направление практики на обращении и вид шаблона договора.

Механика одна на всех; практика решает три вещи: категорию на входе, нужна
ли проверка конфликта интересов как условие договора и какой шаблон текста у
договора. Здесь закрепляется именно это — и то, что для существующих
юридических обращений ничего не изменилось.
"""

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
    Practice,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

_OPERATOR = SimpleNamespace(
    operator_name="Иванов Иван Иванович",
    operator_status="самозанятый",
    operator_inn="123456789012",
    operator_details="Москва, example@example.ru",
)

_AGREEMENT_BODY = {
    "prepared_by_telegram_user_id": 42,
    "subject": "Telegram-бот для приёма заявок отдела продаж",
    "scope_text": "Бот, админ-панель, интеграция с CRM по API",
    "exclusions_text": "Хостинг и доменное имя",
    "schedule_text": "Два этапа по две недели",
    "price_text": "120 000 рублей",
    "payment_terms": "50% аванс, 50% по приёмке",
}


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


def _seed(*, practice: Practice, conflict: ConflictCheckStatus, nda: bool, category: str | None = None) -> dict:
    telegram_id = 8_000_000_000 + int(uuid4().hex[:6], 16)
    db = SessionLocal()
    try:
        lead = Lead(
            source=LeadSource.telegram_bot,
            telegram_user_id=telegram_id,
            name="Пётр Петров",
            contact="+7 900 000-00-00",
            company="ООО Ромашка",
        )
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Нужен бот для приёма заявок, сейчас всё руками в таблице.",
            conflict_status=conflict,
            practice=practice,
            category=category,
        )
        db.add(intake)
        db.flush()
        if nda:
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
        return {"intake_id": str(intake.id), "lead_id": lead.id, "telegram_id": telegram_id}
    finally:
        db.close()


def _cleanup(names: list[str], lead_id) -> None:
    db = SessionLocal()
    try:
        if lead_id is not None:
            ids = list(
                db.execute(select(ServiceAgreement.id).where(ServiceAgreement.lead_id == lead_id)).scalars()
            )
            if ids:
                db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
                db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(ids)))
            db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead_id))
            db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
            db.execute(delete(Lead).where(Lead.id == lead_id))
        if names:
            db.execute(delete(ApiKey).where(ApiKey.name.in_(names)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _create_agreement(client: TestClient, key: str, intake_id: str):
    return client.post(
        "/api/v1/service-agreements",
        headers={"X-API-Key": key},
        json={"intake_id": intake_id, **_AGREEMENT_BODY},
    )


def test_engineering_agreement_needs_neither_nda_nor_conflict_check(monkeypatch) -> None:
    """Инженерной практике не нужны ни NDA, ни проверка конфликта как условие договора."""
    from core_api.routers import service_agreements as api

    monkeypatch.setattr(api, "get_settings", lambda: _OPERATOR)
    names = [f"pytest.practice.eng.{uuid4().hex}"]
    key = _key(Scope.admin, names[0])
    seeded = _seed(practice=Practice.engineering, conflict=ConflictCheckStatus.unchecked, nda=False, category="telegram_bot")
    client = TestClient(app)
    try:
        created = _create_agreement(client, key, seeded["intake_id"])
        assert created.status_code == 201, created.text
        agreement = created.json()
        assert agreement["template_kind"] == "software_development"
        assert agreement["text"].startswith("ДОГОВОР НА РАЗРАБОТКУ ПРОГРАММНОГО ОБЕСПЕЧЕНИЯ")
        assert "статья 1296" in agreement["text"]
        assert agreement["version"] == "2026-09-12.1"
        # Реквизиты подписанта — из карточки клиента, NDA нет.
        assert agreement["client_name"] == "Пётр Петров"
        assert agreement["client_org"] == "ООО Ромашка"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_legal_agreement_still_requires_nda_and_clear_conflict(monkeypatch) -> None:
    """Для права ничего не изменилось: без NDA и без чистой проверки — 409."""
    from core_api.routers import service_agreements as api

    monkeypatch.setattr(api, "get_settings", lambda: _OPERATOR)
    names = [f"pytest.practice.legal.{uuid4().hex}"]
    key = _key(Scope.admin, names[0])
    client = TestClient(app)

    unchecked = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.unchecked, nda=True)
    try:
        response = _create_agreement(client, key, unchecked["intake_id"])
        assert response.status_code == 409
        assert "Conflict check" in response.json()["detail"]
    finally:
        _cleanup([], unchecked["lead_id"])

    no_nda = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=False)
    try:
        response = _create_agreement(client, key, no_nda["intake_id"])
        assert response.status_code == 409
        assert "NDA" in response.json()["detail"]
    finally:
        _cleanup([], no_nda["lead_id"])

    ready = _seed(practice=Practice.legal, conflict=ConflictCheckStatus.clear, nda=True)
    try:
        created = _create_agreement(client, key, ready["intake_id"])
        assert created.status_code == 201, created.text
        assert created.json()["template_kind"] == "legal_services"
        assert created.json()["text"].startswith("ДОГОВОР ВОЗМЕЗДНОГО ОКАЗАНИЯ ЮРИДИЧЕСКИХ УСЛУГ")
        assert created.json()["version"] == "2026-09-10.1"
    finally:
        _cleanup(names, ready["lead_id"])


def test_hybrid_keeps_conflict_check_and_gets_automation_template(monkeypatch) -> None:
    """Гибрид — инженерный проект с юридической составляющей: конфликт проверяем, шаблон — свой."""
    from core_api.routers import service_agreements as api

    monkeypatch.setattr(api, "get_settings", lambda: _OPERATOR)
    names = [f"pytest.practice.hybrid.{uuid4().hex}"]
    key = _key(Scope.admin, names[0])
    client = TestClient(app)

    unchecked = _seed(practice=Practice.hybrid, conflict=ConflictCheckStatus.unchecked, nda=True, category="contracts_flow")
    try:
        assert _create_agreement(client, key, unchecked["intake_id"]).status_code == 409
    finally:
        _cleanup([], unchecked["lead_id"])

    ready = _seed(practice=Practice.hybrid, conflict=ConflictCheckStatus.clear, nda=True, category="contracts_flow")
    try:
        created = _create_agreement(client, key, ready["intake_id"])
        assert created.status_code == 201, created.text
        assert created.json()["template_kind"] == "legal_automation"
        assert created.json()["text"].startswith("ДОГОВОР НА АВТОМАТИЗАЦИЮ ЮРИДИЧЕСКОЙ ФУНКЦИИ")
    finally:
        _cleanup(names, ready["lead_id"])


def test_intake_api_carries_practice_and_validates_category() -> None:
    """Категория обязательна и проверяется по практике; у права её нет."""
    names = [f"pytest.practice.intake.{uuid4().hex}"]
    key = _key(Scope.bot, names[0])
    client = TestClient(app)
    base = {
        "source": "website_form",
        "name": "Иван Петров",
        "contact": "+7 900 000-00-01",
        "client_type": "company",
        "description": "Хотим бота, который принимает заявки и кладёт их в CRM без ручного ввода.",
        "consent_accepted": True,
        "consent_version": "pytest-v1",
        "consent_at": "2026-09-12T10:00:00Z",
    }
    lead_ids: list = []
    try:
        missing = client.post(
            "/api/v1/legal-intakes", headers={"X-API-Key": key}, json={**base, "practice": "engineering"}
        )
        assert missing.status_code == 422

        unknown = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": key},
            json={**base, "practice": "engineering", "category": "spaceship"},
        )
        assert unknown.status_code == 422

        legal_with_category = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": key},
            json={**base, "practice": "legal", "category": "telegram_bot"},
        )
        assert legal_with_category.status_code == 422

        created = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": key},
            json={**base, "practice": "engineering", "category": "integration"},
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["practice"] == "engineering"
        assert body["category"] == "integration"
        lead_ids.append(body["lead_id"])

        db = SessionLocal()
        try:
            lead = db.get(Lead, body["lead_id"])
            assert lead.service_category == "engineering:integration"
        finally:
            db.close()

        # Старый вход без practice — по-прежнему право.
        legacy = client.post(
            "/api/v1/legal-intakes",
            headers={"X-API-Key": key},
            json={**base, "contact": "+7 900 000-00-02", "legal_area": "contracts"},
        )
        assert legacy.status_code == 201
        assert legacy.json()["practice"] == "legal"
        assert legacy.json()["category"] is None
        lead_ids.append(legacy.json()["lead_id"])
    finally:
        for lid in lead_ids:
            _cleanup([], lid)
        _cleanup(names, None)


def test_workspace_shows_practice_on_card_and_list(monkeypatch) -> None:
    from core_api.routers import service_agreements as api

    monkeypatch.setattr(api, "get_settings", lambda: _OPERATOR)
    names = [f"pytest.practice.ws.{uuid4().hex}"]
    key = _key(Scope.admin, names[0])
    seeded = _seed(practice=Practice.engineering, conflict=ConflictCheckStatus.unchecked, nda=False, category="ai_module")
    client = TestClient(app)
    try:
        assert _create_agreement(client, key, seeded["intake_id"]).status_code == 201
        card = client.get(f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}).json()
        (intake,) = card["intakes"]
        assert intake["practice"] == "engineering"
        assert intake["category"] == "ai_module"
        (agreement,) = card["agreements"]
        assert agreement["template_kind"] == "software_development"

        rows = client.get("/api/v1/lawyer/clients?search=Петров", headers={"X-API-Key": key}).json()
        mine = next(r for r in rows if r["lead_id"] == str(seeded["lead_id"]))
        assert mine["practices"] == ["engineering"]
    finally:
        _cleanup(names, seeded["lead_id"])
