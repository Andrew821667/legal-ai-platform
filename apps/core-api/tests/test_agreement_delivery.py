"""Доставка договора и ответа клиенту.

Проверяется порядок шагов: отметка об отправке ставится только после успешной
доставки, а ответ записывается только после того, как дошёл. Обратный порядок в
обоих случаях создал бы ложную картину — юрист считал бы, что клиент получил и
проигнорировал.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from core_api import client_proposal
from core_api.auth import cache
from core_api.db import SessionLocal
from core_api.main import app
from core_api.models import (
    ApiKey,
    Lead,
    LeadSource,
    Scope,
    ServiceAgreement,
    ServiceAgreementMessage,
    ServiceAgreementStatus,
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


def _seed(*, telegram: int | None = 5150, status=ServiceAgreementStatus.draft) -> dict:
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
        ids = db.execute(
            select(ServiceAgreement.id).where(ServiceAgreement.lead_id == lead_id)
        ).scalars().all()
        if ids:
            db.execute(delete(ServiceAgreementMessage).where(ServiceAgreementMessage.agreement_id.in_(ids)))
            db.execute(delete(ServiceAgreement).where(ServiceAgreement.id.in_(ids)))
        db.execute(delete(Lead).where(Lead.id == lead_id))
        db.execute(delete(ApiKey).where(ApiKey.name.in_(keys)))
        db.commit()
        cache.invalidate()
    finally:
        db.close()


@pytest.fixture
def sent(monkeypatch):
    """Перехватывает отправку в Telegram."""
    calls: list[dict] = []

    def _send(token, chat_id, text, reply_markup=None):
        calls.append({"chat_id": chat_id, "text": text, "markup": reply_markup})

    import core_api.routers.service_agreements as router

    monkeypatch.setattr(router, "_post_telegram_message", _send)
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")
    return calls


def test_delivery_sends_terms_and_buttons(sent) -> None:
    client = TestClient(app)
    names = ["pytest.deliver.ok"]
    key = _key(names[0])
    seeded = _seed()
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/deliver",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "sent"

        assert len(sent) == 1
        assert sent[0]["chat_id"] == "5150"
        # Условия видны до открытия документа.
        assert "Раздел имущества" in sent[0]["text"]
        assert "80 000 ₽" in sent[0]["text"]
        # Кнопки те же, что у бота: их обрабатывает он.
        assert f"sa_c:open:{seeded['agreement_id']}" in sent[0]["markup"]
    finally:
        _cleanup(names, seeded["lead_id"])


def test_failed_delivery_leaves_the_draft_alone(monkeypatch) -> None:
    """Отметка после неудачи оставила бы юриста ждать ответа, которого не будет."""
    import core_api.routers.service_agreements as router

    def _boom(*args, **kwargs):
        raise TimeoutError("Telegram молчит")

    monkeypatch.setattr(router, "_post_telegram_message", _boom)
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")

    client = TestClient(app)
    names = ["pytest.deliver.fail"]
    key = _key(names[0])
    seeded = _seed()
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/deliver",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 502

        db = SessionLocal()
        try:
            item = db.get(ServiceAgreement, seeded["agreement_id"])
            assert item.status == ServiceAgreementStatus.draft
            assert item.sent_at is None
        finally:
            db.close()
    finally:
        _cleanup(names, seeded["lead_id"])


def test_already_sent_is_not_sent_twice(sent) -> None:
    client = TestClient(app)
    names = ["pytest.deliver.twice"]
    key = _key(names[0])
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/deliver",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 409
        assert sent == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_client_without_telegram_is_refused(sent) -> None:
    client = TestClient(app)
    names = ["pytest.deliver.notg"]
    key = _key(names[0])
    seeded = _seed(telegram=None)
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/deliver",
            headers={"X-API-Key": key},
        )
        assert response.status_code == 409
        assert sent == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_reply_is_recorded_only_after_it_reaches_the_client(monkeypatch) -> None:
    """Записанный, но не дошедший ответ выглядел бы отправленным."""
    import core_api.routers.service_agreements as router

    monkeypatch.setattr(
        router, "_post_telegram_message", lambda *a, **k: (_ for _ in ()).throw(TimeoutError())
    )
    monkeypatch.setattr(router, "_client_bot_token", lambda: "token")

    client = TestClient(app)
    names = ["pytest.reply.fail"]
    key = _key(names[0])
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/replies/deliver",
            headers={"X-API-Key": key},
            json={"text": "Госпошлина оплачивается отдельно."},
        )
        assert response.status_code == 502

        db = SessionLocal()
        try:
            count = db.execute(
                select(ServiceAgreementMessage).where(
                    ServiceAgreementMessage.agreement_id == seeded["agreement_id"]
                )
            ).scalars().all()
            assert count == []
        finally:
            db.close()
    finally:
        _cleanup(names, seeded["lead_id"])


def test_reply_reaches_the_client_and_is_recorded(sent) -> None:
    client = TestClient(app)
    names = ["pytest.reply.ok"]
    key = _key(names[0])
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/replies/deliver",
            headers={"X-API-Key": key},
            json={"text": "Госпошлина оплачивается отдельно."},
        )
        assert response.status_code == 201, response.text
        assert response.json()["delivered"] is True
        assert "Госпошлина" in sent[0]["text"]

        db = SessionLocal()
        try:
            rows = db.execute(
                select(ServiceAgreementMessage).where(
                    ServiceAgreementMessage.agreement_id == seeded["agreement_id"]
                )
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].role.value == "lawyer"
        finally:
            db.close()
    finally:
        _cleanup(names, seeded["lead_id"])


def test_empty_reply_is_refused(sent) -> None:
    client = TestClient(app)
    names = ["pytest.reply.empty"]
    key = _key(names[0])
    seeded = _seed(status=ServiceAgreementStatus.sent)
    try:
        response = client.post(
            f"/api/v1/service-agreements/{seeded['agreement_id']}/replies/deliver",
            headers={"X-API-Key": key},
            json={"text": "   "},
        )
        assert response.status_code == 422
        assert sent == []
    finally:
        _cleanup(names, seeded["lead_id"])


def test_proposal_buttons_match_what_the_bot_handles() -> None:
    """callback_data — договорённость с ботом: меняя строки, надо менять и его."""
    markup = client_proposal.build_proposal_markup("abc")
    for expected in ("sa_c:open:abc", "sa_c:q:abc", "sa_c:no:abc"):
        assert expected in markup
