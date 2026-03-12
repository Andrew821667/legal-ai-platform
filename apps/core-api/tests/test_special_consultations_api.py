from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Event,
    Lead,
    Scope,
    SpecialConsultationOrder,
    SpecialConsultationPayment,
)
from core_api.security import generate_api_key, hash_api_key


def _create_api_key(scope: Scope, name: str) -> str:
    raw_key = generate_api_key()
    db = SessionLocal()
    try:
        db.add(
            ApiKey(
                key_hash=hash_api_key(raw_key),
                scope=scope,
                name=name,
                is_active=True,
            )
        )
        db.commit()
        cache.invalidate()
    finally:
        db.close()
    return raw_key


def _delete_api_key_by_name(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(delete(ApiKey).where(ApiKey.name == name))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


def test_special_consultation_order_and_payment_flow() -> None:
    client = TestClient(app)
    api_key_name = f"pytest.special-consultations.{uuid4().hex}"
    raw_key = _create_api_key(Scope.admin, api_key_name)
    created_order_id = None
    created_payment_id = None
    created_lead_id = None

    try:
        products_response = client.get(
            "/api/v1/special-consultations/products",
            headers={"X-API-Key": raw_key},
        )
        assert products_response.status_code == 200
        products = products_response.json()
        product_codes = {row["code"] for row in products}
        assert "urgent_consultation" in product_codes
        urgent_product = next(row for row in products if row["code"] == "urgent_consultation")
        assert urgent_product["requires_manual_quote"] is True
        assert urgent_product["base_price_minor"] is None

        order_response = client.post(
            "/api/v1/special-consultations/orders",
            headers={"X-API-Key": raw_key, "Idempotency-Key": f"special-order-{uuid4().hex}"},
            json={
                "product_code": "urgent_consultation",
                "source": "lead_bot",
                "telegram_user_id": 424242424,
                "customer_name": "Ирина Пример",
                "customer_contact": "@irina_example",
                "customer_email": "irina@example.com",
                "customer_phone": "+79990000000",
                "customer_company": "ООО Пример",
                "request_note": "Нужен срочный слот по сложному кадровому кейсу",
            },
        )
        assert order_response.status_code == 200
        order_payload = order_response.json()
        created_order_id = UUID(order_payload["id"])
        created_lead_id = UUID(order_payload["lead_id"])
        assert order_payload["status"] == "awaiting_quote"
        assert order_payload["amount_minor"] is None
        assert order_payload["product_code"] == "urgent_consultation"

        payment_response = client.post(
            f"/api/v1/special-consultations/orders/{created_order_id}/payments",
            headers={"X-API-Key": raw_key},
            json={
                "provider": "yookassa",
                "amount_minor": 3500000,
                "provider_payment_id": "yo_test_payment_001",
                "external_reference": f"special-{uuid4().hex}",
                "confirmation_url": "https://pay.example.test/checkout/yo_test_payment_001",
                "raw_payload": {"checkout": True},
            },
        )
        assert payment_response.status_code == 200
        payment_payload = payment_response.json()
        created_payment_id = UUID(payment_payload["id"])
        assert payment_payload["status"] == "requires_action"
        assert payment_payload["amount_minor"] == 3500000

        order_after_payment = client.get(
            f"/api/v1/special-consultations/orders/{created_order_id}",
            headers={"X-API-Key": raw_key},
        )
        assert order_after_payment.status_code == 200
        assert order_after_payment.json()["status"] == "awaiting_payment"
        assert order_after_payment.json()["amount_minor"] == 3500000

        reconcile_response = client.post(
            "/api/v1/special-consultations/payments/events",
            headers={"X-API-Key": raw_key},
            json={
                "provider": "yookassa",
                "status": "paid",
                "provider_payment_id": "yo_test_payment_001",
                "raw_payload": {"event": "payment.succeeded"},
            },
        )
        assert reconcile_response.status_code == 200
        reconcile_payload = reconcile_response.json()
        assert reconcile_payload["payment"]["status"] == "paid"
        assert reconcile_payload["order"]["status"] == "paid"
        assert reconcile_payload["order"]["paid_at"] is not None
    finally:
        db = SessionLocal()
        try:
            if created_payment_id is not None:
                db.execute(delete(SpecialConsultationPayment).where(SpecialConsultationPayment.id == created_payment_id))
            if created_order_id is not None:
                if created_lead_id is not None:
                    db.execute(delete(Event).where(Event.lead_id == created_lead_id))
                db.execute(delete(SpecialConsultationOrder).where(SpecialConsultationOrder.id == created_order_id))
            if created_lead_id is not None:
                db.execute(delete(Lead).where(Lead.id == created_lead_id))
            db.commit()
        finally:
            db.close()
        _delete_api_key_by_name(api_key_name)
