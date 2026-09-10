"""Рабочее место юриста.

Главное, что здесь закрепляется: экран «Сегодня» показывает застрявшее, а не
всё подряд. Список всех дел не отвечает на вопрос «что стоит из-за меня», и
именно ради этого ответа экран заводился.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Lead,
    LegalIntake,
    LeadSource,
    LegalIntakeStatus,
    NdaSignature,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementMessageRole,
    ServiceAgreementStatus,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete


def _key(name: str) -> str:
    raw = generate_api_key()
    db = SessionLocal()
    try:
        db.add(ApiKey(key_hash=hash_api_key(raw), scope=Scope.admin, name=name, is_active=True))
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw


def _agreement(**kwargs) -> ServiceAgreement:
    defaults = dict(
        agreement_number=f"A-{datetime.now(timezone.utc).timestamp()}",
        subject="Раздел имущества",
        scope_text="",
        exclusions_text="",
        schedule_text="",
        price_text="80 000 ₽",
        payment_terms="",
        operator_snapshot={},
        client_snapshot={},
        document_text="текст",
        document_version="v1",
        document_hash="h" * 64,
        status=ServiceAgreementStatus.draft,
    )
    defaults.update(kwargs)
    return ServiceAgreement(**defaults)


def _seed() -> dict:
    """Клиент с обращением и черновиком, который не ушёл."""
    db = SessionLocal()
    try:
        lead = Lead(name="Рябов Александр", contact="@ryabov", source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Раздел квартиры в ипотеке после развода.",
            status=LegalIntakeStatus.scope_preparation,
        )
        db.add(intake)
        db.flush()
        agreement = _agreement(lead_id=lead.id, intake_id=intake.id)
        db.add(agreement)
        db.commit()
        return {"lead_id": str(lead.id), "intake_id": str(intake.id), "agreement_id": str(agreement.id)}
    finally:
        db.close()


def _cleanup(keys: list[str], lead_id: str) -> None:
    db = SessionLocal()
    try:
        ids = db.execute(
            delete(ServiceAgreement).where(ServiceAgreement.lead_id == lead_id).returning(ServiceAgreement.id)
        ).scalars().all()
        if ids:
            db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
        db.execute(delete(NdaSignature).where(NdaSignature.lead_id == lead_id))
        db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def _section(body: dict, key: str) -> dict:
    return next(s for s in body["sections"] if s["key"] == key)


def test_today_surfaces_the_unsent_draft() -> None:
    """Самая обидная задержка: работа сделана, а клиент ждёт и не знает почему."""
    client = TestClient(app)
    names = ["pytest.workspace.today"]
    key = _key(names[0])
    seeded = _seed()
    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        drafts = _section(body, "draft_not_sent")["items"]
        mine = [d for d in drafts if d["agreement_id"] == seeded["agreement_id"]]
        assert len(mine) == 1
        assert mine[0]["client"] == "Рябов Александр"
        assert mine[0]["price_text"] == "80 000 ₽"
        assert mine[0]["days_waiting"] is not None
    finally:
        _cleanup(names, seeded["lead_id"])


def test_today_flags_an_unanswered_client_question() -> None:
    """Последнее слово за клиентом — значит очередь наша."""
    client = TestClient(app)
    names = ["pytest.workspace.question"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.client,
                text="А госпошлина входит в стоимость?",
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "client_question")["items"]
        assert any("госпошлина" in i["question"] for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_answered_question_leaves_the_queue() -> None:
    """Ответили — задача уходит с экрана, иначе он перестаёт быть списком дел."""
    client = TestClient(app)
    names = ["pytest.workspace.answered"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        base = datetime.now(timezone.utc)
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.client,
                text="Вопрос",
                created_at=base - timedelta(hours=2),
            )
        )
        db.add(
            ServiceAgreementMessage(
                agreement_id=seeded["agreement_id"],
                role=ServiceAgreementMessageRole.lawyer,
                text="Ответ",
                created_at=base,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "client_question")["items"]
        assert not any(i["agreement_id"] == seeded["agreement_id"] for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_unreachable_client_is_shown() -> None:
    """Бот не может написать первым — нужен человек."""
    client = TestClient(app)
    names = ["pytest.workspace.unreachable"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        intake = db.get(LegalIntake, seeded["intake_id"])
        intake.outreach_blocked_reason = "no_telegram"
        db.add(intake)
        db.commit()
    finally:
        db.close()

    try:
        body = client.get("/api/v1/lawyer/today", headers={"X-API-Key": key}).json()
        items = _section(body, "unreachable")["items"]
        assert any(i["intake_id"] == seeded["intake_id"] and i["reason"] == "no_telegram" for i in items)
    finally:
        _cleanup(names, seeded["lead_id"])


def test_client_card_gathers_everything_in_one_answer() -> None:
    """Карточку открывают, чтобы вспомнить контекст перед разговором."""
    client = TestClient(app)
    names = ["pytest.workspace.card"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(
            NdaSignature(
                lead_id=seeded["lead_id"],
                signer_full_name="Рябов Александр Алексеевич",
                signer_contact="+79000000000",
                document_version="v1",
                document_hash="n" * 64,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": key}
        ).json()
        assert card["nda"]["signer_full_name"] == "Рябов Александр Алексеевич"
        assert len(card["intakes"]) == 1
        assert "ипотеке" in card["intakes"][0]["description"]
        assert len(card["agreements"]) == 1
        assert card["agreements"][0]["status"] == "draft"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_client_list_shows_only_those_with_intakes() -> None:
    """В таблице лидов лежат и те, кто просто нажал кнопку, — в рабочем месте они лишние."""
    client = TestClient(app)
    names = ["pytest.workspace.list"]
    key = _key(names[0])
    seeded = _seed()
    db = SessionLocal()
    try:
        db.add(Lead(name="Просто нажал кнопку", contact="@idle", source=LeadSource.telegram_bot))
        db.commit()
    finally:
        db.close()

    try:
        rows = client.get("/api/v1/lawyer/clients", headers={"X-API-Key": key}).json()
        names_shown = [r["name"] for r in rows]
        assert "Рябов Александр" in names_shown
        assert "Просто нажал кнопку" not in names_shown
    finally:
        _cleanup(names, seeded["lead_id"])
        db = SessionLocal()
        try:
            db.execute(delete(Lead).where(Lead.name == "Просто нажал кнопку"))
            db.commit()
        finally:
            db.close()


def test_search_finds_by_name() -> None:
    client = TestClient(app)
    names = ["pytest.workspace.search"]
    key = _key(names[0])
    seeded = _seed()
    try:
        rows = client.get(
            "/api/v1/lawyer/clients?search=рябов", headers={"X-API-Key": key}
        ).json()
        assert any(r["lead_id"] == seeded["lead_id"] for r in rows)
        empty = client.get(
            "/api/v1/lawyer/clients?search=такогонет", headers={"X-API-Key": key}
        ).json()
        assert empty == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_unknown_client_is_not_found() -> None:
    from uuid import uuid4

    client = TestClient(app)
    names = ["pytest.workspace.404"]
    key = _key(names[0])
    try:
        response = client.get(
            f"/api/v1/lawyer/clients/{uuid4()}", headers={"X-API-Key": key}
        )
        assert response.status_code == 404
    finally:
        db = SessionLocal()
        try:
            db.execute(delete(ApiKey).where(ApiKey.name.in_(names)))
            db.commit()
            cache.invalidate()
        finally:
            db.close()
