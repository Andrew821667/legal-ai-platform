"""Дополнительное соглашение к подписанному договору.

Главное, что здесь закрепляется: сумму подписанного договора нельзя поменять
в одну сторону. Новая стоимость уходит клиенту документом, и только его
подпись переносит её в договор — ровно один раз, без двойного счёта в итогах.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
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
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementStatus,
    WorkAct,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, select


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


def _seed(*, status=ServiceAgreementStatus.signed, amount_minor: int | None = 10_000_000) -> dict:
    """Клиент с подписанным договором на 100 000 ₽."""
    telegram_id = 7_000_000_000 + int(uuid4().hex[:6], 16)
    db = SessionLocal()
    try:
        lead = Lead(
            name="Рябова Алёна",
            contact="@ryabova",
            telegram_user_id=telegram_id,
            source=LeadSource.telegram_bot,
        )
        db.add(lead)
        db.flush()
        intake = LegalIntake(
            lead_id=lead.id,
            description="Сопровождение сделки купли-продажи квартиры.",
            status=LegalIntakeStatus.accepted,
        )
        db.add(intake)
        db.flush()
        agreement = ServiceAgreement(
            agreement_number=f"AV-20260901-{uuid4().hex[:6].upper()}",
            lead_id=lead.id,
            intake_id=intake.id,
            revision=2,
            subject="Сопровождение сделки",
            scope_text="Проверка документов и договора",
            exclusions_text="Суд",
            schedule_text="Две недели",
            price_text="100 000 ₽",
            amount_minor=amount_minor,
            payment_terms="50% предоплата",
            operator_snapshot={"name": "Иванов Иван", "status": "самозанятый", "inn": "123456789012", "details": "Москва"},
            client_snapshot={
                "client_type": "person",
                "full_name": "Рябова Алёна Игоревна",
                "contact": "@ryabova",
                "address": "Москва, ул. Пример, 1",
                "identity_document": "паспорт 0000 000000",
                "org": None,
                "details_complete": True,
            },
            document_text="текст",
            document_version="v1",
            document_hash="h" * 64,
            status=status,
            signed_at=datetime(2026, 9, 1, 21, 30, tzinfo=timezone.utc)
            if status == ServiceAgreementStatus.signed
            else None,
            client_telegram_user_id=telegram_id,
        )
        db.add(agreement)
        db.commit()
        return {
            "lead_id": str(lead.id),
            "intake_id": str(intake.id),
            "agreement_id": str(agreement.id),
            "number": agreement.agreement_number,
            "telegram_id": telegram_id,
        }
    finally:
        db.close()


def _cleanup(keys: list[str], lead_id: str) -> None:
    db = SessionLocal()
    try:
        ids = db.execute(
            select(ServiceAgreement.id).where(ServiceAgreement.lead_id == lead_id)
        ).scalars().all()
        if ids:
            db.execute(delete(AuditLog).where(AuditLog.target_id.in_(ids)))
            db.execute(delete(WorkAct).where(WorkAct.agreement_id.in_(ids)))
            db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.parent_agreement_id.in_(ids)))
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(ids)))
        db.execute(delete(LegalIntake).where(LegalIntake.lead_id == lead_id))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


@pytest.fixture
def sent(monkeypatch):
    calls: list[dict] = []

    def _send(token, chat_id, text, reply_markup=None):
        calls.append({"chat_id": chat_id, "text": text, "markup": reply_markup})

    import core_api.routers.service_agreements as router

    monkeypatch.setattr(router, "_post_telegram_message", _send)
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")
    return calls


_BODY = {
    "prepared_by_telegram_user_id": 42,
    "scope_text": "Подготовка и подача иска о взыскании неустойки",
    "schedule_text": "Месяц с даты подписания",
    "price_text": "150 000 ₽",
    "amount_minor": 15_000_000,
    "payment_terms": "Доплата 50 000 ₽ в течение 5 дней",
}


def _create(client: TestClient, key: str, agreement_id: str, **overrides):
    return client.post(
        f"/api/v1/service-agreements/{agreement_id}/supplements",
        headers={"X-API-Key": key},
        json={**_BODY, **overrides},
    )


def test_signed_supplement_moves_the_amount_once(sent) -> None:
    """Весь путь: составить → отправить → клиент открыл → подписал → сумма договора новая."""
    client = TestClient(app)
    admin_name = f"pytest.supplement.admin.{uuid4().hex}"
    bot_name = f"pytest.supplement.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    seeded = _seed()
    try:
        created = _create(client, admin, seeded["agreement_id"])
        assert created.status_code == 201, created.text
        supplement = created.json()
        supplement_id = supplement["id"]
        assert supplement["kind"] == "supplement"
        assert supplement["status"] == "draft"
        assert supplement["agreement_number"] == f"{seeded['number']}-DS1"
        assert supplement["parent_agreement_id"] == seeded["agreement_id"]
        # Реквизиты взяты из договора — второй раз клиента о них не спрашиваем.
        assert supplement["client_details_complete"] is True
        text = supplement["text"]
        assert text.startswith("ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № 1")
        assert f"к Договору возмездного оказания юридических услуг № {seeded['number']}" in text
        # Подписан 1 сентября в 21:30 UTC — по Москве это уже 2 сентября.
        assert "от 02.09.2026" in text
        assert "с учётом дополнительных составляет 150 000 ₽" in text
        assert "Подготовка и подача иска" in text
        # До подписи клиента сумма договора прежняя.
        db = SessionLocal()
        try:
            assert db.get(ServiceAgreement, seeded["agreement_id"]).amount_minor == 10_000_000
        finally:
            db.close()

        delivered = client.post(
            f"/api/v1/service-agreements/{supplement_id}/deliver", headers={"X-API-Key": admin}
        )
        assert delivered.status_code == 200, delivered.text
        assert "дополнительное соглашение" in sent[0]["text"]
        assert "Стоимость по договору: 150 000 ₽" in sent[0]["text"]
        assert "Открыть допсоглашение" in sent[0]["markup"]
        assert f"sa_c:open:{supplement_id}" in sent[0]["markup"]

        viewed = client.post(
            f"/api/v1/service-agreements/{supplement_id}/viewed",
            headers={"X-API-Key": bot},
            json={
                "telegram_user_id": seeded["telegram_id"],
                "document_hash": supplement["hash"],
                "callback_id": "view-1",
            },
        )
        assert viewed.status_code == 200, viewed.text
        signed = client.post(
            f"/api/v1/service-agreements/{supplement_id}/sign",
            headers={"X-API-Key": bot},
            json={
                "telegram_user_id": seeded["telegram_id"],
                "document_hash": supplement["hash"],
                "callback_id": "sign-1",
            },
        )
        assert signed.status_code == 201, signed.text
        assert signed.json()["status"] == "signed"

        db = SessionLocal()
        try:
            parent = db.get(ServiceAgreement, seeded["agreement_id"])
            assert parent.amount_minor == 15_000_000
            # Подписанный текст договора не трогаем — новая цена живёт в допсоглашении.
            assert parent.price_text == "100 000 ₽"
            trail = db.execute(
                select(AuditLog)
                .where(AuditLog.target_id == parent.id)
                .where(AuditLog.action == "service_agreement.amount")
            ).scalar_one()
            assert trail.details["from"] == 10_000_000
            assert trail.details["to"] == 15_000_000
            assert trail.details["supplement_number"] == f"{seeded['number']}-DS1"
            # Дело не откатывается: оно было в работе и осталось.
            assert db.get(LegalIntake, seeded["intake_id"]).status == LegalIntakeStatus.accepted
        finally:
            db.close()

        card = client.get(
            f"/api/v1/lawyer/clients/{seeded['lead_id']}", headers={"X-API-Key": admin}
        ).json()
        assert card["stage"] == "Договор подписан"
        assert [a["agreement_id"] for a in card["agreements"]] == [seeded["agreement_id"]]
        assert card["agreements"][0]["amount_minor"] == 15_000_000
        assert card["agreements"][0]["supplements"][0]["status"] == "signed"

        rows = client.get("/api/v1/lawyer/clients", headers={"X-API-Key": admin}).json()
        row = next(item for item in rows if item["lead_id"] == seeded["lead_id"])
        # Не 250 000: допсоглашение — не вторая сделка.
        assert row["amount_minor"] == 15_000_000

        finance = client.get("/api/v1/lawyer/finance", headers={"X-API-Key": admin}).json()
        assert all(a["agreement_id"] != supplement_id for a in finance["agreements"])
    finally:
        _cleanup([admin_name, bot_name], seeded["lead_id"])


def test_supplement_needs_a_signed_agreement() -> None:
    """Неподписанный договор меняется новой редакцией, а не допсоглашением."""
    client = TestClient(app)
    name = f"pytest.supplement.unsigned.{uuid4().hex}"
    admin = _key(Scope.admin, name)
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = _create(client, admin, seeded["agreement_id"])
        assert response.status_code == 409
        assert "new revision" in response.json()["detail"]
    finally:
        _cleanup([name], seeded["lead_id"])


def test_new_supplement_replaces_the_unsigned_one(sent) -> None:
    """У клиента на руках одна актуальная редакция; номер растёт только с подписью."""
    client = TestClient(app)
    admin_name = f"pytest.supplement.replace.{uuid4().hex}"
    bot_name = f"pytest.supplement.replace.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    seeded = _seed()
    try:
        first = _create(client, admin, seeded["agreement_id"]).json()
        second = _create(client, admin, seeded["agreement_id"], price_text="140 000 ₽", amount_minor=14_000_000).json()
        assert second["agreement_number"] == f"{seeded['number']}-DS1-R2"
        db = SessionLocal()
        try:
            assert db.get(ServiceAgreement, first["id"]).status == ServiceAgreementStatus.superseded
        finally:
            db.close()

        client.post(f"/api/v1/service-agreements/{second['id']}/deliver", headers={"X-API-Key": admin})
        for path, extra in (("viewed", {}), ("sign", {})):
            response = client.post(
                f"/api/v1/service-agreements/{second['id']}/{path}",
                headers={"X-API-Key": bot},
                json={
                    "telegram_user_id": seeded["telegram_id"],
                    "document_hash": second["hash"],
                    "callback_id": f"{path}-1",
                    **extra,
                },
            )
            assert response.status_code in (200, 201), response.text

        third = _create(client, admin, seeded["agreement_id"], price_text="160 000 ₽", amount_minor=16_000_000).json()
        assert third["agreement_number"] == f"{seeded['number']}-DS2"
        assert third["text"].startswith("ДОПОЛНИТЕЛЬНОЕ СОГЛАШЕНИЕ № 2")
        # Допсоглашение к допсоглашению не бывает — только к договору.
        nested = _create(client, admin, second["id"])
        assert nested.status_code == 409
    finally:
        _cleanup([admin_name, bot_name], seeded["lead_id"])


def test_declined_supplement_leaves_the_agreement_as_it_was(sent) -> None:
    client = TestClient(app)
    admin_name = f"pytest.supplement.decline.{uuid4().hex}"
    bot_name = f"pytest.supplement.decline.bot.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    bot = _key(Scope.bot, bot_name)
    seeded = _seed()
    try:
        supplement = _create(client, admin, seeded["agreement_id"]).json()
        client.post(f"/api/v1/service-agreements/{supplement['id']}/deliver", headers={"X-API-Key": admin})
        declined = client.post(
            f"/api/v1/service-agreements/{supplement['id']}/decline",
            headers={"X-API-Key": bot},
            json={"telegram_user_id": seeded["telegram_id"], "reason": "Дорого", "callback_id": "no-1"},
        )
        assert declined.status_code == 200, declined.text
        db = SessionLocal()
        try:
            assert db.get(ServiceAgreement, seeded["agreement_id"]).amount_minor == 10_000_000
            assert db.get(LegalIntake, seeded["intake_id"]).status == LegalIntakeStatus.accepted
        finally:
            db.close()
    finally:
        _cleanup([admin_name, bot_name], seeded["lead_id"])


def test_amount_is_only_filled_in_never_rewritten() -> None:
    """Правка суммы в одну сторону закрыта: пустую можно дозаполнить, указанную — нет."""
    client = TestClient(app)
    name = f"pytest.supplement.amount.{uuid4().hex}"
    admin = _key(Scope.admin, name)
    priced = _seed()
    unpriced = _seed(amount_minor=None)
    try:
        refused = client.patch(
            f"/api/v1/lawyer/agreements/{priced['agreement_id']}/amount",
            headers={"X-API-Key": admin},
            json={"amount_minor": 1},
        )
        assert refused.status_code == 409
        filled = client.patch(
            f"/api/v1/lawyer/agreements/{unpriced['agreement_id']}/amount",
            headers={"X-API-Key": admin},
            json={"amount_minor": 5_000_000},
        )
        assert filled.status_code == 200, filled.text
    finally:
        _cleanup([name], priced["lead_id"])
        _cleanup([], unpriced["lead_id"])


def test_act_goes_under_the_main_agreement(sent) -> None:
    client = TestClient(app)
    admin_name = f"pytest.supplement.act.{uuid4().hex}"
    admin = _key(Scope.admin, admin_name)
    seeded = _seed()
    try:
        supplement = _create(client, admin, seeded["agreement_id"]).json()
        db = SessionLocal()
        try:
            db.get(ServiceAgreement, supplement["id"]).status = ServiceAgreementStatus.signed
            db.commit()
        finally:
            db.close()
        response = client.post(
            "/api/v1/work-acts",
            headers={"X-API-Key": admin},
            json={
                "agreement_id": supplement["id"],
                "description_text": "Подан иск",
                "amount_minor": 5_000_000,
                "prepared_by_telegram_user_id": 42,
            },
        )
        assert response.status_code == 409
    finally:
        _cleanup([admin_name], seeded["lead_id"])
