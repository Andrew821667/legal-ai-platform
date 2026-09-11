"""Акт выполненных работ: заводится по подписанному договору, доставляется
клиенту напрямую из ядра, «оплачено» подтверждает только юрист.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Lead,
    LeadSource,
    Scope,
    ServiceAgreement,
    ServiceAgreementStatus,
    WorkAct,
    WorkActStatus,
)
from core_api.security import generate_api_key, hash_api_key
from fastapi.testclient import TestClient
from sqlalchemy import delete, select


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


def _seed(*, telegram: int | None = 5150, status=ServiceAgreementStatus.signed) -> dict:
    db = SessionLocal()
    try:
        lead = Lead(name="Рябов Александр", contact="@r", source=LeadSource.telegram_bot)
        db.add(lead)
        db.flush()
        agreement = ServiceAgreement(
            agreement_number=f"A-{datetime.now(timezone.utc).timestamp()}",
            lead_id=lead.id,
            subject="Раздел имущества",
            scope_text="",
            exclusions_text="",
            schedule_text="",
            price_text="80 000 ₽",
            amount_minor=8_000_000,
            payment_terms="50% предоплата",
            operator_snapshot={},
            client_snapshot={},
            document_text="текст",
            document_version="v1",
            document_hash="h" * 64,
            status=status,
            client_telegram_user_id=telegram,
        )
        db.add(agreement)
        db.commit()
        return {"lead_id": str(lead.id), "agreement_id": str(agreement.id)}
    finally:
        db.close()


def _cleanup(keys: list[str], lead_id: str) -> None:
    db = SessionLocal()
    try:
        agreement_ids = db.execute(
            select(ServiceAgreement.id).where(ServiceAgreement.lead_id == lead_id)
        ).scalars().all()
        if agreement_ids:
            db.execute(delete(WorkAct).where(WorkAct.agreement_id.in_(agreement_ids)))
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(agreement_ids)))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram — как в test_agreement_delivery.py."""
    calls: list[dict] = []

    def _send(token, chat_id, text, reply_markup=None, parse_mode=None):
        calls.append(
            {"token": token, "chat_id": chat_id, "text": text, "markup": reply_markup, "parse_mode": parse_mode}
        )
        return {"message_id": 777}

    import core_api.routers.work_acts as router

    monkeypatch.setattr(router, "_post_telegram_message", _send)
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")
    return calls


def _create_act(client: TestClient, key: str, agreement_id: str, **overrides) -> dict:
    payload = {
        "agreement_id": agreement_id,
        "description_text": "Подготовлено и подано заявление, представительство на заседании.",
        "amount_minor": 8_000_000,
        **overrides,
    }
    response = client.post("/api/v1/work-acts", json=payload, headers={"X-API-Key": key})
    assert response.status_code == 201, response.text
    return response.json()


def test_act_requires_a_signed_agreement() -> None:
    """Выставлять счёт за работу, которую клиент ещё не принял, нечем обосновать."""
    client = TestClient(app)
    names = ["pytest.act.not_signed"]
    key = _key(names[0])
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = client.post(
            "/api/v1/work-acts",
            json={
                "agreement_id": seeded["agreement_id"],
                "description_text": "Работа выполнена.",
                "amount_minor": 100_00,
            },
            headers={"X-API-Key": key},
        )
        assert response.status_code == 409
    finally:
        _cleanup(names, seeded["lead_id"])


def test_create_act_on_a_signed_agreement() -> None:
    client = TestClient(app)
    names = ["pytest.act.create"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        assert act["status"] == "draft"
        assert act["act_number"].startswith("AC-")
        assert act["amount_minor"] == 8_000_000
        assert act["currency"] == "RUB"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_send_delivers_text_with_payment_details(sent, monkeypatch) -> None:
    from core_api import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "lawyer_payment_card_number", "2200 1234 5678 9010", raising=False)
    monkeypatch.setattr(config_module.get_settings(), "lawyer_payment_sbp_phone", "+7 900 000-00-00", raising=False)

    client = TestClient(app)
    names = ["pytest.act.send"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        response = client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "sent"

        assert len(sent) == 1
        assert sent[0]["chat_id"] == "5150"
        assert sent[0]["parse_mode"] == "HTML"
        assert act["act_number"] in sent[0]["text"]
        assert "80 000" in sent[0]["text"]
        assert "<code>2200 1234 5678 9010</code>" in sent[0]["text"]
        assert "<code>+7 900 000-00-00</code>" in sent[0]["text"]
        assert f"act_c:claim:{act['id']}" in sent[0]["markup"]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_send_without_payment_details_configured_omits_the_section(sent, monkeypatch) -> None:
    """Без настроенных реквизитов акт уходит без раздела «Оплата» — не с
    местом, которое обещает реквизиты и ничего не показывает."""
    from core_api import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "lawyer_payment_card_number", None, raising=False)
    monkeypatch.setattr(config_module.get_settings(), "lawyer_payment_sbp_phone", None, raising=False)

    client = TestClient(app)
    names = ["pytest.act.send.nodetails"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        assert "Оплата:" not in sent[0]["text"]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_send_fails_without_client_telegram(sent) -> None:
    client = TestClient(app)
    names = ["pytest.act.send.notg"]
    key = _key(names[0])
    seeded = _seed(telegram=None)
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        response = client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        assert response.status_code == 409
        assert sent == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_send_twice_fails(sent) -> None:
    client = TestClient(app)
    names = ["pytest.act.send.twice"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        response = client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        assert response.status_code == 409
        assert len(sent) == 1
    finally:
        _cleanup(names, seeded["lead_id"])


def test_client_claims_paid(sent) -> None:
    client = TestClient(app)
    names = ["pytest.act.claim"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        response = client.post(
            f"/api/v1/work-acts/{act['id']}/claim-paid",
            json={"telegram_user_id": 5150},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "claimed_paid"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_a_stranger_cannot_claim_someone_elses_act(sent) -> None:
    """Тот же id акта, чужой telegram_user_id — заявление не принимается."""
    client = TestClient(app)
    names = ["pytest.act.claim.stranger"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        response = client.post(
            f"/api/v1/work-acts/{act['id']}/claim-paid",
            json={"telegram_user_id": 999999},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 403
    finally:
        _cleanup(names, seeded["lead_id"])


def test_claim_paid_requires_the_act_to_be_sent() -> None:
    client = TestClient(app)
    names = ["pytest.act.claim.draft"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        response = client.post(
            f"/api/v1/work-acts/{act['id']}/claim-paid",
            json={"telegram_user_id": 5150},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 409
    finally:
        _cleanup(names, seeded["lead_id"])


def test_lawyer_confirms_paid_directly_from_sent(sent) -> None:
    """Юрист может подтвердить оплату сразу, не дожидаясь клика клиента —
    деньги он видит первым, а не через заявление в чате."""
    client = TestClient(app)
    names = ["pytest.act.paid.direct"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        response = client.patch(
            f"/api/v1/work-acts/{act['id']}/paid",
            json={"note": "Пришло на СБП"},
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "paid"
        assert body["paid_note"] == "Пришло на СБП"
        assert body["paid_at"] is not None
    finally:
        _cleanup(names, seeded["lead_id"])


def test_lawyer_confirms_paid_after_client_claimed(sent) -> None:
    client = TestClient(app)
    names = ["pytest.act.paid.after_claim"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        client.post(
            f"/api/v1/work-acts/{act['id']}/claim-paid",
            json={"telegram_user_id": 5150},
            headers={"X-API-Key": key},
        )
        response = client.patch(f"/api/v1/work-acts/{act['id']}/paid", json={}, headers={"X-API-Key": key})
        assert response.status_code == 200
        assert response.json()["status"] == "paid"
    finally:
        _cleanup(names, seeded["lead_id"])


def test_paid_twice_fails(sent) -> None:
    client = TestClient(app)
    names = ["pytest.act.paid.twice"]
    key = _key(names[0])
    seeded = _seed()
    try:
        act = _create_act(client, key, seeded["agreement_id"])
        client.post(f"/api/v1/work-acts/{act['id']}/send", headers={"X-API-Key": key})
        client.patch(f"/api/v1/work-acts/{act['id']}/paid", json={}, headers={"X-API-Key": key})
        response = client.patch(f"/api/v1/work-acts/{act['id']}/paid", json={}, headers={"X-API-Key": key})
        assert response.status_code == 409
    finally:
        _cleanup(names, seeded["lead_id"])


def test_list_by_agreement_orders_newest_first() -> None:
    client = TestClient(app)
    names = ["pytest.act.list"]
    key = _key(names[0])
    seeded = _seed()
    try:
        first = _create_act(client, key, seeded["agreement_id"], description_text="Первый этап работ выполнен.")
        second = _create_act(client, key, seeded["agreement_id"], description_text="Второй этап работ выполнен.")
        response = client.get(
            f"/api/v1/work-acts/by-agreement/{seeded['agreement_id']}", headers={"X-API-Key": key}
        )
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert ids == [second["id"], first["id"]]
    finally:
        _cleanup(names, seeded["lead_id"])
